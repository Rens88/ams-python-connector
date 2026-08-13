# Current Work

This file is the current milestone and handoff note for coding agents. It should stay short and should not duplicate the long-term roadmap in [../docs/roadmap.md](../docs/roadmap.md).

## 001 Daily Data Pipeline (Implemented 2026-08-12)

The sibling `ams-sandbox-data-synthesis` repository now contains the stateful,
append-only daily pipeline described by `specs/002-daily-data-pipeline`.
Applicable connector aims are B2, B4, B6-B8, C1-C3, C5-C8, E1, E4, E6-E9,
F3, F5, F7, and F8; the highest risk remains **High** because a separate local
interactive command can insert sandbox events.

Implemented boundaries:

- deterministic date transitions with immutable hash-linked checkpoints,
  missing-date catch-up, stable IDs, weekly context, pending events, and
  effective-dated roster cutovers;
- one local CLI for WSV, KNLTB, or both, including read-only remote
  classification, immutable daily/master upload plans, status, and reporting;
- a protected-Volume/Delta Databricks adapter and a paused serverless
  prepare-only job; scheduled publication is deliberately absent; and
- interactive event-only publication with a fresh complete scope read, exact
  target/plan/hash checks, a real-TTY typed phrase, single-use authorization,
  no mutation retry, and exact read-only reconciliation.

Verification evidence:

- 47 daily-focused synthesis tests pass after final safety changes;
- the complete connector suite passes 147 tests with 1 opt-in live test skipped;
- the synthesis wheel and connector wheel build, the synthesis wheel contains
  all required root modules/package files and no state or credential files, and
  an external wheel-path import smoke test passes;
- CLI help, form-map JSON, Databricks YAML structural safeguards, Python
  compilation, task format/completion, and scoped `git diff --check` pass; and
- the full sibling synthesis suite runs 188 tests; 186 pass and two pre-existing
  refresh tests error because current ignored template/form-map fixtures do not
  match their assumptions. Neither failing test touches the new daily modules.

No live AMS request, mutation, Databricks bundle validation, deployment, or
schedule activation was performed. The first recommended next action is the
README's local WSV-yesterday `init`/`prepare --remote-check skip` smoke test,
followed by the read-only `--remote-check require` step under an authorized
operator account.

## Current Milestone

The next major workflow is a sandbox-safe synthetic-data pipeline:

1. Fetch athlete information so the system knows which athletes synthetic data should be generated for.
2. Generate synthetic data for those athletes.
3. Plan deletion of existing data for affected athletes and forms.
4. Delete only overlapping records or all targeted records in sandbox, depending on the selected mode.
5. Upload generated replacement data back into Smartabase.
6. Save enough run metadata to repeat, inspect, or roll forward safely.

If future code changes need more detail about the synthetic generator, deletion scope, form coverage, or required realism rules, ask the user before inventing behavior.

## Immediate Tasks

1. Add richer write-input semantics for nested Smartabase table fields.
2. Use the tracked nested-table CSV examples under [../docs/reference-data/smartabase-nested-table-examples](../docs/reference-data/smartabase-nested-table-examples/) as reference material.
3. Add automated opt-in coverage for the verified named-group sandbox
   initializer path. If `include_all_cols` needs tenant-specific verification,
   retain only an authorized redacted or structural fixture.
4. Add broader sandbox-safe orchestration that ties fetch, generate, delete, and upload together.
5. Add opt-in live integration tests for sandbox workflows.

## Resolved Questions And Answers

`Q1`: What does "table fields" mean for this project?

`A1`: A table field means one Smartabase event that contains a repeating internal table. For example, one gym-session event can contain multiple exercise rows such as squat, bench, and row. This is different from three separate Smartabase events.

`Q2`: What does duplicate event handling mean here?

`A2`: The duplicate concern is about write-batch rows with the same `form`, same `user_id`, same `start_date`, and possibly the same missing or blank `start_time`.

`Q3`: If two rows have the same `form`, `user_id`, and `start_date` but different useful `start_time` values, should they be separate events?

`A3`: Yes. Distinct useful start times, such as one training at `09:00` and another at `18:00`, should usually become separate Smartabase events.

`Q4`: Are the nested-table CSV exports secret?

`A4`: No. The CSV files in `tmp/smartabase-nested-table-examples` were confirmed as non-secret and important for future work. Tracked copies now belong under `docs/reference-data/smartabase-nested-table-examples/`.

## Unresolved Questions

- If rows have the same `form`, `user_id`, `start_date`, and no useful `start_time` difference, should they be separate events, grouped into one table-field event, or deduplicated?
- Should nested table input prefer explicit nested Python data such as `table_rows=[...]`, automatic grouping of flat CSV rows, or both?
- Which Smartabase forms should be generated first?
- Which athlete identifiers are authoritative for generation: `user_id`, `about`, username, email, federation number, or personal code?
- Should profile data be regenerated as part of the workflow, or only event forms?
- What output format should the synthetic generator consume and emit?
- How should overlapping date windows be defined for each form?

## Handoff Notes

Current implementation evidence indicates:

- `examples/replay_form_entries.py` exists for delete plus reinsert.
- `examples/delete_form_entries.py` exists for delete-only workflows.
- Both example workflows support sandbox-only `--delete-all-in-range`.
- Live delete/modify operations are blocked outside sandbox.
- Write inputs support `list[dict]`, CSV paths, and dataframe-like objects with `to_dict("records")`.
- Client write calls can optionally resolve missing `user_id` values from `username`, `email`, or `about`.
- Normalized roster helpers exist: `fetch_roster`, `flatten_roster_response`, and `resolve_user_ids`.
- Roster normalization handles the official two-level user response shape
  (`results` batches containing nested `results` user rows), retains flat
  response compatibility, and rejects mixed or malformed batches without
  logging response values.
- Event/profile normalization now applies the same fail-closed boundary to
  known flat collections and two-level search batches. It extracts only the
  nested event/profile records, preserves `rows -> pairs` flattening, and
  rejects mixed direct/batched, ambiguous, deeper-than-supported, or
  non-object shapes without including response values in errors.
- `initialize_sandbox_athletes` now provides a sandbox-only, read-only remote
  workflow that validates and atomically stages a stable six-column local
  athlete registry plus redacted metadata and optional groups.
- `ams-initialize-sandbox-athletes` and
  `python -m ams_smartabase.initializer` expose the same packaged CLI without a
  password argument or R runtime.
- The sibling synthesis repository's initializer is a thin wrapper around the
  installed connector, and its generator accepts the connector CSV contract
  without transformation. Its current local migration also replaces the
  fetch and upload/delete R bridges with direct Python connector calls; this
  broader migration has synthetic/offline test evidence only and still needs
  authorized sandbox verification before any live-behavior claim.
- Generalized planning/workflow helpers exist: `build_event_write_targets`, `plan_event_deletions`, and `run_event_replace_workflow`.
- Generic diagnostics now have a public, structured surface: canonical
  `DD/MM/YYYY` parsing, typed pre-transport validation errors, sanitized
  endpoint provenance and fallback warnings, strict exact-event-ID
  verification, and mutation assessment that does not confuse
  `SUCCESSFULLY_IMPORTED` with confirmed completion.
- Provider-versus-caller ownership and dated decisions are recorded in
  `docs/connector-caller-diagnostics-boundary.md`. The sibling Synthetic Data
  workflow consumes these public helpers while retaining its own source
  conversion, stage logging, previews, confirmations, and reconciliation.

Initializer verification on 2026-07-29:

- 66 focused initializer/config/client/endpoint/roster tests passed; the
  opt-in live test was skipped because no authorized live-test flag or
  named-group fixture was supplied.
- Editable installation worked from the sibling checkout.
- An isolated wheel exposed the same public initializer API and console entry
  point and contained no local credential or sandbox-state artifacts.
- The downstream compatibility suite passed 4/4 tests, including an end-to-end
  connector-export-to-generator check and repository-root default-path checks.
- The full connector suite ran 107 tests: 93 passed, 1 skipped, and 13
  pre-existing workflow tests errored because ignored local
  `use_case_examples/synthetic_data` fixtures are absent.

Roster response verification on 2026-08-05:

- A privacy-minimizing live probe confirmed a non-empty outer `results` batch
  without printing or retaining athlete values.
- The shape matches Teamworks' public `smartabaseR` user fixture, so an offline
  synthetic fixture now covers the nested response without committing live
  data.
- The 46 focused roster and initializer tests pass under both the repository's
  Windows virtual environment and the Linux Python environment.
- The sibling synthesis initializer compatibility suite passes 12/12 against
  the editable connector checkout.
- The full Linux suite ran 116 tests: 102 passed, 1 opt-in live test skipped,
  and the same 13 pre-existing workflow tests errored because the ignored
  `use_case_examples/synthetic_data/config.json` fixture is absent.
- An authorized manual named-group initializer rerun completed successfully
  without retaining raw response data. The automated opt-in test and
  `include_all_cols` live fixture remain pending.

Event/profile and downstream migration verification on 2026-08-05:

- Fourteen focused connector flattening tests passed for flat event/profile
  responses, two-level nested search batches, empty batches, and fail-closed
  malformed or mixed shapes.
- Three focused workflow tests passed for nested event-ID counting, strict
  non-lossy positive event-ID parsing, and rejection of mixed
  deletion-planning input.
- The sibling synthesis repository's 54 fetch and upload/delete workflow tests
  passed against the editable connector checkout; its full 72-test suite also
  passed. These tests use synthetic payloads and mocked connector operations;
  they did not call a live AMS site or authorize a live mutation.

Diagnostics-boundary verification on 2026-08-06:

- 63 focused connector tests passed, including canonical date errors with
  field/row context, sanitized endpoint fallback, exact event-ID fail-closed
  behavior, and accepted-versus-confirmed mutation classification.
- The sibling Synthetic Data fetch/sync/refresh suites passed 69 tests and 26
  subtests; its complete suite passed 87 tests and 47 subtests against the
  editable connector. No live AMS request was made.
- The full connector suite reached 129 passed and 1 skipped; the same 13 known
  ignored-fixture workflow tests failed because
  `use_case_examples/synthetic_data/config.json` is absent.

Run the current test suite again before claiming current verification.

Resolved local safety issue outside this connector worktree: the sibling
synthesis repository's legacy `test.R` and its reachable local history were
sanitized after the exposed password was rotated. Remote-host cleanup was not
verified from this connector work, so confirm the public repository separately
before relying on that status. Do not copy credential values into issues, logs,
or commits.

Deployment follow-up: the sibling environment was verified with an editable
connector install. Add an organization-approved release or commit pin before
expecting `pip install -r requirements.txt` to reproduce that dependency in CI
or on an independent machine.

## Recent Session Summary

2026-08-06:

- Replaced the workflow tests' dependency on ignored local
  `use_case_examples/synthetic_data` files with a committed, deterministic
  fixture pair under `tests/fixtures/workflow`.
- The fixture contains fictional test-only values and is passed explicitly to
  `load_example_event_workflow_input()`; the ignored operational example
  directory remains excluded from version control.
- The 13 previously known missing-fixture failures are resolved. All 21
  workflow tests pass, and the full connector suite passes 144 tests with the
  opt-in live test skipped. No live AMS request or mutation was performed.

2026-08-05:

- Corrected roster parsing for the official nested user-result batch shape.
- Kept identity extraction shallow so query selectors and nested group/role
  `id` or `name` fields cannot be mistaken for athlete identity.
- Added fail-closed synthetic regression tests and existing-registry
  preservation coverage; no raw live response was stored.
- Confirmed an authorized manual named-group initializer run succeeds with the
  nested parser fix; the output values and group name were not recorded here.
- Added strict event/profile parsing for supported flat collections and nested
  search-result batches, with fail-closed handling for malformed, mixed, or
  ambiguous shapes.
- Recorded the sibling synthesis repository's in-progress native Python
  fetch/upload/delete migration. Offline tests pass; no live event/profile
  fetch, upload, or delete validation was performed as part of that migration.

2026-07-29:

- Implemented the Python-only sandbox athlete initializer plan under aims
  `A1`, `A3`-`A5`, `B6`-`B9`, `E1`-`E10`, and `F1`-`F8`; highest applicable
  risk was Medium because the remote operation is read-only but the local
  athlete export contains sensitive data and replaces files.
- Added path-aware credentials, fail-closed v1 RPC errors, deterministic roster
  and group serialization, generator-compatible validation, staged output,
  public API/CLI packaging, offline tests, an opt-in live test, and safety
  documentation.
- Migrated the sibling synthesis initializer away from R while leaving its
  separate legacy fetch/upload/delete R workflows unchanged.

2026-07-27:

- Formalized `.specify/memory/constitution.md` as v1.0.0 with durable AMS Python Connector governance principles only.
- Propagated constitution gates into Spec Kit plan, spec, and task templates.
- Updated local `speckit-specify` and `speckit-tasks` skill guidance so generated artifacts align with governance constraints.
- No Python source code was changed. `git diff --check` passed.
