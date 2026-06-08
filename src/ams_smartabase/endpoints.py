"""Smartabase endpoint alias handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


DEFAULT_ENDPOINTS: dict[str, str] = {
    "usersearch": "usersearch",
    "groupmembers": "groupmembers",
    "currentgroup": "currentgroup",
    "listgroups": "listgroups",
    "eventsearch": "eventsearch",
    "filteredeventsearch": "filteredeventsearch",
    "profilesearch": "profilesearch",
    "synchronise": "synchronise",
    "eventsimport": "eventsimport",
    "profileimport": "profileimport",
    "deleteevent": "deleteevent",
}


@dataclass
class EndpointMap:
    """Resolve logical endpoint names to Smartabase endpoint aliases."""

    aliases: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ENDPOINTS))

    def resolve(self, endpoint_key: str) -> str:
        try:
            return self.aliases[endpoint_key]
        except KeyError as exc:
            raise KeyError(f"Missing Smartabase endpoint alias: {endpoint_key}") from exc

    def update(self, aliases: Mapping[str, str]) -> None:
        for key, value in aliases.items():
            if key in DEFAULT_ENDPOINTS and value:
                self.aliases[key] = value

    @classmethod
    def from_discovery(cls, payload: Any) -> "EndpointMap":
        """Build endpoint aliases from a permissive endpoint-discovery payload."""

        endpoint_map = cls()
        endpoint_map.update(_extract_aliases(payload))
        return endpoint_map


def _extract_aliases(payload: Any) -> dict[str, str]:
    found: dict[str, str] = {}

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            if key_text in DEFAULT_ENDPOINTS and isinstance(value, str):
                found[key_text] = _last_path_part(value)
            elif key_text in {"endpoint", "name", "key", "id"} and str(value) in DEFAULT_ENDPOINTS:
                alias = _pick_alias(payload)
                if alias:
                    found[str(value)] = alias
            else:
                found.update(_extract_aliases(value))
    elif isinstance(payload, list):
        for item in payload:
            found.update(_extract_aliases(item))

    return found


def _pick_alias(item: Mapping[str, Any]) -> str:
    for key in ("alias", "path", "url", "endpointName", "endpoint"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return _last_path_part(value)
    return ""


def _last_path_part(value: str) -> str:
    return value.rstrip("/").split("/")[-1]
