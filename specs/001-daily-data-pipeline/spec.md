# Feature Specification: Incremental Synthetic Data Pipeline

**Feature Branch**: `001-daily-data-pipeline` (Spec Kit feature identifier;
the existing worktree remains on `agent/native-event-parsing`)

**Created**: 2026-08-11

**Status**: Draft

**Input**: User description: "Create a daily or periodically run synthetic-data pipeline that detects missing dates, generates those dates sequentially with longitudinal state, and provides one safe workflow for local or scheduled Databricks use."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fill Missing Dates With Longitudinal Data (Priority: P1)

An operator runs the pipeline for a requested through-date. The pipeline identifies every uncommitted date after the last complete date, generates the missing dates in chronological order, and carries each athlete's relevant history into the next date.

**Why this priority**: This creates the core value: the same workflow works daily, after an interruption, or after an irregular gap without regenerating completed history.

**Independent Test**: Generate a fixed interval once, then generate the same interval through consecutive daily invocations. The committed daily outputs and ending state must be equivalent.

**Acceptance Scenarios**:

1. **Given** a complete committed dataset through 1 August, **When** the operator requests generation through 5 August, **Then** the pipeline generates 2–5 August in order and commits each date once.
2. **Given** the requested through-date is already complete, **When** the pipeline runs, **Then** it reports a successful no-op and does not rewrite committed dates.
3. **Given** a partially written but uncommitted date, **When** the pipeline reruns, **Then** it rejects or replaces only the incomplete attempt from the last valid checkpoint and does not advance from uncertain state.

---

### User Story 2 - Run The Same Workflow Locally Or On A Schedule (Priority: P2)

An operator can invoke one pipeline contract from a local machine or a persistent scheduled workspace. Both contexts use the same date-selection, generation, validation, state, and operation-plan rules.

**Why this priority**: A single operational path prevents local runs and scheduled runs from producing incompatible datasets or bypassing safeguards.

**Independent Test**: Run the workflow in two isolated environments from identical configuration and prior state, then compare the committed manifests and plan hashes.

**Acceptance Scenarios**:

1. **Given** identical prior state and configuration, **When** the same missing date is prepared locally and in a scheduled environment, **Then** both produce the same daily content and manifest fingerprint.
2. **Given** a non-interactive scheduled run, **When** missing dates are found, **Then** generation and upload planning may complete but no live AMS mutation is executed.
3. **Given** a local interactive run, **When** reviewed daily upload plans are ready, **Then** the operator can continue through the existing scope-derived confirmation workflow.

---

### User Story 3 - Publish Only Safe Missing Daily Scopes (Priority: P3)

An operator prepares new synthetic event records for dates that are absent from the target sandbox scope. Previously published dates are reconciled and skipped, while unexpected existing records block the affected daily scope without deletion or partial conflict-free upload.

**Why this priority**: Append-only daily publication minimizes requests and avoids making destructive refresh behavior routine.

**Independent Test**: Exercise empty, previously published, partially populated, and unexpectedly populated target dates using offline connector doubles and immutable plans.

**Acceptance Scenarios**:

1. **Given** an empty target date, **When** the pipeline prepares publication, **Then** it freezes an event-only immutable upload plan for that date.
2. **Given** a target date matching a previously published immutable plan, **When** the pipeline reconciles it, **Then** it marks the date complete without uploading it again.
3. **Given** unexpected existing records in any selected athlete/form scope for a date, **When** the pipeline checks that date, **Then** it blocks all upload for that date and neither deletes nor modifies existing records.
4. **Given** an upload with a partial or uncertain result, **When** the workflow stops, **Then** no automatic mutation retry occurs and recovery begins with read-only reconciliation.

---

### User Story 4 - Evolve The Athlete Population Safely (Priority: P4)

An operator can refresh the authorized sandbox athlete registry without changing the previously frozen pattern identity or historical data for existing athletes.

**Why this priority**: Long-running scheduled synthesis must tolerate roster changes without silently rewriting established athlete histories.

**Independent Test**: Add, remove, and reorder registry rows between daily runs and verify stable assignments and bounded effective dates.

**Acceptance Scenarios**:

1. **Given** existing athletes are reordered in the registry, **When** generation continues, **Then** their pattern assignments and future deterministic outputs remain stable.
2. **Given** a new authorized athlete appears, **When** the next run starts, **Then** the athlete receives an explicit effective-from date and initialized state without changing existing athletes.
3. **Given** an athlete is no longer selected, **When** later dates are generated, **Then** no new records are created for that athlete and existing committed history remains unchanged.

### Edge Cases

- The requested through-date precedes the last committed date.
- One or more dates are absent between otherwise committed dates.
- A daily partition exists but its manifest, state checkpoint, or hashes are missing or invalid.
- Configuration, generator version, seed, templates, form mappings, or athlete assignments change mid-series.
- A complaint or another generated entity begins on one date and produces a record on a later date.
- A week crosses a month, year, daylight-saving boundary, or scheduled-job outage.
- Multiple runs target the same dataset and date concurrently.
- A new athlete is first observed while the pipeline is catching up several historical dates.
- AMS contains records for a date that has no matching local publication evidence.
- AMS accepted a write but returned an incomplete or ambiguous acknowledgement.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST accept an explicit target dataset and through-date and determine missing dates from durable committed state rather than from wall-clock assumptions alone.
- **FR-002**: The pipeline MUST process missing dates strictly in chronological order from the last valid checkpoint.
- **FR-003**: Each generated athlete-day MUST depend on an explicit prior athlete state containing only the history needed for future generation.
- **FR-004**: Given the same dataset version, configuration, athlete, date, and prior state, generation MUST produce identical content and identifiers.
- **FR-005**: Existing committed daily data MUST be immutable; reruns MUST be no-ops when hashes match and fail closed when they differ.
- **FR-006**: A date MUST become committed only after its generated records, validation result, next-state checkpoint, configuration references, and hashes are complete.
- **FR-007**: The system MUST preserve active multi-day conditions, recent-practice effects, fatigue, weekly planning context, and pending future-dated records across run boundaries.
- **FR-008**: Identifiers MUST remain unique and stable across independently generated dates and retries.
- **FR-009**: Pattern phase and progression MUST be based on a stable simulation timeline rather than the length of the current invocation.
- **FR-010**: Athlete-to-pattern assignments MUST remain stable when the registry is reordered or refreshed.
- **FR-011**: New and removed athletes MUST have explicit effective dates; roster changes MUST NOT rewrite committed history for existing athletes.
- **FR-012**: The same user-facing pipeline contract MUST support local interactive use and non-interactive scheduled preparation.
- **FR-013**: Scheduled execution MUST stop after read-only checks, generation, validation, and immutable upload-plan preparation; it MUST NOT supply confirmation or execute live AMS mutation under current governance.
- **FR-014**: Live upload MUST remain a separate interactive operation using the existing plan-derived confirmation, immutable-plan validation, sandbox verification, bounded batches, and audit results.
- **FR-015**: The incremental workflow MUST insert event records only; profile upsert, update, replace, overwrite, and deletion are out of scope.
- **FR-016**: Before preparing a new daily upload, the pipeline MUST classify the target daily scope as empty, previously published and matching, unexpectedly populated, or read-uncertain.
- **FR-017**: Unexpectedly populated or read-uncertain scopes MUST block the complete daily upload without deletion or partial conflict-free upload.
- **FR-018**: Previously published dates MUST be reconciled against their immutable local publication plan and MUST NOT be uploaded again.
- **FR-019**: Partial, unknown, or contradictory mutation results MUST stop processing without automatic mutation retry and MUST retain enough redacted audit metadata for read-only recovery.
- **FR-020**: The pipeline MUST detect concurrent attempts for the same dataset/date and permit at most one successful commit and one authorized publication path.
- **FR-021**: Generated athlete data, checkpoints, payload material, and operation artifacts MUST remain in ignored or access-controlled persistent storage and MUST never contain credentials.
- **FR-022**: Human-readable status MUST distinguish generated, planned, ready for review, published, reconciled, blocked, partial/unknown, and failed dates.
- **FR-023**: The pipeline MUST support catch-up after missed or irregular runs without requiring regeneration or deletion of earlier committed dates.
- **FR-024**: A configuration or schema change that could alter future generation MUST create an explicit new dataset version or reviewed cutover; it MUST NOT silently continue an incompatible state series.

### Constitution Impact

- **Runtime boundary**: Python-only runtime in both repositories; no R, Rscript, or `smartabaseR` execution.
- **AMS/Smartabase API use**: Read-only checks and event insert planning/execution use the installed Python connector directly.
- **Mutation safety**: High-risk event creation remains dry-run-first and human-confirmed. Scheduled live mutation, profile upsert, update, overwrite, and deletion are excluded.
- **Auditability**: Adds versioned daily generation checkpoints, immutable commit manifests, daily upload plans, publication status, and redacted reconciliation evidence.
- **Public interfaces**: Introduces a reusable incremental-generation API, persistent state/manifest schemas, and a unified local/scheduled command contract.
- **Testing evidence**: Requires offline equivalence, determinism, gap recovery, concurrency, conflict, confirmation, partial-result, and artifact-safety tests; live sandbox tests remain opt-in.
- **Credentials and athlete data**: Credentials remain runtime-only; registry, generated data, state, and operation artifacts remain uncommitted and access-controlled.
- **Documentation**: Requires local and scheduled quickstarts, state/storage lifecycle guidance, recovery instructions, and warnings beside upload execution.

### Key Entities

- **Dataset Version**: Immutable simulation identity binding the seed, generator policy, timeline, templates, form mappings, and athlete-pattern assignments.
- **Athlete State**: Minimal longitudinal state needed to generate the athlete's next day, including effective date and last generated date.
- **Daily Generation**: All generated entities attributable to one simulation date, including records scheduled for later emission.
- **Pending Event**: A generated entity decided on one date but emitted on a later event date.
- **State Checkpoint**: Immutable ending state for every selected athlete after a committed date.
- **Daily Commit Manifest**: Hash-bound declaration that a date's data, validation, and next checkpoint are complete.
- **Daily Upload Plan**: Immutable, event-only plan for one target date and exact sandbox scope.
- **Publication Record**: Redacted outcome and reconciliation status for a daily upload plan.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a fixed dataset version, a 90-day one-shot run and 90 consecutive daily runs produce identical daily manifests and equivalent ending state.
- **SC-002**: After any interruption between daily commits, a rerun generates every missing date exactly once and rewrites zero previously committed dates.
- **SC-003**: Repeating a preparation run for the same date produces the same daily and upload-plan fingerprints in 100% of offline determinism tests.
- **SC-004**: A run with no missing dates completes as a successful no-op without creating a new generation or mutation attempt.
- **SC-005**: Registry row reordering changes zero existing athlete assignments or previously deterministic future outputs.
- **SC-006**: Every unexpected non-empty or read-uncertain daily AMS scope causes zero write, update, upsert, or delete requests.
- **SC-007**: Every non-interactive scheduled run causes zero live AMS mutation requests under current governance.
- **SC-008**: Every partial or uncertain upload result stops later mutation attempts and produces an actionable read-only recovery status.
- **SC-009**: An operator can use one documented workflow locally or on a schedule to prepare all dates missed since the last successful run without manually listing those dates.
- **SC-010**: No credential or generated/fetched athlete-data artifact is introduced into source control by the feature's automated tests or normal workflows.

## Assumptions

- Version 1 targets explicitly mapped event forms in a verified Smartabase sandbox and excludes Athlete Profile.
- The desired synthetic timeline is append-only. Consumers can select a rolling 90-day view without scheduled deletion of older events.
- A non-interactive schedule prepares plans but does not perform live AMS mutation under the current constitution and risk model.
- A human may run the same pipeline interactively to review and confirm a prepared daily upload.
- Persistent storage is available to both local and scheduled executions; its concrete implementation is selected during planning.
- One logical writer operates per dataset version. Concurrent attempts are rejected or serialized.
- New athletes begin on an explicit effective-from date and are not backfilled before that date unless a future reviewed requirement adds that behavior.
- Existing connector batch, exact-target, dry-run, confirmation, and partial-result safeguards remain authoritative.
