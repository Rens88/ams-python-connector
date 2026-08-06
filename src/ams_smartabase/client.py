"""Small Smartabase HTTP client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .config import DEFAULT_USER_AGENT, SmartabaseCredentials
from .diagnostics import MutationState
from .endpoints import EndpointMap
from .filters import (
    DataFilter,
    build_event_export_request,
    build_group_request,
    build_profile_export_request,
    build_sync_request,
    build_user_request,
)
from .payloads import (
    PayloadPackage,
    build_delete_payloads,
    build_event_import_payloads,
    build_profile_upsert_payloads,
)


@dataclass(frozen=True)
class OperationExecution:
    endpoint: str
    attempted_count: int
    dry_run: bool
    executed: bool
    body: object
    row_operations: list[dict[str, object]]
    responses: list[Any]

    @property
    def mutation_state(self) -> MutationState:
        """Return the strongest generic claim available from transport state."""

        return (
            MutationState.REQUEST_STARTED
            if self.executed
            else MutationState.NO_REQUEST_SENT
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
        self.session = session
        self.endpoints = endpoints or EndpointMap()
        self.user_agent = user_agent
        self.login_result: Any | None = None
        self.session_header = ""

    def login(self) -> Any:
        response = self._session().post(
            f"{self.credentials.url}/api/v2/user/loginUser",
            json=self.login_body(),
            auth=(self.credentials.username, self.credentials.password),
            headers=self._headers(),
        )
        response.raise_for_status()
        self.session_header = response.headers.get("session-header", "")
        payload = _json_or_text(response)
        if isinstance(payload, dict):
            payload = dict(payload)
            if self.session_header:
                payload.setdefault("session_header", self.session_header)
            cookie_header = response.headers.get("Set-Cookie", "")
            if cookie_header:
                payload.setdefault("cookie", cookie_header)
            _raise_for_rpc_exception(payload)
        self.login_result = payload
        return payload

    def login_body(self) -> dict[str, object]:
        return {
            "username": self.credentials.username,
            "password": self.credentials.password,
            "loginProperties": {
                "appName": _smartabase_app_name(self.credentials.url),
                "clientTime": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M"),
            },
        }

    def discover_endpoints(self) -> EndpointMap:
        if not self.session_header:
            self.login()
        response = self._session().get(
            f"{self.credentials.url}/api/v3/endpoints",
            params={"version": "v1"},
            auth=(self.credentials.username, self.credentials.password),
            headers=self._headers(include_session=True),
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            _raise_for_rpc_exception(payload)
        self.endpoints = EndpointMap.from_discovery(payload)
        return self.endpoints

    def post_v1(self, endpoint_key: str, body: dict[str, object] | list[object]) -> Any:
        endpoint = self.endpoints.resolve(endpoint_key)
        response = self._session().post(
            f"{self.credentials.url}/api/v1/{endpoint}",
            params={"informat": "json", "format": "json"},
            json=body,
            auth=(self.credentials.username, self.credentials.password),
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = _json_or_text(response)
        if isinstance(payload, dict):
            _raise_for_rpc_exception(payload)
        return payload

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

    def insert_event(
        self,
        records: object,
        *,
        form: str | None = None,
        entered_by_user_id: int | None = None,
        nested_table_identifiers: dict[str, list[str]] | list[str] | None = None,
        resolve_user_ids: bool = False,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> OperationExecution:
        prepared_records = self._prepare_write_records(records, resolve_user_ids=resolve_user_ids)
        package = build_event_import_payloads(
            prepared_records,
            form=form,
            mode="insert",
            entered_by_user_id=entered_by_user_id,
            nested_table_identifiers=nested_table_identifiers,
        )
        return self._execute_payload_package(package, dry_run=dry_run, confirm=confirm)

    def update_event(
        self,
        records: object,
        *,
        form: str | None = None,
        entered_by_user_id: int | None = None,
        nested_table_identifiers: dict[str, list[str]] | list[str] | None = None,
        resolve_user_ids: bool = False,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> OperationExecution:
        prepared_records = self._prepare_write_records(records, resolve_user_ids=resolve_user_ids)
        package = build_event_import_payloads(
            prepared_records,
            form=form,
            mode="update",
            entered_by_user_id=entered_by_user_id,
            nested_table_identifiers=nested_table_identifiers,
        )
        return self._execute_payload_package(package, dry_run=dry_run, confirm=confirm)

    def upsert_event(
        self,
        records: object,
        *,
        form: str | None = None,
        entered_by_user_id: int | None = None,
        nested_table_identifiers: dict[str, list[str]] | list[str] | None = None,
        resolve_user_ids: bool = False,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> OperationExecution:
        prepared_records = self._prepare_write_records(records, resolve_user_ids=resolve_user_ids)
        package = build_event_import_payloads(
            prepared_records,
            form=form,
            mode="upsert",
            entered_by_user_id=entered_by_user_id,
            nested_table_identifiers=nested_table_identifiers,
        )
        return self._execute_payload_package(package, dry_run=dry_run, confirm=confirm)

    def upsert_profile(
        self,
        records: object,
        *,
        form: str | None = None,
        entered_by_user_id: int | None = None,
        resolve_user_ids: bool = False,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> OperationExecution:
        prepared_records = self._prepare_write_records(records, resolve_user_ids=resolve_user_ids)
        package = build_profile_upsert_payloads(
            prepared_records,
            form=form,
            entered_by_user_id=entered_by_user_id,
        )
        return self._execute_payload_package(package, dry_run=dry_run, confirm=confirm)

    def delete_event(
        self,
        event_ids: list[int | str],
        *,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> OperationExecution:
        package = build_delete_payloads(event_ids)
        return self._execute_payload_package(package, dry_run=dry_run, confirm=confirm)

    def _headers(self, *, include_session: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
            "X-GWT-Permutation": "HostedMode",
        }
        if include_session and self.session_header:
            headers["session-header"] = self.session_header
            headers["Cookie"] = f"JSESSIONID={self.session_header}"
        return headers

    def _session(self) -> Any:
        if self.session is None:
            self.session = _requests_session()
        return self.session

    def _prepare_write_records(self, records: object, *, resolve_user_ids: bool) -> object:
        if not resolve_user_ids:
            return records
        from .roster import resolve_user_ids as resolve_roster_user_ids

        return resolve_roster_user_ids(self, records)

    def _execute_payload_package(
        self,
        package: PayloadPackage,
        *,
        dry_run: bool,
        confirm: bool,
    ) -> OperationExecution:
        if dry_run:
            return OperationExecution(
                endpoint=package.endpoint,
                attempted_count=package.attempted_count,
                dry_run=True,
                executed=False,
                body=package.body,
                row_operations=package.row_operations,
                responses=[],
            )
        self._ensure_live_mutation_allowed()
        if not confirm:
            raise ValueError("confirm=True is required when dry_run=False.")

        responses: list[Any] = []
        if isinstance(package.body, list):
            for item in package.body:
                responses.append(self.post_v1(package.endpoint, item))
        else:
            responses.append(self.post_v1(package.endpoint, package.body))

        return OperationExecution(
            endpoint=package.endpoint,
            attempted_count=package.attempted_count,
            dry_run=False,
            executed=True,
            body=package.body,
            row_operations=package.row_operations,
            responses=responses,
        )

    def _ensure_live_mutation_allowed(self) -> None:
        if "sandbox" in self.credentials.url.lower():
            return
        raise PermissionError(
            "Live delete/modify operations are restricted to Smartabase sandbox sites. "
            "Run this workflow in dry-run mode or obtain authorization before continuing."
        )


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


def _raise_for_rpc_exception(payload: dict[str, Any]) -> None:
    if not payload.get("__is_rpc_exception__"):
        return
    value = payload.get("value")
    if isinstance(value, dict):
        detail = value.get("detailMessage")
        if detail:
            raise RuntimeError(str(detail))
    raise RuntimeError("Smartabase API returned an RPC exception.")


def _smartabase_app_name(url: str) -> str:
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if path_parts:
        return path_parts[-1]
    return parsed.netloc
