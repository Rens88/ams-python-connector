"""Payload builders for Smartabase write and delete operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
from typing import Iterable, Mapping, Sequence


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


@dataclass(frozen=True)
class PayloadPackage:
    endpoint: str
    body: object
    row_operations: list[dict[str, object]]

    @property
    def attempted_count(self) -> int:
        return len(self.row_operations)


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
    records: Sequence[Mapping[str, object]],
    *,
    form: str | None = None,
    mode: str = "insert",
    entered_by_user_id: int | None = None,
    now: datetime | None = None,
) -> PayloadPackage:
    """Build event import/update/upsert payloads without making an HTTP call."""

    if mode not in {"insert", "update", "upsert"}:
        raise ValueError("mode must be one of: insert, update, upsert.")
    normalized = [_normalize_record(record) for record in records]
    if not normalized:
        return PayloadPackage(EVENT_IMPORT_ENDPOINT, {"events": []}, [])
    if mode in {"update", "upsert"} and not all("event_id" in row for row in normalized):
        raise ValueError("event_id column is required for update and upsert.")

    clock = now or datetime.now()
    events: list[dict[str, object]] = []
    row_operations: list[dict[str, object]] = []

    for index, row in enumerate(normalized):
        event_id = row.get("event_id")
        if mode == "update" and _is_missing(event_id):
            raise ValueError("All update rows require event_id.")

        operation = "insert" if mode == "insert" or _is_missing(event_id) else "update"
        event = _event_payload(row, form=form, entered_by_user_id=entered_by_user_id, now=clock)
        if operation == "update":
            event["existingEventId"] = int(event_id)
        events.append(event)
        row_operations.append(
            {
                "row_index": index,
                "operation": operation,
                "event_id": "" if _is_missing(event_id) else event_id,
                "user_id": row.get("user_id", ""),
            }
        )

    return PayloadPackage(EVENT_IMPORT_ENDPOINT, {"events": events}, row_operations)


def build_profile_upsert_payloads(
    records: Sequence[Mapping[str, object]],
    *,
    form: str | None = None,
    entered_by_user_id: int | None = None,
) -> PayloadPackage:
    """Build profile upsert payloads without making an HTTP call."""

    normalized = [_normalize_record(record) for record in records]
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
    row: Mapping[str, object],
    *,
    form: str | None,
    entered_by_user_id: int | None,
    now: datetime,
) -> dict[str, object]:
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
        "rows": [{"row": 0, "pairs": _field_pairs(row)}],
    }
    if not _is_missing(entered_by):
        event["enteredByUserId"] = int(entered_by)
    return event


def _field_pairs(row: Mapping[str, object]) -> list[dict[str, str]]:
    pairs = []
    for key, value in row.items():
        if key in METADATA_COLUMNS:
            continue
        pairs.append({"key": key, "value": "" if value is None else str(value)})
    return pairs


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
