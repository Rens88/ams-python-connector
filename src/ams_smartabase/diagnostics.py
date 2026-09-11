"""Stable, structured diagnostics shared by connector entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Iterable, Mapping
import warnings

from .endpoints import DEFAULT_ENDPOINTS


EXACT_EVENT_ID_KEYS = ("event_id", "eventId", "existingEventId")
EXACT_EVENT_ID_LIST_KEYS = ("ids",)
SUCCESS_STATUSES = {
    "ok",
    "success",
    "succeeded",
    "complete",
    "completed",
    "deleted",
    "inserted",
    "imported",
}
SUCCESS_COUNT_KEYS = (
    "success_count",
    "successCount",
    "inserted",
    "imported",
    "deleted_count",
    "deletedCount",
)
DELETE_SUCCESS_MESSAGE_RE = re.compile(r"Deleted ([1-9]\d*)", re.IGNORECASE)


class MutationState(str, Enum):
    """What the connector can safely claim about a mutation attempt."""

    NO_REQUEST_SENT = "no_request_sent"
    REQUEST_STARTED = "request_started"
    ACCEPTED_UNVERIFIED = "accepted_unverified"
    CONFIRMED_COMPLETE = "confirmed_complete"
    PARTIAL_OR_UNKNOWN = "partial_or_unknown"


class AMSConnectorError(Exception):
    """Base class for public connector errors with machine-readable context."""

    default_code = "ams_connector_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        field: str | None = None,
        row_index: int | None = None,
        expected: str | None = None,
        mutation_state: MutationState = MutationState.NO_REQUEST_SENT,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        Exception.__init__(self, message)
        self.code = code or self.default_code
        self.field = field
        self.row_index = row_index
        self.expected = expected
        self.mutation_state = mutation_state
        self.details = dict(details or {})

    @property
    def request_sent(self) -> bool:
        return self.mutation_state is not MutationState.NO_REQUEST_SENT

    def as_dict(self) -> dict[str, Any]:
        """Return non-secret diagnostic metadata suitable for caller logging."""

        result: dict[str, Any] = {
            "type": type(self).__name__,
            "code": self.code,
            "message": str(self),
            "mutation_state": self.mutation_state.value,
            "request_sent": self.request_sent,
        }
        if self.field is not None:
            result["field"] = self.field
        if self.row_index is not None:
            result["row_index"] = self.row_index
        if self.expected is not None:
            result["expected"] = self.expected
        if self.details:
            result["details"] = dict(self.details)
        return result


class AMSInputValidationError(AMSConnectorError, ValueError):
    """A caller supplied input that does not satisfy the generic AMS contract."""

    default_code = "invalid_input"


class AMSDateFormatError(AMSInputValidationError):
    """An AMS date value was neither a date object nor canonical day-first text."""

    default_code = "invalid_date_format"


class AMSResponseShapeError(AMSConnectorError, ValueError):
    """AMS returned a response shape that cannot be interpreted safely."""

    default_code = "invalid_response_shape"


class AMSEventIdUnavailableError(AMSResponseShapeError):
    """A non-empty event response does not provide verified exact event IDs."""

    default_code = "exact_event_id_unavailable"


class AMSEndpointFallbackWarning(RuntimeWarning):
    """Endpoint discovery was incomplete and known connector defaults are used."""


@dataclass(frozen=True)
class EndpointProvenance:
    """Non-secret evidence describing discovered versus default endpoints."""

    source: str
    discovered_aliases: tuple[str, ...]
    defaulted_aliases: tuple[str, ...]
    error_type: str | None = None
    warning_message: str | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "source": self.source,
            "discovered_aliases": list(self.discovered_aliases),
            "defaulted_aliases": list(self.defaulted_aliases),
        }
        if self.error_type is not None:
            result["error_type"] = self.error_type
        return result


@dataclass(frozen=True)
class MutationAssessment:
    """Sanitized interpretation of a connector mutation execution."""

    state: MutationState
    confirmed: bool
    reason_code: str
    response_count: int
    event_ids: tuple[int, ...] = ()
    acceptance_states: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "mutation_state": self.state.value,
            "confirmed": self.confirmed,
            "reason_code": self.reason_code,
            "response_count": self.response_count,
            "event_ids": list(self.event_ids),
        }
        if self.acceptance_states:
            result["smartabase_acceptance_states"] = list(self.acceptance_states)
        if self.state is MutationState.ACCEPTED_UNVERIFIED:
            result["accepted_unverified"] = True
        return result


def discover_endpoint_provenance(
    client: object,
    *,
    required_aliases: Iterable[str] | None = None,
    emit_warning: bool = True,
    warning_stacklevel: int = 3,
) -> EndpointProvenance:
    """Discover endpoints and return sanitized fallback provenance.

    The caller is responsible for authentication and for deciding whether its
    workflow may continue. Private exception messages are deliberately omitted.
    """

    required = set(DEFAULT_ENDPOINTS if required_aliases is None else required_aliases)
    try:
        endpoint_map = client.discover_endpoints()  # type: ignore[attr-defined]
    except Exception as exc:
        message = (
            "Smartabase endpoint discovery failed "
            f"({type(exc).__name__}); using the connector's known default endpoints. "
            "Suggested solution: verify that the credentials and site permit endpoint "
            "discovery. The caller should report which workflow stage uses the fallback."
        )
        _emit_endpoint_warning(message, emit_warning, warning_stacklevel)
        return EndpointProvenance(
            source="defaults",
            discovered_aliases=(),
            defaulted_aliases=tuple(sorted(required)),
            error_type=type(exc).__name__,
            warning_message=message,
        )

    discovered = set(getattr(endpoint_map, "discovered_aliases", set()))
    missing = required - discovered
    if missing:
        message = (
            "Smartabase endpoint discovery did not return every required alias; using "
            "known default endpoints for the missing aliases. Suggested solution: verify "
            "the discovered endpoint permissions before relying on tenant-specific aliases."
        )
        _emit_endpoint_warning(message, emit_warning, warning_stacklevel)
        return EndpointProvenance(
            source="partial" if discovered else "defaults",
            discovered_aliases=tuple(sorted(discovered)),
            defaulted_aliases=tuple(sorted(missing)),
            warning_message=message,
        )

    return EndpointProvenance(
        source="discovered",
        discovered_aliases=tuple(sorted(discovered)),
        defaulted_aliases=(),
    )


def assess_operation_execution(
    execution: object,
    *,
    expected_count: int,
    operation: str,
    expected_event_id: int | None = None,
) -> MutationAssessment:
    """Classify a mutation without overstating accepted or unknown responses."""

    responses = list(getattr(execution, "responses", []))
    response_count = len(responses)
    event_ids = tuple(_extract_event_ids(responses))
    if operation == "delete_event":
        # AMS' delete endpoint can confirm the exact deleted ID only in a
        # message such as ``{"message": "Deleted 123"}``. Keep this strict and
        # delete-specific: interpreting arbitrary response text as an event ID
        # would weaken exact-ID deletion validation.
        event_ids = tuple(
            sorted(set(event_ids).union(_extract_delete_success_event_ids(responses)))
        )
    acceptance_states = tuple(
        state
        for response in responses
        if (state := smartabase_acceptance_state(response)) is not None
    )

    dry_run = bool(getattr(execution, "dry_run", False))
    executed = bool(getattr(execution, "executed", False))
    attempted_count = getattr(execution, "attempted_count", None)
    if dry_run or not executed:
        return MutationAssessment(
            MutationState.NO_REQUEST_SENT,
            False,
            "no_request_sent",
            response_count,
            event_ids,
            acceptance_states,
        )
    if attempted_count != expected_count:
        return MutationAssessment(
            MutationState.PARTIAL_OR_UNKNOWN,
            False,
            "attempted_count_mismatch",
            response_count,
            event_ids,
            acceptance_states,
        )

    expected_responses = expected_count if operation == "upsert_profile" else 1
    if response_count != expected_responses:
        return MutationAssessment(
            MutationState.PARTIAL_OR_UNKNOWN,
            False,
            "response_count_mismatch",
            response_count,
            event_ids,
            acceptance_states,
        )
    if not all(
        response_confirms_success(response, expected_count, operation)
        for response in responses
    ):
        return MutationAssessment(
            MutationState.PARTIAL_OR_UNKNOWN,
            False,
            "unrecognized_or_error_response",
            response_count,
            event_ids,
            acceptance_states,
        )
    if operation == "delete_event" and (
        expected_event_id is None or event_ids != (expected_event_id,)
    ):
        return MutationAssessment(
            MutationState.PARTIAL_OR_UNKNOWN,
            False,
            "delete_event_id_mismatch",
            response_count,
            event_ids,
            acceptance_states,
        )

    if operation == "insert_event":
        has_matching_count = any(
            _response_has_matching_success_count(response, expected_count, operation)
            for response in responses
        )
        if acceptance_states and not has_matching_count and len(event_ids) != expected_count:
            return MutationAssessment(
                MutationState.ACCEPTED_UNVERIFIED,
                False,
                "accepted_without_authoritative_count",
                response_count,
                event_ids,
                acceptance_states,
            )
        if expected_count > 1 and (
            (event_ids and len(event_ids) != expected_count)
            or (not has_matching_count and len(event_ids) != expected_count)
        ):
            return MutationAssessment(
                MutationState.PARTIAL_OR_UNKNOWN,
                False,
                "insert_count_unverified",
                response_count,
                event_ids,
                acceptance_states,
            )

    return MutationAssessment(
        MutationState.CONFIRMED_COMPLETE,
        True,
        "confirmed_complete",
        response_count,
        event_ids,
        acceptance_states,
    )


def response_confirms_success(response: object, expected_count: int, operation: str) -> bool:
    """Return whether one AMS mutation response contains consistent success evidence."""

    if isinstance(response, str):
        return (
            response.strip().casefold() in SUCCESS_STATUSES
            or smartabase_acceptance_state(response) is not None
            or (
                operation == "delete_event"
                and _delete_success_event_id(response) is not None
            )
        )
    if not isinstance(response, Mapping) or response.get("__is_rpc_exception__"):
        return False
    if _response_has_error(response):
        return False
    status = str(
        response.get("status") or response.get("result") or response.get("message") or ""
    ).strip().casefold()
    if (
        status not in SUCCESS_STATUSES
        and response.get("success") is not True
        and smartabase_acceptance_state(response) is None
        and not (
            operation == "delete_event"
            and _delete_success_event_id(response) is not None
        )
    ):
        return False
    expected = 1 if operation in {"delete_event", "upsert_profile"} else expected_count
    for key in SUCCESS_COUNT_KEYS:
        if key in response and _response_count(response[key]) != expected:
            return False
    return True


def smartabase_acceptance_state(response: object, *, _depth: int = 0) -> str | None:
    """Return a verified non-final AMS acceptance state from nested response data."""

    if _depth > 3:
        return None
    if isinstance(response, Mapping):
        if response.get("__is_rpc_exception__") or _response_has_error(response):
            return None
        for key in ("state", "status", "result", "message"):
            if key in response:
                state = smartabase_acceptance_state(response[key], _depth=_depth + 1)
                if state is not None:
                    return state
        return None
    if not isinstance(response, str):
        return None
    text = response.strip()
    normalized = text.casefold()
    if normalized == "successfully_imported":
        return "SUCCESSFULLY_IMPORTED"
    if normalized == "success":
        return "SUCCESS"
    if text[:1] not in {"{", "[", '"'}:
        return None
    try:
        nested = json.loads(text)
    except json.JSONDecodeError:
        return None
    return smartabase_acceptance_state(nested, _depth=_depth + 1)


def _response_has_error(response: Mapping[object, object]) -> bool:
    return any(
        response.get(key) not in (None, "", [], {}, 0, False)
        for key in ("error", "errors", "exception", "failed", "failure")
    )


def _response_has_matching_success_count(
    response: object,
    expected_count: int,
    operation: str,
) -> bool:
    if not isinstance(response, Mapping):
        return False
    expected = 1 if operation in {"delete_event", "upsert_profile"} else expected_count
    return any(
        key in response and _response_count(response[key]) == expected
        for key in SUCCESS_COUNT_KEYS
    )


def _response_count(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        return int(value.strip())
    return None


def _extract_event_ids(value: object) -> list[int]:
    found: set[int] = set()

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if str(key) in EXACT_EVENT_ID_KEYS:
                    event_id = _response_count(nested)
                    if event_id is not None and event_id > 0:
                        found.add(event_id)
                elif str(key) in EXACT_EVENT_ID_LIST_KEYS and isinstance(nested, list):
                    # Smartabase eventsimport success responses return new IDs as a
                    # plain list under "ids" rather than under EXACT_EVENT_ID_KEYS.
                    for candidate in nested:
                        event_id = _response_count(candidate)
                        if event_id is not None and event_id > 0:
                            found.add(event_id)
                else:
                    visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return sorted(found)


def _extract_delete_success_event_ids(value: object) -> list[int]:
    """Extract IDs only from the verified delete-endpoint success message."""

    found: set[int] = set()

    def visit(item: object) -> None:
        event_id = _delete_success_event_id(item)
        if event_id is not None:
            found.add(event_id)
        if isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return sorted(found)


def _delete_success_event_id(response: object) -> int | None:
    if isinstance(response, Mapping):
        if response.get("__is_rpc_exception__") or _response_has_error(response):
            return None
        message = response.get("message")
    else:
        message = response
    if not isinstance(message, str):
        return None
    match = DELETE_SUCCESS_MESSAGE_RE.fullmatch(message.strip())
    return int(match.group(1)) if match is not None else None


def _emit_endpoint_warning(message: str, enabled: bool, stacklevel: int) -> None:
    if enabled:
        warnings.warn(
            message,
            AMSEndpointFallbackWarning,
            stacklevel=stacklevel,
        )
