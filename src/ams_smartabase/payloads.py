"""Payload builders for Smartabase write and delete operations."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


EVENT_IMPORT_ENDPOINT = "eventsimport"
PROFILE_IMPORT_ENDPOINT = "profileimport"
DELETE_EVENT_ENDPOINT = "deleteevent"

METADATA_COLUMNS = {
    "user_id",
    "about",
    "form",
    "username",
    "email",
    "start_date",
    "end_date",
    "start_time",
    "end_time",
    "entered_by_user_id",
    "event_id",
    "uuid",
    "export",
    "synchronise",
}
PROTECTED_IDENTITY_FIELDS = {"first_name", "last_name"}
MISSING_VALUES = {None, ""}
SUGGESTED_IDENTIFIER_METADATA = (
    ("start_date", "Date"),
    ("start_time", "Start Time"),
    ("end_date", "Finish Date"),
    ("end_time", "Finish Time"),
    ("about", "About"),
    ("username", "Username"),
    ("email", "Email"),
)


@dataclass(frozen=True)
class PayloadPackage:
    endpoint: str
    body: object
    row_operations: list[dict[str, object]]

    @property
    def attempted_count(self) -> int:
        return len(self.row_operations)


def coerce_records_input(records: object) -> list[dict[str, object]]:
    """Accept common write-input shapes and return row dictionaries."""

    if isinstance(records, (str, Path)):
        return _read_csv_records(records)
    if _looks_like_dataframe(records):
        return _records_from_dataframe(records)
    if isinstance(records, Mapping):
        raise TypeError("Write inputs must be row collections, not a single mapping.")
    if isinstance(records, Sequence):
        return _records_from_sequence(records)
    if isinstance(records, Iterable):
        return _records_from_sequence(list(records))
    raise TypeError("Unsupported write input. Use a CSV path, a DataFrame-like object, or rows of mappings.")


def select_metadata(columns: Iterable[str]) -> list[str]:
    """Return known metadata columns present in the supplied column names."""

    normalized = {_normalize_column_name(column): column for column in columns}
    preferred_order = [
        "about",
        "user_id",
        "form",
        "start_date",
        "end_date",
        "start_time",
        "end_time",
        "entered_by_user_id",
        "event_id",
        "uuid",
        "export",
        "synchronise",
    ]
    return [normalized[name] for name in preferred_order if name in normalized]


def build_event_import_payloads(
    records: object,
    *,
    form: str | None = None,
    mode: str = "insert",
    entered_by_user_id: int | None = None,
    nested_table_identifiers: Mapping[str, Sequence[str]] | Sequence[str] | None = None,
    now: datetime | None = None,
) -> PayloadPackage:
    """Build event import/update/upsert payloads without making an HTTP call."""

    if mode not in {"insert", "update", "upsert"}:
        raise ValueError("mode must be one of: insert, update, upsert.")
    normalized = [_normalize_record(record) for record in coerce_records_input(records)]
    if not normalized:
        return PayloadPackage(EVENT_IMPORT_ENDPOINT, {"events": []}, [])
    grouped_records = _group_event_records(
        normalized,
        form=form,
        nested_table_identifiers=nested_table_identifiers,
    )
    if mode in {"update", "upsert"} and not all(group["event_id_present"] for group in grouped_records):
        raise ValueError("event_id column is required for update and upsert.")

    clock = now or datetime.now()
    events: list[dict[str, object]] = []
    row_operations: list[dict[str, object]] = []

    for index, group in enumerate(grouped_records):
        event_id = group["event_id"]
        if mode == "update" and _is_missing(event_id):
            raise ValueError("All update rows require event_id.")

        operation = "insert" if mode == "insert" or _is_missing(event_id) else "update"
        event = _event_payload(group["records"], form=form, entered_by_user_id=entered_by_user_id, now=clock)
        if operation == "update":
            event["existingEventId"] = int(event_id)
        events.append(event)
        row_operations.append(
            {
                "row_index": index,
                "source_row_indices": list(group["source_row_indices"]),
                "operation": operation,
                "event_id": "" if _is_missing(event_id) else event_id,
                "user_id": group["records"][0].get("user_id", ""),
            }
        )

    return PayloadPackage(EVENT_IMPORT_ENDPOINT, {"events": events}, row_operations)


def build_profile_upsert_payloads(
    records: object,
    *,
    form: str | None = None,
    entered_by_user_id: int | None = None,
) -> PayloadPackage:
    """Build profile upsert payloads without making an HTTP call."""

    normalized = [_normalize_record(record) for record in coerce_records_input(records)]
    profiles: list[dict[str, object]] = []
    row_operations: list[dict[str, object]] = []

    for index, row in enumerate(normalized):
        record_form = form or str(row.get("form") or "")
        if not record_form:
            raise ValueError("form is required for profile upsert payloads.")
        user_id = _required_int(row, "user_id")
        profile: dict[str, object] = {
            "formName": record_form,
            "userId": {"userId": user_id},
            "rows": [{"row": 0, "pairs": _field_pairs(row)}],
        }
        entered_by = entered_by_user_id if entered_by_user_id is not None else row.get("entered_by_user_id")
        if not _is_missing(entered_by):
            profile["enteredByUserId"] = int(entered_by)
        profiles.append(profile)
        row_operations.append({"row_index": index, "operation": "upsert", "user_id": user_id})

    return PayloadPackage(PROFILE_IMPORT_ENDPOINT, profiles, row_operations)


def build_delete_payloads(event_ids: Sequence[int | str]) -> PayloadPackage:
    """Build one delete request body per explicit Smartabase event ID."""

    bodies: list[dict[str, int]] = []
    rows: list[dict[str, object]] = []
    for index, value in enumerate(event_ids):
        if _is_missing(value):
            raise ValueError("event_id values cannot be missing for deletion.")
        event_id = int(value)
        bodies.append({"eventId": event_id})
        rows.append({"row_index": index, "operation": "delete", "event_id": event_id})
    return PayloadPackage(DELETE_EVENT_ENDPOINT, bodies, rows)


def _event_payload(
    event_rows: Sequence[Mapping[str, object]],
    *,
    form: str | None,
    entered_by_user_id: int | None,
    now: datetime,
) -> dict[str, object]:
    if not event_rows:
        raise ValueError("event payloads require at least one row.")
    row = event_rows[0]
    record_form = form or str(row.get("form") or "")
    if not record_form:
        raise ValueError("form is required for event payloads.")

    start_dt = _date_or_default(row.get("start_date"), now.date())
    start_time = _time_or_default(row.get("start_time"), now.time().replace(second=0, microsecond=0))
    default_end = datetime.combine(start_dt, start_time) + timedelta(hours=1)

    if _is_missing(row.get("start_date")) and not _is_missing(row.get("end_date")):
        raise ValueError("end_date cannot be supplied without start_date.")
    if _is_missing(row.get("start_time")) and not _is_missing(row.get("end_time")):
        raise ValueError("end_time cannot be supplied without start_time.")

    end_dt = _date_or_default(row.get("end_date"), default_end.date())
    end_time = _time_or_default(row.get("end_time"), default_end.time())
    user_id = _required_int(row, "user_id")
    entered_by = entered_by_user_id if entered_by_user_id is not None else row.get("entered_by_user_id")

    event: dict[str, object] = {
        "formName": record_form,
        "startDate": _format_date(start_dt),
        "finishDate": _format_date(end_dt),
        "startTime": _format_time(start_time),
        "finishTime": _format_time(end_time),
        "userId": {"userId": user_id},
        "rows": _event_rows_payload(event_rows),
    }
    if not _is_missing(entered_by):
        event["enteredByUserId"] = int(entered_by)
    return event


def _event_rows_payload(event_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if len(event_rows) == 1:
        return [{"row": 0, "pairs": _field_pairs(event_rows[0])}]

    shared_fields, nested_fields = _partition_group_field_names(event_rows)
    payload_rows: list[dict[str, object]] = [{"row": 0, "pairs": _field_pairs_subset(event_rows[0], shared_fields)}]
    if not nested_fields:
        return payload_rows
    for row_number, row in enumerate(event_rows, start=1):
        payload_rows.append({"row": row_number, "pairs": _field_pairs_subset(row, nested_fields)})
    return payload_rows


def _field_pairs(row: Mapping[str, object]) -> list[dict[str, str]]:
    pairs = []
    for key, value in row.items():
        if key in METADATA_COLUMNS:
            continue
        pairs.append({"key": key, "value": "" if value is None else str(value)})
    return pairs


def _field_pairs_subset(row: Mapping[str, object], fields: Sequence[str]) -> list[dict[str, str]]:
    allowed = set(fields)
    pairs = []
    for key, value in row.items():
        if key in METADATA_COLUMNS or key not in allowed:
            continue
        pairs.append({"key": key, "value": "" if value is None else str(value)})
    return pairs


def suggest_nested_table_candidates(
    records: object,
    *,
    form: str | None = None,
) -> list[dict[str, object]]:
    """Summarize repeated rows that look like nested-table candidates."""

    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    normalized = [_normalize_record(record) for record in coerce_records_input(records)]
    for index, row in enumerate(normalized):
        record_form = form or str(row.get("form") or "")
        key = (
            record_form,
            row.get("user_id", ""),
            row.get("about", ""),
            row.get("username", ""),
            row.get("email", ""),
            row.get("start_date", ""),
            row.get("start_time", ""),
            row.get("end_date", ""),
            row.get("end_time", ""),
        )
        grouped.setdefault(key, []).append({"row_index": index, "record": row})

    suggestions: list[dict[str, object]] = []
    for key, items in grouped.items():
        records_in_group = [item["record"] for item in items]
        if len(records_in_group) < 2:
            continue
        shared_fields, nested_fields = _partition_group_field_names(records_in_group)
        useful_shared_fields = [field for field in shared_fields if not _column_all_missing(records_in_group, field)]
        metadata_fields = [
            (field, label)
            for field, label in SUGGESTED_IDENTIFIER_METADATA
            if not _column_all_missing(records_in_group, field)
        ]
        main_table = {label: records_in_group[0].get(field, "") for field, label in metadata_fields}
        main_table.update({field: records_in_group[0].get(field, "") for field in useful_shared_fields})
        suggestions.append(
            {
                "form": key[0],
                "user_id": key[1],
                "about": key[2],
                "username": key[3],
                "email": key[4],
                "start_date": key[5],
                "start_time": key[6],
                "end_date": key[7],
                "end_time": key[8],
                "row_count": len(records_in_group),
                "source_row_indices": [item["row_index"] for item in items],
                "candidate_identifier_columns": [label for _, label in metadata_fields] + useful_shared_fields,
                "nested_columns": nested_fields,
                "main_table": main_table,
                "nested_table": [
                    {field: row.get(field, "") for field in nested_fields}
                    for row in records_in_group
                ],
            }
        )
    return suggestions


def _normalize_record(record: Mapping[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in record.items():
        canonical = _normalize_column_name(key)
        if canonical in PROTECTED_IDENTITY_FIELDS:
            raise ValueError(f"Protected identity field cannot be imported: {key!r}.")
        output_key = canonical if canonical in METADATA_COLUMNS else str(key).strip()
        normalized[output_key] = value
    return normalized


def _normalize_column_name(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = text.replace("-", "_").replace(" ", "_")
    text = re.sub(r"_+", "_", text)
    return text.lower()


def _group_event_records(
    records: Sequence[Mapping[str, object]],
    *,
    form: str | None,
    nested_table_identifiers: Mapping[str, Sequence[str]] | Sequence[str] | None,
) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    grouped_indexes: dict[tuple[object, ...], int] = {}

    for source_index, row in enumerate(records):
        record_form = form or str(row.get("form") or "")
        identifier_columns = _resolve_nested_table_identifiers(nested_table_identifiers, record_form)
        if not identifier_columns:
            groups.append(
                {
                    "records": [dict(row)],
                    "source_row_indices": [source_index],
                    "event_id": row.get("event_id"),
                    "event_id_present": "event_id" in row,
                }
            )
            continue

        key = _nested_event_group_key(row, record_form=record_form, identifier_columns=identifier_columns)
        existing_index = grouped_indexes.get(key)
        if existing_index is None:
            groups.append(
                {
                    "records": [dict(row)],
                    "source_row_indices": [source_index],
                    "event_id": row.get("event_id"),
                    "event_id_present": "event_id" in row,
                }
            )
            grouped_indexes[key] = len(groups) - 1
            continue

        group = groups[existing_index]
        group["records"].append(dict(row))
        group["source_row_indices"].append(source_index)
        group["event_id_present"] = bool(group["event_id_present"]) or ("event_id" in row)
        group["event_id"] = _merge_group_event_id(group["event_id"], row.get("event_id"))
    return groups


def _resolve_nested_table_identifiers(
    nested_table_identifiers: Mapping[str, Sequence[str]] | Sequence[str] | None,
    record_form: str,
) -> list[str]:
    if nested_table_identifiers is None:
        return []
    if isinstance(nested_table_identifiers, Mapping):
        normalized_form = _normalize_form_name(record_form)
        for form_name, columns in nested_table_identifiers.items():
            if _normalize_form_name(form_name) == normalized_form:
                return [str(column).strip() for column in columns]
        return []
    return [str(column).strip() for column in nested_table_identifiers]


def _nested_event_group_key(
    row: Mapping[str, object],
    *,
    record_form: str,
    identifier_columns: Sequence[str],
) -> tuple[object, ...]:
    key: list[object] = [
        record_form,
        _group_key_value(row.get("user_id")),
        _group_key_value(row.get("start_date")),
        _group_key_value(row.get("start_time")),
        _group_key_value(row.get("end_date")),
        _group_key_value(row.get("end_time")),
    ]
    for column in identifier_columns:
        value = _find_column_value(row, column)
        key.append(_group_key_value(value))
    return tuple(key)


def _merge_group_event_id(existing: object, incoming: object) -> object:
    if _is_missing(existing):
        return incoming
    if _is_missing(incoming):
        return existing
    if str(existing) != str(incoming):
        raise ValueError("Grouped nested-table rows must not contain multiple event_id values.")
    return existing


def _find_column_value(row: Mapping[str, object], column: str) -> object:
    if column in row:
        return row[column]
    normalized = _normalize_column_name(column)
    for key, value in row.items():
        if _normalize_column_name(key) == normalized:
            return value
    return None


def _partition_group_field_names(records: Sequence[Mapping[str, object]]) -> tuple[list[str], list[str]]:
    ordered_fields: list[str] = []
    seen = set()
    for row in records:
        for key in row:
            if key in METADATA_COLUMNS or key in seen:
                continue
            seen.add(key)
            ordered_fields.append(key)

    shared_fields: list[str] = []
    nested_fields: list[str] = []
    for field in ordered_fields:
        values = [_group_key_value(_find_column_value(row, field)) for row in records]
        if len(set(values)) <= 1:
            shared_fields.append(field)
        else:
            nested_fields.append(field)
    return shared_fields, nested_fields


def _column_all_missing(records: Sequence[Mapping[str, object]], field: str) -> bool:
    return all(_group_key_value(_find_column_value(row, field)) == "" for row in records)


def _group_key_value(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _normalize_form_name(value: object) -> str:
    return " ".join(str(value).split()).casefold()


def _required_int(row: Mapping[str, object], key: str) -> int:
    value = row.get(key)
    if _is_missing(value):
        raise ValueError(f"{key} is required.")
    return int(value)


def _is_missing(value: object) -> bool:
    return value in MISSING_VALUES


def _date_or_default(value: object, default: date) -> date:
    if _is_missing(value):
        return default
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%d/%m/%Y").date()


def _time_or_default(value: object, default: time) -> time:
    if _is_missing(value):
        return default
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    for pattern in ("%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(str(value).strip(), pattern).time()
        except ValueError:
            pass
    raise ValueError(f"Invalid Smartabase time: {value!r}.")


def _format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _format_time(value: time) -> str:
    return datetime.combine(date.today(), value).strftime("%I:%M %p").lstrip("0").lower()


def _read_csv_records(value: str | Path) -> list[dict[str, object]]:
    path = Path(value)
    if not path.exists():
        raise FileNotFoundError(f"Write input CSV not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _looks_like_dataframe(value: object) -> bool:
    return hasattr(value, "to_dict") and callable(getattr(value, "to_dict"))


def _records_from_dataframe(value: object) -> list[dict[str, object]]:
    records = value.to_dict("records")
    if not isinstance(records, list):
        raise TypeError("DataFrame-like write inputs must support to_dict('records').")
    return _records_from_sequence(records)


def _records_from_sequence(records: Sequence[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise TypeError(f"Write input row {index} is not a mapping.")
        normalized.append(dict(record))
    return normalized
