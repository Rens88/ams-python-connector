"""Auditable event replay workflow for example synthetic-data files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping
import warnings

from .client import OperationExecution, SmartabaseClient
from .dates import format_ams_date, parse_ams_date
from .diagnostics import (
    AMSEventIdUnavailableError,
    AMSResponseShapeError,
    EXACT_EVENT_ID_KEYS,
)
from .flatten import find_event_records, flatten_event_response
from .manifests import create_operation_folder, write_json_artifact, write_manifest_csv, write_operation_config
from .payloads import coerce_records_input


DEFAULT_EXAMPLE_CONFIG = Path("use_case_examples/synthetic_data/config.json")
DEFAULT_EXAMPLE_CSV = Path("use_case_examples/synthetic_data/csv/training load template 1777445863459.csv")
EVENT_ID_KEYS = EXACT_EVENT_ID_KEYS
_TIME_COLUMN = "Time"
_DATE_COLUMN = "Date"
_NAME_COLUMNS = ("First Name", "Last Name")
_FORM_ACRONYMS = {"wsv": "WSV", "hrv": "HRV", "mdo": "MDO", "garmin": "Garmin"}
_EXCLUDED_MATCH_KEYS = {"about", "username", "email", "entered_by_user_id", "event_id", "end_date", "end_time"}
_PREFERRED_MATCH_KEYS = ("form_id", "uuid")
_MATCH_KEY_LABELS = {"form_id": "Form ID", "uuid": "UUID"}
_COLUMN_ALIASES = {
    "formname": "form",
    "userid": "user_id",
    "startdate": "start_date",
    "starttime": "start_time",
    "finishdate": "end_date",
    "finishtime": "end_time",
    "eventid": "event_id",
    "existingeventid": "event_id",
    "id": "event_id",
}


@dataclass(frozen=True)
class ExampleEventWorkflowInput:
    csv_path: Path
    form: str
    user_id: int
    about: str
    username: str
    email: str
    first_name: str
    last_name: str
    date_range: tuple[str, str]
    records: list[dict[str, object]]

    @property
    def expected_upload_count(self) -> int:
        return len(self.records)


@dataclass(frozen=True)
class EventWriteTarget:
    form: str
    user_id: int
    about: str
    username: str
    email: str
    date_range: tuple[str, str]
    records: list[dict[str, object]]

    @property
    def expected_upload_count(self) -> int:
        return len(self.records)


@dataclass(frozen=True)
class EventCountResult:
    form: str
    user_id: int
    date_range: tuple[str, str]
    entry_count: int
    event_ids: list[int]
    rows: list[dict[str, object]]
    raw_payload: Any


@dataclass(frozen=True)
class ReplayPreflightResult:
    match_strategy: str
    match_fields: list[str]
    delete_event_ids: list[int]
    matched_existing_count: int
    unmatched_existing_event_ids: list[int]
    unmatched_existing_count: int
    missing_target_keys: list[str]
    missing_target_count: int
    duplicate_target_keys: list[str]
    duplicate_target_count: int
    duplicate_existing_keys: list[str]
    duplicate_existing_count: int
    warnings: list[str]


def load_example_event_workflow_input(
    *,
    csv_path: str | Path = DEFAULT_EXAMPLE_CSV,
    config_path: str | Path = DEFAULT_EXAMPLE_CONFIG,
) -> ExampleEventWorkflowInput:
    csv_file = Path(csv_path)
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    with csv_file.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Example CSV is empty: {csv_file}")

    first_name = rows[0].get(_NAME_COLUMNS[0], "").strip()
    last_name = rows[0].get(_NAME_COLUMNS[1], "").strip()
    if not first_name or not last_name:
        raise ValueError(f"Example CSV must include {_NAME_COLUMNS!r} columns with values.")

    athlete = _match_athlete(config.get("athletes", []), first_name, last_name)
    athlete_rows = [
        row
        for row in rows
        if row.get(_NAME_COLUMNS[0], "").strip() == first_name and row.get(_NAME_COLUMNS[1], "").strip() == last_name
    ]
    if not athlete_rows:
        raise ValueError(f"No rows found for example athlete {first_name} {last_name}.")

    form = _derive_form_name(csv_file.name)
    dates = [_parse_date(row[_DATE_COLUMN]) for row in athlete_rows if row.get(_DATE_COLUMN)]
    if not dates:
        raise ValueError(f"Example CSV must include {_DATE_COLUMN!r} values.")

    records = [
        _csv_row_to_event_record(
            row,
            user_id=int(athlete["smartabase_user_id"]),
            about=str(athlete["about"]),
        )
        for row in athlete_rows
    ]

    return ExampleEventWorkflowInput(
        csv_path=csv_file,
        form=form,
        user_id=int(athlete["smartabase_user_id"]),
        about=str(athlete["about"]),
        username=str(athlete.get("username", "")),
        email=str(athlete.get("email", "")),
        first_name=first_name,
        last_name=last_name,
        date_range=(min(dates).strftime("%d/%m/%Y"), max(dates).strftime("%d/%m/%Y")),
        records=records,
    )


def count_event_entries(
    client: SmartabaseClient,
    *,
    form: str,
    user_id: int,
    date_range: tuple[str, str],
) -> EventCountResult:
    payload = client.get_event(form=form, user_ids=[user_id], date_range=date_range)
    rows = flatten_event_response(payload)
    records = _find_event_records(payload)
    event_ids = _extract_event_ids(records, rows)
    entry_count = len(event_ids) if event_ids else (len(records) if records else len(rows))
    return EventCountResult(
        form=form,
        user_id=user_id,
        date_range=date_range,
        entry_count=entry_count,
        event_ids=event_ids,
        rows=rows,
        raw_payload=payload,
    )


def require_exact_event_ids(result: EventCountResult) -> list[int]:
    """Return verified exact event IDs or fail closed with safe diagnostics."""

    try:
        records = find_event_records(result.raw_payload)
    except ValueError as exc:
        raise AMSResponseShapeError(
            f"Smartabase returned an unrecognized event response for {result.form!r}. "
            "No deletion request was sent. Inspect endpoint permissions or response-shape "
            "compatibility before retrying.",
            code="unrecognized_event_response",
            details={"form": result.form},
        ) from exc

    record_ids = [_coerce_event_id(record) for record in records]
    if records and any(event_id is None for event_id in record_ids):
        id_like_fields = sorted(
            {
                str(key)
                for record in records
                for key in record
                if "id" in str(key).casefold()
            },
            key=str.casefold,
        )
        fields_label = ", ".join(id_like_fields) if id_like_fields else "none"
        raise AMSEventIdUnavailableError(
            f"Smartabase returned one or more {result.form!r} events without an exact "
            "event ID that could be verified. Recognized event-ID fields are "
            f"{', '.join(EVENT_ID_KEYS)}; returned ID-like fields: {fields_label}. "
            "Generic, athlete, and profile IDs are not safe deletion targets. No deletion "
            "request was sent. Verify endpoint permissions or obtain a response containing "
            "exact event IDs before retrying.",
            details={
                "form": result.form,
                "recognized_event_id_fields": list(EVENT_ID_KEYS),
                "returned_id_like_fields": id_like_fields,
            },
        )

    exact_ids = [int(value) for value in result.event_ids]
    if result.entry_count and not exact_ids:
        raise AMSEventIdUnavailableError(
            f"Smartabase returned {result.entry_count} {result.form!r} event(s) without "
            "verified exact event IDs. No deletion request was sent. Verify endpoint "
            "permissions before retrying.",
            details={"form": result.form, "entry_count": result.entry_count},
        )
    if len(exact_ids) != len(set(exact_ids)):
        raise AMSEventIdUnavailableError(
            f"Smartabase returned duplicate exact event IDs for {result.form!r}. No "
            "deletion request was sent.",
            code="duplicate_exact_event_id",
            details={"form": result.form},
        )
    if records:
        nonmissing_ids = [int(value) for value in record_ids if value is not None]
        if len(nonmissing_ids) != len(set(nonmissing_ids)):
            raise AMSEventIdUnavailableError(
                f"Smartabase returned duplicate event IDs within {result.form!r}. No "
                "deletion request was sent.",
                code="duplicate_exact_event_id",
                details={"form": result.form},
            )
        if set(nonmissing_ids) != set(exact_ids):
            raise AMSEventIdUnavailableError(
                f"Smartabase returned inconsistent exact event IDs for {result.form!r}. "
                "No deletion request was sent.",
                code="inconsistent_exact_event_id",
                details={"form": result.form},
            )
    return exact_ids


def run_event_replay_workflow(
    client: SmartabaseClient,
    target: ExampleEventWorkflowInput,
    *,
    base_dir: str | Path = "smartabase_runs",
    dry_run: bool = True,
    confirm: bool = False,
    delete_all_in_range: bool = False,
) -> dict[str, object]:
    _ensure_delete_all_in_range_allowed(client, delete_all_in_range=delete_all_in_range)
    operation_dir = create_operation_folder(f"replay_{target.form}", base_dir=base_dir)
    write_operation_config(
        operation_dir,
        {
            "operation": "event_replay",
            "csv_path": str(target.csv_path),
            "form": target.form,
            "user_id": target.user_id,
            "about": target.about,
            "username": target.username,
            "email": target.email,
            "date_range": list(target.date_range),
            "dry_run": dry_run,
            "confirm": confirm,
            "delete_all_in_range": delete_all_in_range,
            "expected_upload_count": target.expected_upload_count,
        },
    )

    manifest_rows: list[dict[str, object]] = []

    before = count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range)
    before_summary = _count_summary("count_before", before)
    before_summary_path = write_json_artifact(operation_dir, "raw_json/01_count_before.json", before_summary)
    write_json_artifact(operation_dir, "raw_json/01_count_before_raw.json", before.raw_payload)
    manifest_rows.append(_manifest_row("count_before", "eventsearch", target.form, before_summary_path, before.entry_count))

    require_exact_event_ids(before)

    preflight = _build_replay_preflight(target, before, delete_all_in_range=delete_all_in_range)
    for message in preflight.warnings:
        warnings.warn(message, RuntimeWarning, stacklevel=2)
    preflight_summary_path = write_json_artifact(
        operation_dir,
        "raw_json/02_preflight_diff.json",
        _preflight_summary(target, before, preflight),
    )
    manifest_rows.append(
        _manifest_row("preflight_diff", "local", target.form, preflight_summary_path, len(preflight.delete_event_ids))
    )

    delete_execution = client.delete_event(preflight.delete_event_ids, dry_run=dry_run, confirm=confirm)
    delete_payload_path = write_json_artifact(
        operation_dir,
        "payloads/02_delete_event_payload.json",
        _operation_summary(delete_execution),
    )
    write_json_artifact(operation_dir, "raw_json/02_delete_event_responses.json", delete_execution.responses)
    manifest_rows.append(
        _manifest_row(
            "delete_event",
            delete_execution.endpoint,
            target.form,
            delete_payload_path,
            delete_execution.attempted_count,
            status=_operation_status(delete_execution),
        )
    )

    after_delete = count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range)
    after_delete_summary = _count_summary("count_after_delete", after_delete)
    after_delete_summary_path = write_json_artifact(operation_dir, "raw_json/03_count_after_delete.json", after_delete_summary)
    write_json_artifact(operation_dir, "raw_json/03_count_after_delete_raw.json", after_delete.raw_payload)
    manifest_rows.append(
        _manifest_row("count_after_delete", "eventsearch", target.form, after_delete_summary_path, after_delete.entry_count)
    )

    upload_execution = client.insert_event(target.records, form=target.form, dry_run=dry_run, confirm=confirm)
    upload_payload_path = write_json_artifact(
        operation_dir,
        "payloads/04_insert_event_payload.json",
        _operation_summary(upload_execution),
    )
    write_json_artifact(operation_dir, "raw_json/04_insert_event_responses.json", upload_execution.responses)
    manifest_rows.append(
        _manifest_row(
            "insert_event",
            upload_execution.endpoint,
            target.form,
            upload_payload_path,
            upload_execution.attempted_count,
            status=_operation_status(upload_execution),
        )
    )

    after_upload = count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range)
    after_upload_summary = _count_summary("count_after_upload", after_upload)
    after_upload_summary_path = write_json_artifact(operation_dir, "raw_json/05_count_after_upload.json", after_upload_summary)
    write_json_artifact(operation_dir, "raw_json/05_count_after_upload_raw.json", after_upload.raw_payload)
    manifest_rows.append(
        _manifest_row("count_after_upload", "eventsearch", target.form, after_upload_summary_path, after_upload.entry_count)
    )

    manifest_path = write_manifest_csv(operation_dir, manifest_rows)
    summary = {
        "operation_dir": str(operation_dir),
        "manifest_path": str(manifest_path),
        "dry_run": dry_run,
        "target": {
            "csv_path": str(target.csv_path),
            "form": target.form,
            "user_id": target.user_id,
            "about": target.about,
            "date_range": list(target.date_range),
            "delete_all_in_range": delete_all_in_range,
            "expected_upload_count": target.expected_upload_count,
        },
        "counts": {
            "before": before_summary,
            "after_delete": after_delete_summary,
            "after_upload": after_upload_summary,
        },
        "preflight": _preflight_summary(target, before, preflight),
        "delete_event": _operation_summary(delete_execution),
        "insert_event": _operation_summary(upload_execution),
    }
    write_json_artifact(operation_dir, "workflow_summary.json", summary)
    return summary


def run_event_delete_workflow(
    client: SmartabaseClient,
    target: ExampleEventWorkflowInput,
    *,
    base_dir: str | Path = "smartabase_runs",
    dry_run: bool = True,
    confirm: bool = False,
    delete_all_in_range: bool = False,
) -> dict[str, object]:
    _ensure_delete_all_in_range_allowed(client, delete_all_in_range=delete_all_in_range)
    operation_dir = create_operation_folder(f"delete_{target.form}", base_dir=base_dir)
    write_operation_config(
        operation_dir,
        {
            "operation": "event_delete",
            "csv_path": str(target.csv_path),
            "form": target.form,
            "user_id": target.user_id,
            "about": target.about,
            "username": target.username,
            "email": target.email,
            "date_range": list(target.date_range),
            "dry_run": dry_run,
            "confirm": confirm,
            "delete_all_in_range": delete_all_in_range,
            "expected_delete_match_count": target.expected_upload_count,
        },
    )

    manifest_rows: list[dict[str, object]] = []

    before = count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range)
    before_summary = _count_summary("count_before", before)
    before_summary_path = write_json_artifact(operation_dir, "raw_json/01_count_before.json", before_summary)
    write_json_artifact(operation_dir, "raw_json/01_count_before_raw.json", before.raw_payload)
    manifest_rows.append(_manifest_row("count_before", "eventsearch", target.form, before_summary_path, before.entry_count))

    require_exact_event_ids(before)

    preflight = _build_replay_preflight(target, before, delete_all_in_range=delete_all_in_range)
    for message in preflight.warnings:
        warnings.warn(message, RuntimeWarning, stacklevel=2)
    preflight_summary_path = write_json_artifact(
        operation_dir,
        "raw_json/02_preflight_diff.json",
        _preflight_summary(target, before, preflight),
    )
    manifest_rows.append(
        _manifest_row("preflight_diff", "local", target.form, preflight_summary_path, len(preflight.delete_event_ids))
    )

    delete_execution = client.delete_event(preflight.delete_event_ids, dry_run=dry_run, confirm=confirm)
    delete_payload_path = write_json_artifact(
        operation_dir,
        "payloads/02_delete_event_payload.json",
        _operation_summary(delete_execution),
    )
    write_json_artifact(operation_dir, "raw_json/02_delete_event_responses.json", delete_execution.responses)
    manifest_rows.append(
        _manifest_row(
            "delete_event",
            delete_execution.endpoint,
            target.form,
            delete_payload_path,
            delete_execution.attempted_count,
            status=_operation_status(delete_execution),
        )
    )

    after_delete = count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range)
    after_delete_summary = _count_summary("count_after_delete", after_delete)
    after_delete_summary_path = write_json_artifact(operation_dir, "raw_json/03_count_after_delete.json", after_delete_summary)
    write_json_artifact(operation_dir, "raw_json/03_count_after_delete_raw.json", after_delete.raw_payload)
    manifest_rows.append(
        _manifest_row("count_after_delete", "eventsearch", target.form, after_delete_summary_path, after_delete.entry_count)
    )

    manifest_path = write_manifest_csv(operation_dir, manifest_rows)
    summary = {
        "operation_dir": str(operation_dir),
        "manifest_path": str(manifest_path),
        "dry_run": dry_run,
        "target": {
            "csv_path": str(target.csv_path),
            "form": target.form,
            "user_id": target.user_id,
            "about": target.about,
            "date_range": list(target.date_range),
            "delete_all_in_range": delete_all_in_range,
            "expected_delete_match_count": target.expected_upload_count,
        },
        "counts": {
            "before": before_summary,
            "after_delete": after_delete_summary,
        },
        "preflight": _preflight_summary(target, before, preflight),
        "delete_event": _operation_summary(delete_execution),
    }
    write_json_artifact(operation_dir, "workflow_summary.json", summary)
    return summary


def run_event_replace_workflow(
    client: SmartabaseClient,
    records: object,
    *,
    form: str | None = None,
    base_dir: str | Path = "smartabase_runs",
    dry_run: bool = True,
    confirm: bool = False,
    delete_all_for_targets: bool = False,
) -> dict[str, object]:
    _ensure_delete_all_in_range_allowed(client, delete_all_in_range=delete_all_for_targets)
    input_records = coerce_records_input(records)
    targets = build_event_write_targets(input_records, form=form)
    operation_name = f"replace_{targets[0].form}" if len(targets) == 1 else "replace_multiple_forms"
    operation_dir = create_operation_folder(operation_name, base_dir=base_dir)
    write_operation_config(
        operation_dir,
        {
            "operation": "event_replace",
            "form_override": form,
            "target_count": len(targets),
            "dry_run": dry_run,
            "confirm": confirm,
            "delete_all_for_targets": delete_all_for_targets,
            "record_count": len(input_records),
        },
    )

    manifest_rows: list[dict[str, object]] = []
    target_plans: list[dict[str, object]] = []
    delete_event_ids: list[int] = []

    for target in targets:
        before = count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range)
        require_exact_event_ids(before)
        preflight = _build_replay_preflight(target, before, delete_all_in_range=delete_all_for_targets)
        for message in preflight.warnings:
            warnings.warn(message, RuntimeWarning, stacklevel=2)
        summary = _preflight_summary(target, before, preflight)
        summary.update({"about": target.about, "username": target.username, "email": target.email})
        target_plans.append(summary)
        delete_event_ids.extend(preflight.delete_event_ids)

    plan_path = write_json_artifact(operation_dir, "raw_json/01_deletion_plan.json", target_plans)
    manifest_rows.append(_manifest_row("deletion_plan", "local", form or "multiple", plan_path, len(target_plans)))

    delete_execution = client.delete_event(_unique_ints(delete_event_ids), dry_run=dry_run, confirm=confirm)
    delete_payload_path = write_json_artifact(
        operation_dir,
        "payloads/02_delete_event_payload.json",
        _operation_summary(delete_execution),
    )
    write_json_artifact(operation_dir, "raw_json/02_delete_event_responses.json", delete_execution.responses)
    manifest_rows.append(
        _manifest_row(
            "delete_event",
            delete_execution.endpoint,
            form or "multiple",
            delete_payload_path,
            delete_execution.attempted_count,
            status=_operation_status(delete_execution),
        )
    )

    after_delete = [
        _count_summary(
            "count_after_delete",
            count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range),
        )
        for target in targets
    ]
    after_delete_path = write_json_artifact(operation_dir, "raw_json/03_counts_after_delete.json", after_delete)
    manifest_rows.append(_manifest_row("count_after_delete", "eventsearch", form or "multiple", after_delete_path, len(after_delete)))

    upload_execution = client.insert_event(input_records, form=form, dry_run=dry_run, confirm=confirm)
    upload_payload_path = write_json_artifact(
        operation_dir,
        "payloads/04_insert_event_payload.json",
        _operation_summary(upload_execution),
    )
    write_json_artifact(operation_dir, "raw_json/04_insert_event_responses.json", upload_execution.responses)
    manifest_rows.append(
        _manifest_row(
            "insert_event",
            upload_execution.endpoint,
            form or "multiple",
            upload_payload_path,
            upload_execution.attempted_count,
            status=_operation_status(upload_execution),
        )
    )

    after_upload = [
        _count_summary(
            "count_after_upload",
            count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range),
        )
        for target in targets
    ]
    after_upload_path = write_json_artifact(operation_dir, "raw_json/05_counts_after_upload.json", after_upload)
    manifest_rows.append(_manifest_row("count_after_upload", "eventsearch", form or "multiple", after_upload_path, len(after_upload)))

    manifest_path = write_manifest_csv(operation_dir, manifest_rows)
    summary = {
        "operation_dir": str(operation_dir),
        "manifest_path": str(manifest_path),
        "dry_run": dry_run,
        "form_override": form,
        "delete_all_for_targets": delete_all_for_targets,
        "target_count": len(targets),
        "record_count": len(input_records),
        "targets": target_plans,
        "counts": {
            "after_delete": after_delete,
            "after_upload": after_upload,
        },
        "delete_event": _operation_summary(delete_execution),
        "insert_event": _operation_summary(upload_execution),
    }
    write_json_artifact(operation_dir, "workflow_summary.json", summary)
    return summary


def run_example_event_replay(
    client: SmartabaseClient,
    *,
    csv_path: str | Path = DEFAULT_EXAMPLE_CSV,
    config_path: str | Path = DEFAULT_EXAMPLE_CONFIG,
    base_dir: str | Path = "smartabase_runs",
    dry_run: bool = True,
    confirm: bool = False,
    delete_all_in_range: bool = False,
) -> dict[str, object]:
    target = load_example_event_workflow_input(csv_path=csv_path, config_path=config_path)
    return run_event_replay_workflow(
        client,
        target,
        base_dir=base_dir,
        dry_run=dry_run,
        confirm=confirm,
        delete_all_in_range=delete_all_in_range,
    )


def run_example_event_delete(
    client: SmartabaseClient,
    *,
    csv_path: str | Path = DEFAULT_EXAMPLE_CSV,
    config_path: str | Path = DEFAULT_EXAMPLE_CONFIG,
    base_dir: str | Path = "smartabase_runs",
    dry_run: bool = True,
    confirm: bool = False,
    delete_all_in_range: bool = False,
) -> dict[str, object]:
    target = load_example_event_workflow_input(csv_path=csv_path, config_path=config_path)
    return run_event_delete_workflow(
        client,
        target,
        base_dir=base_dir,
        dry_run=dry_run,
        confirm=confirm,
        delete_all_in_range=delete_all_in_range,
    )


def build_event_write_targets(
    records: object,
    *,
    form: str | None = None,
) -> list[EventWriteTarget]:
    grouped: dict[tuple[str, int], dict[str, object]] = {}
    for row_index, row in enumerate(coerce_records_input(records)):
        metadata = _canonical_metadata_row(row)
        row_form = form or str(metadata.get("form") or "").strip()
        if not row_form:
            raise ValueError("form is required for event target planning when records do not include form metadata.")
        user_id_raw = metadata.get("user_id")
        if user_id_raw in (None, ""):
            raise ValueError("user_id is required for event target planning.")
        start_date_raw = metadata.get("start_date")
        if start_date_raw in (None, ""):
            raise ValueError("start_date is required for event target planning.")
        user_id = int(user_id_raw)
        start_date = parse_ams_date(
            start_date_raw,
            field="start_date",
            row_index=row_index,
        )
        key = (row_form, user_id)
        if key not in grouped:
            grouped[key] = {
                "form": row_form,
                "user_id": user_id,
                "about": str(metadata.get("about") or ""),
                "username": str(metadata.get("username") or ""),
                "email": str(metadata.get("email") or ""),
                "dates": [start_date],
                "records": [dict(row)],
            }
            continue
        grouped[key]["dates"].append(start_date)
        grouped[key]["records"].append(dict(row))
        if not grouped[key]["about"] and metadata.get("about"):
            grouped[key]["about"] = str(metadata["about"])
        if not grouped[key]["username"] and metadata.get("username"):
            grouped[key]["username"] = str(metadata["username"])
        if not grouped[key]["email"] and metadata.get("email"):
            grouped[key]["email"] = str(metadata["email"])

    targets: list[EventWriteTarget] = []
    for item in grouped.values():
        dates = item["dates"]
        targets.append(
            EventWriteTarget(
                form=str(item["form"]),
                user_id=int(item["user_id"]),
                about=str(item["about"]),
                username=str(item["username"]),
                email=str(item["email"]),
                date_range=(format_ams_date(min(dates)), format_ams_date(max(dates))),
                records=list(item["records"]),
            )
        )
    return sorted(targets, key=lambda item: (item.form, item.user_id, item.date_range))


def plan_event_deletions(
    client: SmartabaseClient,
    records: object,
    *,
    form: str | None = None,
    delete_all_for_targets: bool = False,
) -> list[dict[str, object]]:
    plans: list[dict[str, object]] = []
    for target in build_event_write_targets(records, form=form):
        before = count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range)
        require_exact_event_ids(before)
        preflight = _build_replay_preflight(target, before, delete_all_in_range=delete_all_for_targets)
        summary = _preflight_summary(target, before, preflight)
        summary.update(
            {
                "about": target.about,
                "username": target.username,
                "email": target.email,
                "delete_all_for_targets": delete_all_for_targets,
            }
        )
        plans.append(summary)
    return plans


def _match_athlete(athletes: list[Mapping[str, Any]], first_name: str, last_name: str) -> Mapping[str, Any]:
    about = f"{first_name} {last_name}"
    for athlete in athletes:
        if str(athlete.get("about", "")).strip() == about:
            return athlete
    for athlete in athletes:
        if (
            str(athlete.get("first_name", "")).strip() == first_name
            and str(athlete.get("last_name", "")).strip() == last_name
        ):
            return athlete
    raise ValueError(f"Could not match example athlete {about!r} from config.")


def _derive_form_name(filename: str) -> str:
    stem = Path(filename).stem
    if " template " in stem:
        stem = stem.split(" template ", 1)[0]
    words = []
    for token in stem.split():
        lower = token.lower()
        words.append(_FORM_ACRONYMS.get(lower, token.capitalize()))
    return " ".join(words)


def _csv_row_to_event_record(
    row: Mapping[str, str],
    *,
    user_id: int,
    about: str,
) -> dict[str, object]:
    record: dict[str, object] = {
        "user_id": user_id,
        "about": about,
        "start_date": row.get(_DATE_COLUMN, "").strip(),
    }
    raw_time = row.get(_TIME_COLUMN, "").strip()
    if raw_time:
        record["start_time"] = raw_time
    for key, value in row.items():
        if key in _NAME_COLUMNS or key in {_DATE_COLUMN, _TIME_COLUMN}:
            continue
        record[key] = value
    return record


def _parse_date(value: str) -> datetime:
    parsed = parse_ams_date(value, field="Date")
    return datetime.combine(parsed, datetime.min.time())


def _find_event_records(payload: Any) -> list[Mapping[str, Any]]:
    return find_event_records(payload)


def _extract_event_ids(records: list[Mapping[str, Any]], rows: list[Mapping[str, object]]) -> list[int]:
    values: list[int] = []
    for item in records:
        extracted = _coerce_event_id(item)
        if extracted is not None:
            values.append(extracted)
    if values:
        return _unique_ints(values)
    for item in rows:
        extracted = _coerce_event_id(item)
        if extracted is not None:
            values.append(extracted)
    return _unique_ints(values)


def _coerce_event_id(item: Mapping[str, Any]) -> int | None:
    for key in EVENT_ID_KEYS:
        if key not in item:
            continue
        value = item[key]
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            event_id = value
        elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
            event_id = int(value.strip())
        else:
            return None
        return event_id if event_id > 0 else None
    return None


def _unique_ints(values: list[int]) -> list[int]:
    unique: list[int] = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _count_summary(step: str, result: EventCountResult) -> dict[str, object]:
    return {
        "step": step,
        "form": result.form,
        "user_id": result.user_id,
        "date_range": list(result.date_range),
        "entry_count": result.entry_count,
        "event_id_count": len(result.event_ids),
        "event_ids": result.event_ids,
        "row_count": len(result.rows),
    }


def _preflight_summary(
    target: ExampleEventWorkflowInput,
    before: EventCountResult,
    preflight: ReplayPreflightResult,
) -> dict[str, object]:
    return {
        "form": target.form,
        "user_id": target.user_id,
        "date_range": list(target.date_range),
        "expected_upload_count": target.expected_upload_count,
        "before_entry_count": before.entry_count,
        "match_strategy": preflight.match_strategy,
        "match_fields": preflight.match_fields,
        "delete_count": len(preflight.delete_event_ids),
        "delete_event_ids": preflight.delete_event_ids,
        "matched_existing_count": preflight.matched_existing_count,
        "unmatched_existing_count": preflight.unmatched_existing_count,
        "unmatched_existing_event_ids": preflight.unmatched_existing_event_ids,
        "missing_target_count": preflight.missing_target_count,
        "missing_target_keys": preflight.missing_target_keys,
        "duplicate_target_count": preflight.duplicate_target_count,
        "duplicate_target_keys": preflight.duplicate_target_keys,
        "duplicate_existing_count": preflight.duplicate_existing_count,
        "duplicate_existing_keys": preflight.duplicate_existing_keys,
        "warnings": preflight.warnings,
    }


def _operation_summary(result: OperationExecution) -> dict[str, object]:
    return {
        "endpoint": result.endpoint,
        "attempted_count": result.attempted_count,
        "dry_run": result.dry_run,
        "executed": result.executed,
        "body": result.body,
        "row_operations": result.row_operations,
        "responses": result.responses,
    }


def _operation_status(result: OperationExecution) -> str:
    if result.dry_run:
        return "dry_run"
    if result.executed:
        return "executed"
    return "skipped"


def _manifest_row(
    operation: str,
    endpoint: str,
    form: str,
    output_path: Path,
    row_count: int,
    *,
    status: str = "ok",
) -> dict[str, object]:
    return {
        "operation": operation,
        "endpoint": endpoint,
        "form": form,
        "output_path": str(output_path),
        "row_count": row_count,
        "status": status,
    }


def _canonical_metadata_row(row: Mapping[str, object]) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key, value in row.items():
        canonical = _compare_key(key)
        if canonical in {"form", "user_id", "about", "username", "email", "start_date"}:
            metadata[canonical] = value
    return metadata


def _ensure_delete_all_in_range_allowed(client: SmartabaseClient, *, delete_all_in_range: bool) -> None:
    if not delete_all_in_range:
        return
    if "sandbox" in client.credentials.url.lower():
        return
    raise PermissionError(
        "delete_all_in_range is restricted to Smartabase sandbox sites because it deletes all events in the "
        "form/user/date range."
    )


def _build_replay_preflight(
    target: ExampleEventWorkflowInput,
    before: EventCountResult,
    *,
    delete_all_in_range: bool,
) -> ReplayPreflightResult:
    if delete_all_in_range:
        warnings_list: list[str] = []
        if len(before.event_ids) > target.expected_upload_count:
            warnings_list.append(
                "Replay preflight warning: "
                f"{len(before.event_ids)} existing form instances are scheduled for deletion but only "
                f"{target.expected_upload_count} records are scheduled for upload. "
                "This usually means a previous upload added new events for the same date range without deleting the original data. "
                "If it is inexplicable that not the same number of datapoints is uploaded, inspect the run artifacts before continuing. "
                "This can happen in the sandbox workflow. On a real site this should not happen and requires authorization before continuing."
            )
        return ReplayPreflightResult(
            match_strategy="full_range",
            match_fields=["form", "user_id", "date_range"],
            delete_event_ids=before.event_ids,
            matched_existing_count=len(before.event_ids),
            unmatched_existing_event_ids=[],
            unmatched_existing_count=0,
            missing_target_keys=[],
            missing_target_count=0,
            duplicate_target_keys=[],
            duplicate_target_count=0,
            duplicate_existing_keys=[],
            duplicate_existing_count=0,
            warnings=warnings_list,
        )

    target_rows = [_canonicalize_target_record(record) for record in target.records]
    existing_rows = [_canonicalize_existing_row(row) for row in before.rows]

    match_field = _select_preferred_match_field(target_rows, existing_rows)
    if match_field:
        match_strategy = "preferred_field"
        match_fields = [_MATCH_KEY_LABELS.get(match_field, match_field)]
        target_keys = [_field_key(row, match_field) for row in target_rows]
        existing_keys = [_field_key(row, match_field) for row in existing_rows]
    else:
        fingerprint_fields = sorted({key for row in target_rows for key in row})
        match_strategy = "normalized_target_fields"
        match_fields = fingerprint_fields
        target_keys = [_fingerprint_key(row, fingerprint_fields) for row in target_rows]
        existing_keys = [_fingerprint_key(row, fingerprint_fields) for row in existing_rows]

    target_counts = _key_counts(target_keys)
    existing_counts = _key_counts(existing_keys)

    delete_event_ids = _delete_event_ids_for_matching_rows(before.rows, existing_keys, set(target_counts))
    missing_target_keys = [key for key in target_counts if key not in existing_counts]
    duplicate_target_keys = [key for key, count in target_counts.items() if count > 1]
    duplicate_existing_keys = [key for key, count in existing_counts.items() if key in target_counts and count > target_counts[key]]

    warnings_list: list[str] = []
    if len(delete_event_ids) > target.expected_upload_count:
        warnings_list.append(
            "Replay preflight warning: "
            f"{len(delete_event_ids)} existing form instances are scheduled for deletion but only "
            f"{target.expected_upload_count} records are scheduled for upload. "
            "This usually means a previous upload added new events for the same date range without deleting the original data. "
            "If it is inexplicable that not the same number of datapoints is uploaded, inspect the run artifacts before continuing. "
            "This can happen in the sandbox workflow. On a real site this should not happen and requires authorization before continuing."
        )

    return ReplayPreflightResult(
        match_strategy=match_strategy,
        match_fields=match_fields,
        delete_event_ids=delete_event_ids,
        matched_existing_count=len(delete_event_ids),
        unmatched_existing_event_ids=_delete_event_ids_for_matching_rows(before.rows, existing_keys, set(existing_counts) - set(target_counts)),
        unmatched_existing_count=sum(count for key, count in existing_counts.items() if key not in target_counts),
        missing_target_keys=missing_target_keys,
        missing_target_count=sum(target_counts[key] for key in missing_target_keys),
        duplicate_target_keys=duplicate_target_keys,
        duplicate_target_count=sum(target_counts[key] - 1 for key in duplicate_target_keys),
        duplicate_existing_keys=duplicate_existing_keys,
        duplicate_existing_count=sum(existing_counts[key] - target_counts[key] for key in duplicate_existing_keys),
        warnings=warnings_list,
    )


def _canonicalize_target_record(record: Mapping[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in record.items():
        canonical = _compare_key(key)
        if canonical in _EXCLUDED_MATCH_KEYS:
            continue
        normalized_value = _normalize_compare_value(canonical, value)
        if normalized_value is None:
            continue
        normalized[canonical] = normalized_value
    return normalized


def _canonicalize_existing_row(row: Mapping[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        canonical = _compare_key(key)
        normalized_value = _normalize_compare_value(canonical, value)
        if normalized_value is None:
            continue
        normalized[canonical] = normalized_value
    return normalized


def _select_preferred_match_field(
    target_rows: list[Mapping[str, str]],
    existing_rows: list[Mapping[str, str]],
) -> str | None:
    for field in _PREFERRED_MATCH_KEYS:
        if not target_rows:
            return None
        if not all(field in row for row in target_rows):
            continue
        if any(field in row for row in existing_rows):
            return field
    return None


def _field_key(row: Mapping[str, str], field: str) -> str:
    value = row.get(field)
    if value is None:
        return ""
    return value


def _fingerprint_key(row: Mapping[str, str], fields: list[str]) -> str:
    payload = {field: row[field] for field in fields if field in row}
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _key_counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _delete_event_ids_for_matching_rows(
    rows: list[Mapping[str, object]],
    row_keys: list[str],
    allowed_keys: set[str],
) -> list[int]:
    event_ids: list[int] = []
    for row, key in zip(rows, row_keys):
        if key not in allowed_keys:
            continue
        event_id = _coerce_event_id(row)
        if event_id is None:
            continue
        event_ids.append(event_id)
    return _unique_ints(event_ids)


def _compare_key(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = text.replace("-", "_").replace(" ", "_")
    text = re.sub(r"_+", "_", text)
    canonical = text.lower().strip("_")
    return _COLUMN_ALIASES.get(canonical, canonical)


def _normalize_compare_value(key: str, value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        if key == "user_id":
            nested_value = value.get("userId", value.get("user_id"))
            return _normalize_compare_value(key, nested_value)
        return None
    if value == "":
        return None
    text = str(value).strip()
    if not text:
        return None
    if key in {"user_id", "entered_by_user_id", "event_id", "id"}:
        try:
            return str(int(text))
        except ValueError:
            return text
    if key in {"start_date", "end_date"}:
        try:
            return datetime.strptime(text, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            return text
    if key in {"start_time", "end_time"}:
        for candidate in (text, text.upper()):
            for pattern in ("%H:%M", "%I:%M %p"):
                try:
                    parsed = datetime.strptime(candidate, pattern)
                    return parsed.strftime("%I:%M %p").lstrip("0").lower()
                except ValueError:
                    continue
        return text.lower()
    return text
