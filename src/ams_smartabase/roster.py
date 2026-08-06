"""Helpers for fetching and normalizing Smartabase user roster payloads."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Mapping

from .client import SmartabaseClient
from .config import _is_secret_key, redact_secrets
from .payloads import coerce_records_input


_ROSTER_KEYS = (
    "users",
    "groupUsers",
    "members",
    "results",
    "data",
    "response",
    "payload",
)
_GROUP_ENVELOPE_KEYS = (
    "groups",
    "groupNames",
    "group_names",
    "results",
    "items",
    "data",
    "response",
    "payload",
)
_GROUP_NAME_KEYS = ("group", "groupName", "group_name", "name")
_SENSITIVE_EXTRA_KEYS = {
    "password",
    "smartabase_password",
    "sb_pass",
    "cookie",
    "cookies",
    "set_cookie",
    "session_header",
    "session_id",
    "jsessionid",
    "authorization",
    "auth_header",
    "access_token",
    "refresh_token",
    "id_token",
    "bearer_token",
    "api_key",
    "secret",
}
_BASE_FIELD_ALIASES = {
    "user_id": (
        "user_id",
        "userId",
        "userid",
        "id",
        "smartabase_user_id",
        "smartabaseUserId",
    ),
    "about": ("about", "name"),
    "first_name": ("first_name", "firstName", "firstname"),
    "last_name": ("last_name", "lastName", "lastname"),
    "username": ("username", "user_name", "userName", "login"),
    "email": ("email", "email_address", "emailAddress", "emailaddress"),
}

BASE_ROSTER_COLUMNS = (
    "user_id",
    "about",
    "first_name",
    "last_name",
    "username",
    "email",
)


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


def roster_entry_to_row(
    entry: RosterEntry,
    *,
    include_all_cols: bool = False,
) -> dict[str, str]:
    """Convert one roster entry to a text-only, CSV-ready row.

    Extended fields come only from ``entry.raw``. Their keys are normalized to
    snake case and their nested values are encoded as compact JSON. Distinct
    raw keys that normalize to the same extended column are rejected rather
    than silently overwriting one another.
    """

    row = {
        "user_id": _entry_user_id_text(entry),
        "about": _text_cell(entry.about),
        "first_name": _text_cell(entry.first_name),
        "last_name": _text_cell(entry.last_name),
        "username": _text_cell(entry.username),
        "email": _text_cell(entry.email),
    }
    if not include_all_cols:
        return row

    extra_values: dict[str, str] = {}
    extra_sources: dict[str, str] = {}
    base_aliases = _normalized_base_aliases()
    for raw_key, raw_value in entry.raw.items():
        normalized_key = _normalize_column_key(raw_key)
        if not normalized_key:
            raise ValueError("Roster extra column keys must contain at least one letter or number.")
        if normalized_key in base_aliases:
            continue
        if normalized_key in _SENSITIVE_EXTRA_KEYS or _is_secret_key(raw_key):
            continue
        if normalized_key in extra_values:
            first_key = extra_sources[normalized_key]
            raise ValueError(
                "Roster extra column collision: "
                f"{first_key!r} and {str(raw_key)!r} both normalize to {normalized_key!r}."
            )
        extra_values[normalized_key] = _serialize_cell(
            redact_secrets(raw_value),
            column=normalized_key,
        )
        extra_sources[normalized_key] = str(raw_key)

    for key in sorted(extra_values):
        row[key] = extra_values[key]
    return row


def roster_to_rows(
    entries: Iterable[RosterEntry],
    *,
    include_all_cols: bool = False,
) -> tuple[list[str], list[dict[str, str]]]:
    """Convert roster entries to deterministic CSV columns and text rows."""

    serialized = [
        roster_entry_to_row(entry, include_all_cols=include_all_cols)
        for entry in entries
    ]
    columns = list(BASE_ROSTER_COLUMNS)
    if include_all_cols:
        extra_columns = sorted(
            {
                key
                for row in serialized
                for key in row
                if key not in BASE_ROSTER_COLUMNS
            }
        )
        columns.extend(extra_columns)

    rows = [{column: row.get(column, "") for column in columns} for row in serialized]
    return columns, rows


def normalize_group_response(payload: Any) -> list[dict[str, str]]:
    """Normalize plausible group response shapes to deterministic name rows."""

    names = _find_group_names(payload)
    if not names and not _is_recognized_group_payload(payload):
        raise ValueError("Unrecognized Smartabase group response shape.")
    unique_names = sorted(set(names), key=lambda value: (value.casefold(), value))
    return [{"group": name} for name in unique_names]


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


def _find_roster_records(
    payload: Any,
    *,
    allow_legacy_identity: bool = True,
) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return _find_roster_records_in_list(
            payload,
            allow_legacy_identity=allow_legacy_identity,
        )
    if not isinstance(payload, Mapping):
        if payload is None or payload == "":
            return []
        raise ValueError("Unrecognized Smartabase roster response shape.")

    is_direct = _is_direct_roster_record(
        payload,
        allow_legacy_identity=allow_legacy_identity,
    )
    envelope_keys = [key for key in _ROSTER_KEYS if key in payload]
    if is_direct and envelope_keys:
        raise ValueError(
            "Ambiguous Smartabase roster response shape: "
            "a user record also contained a candidate roster envelope."
        )
    if is_direct:
        return [payload]
    if len(envelope_keys) > 1:
        raise ValueError(
            "Ambiguous Smartabase roster response shape: "
            "multiple candidate envelopes were returned."
        )
    if envelope_keys:
        value = payload[envelope_keys[0]]
        if value is None:
            return []
        if not isinstance(value, (Mapping, list)):
            raise ValueError(
                "Malformed Smartabase roster response: "
                "the roster envelope must contain an object or list."
            )
        return _find_roster_records(
            value,
            allow_legacy_identity=allow_legacy_identity,
        )

    nested_values = [
        value
        for value in payload.values()
        if isinstance(value, (Mapping, list))
    ]
    if len(nested_values) == 1:
        return _find_roster_records(
            nested_values[0],
            allow_legacy_identity=allow_legacy_identity,
        )
    if not payload:
        return []
    raise ValueError("Unrecognized Smartabase roster response shape.")


def _find_roster_records_in_list(
    payload: list[Any],
    *,
    allow_legacy_identity: bool,
) -> list[Mapping[str, Any]]:
    """Return either direct users or users inside homogeneous result batches."""

    if not payload:
        return []

    mappings: list[Mapping[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(
                "Malformed Smartabase roster response: "
                f"list item {index} is not an object."
            )
        mappings.append(item)

    direct_flags = [
        _is_direct_roster_record(
            item,
            allow_legacy_identity=allow_legacy_identity,
        )
        for item in mappings
    ]
    batch_flags = [_is_roster_result_batch(item) for item in mappings]

    if any(
        is_direct and is_batch
        for is_direct, is_batch in zip(direct_flags, batch_flags)
    ):
        raise ValueError(
            "Ambiguous Smartabase roster response shape: "
            "a list item matched both a user record and a result wrapper."
        )
    if all(direct_flags):
        return mappings
    if all(batch_flags):
        records: list[Mapping[str, Any]] = []
        for item in mappings:
            records.extend(
                _find_roster_records(
                    item["results"],
                    allow_legacy_identity=False,
                )
            )
        return records
    if any(direct_flags) and any(batch_flags):
        raise ValueError(
            "Ambiguous Smartabase roster response shape: "
            "user records and result wrappers were mixed."
        )

    invalid_index = next(
        index
        for index, (is_direct, is_batch) in enumerate(
            zip(direct_flags, batch_flags),
            start=1,
        )
        if not is_direct and not is_batch
    )
    raise ValueError(
        "Malformed Smartabase roster response: "
        f"list item {invalid_index} is neither a user record nor a result wrapper."
    )


def _is_direct_roster_record(
    item: Mapping[str, Any],
    *,
    allow_legacy_identity: bool,
) -> bool:
    """Recognize shallow user fields without matching nested group/role IDs."""

    normalized_keys = {_normalize_column_key(key) for key in item}
    direct_aliases = _normalized_base_aliases() - {"id", "name"}
    if normalized_keys & direct_aliases:
        return True
    return allow_legacy_identity and {"id", "name"}.issubset(normalized_keys)


def _is_roster_result_batch(item: Mapping[str, Any]) -> bool:
    """Recognize the official search-wrapper shape around actual user rows."""

    return isinstance(item.get("results"), list)


def _normalize_roster_entry(item: Mapping[str, Any]) -> RosterEntry:
    user_id = _coerce_int(_first_present(item, *_BASE_FIELD_ALIASES["user_id"]))
    first_name = _first_text(item, *_BASE_FIELD_ALIASES["first_name"])
    last_name = _first_text(item, *_BASE_FIELD_ALIASES["last_name"])
    about = _first_text(
        item,
        *_BASE_FIELD_ALIASES["about"],
        default=_join_about(first_name, last_name),
    )
    username = _first_text(item, *_BASE_FIELD_ALIASES["username"])
    email = _first_text(item, *_BASE_FIELD_ALIASES["email"])
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
    normalized_items = [
        (_normalize_column_key(raw_key), value)
        for raw_key, value in item.items()
        if value not in (None, "")
    ]
    for key in keys:
        normalized_key = _normalize_column_key(key)
        for raw_key, value in normalized_items:
            if raw_key == normalized_key:
                return value
    return None


def _first_text(item: Mapping[str, Any], *keys: str, default: str = "") -> str:
    value = _first_present(item, *keys)
    if value is None:
        return default
    return str(value).strip()


def _join_about(first_name: str, last_name: str) -> str:
    return " ".join(part for part in (first_name, last_name) if part).strip()


def _entry_user_id_text(entry: RosterEntry) -> str:
    raw_value = _first_present(entry.raw, *_BASE_FIELD_ALIASES["user_id"])
    if isinstance(raw_value, Mapping):
        raw_value = _first_present(raw_value, *_BASE_FIELD_ALIASES["user_id"])
    if raw_value not in (None, ""):
        return str(raw_value)
    if entry.user_id is None:
        return ""
    return str(entry.user_id)


def _normalized_base_aliases() -> set[str]:
    return {
        _normalize_column_key(alias)
        for aliases in _BASE_FIELD_ALIASES.values()
        for alias in aliases
    }


def _normalize_column_key(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text)
    return text.strip("_").lower()


def _serialize_cell(value: object, *, column: str) -> str:
    if value is None:
        return ""
    if isinstance(value, (Mapping, list, tuple)):
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Roster column {column!r} contains a value that cannot be encoded as JSON."
            ) from exc
    return str(value)


def _text_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _find_group_names(payload: Any) -> list[str]:
    if isinstance(payload, str):
        text = payload.strip()
        return [text] if text else []
    if isinstance(payload, list):
        names: list[str] = []
        for item in payload:
            names.extend(_find_group_names(item))
        return names
    if not isinstance(payload, Mapping):
        return []

    direct_name = _first_present(payload, *_GROUP_NAME_KEYS)
    if isinstance(direct_name, str):
        text = direct_name.strip()
        if text:
            return [text]

    names = []
    matched_envelope = False
    for key in _GROUP_ENVELOPE_KEYS:
        if key not in payload:
            continue
        matched_envelope = True
        names.extend(_find_group_names(payload[key]))
    if names or matched_envelope:
        return names

    nested_values = [
        value
        for value in payload.values()
        if isinstance(value, (Mapping, list))
    ]
    if len(nested_values) == 1:
        return _find_group_names(nested_values[0])
    return []


def _is_recognized_group_payload(payload: Any) -> bool:
    if payload is None or payload == "":
        return True
    if isinstance(payload, str):
        return True
    if isinstance(payload, list):
        return not payload or all(
            isinstance(item, (str, Mapping))
            and _is_recognized_group_payload(item)
            for item in payload
        )
    if not isinstance(payload, Mapping):
        return False
    if any(key in payload for key in _GROUP_NAME_KEYS):
        return True
    for key in _GROUP_ENVELOPE_KEYS:
        if key in payload:
            return _is_recognized_group_payload(payload[key])
    nested_values = [
        value
        for value in payload.values()
        if isinstance(value, (Mapping, list))
    ]
    return (
        len(nested_values) == 1
        and _is_recognized_group_payload(nested_values[0])
    )


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
    aliases = {
        _normalize_column_key(alias)
        for alias in _BASE_FIELD_ALIASES["user_id"]
    }
    for key, value in row.items():
        if _normalize_column_key(key) in aliases:
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
        _normalize_column_key(alias)
        for alias in _BASE_FIELD_ALIASES[key]
    }
    for raw_key, raw_value in row.items():
        normalized = _normalize_column_key(raw_key)
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
