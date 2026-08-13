# Tasks: Incremental Synthetic Data Pipeline

**Input**: Design documents under `specs/001-daily-data-pipeline/`
**Implementation repository**: `../ams-sandbox-data-synthesis`

## Phase 1: Setup

- [X] T001 Add installable synthesis package metadata and console entry point in `../ams-sandbox-data-synthesis/pyproject.toml` and `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/__init__.py`
- [X] T002 Add daily dataset, staging, plan, audit, build, and Databricks artifact exclusions in `../ams-sandbox-data-synthesis/.gitignore`
- [X] T003 Record the lightweight-daily versus periodic-Plotly reporting policy before changing runtime behavior in `../ams-sandbox-data-synthesis/project_requirements.md` and `../ams-sandbox-data-synthesis/agents.md`

## Phase 2: Foundational Models And Storage

- [X] T004 [P] Add offline canonical-hash, schema-validation, and state-transition tests in `../ams-sandbox-data-synthesis/tests/test_daily_models.py`
- [X] T005 Implement versioned dataset, athlete profile/state, checkpoint, daily manifest, and publication models in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/models.py`
- [X] T006 [P] Add crash, immutable-commit, corruption, no-op, and lock-contention tests in `../ams-sandbox-data-synthesis/tests/test_daily_storage.py`
- [X] T007 Implement the portable store protocol and locked filesystem store in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/storage.py`
- [X] T008 Add optional Unity Catalog Volume plus injected Delta-ledger coordination in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/databricks.py`

## Phase 3: User Story 1 — Fill Missing Dates With Longitudinal Data (P1)

**Goal**: Generate each causally missing date once and carry explicit athlete history.

**Independent test**: One 90-day call and 90 serialized one-day calls have identical daily manifests and ending checkpoints.

- [X] T009 [P] [US1] Add daily-vs-range, restart, deterministic-ID, week-boundary, pending-event, complaint, fatigue, and seasonal-phase tests in `../ams-sandbox-data-synthesis/tests/test_daily_engine.py`
- [X] T010 [US1] Implement stable athlete profiles, SHA-256 RNG streams, absolute phase, daily generation transitions, weekly context, and pending events in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/engine.py`
- [X] T011 [P] [US1] Add missing-date, no-op, target-before-head, backlog-bound, crash-recovery, and corrupt-chain tests in `../ams-sandbox-data-synthesis/tests/test_daily_orchestration.py`
- [X] T012 [US1] Implement chronological catch-up, validation, daily CSV rendering, and immutable commits in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/orchestration.py`
- [X] T013 [P] [US1] Add `init`, `prepare`, and `status` CLI contract tests including `wsv`, `knltb`, and `both` in `../ams-sandbox-data-synthesis/tests/test_daily_cli.py`
- [X] T014 [US1] Implement `init`, local-only `prepare`, and `status` commands in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/cli.py`
- [X] T015 [US1] Add a repository-root compatibility launcher in `../ams-sandbox-data-synthesis/daily_sandbox_pipeline.py`

## Phase 4: User Story 2 — Run The Same Workflow Locally Or On A Schedule (P2)

**Goal**: Use the same CLI/library contract against local storage and Databricks persistence, with scheduled runs unable to mutate AMS.

**Independent test**: Identical initial inputs in local and Volume-like stores produce identical deterministic manifests; non-interactive mode makes zero mutation calls.

- [X] T016 [P] [US2] Add local/Volume-store equivalence, secret-provider, and non-interactive zero-mutation tests in `../ams-sandbox-data-synthesis/tests/test_daily_databricks.py`
- [X] T017 [US2] Add a Databricks in-memory credential-provider adapter without `.env` persistence in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/credentials.py`
- [X] T018 [US2] Wire state-backend and credential-provider selection into `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/cli.py`
- [X] T019 [US2] Add a saved serverless wheel prepare job with one-run concurrency, queueing, Standard mode, and no publish task in `../ams-sandbox-data-synthesis/databricks.yml`

## Phase 5: User Story 3 — Publish Only Safe Missing Daily Scopes (P3)

**Goal**: Freeze and interactively execute only empty event-insert scopes; reconcile known matching scopes and block uncertainty/conflicts.

**Independent test**: Offline connector doubles cover empty, matching, unexpected, read-error, non-TTY, changed-plan, partial, and unknown states with zero unsafe writes.

- [X] T020 [P] [US3] Add remote-scope classification, exact-lineage reconciliation, request-count, and immutable-bundle tests in `../ams-sandbox-data-synthesis/tests/test_daily_planning.py`
- [X] T021 [US3] Implement date-scoped read-only classification, daily upload-child planning, contiguous ready-prefix selection, and bounded master plans in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/planning.py`
- [X] T022 [P] [US3] Add TTY gate, exact sandbox recheck, confirmation mismatch, single-use authorization, tampering, partial/unknown stop, and no-retry tests in `../ams-sandbox-data-synthesis/tests/test_daily_publishing.py`
- [X] T023 [US3] Implement interactive master publication and read-only reconciliation using the existing immutable upload execution safeguards in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/publishing.py`
- [X] T024 [US3] Add `prepare --remote-check`, `publish`, and `reconcile` command handling in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/cli.py`

## Phase 6: User Story 4 — Evolve The Athlete Population Safely (P4)

**Goal**: Preserve established identities while handling explicit additions/removals.

**Independent test**: Registry reorder changes no profile or future output; additions/removals use effective dates and never rewrite committed history.

- [X] T025 [P] [US4] Add reorder, add, remove, ambiguous-organization, and cross-organization regression tests in `../ams-sandbox-data-synthesis/tests/test_daily_roster.py`
- [X] T026 [US4] Implement explicit effective-dated roster reconciliation in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/roster.py`
- [X] T027 [US4] Add reviewed roster reconciliation to `prepare` without implicit historical backfill in `../ams-sandbox-data-synthesis/src/ams_sandbox_synthesis/cli.py`

## Phase 7: Polish And Cross-Cutting Validation

- [X] T028 Add local setup/test commands and separate WSV, KNLTB, and both examples—including the one-day-behind WSV test—to `../ams-sandbox-data-synthesis/README.md`
- [X] T029 Add local/Databricks storage, secrets, scheduling, retention, recovery, independent-project, and operator-responsibility guidance to `../ams-sandbox-data-synthesis/README.md`
- [X] T030 Run the synthesis offline suite, connector offline suite, CLI smoke tests, wheel build/import smoke test, JSON validation, and scoped `git diff --check`; record results in `agent-docs/current-work.md`

## Dependencies

- Setup (T001-T003) precedes all behavior changes.
- Foundational models/storage (T004-T008) precede every user story.
- User Story 1 (T009-T015) is the MVP and precedes remote planning.
- User Story 2 (T016-T019) depends on the User Story 1 CLI/store contract but can be completed before remote publication.
- User Story 3 (T020-T024) depends on committed daily runs from User Story 1.
- User Story 4 (T025-T027) depends on frozen profiles from User Story 1 but is independent of publication execution.
- Documentation and complete validation (T028-T030) follow all stories.

## Parallel Opportunities

- T004 and T006 touch separate test files and may run in parallel after setup.
- T009, T011, and T013 define different P1 contracts but implementation remains ordered T010, T012, T014.
- T016 may be written while the Databricks adapter is isolated from publication.
- T020 and T022 cover separate planning/execution safety surfaces.
- T025 is independent of User Story 3 after stable profiles exist.

## Implementation Strategy

1. Deliver the P1 local MVP first: explicit initialization, deterministic daily
   transitions, durable catch-up, organization selection, and status.
2. Prove local and Databricks-compatible state equivalence while keeping every
   scheduled path mutation-free.
3. Integrate existing read-only fetch and immutable upload safeguards; do not
   create a parallel connector or confirmation mechanism.
4. Add controlled roster evolution and complete documentation/validation.
