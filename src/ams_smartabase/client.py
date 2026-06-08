"""Small Smartabase HTTP client wrapper."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import DEFAULT_USER_AGENT, SmartabaseCredentials
from .endpoints import EndpointMap
from .filters import (
    DataFilter,
    build_event_export_request,
    build_group_request,
    build_profile_export_request,
    build_sync_request,
    build_user_request,
)


class SmartabaseClient:
    """HTTP client that keeps request construction separate from transport."""

    def __init__(
        self,
        credentials: SmartabaseCredentials,
        *,
        session: Any | None = None,
        endpoints: EndpointMap | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.credentials = credentials
        self.session = session or _requests_session()
        self.endpoints = endpoints or EndpointMap()
        self.user_agent = user_agent

    def login(self) -> Any:
        response = self.session.post(
            f"{self.credentials.url}/api/v2/user/loginUser",
            json=self.login_body(),
            auth=(self.credentials.username, self.credentials.password),
            headers=self._headers(),
        )
        response.raise_for_status()
        return _json_or_text(response)

    def login_body(self) -> dict[str, object]:
        return {
            "username": self.credentials.username,
            "password": self.credentials.password,
            "loginProperties": {
                "appName": self.user_agent,
                "clientTimestamp": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
            },
        }

    def discover_endpoints(self) -> EndpointMap:
        response = self.session.get(
            f"{self.credentials.url}/api/v3/endpoints",
            params={"version": "v1"},
            headers=self._headers(),
        )
        response.raise_for_status()
        self.endpoints = EndpointMap.from_discovery(response.json())
        return self.endpoints

    def post_v1(self, endpoint_key: str, body: dict[str, object] | list[object]) -> Any:
        endpoint = self.endpoints.resolve(endpoint_key)
        response = self.session.post(
            f"{self.credentials.url}/api/v1/{endpoint}",
            params={"informat": "json", "format": "json"},
            json=body,
            auth=(self.credentials.username, self.credentials.password),
            headers=self._headers(),
        )
        response.raise_for_status()
        return _json_or_text(response)

    def get_user(self, user_key: str | None = None, user_value: object | None = None) -> Any:
        endpoint_key, body = build_user_request(user_key, user_value)
        return self.post_v1(endpoint_key, body)

    def get_group(self) -> Any:
        endpoint_key, body = build_group_request()
        return self.post_v1(endpoint_key, body)

    def get_event(
        self,
        *,
        form: str,
        user_ids: list[int],
        date_range: tuple[str, str],
        time_range: tuple[str, str] = ("12:00 am", "11:59 pm"),
        data_filters: list[DataFilter] | None = None,
        events_per_user: int | None = None,
    ) -> Any:
        endpoint_key, body = build_event_export_request(
            form,
            user_ids,
            date_range,
            time_range=time_range,
            data_filters=data_filters,
            events_per_user=events_per_user,
        )
        return self.post_v1(endpoint_key, body)

    def get_profile(self, *, form: str, user_ids: list[int]) -> Any:
        endpoint_key, body = build_profile_export_request(form, user_ids)
        return self.post_v1(endpoint_key, body)

    def sync_event(self, *, form: str, user_ids: list[int], last_sync_time_on_server: int) -> Any:
        endpoint_key, body = build_sync_request(form, user_ids, last_sync_time_on_server)
        return self.post_v1(endpoint_key, body)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }


def _requests_session():
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Install the 'requests' package to use SmartabaseClient transport.") from exc
    return requests.Session()


def _json_or_text(response):
    try:
        return response.json()
    except ValueError:
        return response.text
