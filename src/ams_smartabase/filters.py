"""Request-body builders and validation for read operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from typing import Iterable, Sequence


USER_KEYS = {"user_id", "about", "username", "email", "group", "current_group"}
DATA_CONDITION_CODES = {
    "equal_to": 1,
    "=": 1,
    "not_equal_to": 2,
    "!=": 2,
    "contains": 3,
    "%in%": 3,
    "less_than": 4,
    "<": 4,
    "greater_than": 5,
    ">": 5,
    "less_than_or_equal_to": 6,
    "<=": 6,
    "greater_than_or_equal_to": 7,
    ">=": 7,
}

_DATE_FORMAT = "%d/%m/%Y"
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}\s?(am|pm)$", re.IGNORECASE)


@dataclass(frozen=True)
class DataFilter:
    data_key: str
    data_value: object
    data_condition: str = "equal_to"

    def as_smartabase(self) -> dict[str, object]:
        if self.data_condition not in DATA_CONDITION_CODES:
            raise ValueError(f"Unsupported data condition: {self.data_condition!r}.")
        if not self.data_key:
            raise ValueError("Data filter key is required.")
        return {
            "key": self.data_key,
            "value": "" if self.data_value is None else str(self.data_value),
            "filterCondition": DATA_CONDITION_CODES[self.data_condition],
        }


def build_user_request(
    user_key: str | None = None,
    user_value: object | Sequence[object] | None = None,
) -> tuple[str, dict[str, object]]:
    """Return the endpoint key and body for a Smartabase user export."""

    if not user_key:
        return "usersearch", {"identification": None}
    if user_key not in USER_KEYS:
        raise ValueError(f"Unsupported user_key: {user_key!r}.")

    if user_key == "group":
        if user_value in (None, ""):
            raise ValueError("user_value is required when user_key='group'.")
        return "groupmembers", {"name": str(user_value)}
    if user_key == "current_group":
        return "currentgroup", {"name": ""}

    values = _as_list(user_value)
    if not values:
        raise ValueError(f"user_value is required when user_key={user_key!r}.")

    return "usersearch", {"identification": [_identity(user_key, value) for value in values]}


def build_group_request() -> tuple[str, dict[str, str]]:
    return "listgroups", {"name": ""}


def build_event_export_request(
    form: str,
    user_ids: Sequence[int],
    date_range: Sequence[str],
    time_range: Sequence[str] = ("12:00 am", "11:59 pm"),
    data_filters: Sequence[DataFilter] | None = None,
    events_per_user: int | None = None,
) -> tuple[str, dict[str, object]]:
    """Return endpoint key and body for event export or filtered event export."""

    if not form:
        raise ValueError("form is required.")
    start_date, finish_date = _validate_date_range(date_range)
    start_time, finish_time = _validate_time_range(time_range)

    body: dict[str, object] = {
        "formNames": form,
        "userIds": [int(user_id) for user_id in user_ids],
        "startDate": start_date,
        "finishDate": finish_date,
        "startTime": start_time,
        "finishTime": finish_time,
    }
    if events_per_user is not None:
        body["resultsPerUser"] = int(events_per_user)

    filters = list(data_filters or [])
    if not filters:
        return "eventsearch", body

    keys = [item.data_key for item in filters]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate data filter keys are not supported.")

    body["filter"] = [
        {
            "formName": form,
            "filterSet": [item.as_smartabase() for item in filters],
        }
    ]
    return "filteredeventsearch", body


def build_profile_export_request(form: str, user_ids: Sequence[int]) -> tuple[str, dict[str, object]]:
    if not form:
        raise ValueError("form is required.")
    return "profilesearch", {"formNames": form, "userIds": [int(user_id) for user_id in user_ids]}


def build_sync_request(
    form: str,
    user_ids: Sequence[int],
    last_sync_time_on_server: int,
) -> tuple[str, dict[str, object]]:
    if not form:
        raise ValueError("form is required.")
    return (
        "synchronise",
        {
            "formName": form,
            "userIds": [int(user_id) for user_id in user_ids],
            "lastSynchronisationTimeOnServer": int(last_sync_time_on_server),
        },
    )


def sb_date_range(duration: int, end_date: str | date | None = None) -> tuple[str, str]:
    """Return a day-first inclusive date range ending on end_date."""

    if duration < 1:
        raise ValueError("duration must be at least 1 day.")
    finish = _coerce_date(end_date) if end_date is not None else date.today()
    start = finish - timedelta(days=duration - 1)
    return start.strftime(_DATE_FORMAT), finish.strftime(_DATE_FORMAT)


def _identity(user_key: str, value: object) -> dict[str, object]:
    if user_key == "user_id":
        return {"userId": int(value)}
    if user_key == "username":
        return {"username": str(value)}
    if user_key == "email":
        return {"emailAddress": str(value)}
    if user_key == "about":
        first_name, last_name = _split_about(str(value))
        return {"firstName": first_name, "lastName": last_name}
    raise ValueError(f"Unsupported user_key: {user_key!r}.")


def _split_about(value: str) -> tuple[str, str]:
    parts = value.strip().split()
    if not parts:
        raise ValueError("about user values cannot be blank.")
    return parts[0], " ".join(parts[1:])


def _as_list(value: object | Sequence[object] | None) -> list[object]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _validate_date_range(value: Sequence[str]) -> tuple[str, str]:
    if len(value) != 2:
        raise ValueError("date_range must contain start and finish dates.")
    start, finish = value
    start_dt = _coerce_date(start)
    finish_dt = _coerce_date(finish)
    if start_dt > finish_dt:
        raise ValueError("start_date must be on or before finish_date.")
    return start_dt.strftime(_DATE_FORMAT), finish_dt.strftime(_DATE_FORMAT)


def _validate_time_range(value: Sequence[str]) -> tuple[str, str]:
    if len(value) != 2:
        raise ValueError("time_range must contain start and finish times.")
    start, finish = (str(value[0]).strip().lower(), str(value[1]).strip().lower())
    for item in (start, finish):
        if not _TIME_RE.match(item):
            raise ValueError(f"Invalid Smartabase time: {item!r}.")
    return start, finish


def _coerce_date(value: str | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), _DATE_FORMAT).date()
