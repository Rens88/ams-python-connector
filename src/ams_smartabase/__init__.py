"""Python client utilities for Teamworks AMS/Smartabase."""

from .client import OperationExecution, SmartabaseClient
from .config import SmartabaseCredentials, load_credentials, normalize_url
from .endpoints import DEFAULT_ENDPOINTS, EndpointMap
from .filters import (
    DATA_CONDITION_CODES,
    DataFilter,
    build_event_export_request,
    build_group_request,
    build_profile_export_request,
    build_sync_request,
    build_user_request,
    sb_date_range,
)
from .flatten import flatten_event_response, flatten_profile_response
from .workflow import (
    DEFAULT_EXAMPLE_CONFIG,
    DEFAULT_EXAMPLE_CSV,
    EventCountResult,
    EventWriteTarget,
    ExampleEventWorkflowInput,
    build_event_write_targets,
    count_event_entries,
    run_event_delete_workflow,
    load_example_event_workflow_input,
    plan_event_deletions,
    run_example_event_delete,
    run_event_replay_workflow,
    run_event_replace_workflow,
    run_example_event_replay,
)
from .payloads import (
    PayloadPackage,
    build_delete_payloads,
    build_event_import_payloads,
    build_profile_upsert_payloads,
    coerce_records_input,
    select_metadata,
    suggest_nested_table_candidates,
)
from .roster import RosterEntry, fetch_roster, flatten_roster_response, resolve_user_ids
from .smoke_test import run_smoke_test

__all__ = [
    "AthleteInitializationResult",
    "DATA_CONDITION_CODES",
    "DEFAULT_ENDPOINTS",
    "DEFAULT_EXAMPLE_CONFIG",
    "DEFAULT_EXAMPLE_CSV",
    "DataFilter",
    "EndpointMap",
    "EventCountResult",
    "EventWriteTarget",
    "ExampleEventWorkflowInput",
    "OperationExecution",
    "PayloadPackage",
    "RosterEntry",
    "SmartabaseClient",
    "SmartabaseCredentials",
    "build_delete_payloads",
    "build_event_export_request",
    "build_event_import_payloads",
    "build_event_write_targets",
    "build_group_request",
    "build_profile_export_request",
    "build_profile_upsert_payloads",
    "coerce_records_input",
    "build_sync_request",
    "build_user_request",
    "count_event_entries",
    "flatten_event_response",
    "flatten_profile_response",
    "flatten_roster_response",
    "initialize_sandbox_athletes",
    "load_example_event_workflow_input",
    "load_credentials",
    "normalize_url",
    "plan_event_deletions",
    "fetch_roster",
    "resolve_user_ids",
    "run_event_delete_workflow",
    "run_example_event_delete",
    "run_event_replay_workflow",
    "run_event_replace_workflow",
    "run_example_event_replay",
    "run_smoke_test",
    "sb_date_range",
    "select_metadata",
    "suggest_nested_table_candidates",
]


def __getattr__(name: str) -> object:
    """Lazily expose initializer APIs without preloading its CLI module."""

    if name in {"AthleteInitializationResult", "initialize_sandbox_athletes"}:
        from .initializer import (
            AthleteInitializationResult,
            initialize_sandbox_athletes,
        )

        return {
            "AthleteInitializationResult": AthleteInitializationResult,
            "initialize_sandbox_athletes": initialize_sandbox_athletes,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
