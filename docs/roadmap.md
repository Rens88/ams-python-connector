# Roadmap

This is the authoritative progress tracker for the aims in [PROJECT_AIMS.md](../PROJECT_AIMS.md).

Statuses used here:

- `Not started`
- `Planned`
- `In progress`
- `Partial`
- `Implemented`
- `Verified`

`Verified` is reserved for aims with adequate automated evidence or documented sandbox-test evidence. When evidence is incomplete, the status should remain lower even if code appears to exist.

## Aim Progress

| Aim ID | Short description | Current status | Implementation evidence | Remaining work |
|---|---|---|---|---|
| `A1` | Athlete and group discovery | `Partial` | `SmartabaseClient.get_user`, `SmartabaseClient.get_group`, `fetch_roster`, `flatten_roster_response`, and unit tests in `tests/test_roster.py`, `tests/test_client.py`, and `tests/test_filters.py`. | Expand live read-only examples, confirm tenant-specific roster payload shapes, and document output fields. |
| `A2` | Form and dataset discovery | `Planned` | Endpoint discovery exists through `SmartabaseClient.discover_endpoints`, but repository evidence does not show dedicated form/dataset terminology helpers. | Identify supported AMS endpoints for form/dataset metadata, implement read-only helpers, and add examples. |
| `A3` | Terminology usability | `Partial` | Roster normalization returns structured `RosterEntry` objects; response flattening helpers exist. | Normalize form/dataset metadata once discovery helpers exist, and document which identifiers downstream calls require. |
| `A4` | Discovery examples | `Partial` | `examples/smoke_test_connection.py` supports endpoint discovery and group listing. | Add explicit athlete, group, form, dataset, and field inspection examples. |
| `B1` | Single-athlete single-form pull | `Partial` | `SmartabaseClient.get_event`, `SmartabaseClient.get_profile`, event/profile request builders, flattening helpers, and unit tests exist. | Add clearer user-facing examples and opt-in live sandbox verification. |
| `B2` | Multi-athlete multi-form pull | `Partial` | Event/profile methods accept multiple user IDs for a single form; generalized workflows exist for event targets. | Add planned orchestration for multiple forms and multiple athletes in one pull workflow. |
| `B3` | Event and profile exports | `Partial` | `get_event`, `get_profile`, `build_event_export_request`, `build_profile_export_request`, `flatten_event_response`, and `flatten_profile_response` exist. | Confirm live profile/event behavior against sandbox and document limitations. |
| `B4` | Fetch filters | `Partial` | Date range, time range, user IDs, data filters, and `events_per_user` request construction are covered by `src/ams_smartabase/filters.py` and tests. | Add group-to-fetch orchestration and broader examples. |
| `B5` | Analysis-ready output | `Partial` | Flattening helpers exist for event and profile responses. | Ensure lossless raw response preservation in pull workflows and document tabular output conventions. |
| `B6` | Pull auditability | `Partial` | Manifest writers and workflow artifacts exist for example workflows. | Extend audit manifests to general pull workflows, not only replay/delete/upload workflows. |
| `C1` | Common write inputs | `Implemented` | `coerce_records_input` accepts mappings, CSV paths, and dataframe-like objects; unit tests cover these shapes. | Keep behavior documented and add richer user examples. |
| `C2` | Athlete identifier resolution | `Implemented` | `resolve_user_ids` and `SmartabaseClient` write-call integration exist; unit tests cover username, email, and `about` resolution. | Add user-facing examples and live read-only verification. |
| `C3` | Safe upload execution | `Implemented` | Client write methods default to `dry_run=True`, require `confirm=True` for live execution, block live mutation outside sandbox, and have unit tests. | Add documented sandbox execution checklist and live integration coverage. |
| `C4` | Upload examples | `Partial` | README and replay examples show event insertion through workflows. | Add standalone examples for one form, multiple forms, and multiple athletes. |
| `D1` | Update and upsert workflows | `Implemented` | `update_event`, `upsert_event`, `upsert_profile`, payload builders, dry-run/confirm gates, and unit tests exist. | Add live sandbox integration tests and more examples. |
| `D2` | Exact-ID deletion | `Implemented` | `delete_event` and `build_delete_payloads` delete by explicit event IDs; workflow preflight extracts event IDs before deletion. | Add clearer documentation around event ID provenance and review expectations. |
| `D3` | Sandbox batch deletion | `Implemented` | Example workflows support `delete_all_in_range` and tests cover sandbox-only behavior. | Keep sandbox-only behavior prominent and add opt-in live sandbox tests. |
| `D4` | Production deletion restriction | `Implemented` | Client and workflow guards block live delete/modify operations outside URLs containing `sandbox`; tests cover the guard. | Require explicit design review before any production mutation policy change. |
| `D5` | Mutation auditability | `Partial` | Operation folders, manifests, payload artifacts, raw JSON summaries, and workflow summaries exist. | Standardize artifacts for all mutation workflows and document retention/redaction expectations. |
| `E1` | Human setup documentation | `Partial` | README includes setup, quick start, credentials, and library-use guidance. | Expand terminology and troubleshooting documentation. |
| `E2` | Usage examples | `Partial` | Smoke test, replay, and delete examples exist. | Add discovery, pull, standalone upload, multi-athlete, and multi-form examples. |
| `E3` | Terminology documentation | `Planned` | Current documents mention key terms but do not provide a dedicated terminology guide. | Add a terminology section or document covering athletes, groups, forms, datasets, event IDs, user IDs, and fields. |
| `E4` | Safety documentation | `Implemented` | README, constitution, contributing guide, implementation guidance, and PR template cover destructive-operation safety. | Keep safety guidance synchronized as workflows evolve. |
| `E5` | Maintainer handoff documentation | `Implemented` | `agent-docs/README.md`, `agent-docs/current-work.md`, `agent-docs/implementation-guidance.md`, and this roadmap separate ownership. | Keep current work short and avoid duplicating this roadmap. |
| `F1` | Installable package | `Partial` | `pyproject.toml` exists and README documents editable and regular local install. Prior docs noted manual external-consumer validation. | Add automated packaging or external-consumer integration checks. |
| `F2` | Stable import surface | `Partial` | README documents distribution name `ams-python-connector` and import package `ams_smartabase`. | Decide and document the intentionally supported public API surface. |
| `F3` | Library-first examples | `Partial` | Example scripts call reusable library functions rather than carrying all logic inline. | Continue moving reusable behavior into package modules as workflows broaden. |

## Provisional Or Requiring Verification

- Form and dataset terminology support needs API confirmation before implementation status can be raised.
- Multi-form pull orchestration needs implementation evidence beyond single-form methods accepting multiple user IDs.
- Live sandbox verification is still incomplete for read, write, update, upsert, delete, and full fetch-delete-upload workflows.
