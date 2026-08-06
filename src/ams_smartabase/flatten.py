"""Helpers for flattening Smartabase JSON responses."""

from __future__ import annotations

from typing import Any, Mapping


ROW_KEYS = {"rows", "pairs"}
_EVENT_RECORD_KEYS = {
    "about",
    "end_date",
    "eventId",
    "event_id",
    "existingEventId",
    "finishDate",
    "finishTime",
    "form",
    "formName",
    "pairs",
    "rows",
    "startDate",
    "startTime",
    "start_date",
    "start_time",
    "userId",
    "user_id",
}
_PROFILE_RECORD_KEYS = {
    "about",
    "email",
    "form",
    "formName",
    "pairs",
    "profileId",
    "profile_id",
    "rows",
    "userId",
    "user_id",
    "username",
}


def flatten_event_response(payload: Any) -> list[dict[str, object]]:
    return [row for record in find_event_records(payload) for row in _flatten_record(record)]


def flatten_profile_response(payload: Any) -> list[dict[str, object]]:
    return [row for record in find_profile_records(payload) for row in _flatten_record(record)]


def find_event_records(payload: Any) -> list[Mapping[str, Any]]:
    """Return event objects from supported flat or nested response envelopes."""

    return _find_records(
        payload,
        preferred_keys=("events", "eventData", "data", "results"),
        record_label="event",
    )


def find_profile_records(payload: Any) -> list[Mapping[str, Any]]:
    """Return profile objects from supported flat or nested response envelopes."""

    return _find_records(
        payload,
        preferred_keys=("profiles", "profileData", "data", "results"),
        record_label="profile",
    )


def flatten_records(payload: Any, preferred_keys: tuple[str, ...]) -> list[dict[str, object]]:
    records = _find_compatible_records(payload, preferred_keys)
    return [row for record in records for row in _flatten_record(record)]


def _find_compatible_records(payload: Any, preferred_keys: tuple[str, ...]) -> list[Any]:
    """Preserve the permissive generic flattener used outside typed AMS responses."""

    if isinstance(payload, list):
        return payload
    if not isinstance(payload, Mapping):
        return []
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    for value in payload.values():
        nested = _find_compatible_records(value, preferred_keys)
        if nested:
            return nested
    return []


def _find_records(
    payload: Any,
    preferred_keys: tuple[str, ...],
    *,
    record_label: str,
) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return _normalize_collection(payload, record_label=record_label)
    if not isinstance(payload, Mapping):
        if payload is None or payload == "":
            return []
        raise ValueError(f"Unrecognized Smartabase {record_label} response shape.")

    present_keys = [key for key in preferred_keys if key in payload]
    if len(present_keys) > 1:
        raise ValueError(
            f"Malformed Smartabase {record_label} response: multiple record collections were returned."
        )
    if present_keys:
        value = payload[present_keys[0]]
        if value is None:
            return []
        if not isinstance(value, (Mapping, list)):
            raise ValueError(
                f"Malformed Smartabase {record_label} response: "
                "the record collection must be an object or list."
            )
        return _find_records(value, preferred_keys, record_label=record_label)

    if "search" in payload:
        raise ValueError(
            f"Malformed Smartabase {record_label} response: a result batch is missing its nested results list."
        )
    if _is_direct_record(payload, record_label=record_label):
        return [payload]

    nested_values = [value for value in payload.values() if isinstance(value, (Mapping, list))]
    if len(nested_values) == 1:
        return _find_records(nested_values[0], preferred_keys, record_label=record_label)
    if not payload:
        return []
    if len(nested_values) > 1:
        raise ValueError(
            f"Malformed Smartabase {record_label} response: multiple nested response candidates were returned."
        )
    raise ValueError(f"Unrecognized Smartabase {record_label} response shape.")


def _normalize_collection(
    items: list[Any],
    *,
    record_label: str,
) -> list[Mapping[str, Any]]:
    if not items:
        return []
    if not all(isinstance(item, Mapping) for item in items):
        raise ValueError(
            f"Malformed Smartabase {record_label} response: record collections must contain objects only."
        )

    nested_flags = ["results" in item for item in items]
    if any(nested_flags) and not all(nested_flags):
        raise ValueError(
            f"Malformed Smartabase {record_label} response: direct records and nested result batches were mixed."
        )
    if not any(nested_flags):
        if any("search" in item for item in items):
            raise ValueError(
                f"Malformed Smartabase {record_label} response: a result batch is missing its nested results list."
            )
        if not all(_is_direct_record(item, record_label=record_label) for item in items):
            raise ValueError(
                f"Malformed Smartabase {record_label} response: "
                f"record collections must contain recognizable {record_label} objects only."
            )
        return list(items)

    records: list[Mapping[str, Any]] = []
    for batch in items:
        nested = batch["results"]
        if not isinstance(nested, list):
            raise ValueError(
                f"Malformed Smartabase {record_label} response: nested results must be a list."
            )
        if not all(isinstance(item, Mapping) for item in nested):
            raise ValueError(
                f"Malformed Smartabase {record_label} response: nested results must contain objects only."
            )
        if any("results" in item or "search" in item for item in nested):
            raise ValueError(
                f"Malformed Smartabase {record_label} response: nested result batches are deeper than supported."
            )
        if not all(_is_direct_record(item, record_label=record_label) for item in nested):
            raise ValueError(
                f"Malformed Smartabase {record_label} response: "
                f"nested results must contain recognizable {record_label} objects only."
            )
        records.extend(nested)
    return records


def _is_direct_record(item: Mapping[str, Any], *, record_label: str) -> bool:
    keys = _EVENT_RECORD_KEYS if record_label == "event" else _PROFILE_RECORD_KEYS
    return bool(keys.intersection(item))


def _flatten_record(record: Any) -> list[dict[str, object]]:
    if not isinstance(record, Mapping):
        return [{"value": record}]

    metadata = {key: value for key, value in record.items() if key not in ROW_KEYS}
    rows = record.get("rows")
    if isinstance(rows, list) and rows:
        flattened = []
        for index, row in enumerate(rows):
            item = dict(metadata)
            item["row_index"] = _row_index(row, index)
            item.update(_pairs_from(row))
            flattened.append(item)
        return flattened

    pairs = _pairs_from(record)
    if pairs:
        item = dict(metadata)
        item.update(pairs)
        return [item]

    return [metadata]


def _row_index(row: Any, fallback: int) -> int:
    if isinstance(row, Mapping) and "row" in row:
        try:
            return int(row["row"])
        except (TypeError, ValueError):
            return fallback
    return fallback


def _pairs_from(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    pairs = value.get("pairs")
    if isinstance(pairs, Mapping):
        return dict(pairs)
    if not isinstance(pairs, list):
        return {}

    flattened: dict[str, object] = {}
    for pair in pairs:
        if not isinstance(pair, Mapping):
            continue
        key = pair.get("key", pair.get("name"))
        if key is None:
            continue
        flattened[str(key)] = pair.get("value")
    return flattened
