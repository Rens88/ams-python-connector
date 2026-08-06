"""Canonical AMS date parsing and formatting."""

from __future__ import annotations

from datetime import date, datetime

from .diagnostics import AMSDateFormatError


AMS_DATE_FORMAT = "%d/%m/%Y"
AMS_DATE_FORMAT_LABEL = "DD/MM/YYYY"


def parse_ams_date(
    value: object,
    *,
    field: str = "date",
    row_index: int | None = None,
) -> date:
    """Return a date or raise an actionable, pre-transport validation error."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise _date_error(field=field, row_index=row_index, received_type=type(value).__name__)

    text = value.strip()
    try:
        parsed = datetime.strptime(text, AMS_DATE_FORMAT).date()
    except ValueError as exc:
        raise _date_error(
            field=field,
            row_index=row_index,
            received_type="str",
        ) from exc
    if parsed.strftime(AMS_DATE_FORMAT) != text:
        raise _date_error(field=field, row_index=row_index, received_type="str")
    return parsed


def format_ams_date(value: date | datetime) -> str:
    """Serialize a Python date using the canonical AMS day-first format."""

    resolved = value.date() if isinstance(value, datetime) else value
    return resolved.strftime(AMS_DATE_FORMAT)


def _date_error(
    *,
    field: str,
    row_index: int | None,
    received_type: str,
) -> AMSDateFormatError:
    location = f" at row {row_index}" if row_index is not None else ""
    return AMSDateFormatError(
        f"Invalid Smartabase date for {field!r}{location}. Expected a Python date/datetime "
        f"or an exact day-first string in {AMS_DATE_FORMAT_LABEL} format "
        f"({AMS_DATE_FORMAT}), for example 06/08/2026; received {received_type}. "
        "No API request was sent. Convert the source value before retrying.",
        field=field,
        row_index=row_index,
        expected=f"date, datetime, or {AMS_DATE_FORMAT_LABEL} ({AMS_DATE_FORMAT})",
        details={"received_type": received_type},
    )
