"""Helpers for fetching and normalizing Smartabase user roster payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .client import SmartabaseClient
from .payloads import coerce_records_input


_ROSTER_KEYS = ("users", "groupUsers", "members", "results", "data")


@dataclass(frozen=True)
class RosterEntry:
    user_id: int | None
    about: str
    first_name: str
    last_name: str
    username: str
    email: str
    group_names: list[str]
    raw: dict[str, object]


def fetch_roster(
    client: SmartabaseClient,
    *,
    group_name: str | None = None,
    current_group: bool = False,
    user_key: str | None = None,
    user_value: object | None = None,
) -> list[RosterEntry]:
    """Fetch and normalize Smartabase user records for planning workflows."""

    resolved_user_key, resolved_user_value = _resolve_roster_query(
        group_name=group_name,
        current_group=current_group,
        user_key=user_key,
        user_value=user_value,
    )
    payload = client.get_user(user_key=resolved_user_key, user_value=resolved_user_value)
    return flatten_roster_response(payload)


def resolve_user_ids(
    client: SmartabaseClient,
    records: object,
) -> list[dict[str, object]]:
    """Fill missing user_id values from username, email, or about lookups."""

    rows = coerce_records_input(records)
    resolved = [dict(row) for row in rows]
    lookups: dict[str, set[str]] = {"username": set(), "email": set(), "about": set()}
    row_keys: list[tuple[str, str] | None] = []

    for row in resolved:
        if _existing_user_id(row) is not None:
            row_keys.append(None)
            continue
        identifier = _row_identifier(row)
        if identifier is None:
            row_keys.append(None)
            continue
        key, value = identifier
        lookups[key].add(value)
        row_keys.append(identifier)

    resolved_ids: dict[tuple[str, str], int] = {}
    for key in ("username", "email", "about"):
        values = sorted(lookups[key])
        if not values:
            continue
        roster = fetch_roster(client, user_key=key, user_value=values)
        for entry in roster:
            if entry.user_id is None:
                continue
            lookup_value = _entry_identifier(entry, key)
            if not lookup_value:
                continue
            target = (key, lookup_value)
            if target in resolved_ids and resolved_ids[target] != entry.user_id:
                raise ValueError(f"Multiple Smartabase users matched {key}={lookup_value!r}.")
            resolved_ids[target] = entry.user_id

    for row, identifier in zip(resolved, row_keys):
        if identifier is None:
            continue
        if identifier not in resolved_ids:
            key, value = identifier
            raise ValueError(f"Could not resolve Smartabase user_id for {key}={value!r}.")
        row["user_id"] = resolved_ids[identifier]
    return resolved


def flatten_roster_response(payload: Any) -> list[RosterEntry]:
    return [_normalize_roster_entry(item) for item in _find_roster_records(payload)]


def _resolve_roster_query(
    *,
    group_name: str | None,
    current_group: bool,
    user_key: str | None,
    user_value: object | None,
) -> tuple[str | None, object | None]:
    selected = sum(bool(value) for value in (group_name, current_group, user_key))
    if selected > 1:
        raise ValueError("Choose only one roster selector: group_name, current_group, or user_key/user_value.")
    if group_name:
        return "group", group_name
    if current_group:
        return "current_group", None
    return user_key, user_value


def _find_roster_records(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in _ROSTER_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    for value in payload.values():
        nested = _find_roster_records(value)
        if nested:
            return nested
    return []


def _normalize_roster_entry(item: Mapping[str, Any]) -> RosterEntry:
    user_id = _coerce_int(_first_present(item, "user_id", "userId", "id", "smartabase_user_id"))
    first_name = _first_text(item, "first_name", "firstName")
    last_name = _first_text(item, "last_name", "lastName")
    about = _first_text(item, "about", "name", default=_join_about(first_name, last_name))
    username = _first_text(item, "username", "user_name", "login")
    email = _first_text(item, "email", "email_address", "emailAddress")
    group_names = _coerce_group_names(_first_present(item, "group_names", "groupNames", "groups", "group"))
    return RosterEntry(
        user_id=user_id,
        about=about,
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        group_names=group_names,
        raw=dict(item),
    )


def _first_present(item: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _first_text(item: Mapping[str, Any], *keys: str, default: str = "") -> str:
    value = _first_present(item, *keys)
    if value is None:
        return default
    return str(value).strip()


def _join_about(first_name: str, last_name: str) -> str:
    return " ".join(part for part in (first_name, last_name) if part).strip()


def _coerce_group_names(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _coerce_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, Mapping):
        nested = value.get("userId", value.get("user_id"))
        return _coerce_int(nested)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _existing_user_id(row: Mapping[str, object]) -> int | None:
    for key, value in row.items():
        if str(key).strip().lower().replace(" ", "_") in {"user_id", "userid"}:
            return _coerce_int(value)
    return None


def _row_identifier(row: Mapping[str, object]) -> tuple[str, str] | None:
    for key in ("username", "email", "about"):
        value = _lookup_row_value(row, key)
        if value:
            return key, value
    return None


def _lookup_row_value(row: Mapping[str, object], key: str) -> str:
    aliases = {
        "username": {"username", "user_name", "login"},
        "email": {"email", "email_address", "emailaddress"},
        "about": {"about", "name"},
    }[key]
    for raw_key, raw_value in row.items():
        normalized = str(raw_key).strip().lower().replace(" ", "_")
        if normalized not in aliases:
            continue
        text = str(raw_value).strip()
        if text:
            return text
    return ""


def _entry_identifier(entry: RosterEntry, key: str) -> str:
    if key == "username":
        return entry.username
    if key == "email":
        return entry.email
    return entry.about
