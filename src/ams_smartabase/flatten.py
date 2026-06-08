"""Helpers for flattening Smartabase JSON responses."""

from __future__ import annotations

from typing import Any, Mapping


ROW_KEYS = {"rows", "pairs"}


def flatten_event_response(payload: Any) -> list[dict[str, object]]:
    return flatten_records(payload, preferred_keys=("events", "eventData", "data", "results"))


def flatten_profile_response(payload: Any) -> list[dict[str, object]]:
    return flatten_records(payload, preferred_keys=("profiles", "profileData", "data", "results"))


def flatten_records(payload: Any, preferred_keys: tuple[str, ...]) -> list[dict[str, object]]:
    records = _find_records(payload, preferred_keys)
    return [row for record in records for row in _flatten_record(record)]


def _find_records(payload: Any, preferred_keys: tuple[str, ...]) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, Mapping):
        return []
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    for value in payload.values():
        nested = _find_records(value, preferred_keys)
        if nested:
            return nested
    return []


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
