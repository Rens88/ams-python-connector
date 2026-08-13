# Implementation Plan: Incremental Synthetic Data Pipeline

**Feature Branch**: `002-daily-data-pipeline` | **Current Git Branch**:
`agent/native-event-parsing` | **Date**: 2026-08-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-daily-data-pipeline/spec.md`

## Summary

Replace the generator's invocation-scoped athlete/day loop with a deterministic,
checkpointed day-transition engine. A single `sandbox-data` command will scan a
durable dataset, validate its contiguous commit chain, generate every missing
date through an explicit target, and prepare immutable date-scoped upload plans.
The same library and command contract will run against a local directory or a
Unity Catalog Volume. A scheduled Databricks run remains prepare-only; live AMS
event insertion remains a separately invoked, interactive, plan-derived,
human-confirmed operation.

This is the recommended alternative to full 90-day regeneration or prebuilding
a year. It computes only missing days, retains the longitudinal state needed by
future days, never rewrites committed history, and can catch up after irregular
runs. Daily scheduling is optional: a weekly or irregular prepare run produces
the same data and is usually cheaper when Databricks startup time dominates.

## Option Decision

| Option | Advantages | Disadvantages | Decision |
|---|---|---|---|
| Regenerate, delete, and upload 90 days | Reuses the existing batch flow and produces one coherent range | Highest generation/read/write cost; duplicates work; deletion makes routine refresh Critical; largest failure scope | Reject for routine operation; retain temporarily only as rollback tooling |
| Generate one independent day | Minimum daily generation and storage work | Current generator resets causal history, RNG/counters, seasonal phase, weekly context, and IDs | Use only after the stateful transition refactor; then it becomes the normal one-day case |
| Pre-generate one year and reveal one day at a time | Almost no generation compute on publish days | Freezes future roster/config choices; stores unused athlete data; corrections and pending-event changes require awkward invalidation | Reject |
| Stateful missing-date catch-up | Work proportional to actual gaps; identical daily/weekly/irregular behavior; no historical deletion; easy no-op/recovery | Requires versioned state, immutable commits, and concurrency handling | **Selected** |

The selected workflow can still prepare exactly one day when run daily; it is
not a separate generator mode. A weekly invocation simply applies that same
daily transition seven times under one process and one Databricks startup.

## Governance And Risk

**Primary connector aims**: B2, B4, B6, B8, C1-C3, C5-C8, E1, E4,
E6-E9, F3, and F6. Existing roster discovery additionally supports A1; package
deployment carries F5, F7, and F8.

**Highest risk level**: **High**, because the reviewed interactive phase can
create event records in AMS. Generation, local persistence, read-only remote
classification, and scheduled planning are lower-risk stages, but the complete
feature inherits the highest level.

**Reviewed trigger scenarios**: wrong sandbox/athlete/form/date scope;
ambiguous or incomplete reads; duplicate creation after retry or lost local
state; configuration drift; partial or uncertain mutation results; unattended
confirmation; excessive batch/catch-up scope; credentials or athlete data in
artifacts; concurrent writers; and misleading executable documentation.

**Required safeguards carried into design**:

- default to `prepare`/read-only behavior and verify the exact `/sandbox` target;
- scheduled and non-interactive runs cannot enter the live mutation path;
- publish only event inserts; never update, upsert, overwrite, or delete;
- classify the whole frozen daily scope before planning and again just before
  execution; unexpected or uncertain existing data blocks the entire date;
- bind exact child paths, full hashes, counts, ordering, environment, athletes,
  forms, fields, and dates into one immutable master plan;
- retain existing 500-record child-plan and 100-record request-batch limits;
- add reviewed hard limits of 90 missing dates and 25,000 total records per
  catch-up publication bundle, with no CLI bypass; split larger backlogs into
  separately reviewed bundles;
- request the existing scope-derived typed phrase only in an interactive
  `publish` invocation, consume it once, and require a fresh phrase after any
  change;
- never automatically retry a mutation or continue after partial/unknown state;
- store credentials only in memory from local environment/credential storage or
  a Databricks secret provider, never in dataset or Volume artifacts;
- use a single logical writer, immutable daily commits, hash validation, and
  crash-safe staging; and
- use synthetic/redacted offline fixtures by default, with guarded live sandbox
  tests only when explicitly requested.

The 25,000-record bundle cap is a new conservative publication limit, not a
claim about an AMS API maximum. It matches the repository's existing bounded
master-operation scale and must be revisited only through safety review.

## Technical Context

**Language/Version**: Python 3.10+ (matching `ams-python-connector`)

**Primary Dependencies**: Python standard library, installed
`ams-python-connector`, `requests` through that connector, and Plotly only for
separately requested/periodic reports; Databricks SDK is isolated to the
Databricks credential/control adapter if required

**Storage**: Portable append-only filesystem artifacts for generated CSVs,
checkpoints, and immutable plans; local directory for workstation runs; Unity
Catalog Volume plus a small managed Delta control table for Databricks claims
and status indexing, with immutable manifests—not the table—as content authority

**Testing**: `pytest` for the new package and offline workflow doubles; retain
existing generator tests during migration; opt-in guarded live sandbox tests

**Target Platform**: Local Windows/Linux Python and Azure Databricks serverless
Jobs on Linux, using a Unity Catalog-enabled workspace

**Project Type**: Installable Python library plus CLI, implemented in the
sibling `ams-sandbox-data-synthesis` repository and consuming the generic
connector without organization-specific changes to that connector

**Performance Goals**: Generate and commit only missing dates; perform at most
one AMS event-range read per mapped form per classification pass where the API
proves complete multi-athlete results; create no Plotly report on the daily hot
path; complete a no-op without AMS calls unless explicit reconciliation is due

**Constraints**: Preserve `dd/mm/yyyy` generated CSV dates and template schemas;
use only registered sandbox athletes and organization routing; causal dates must
be contiguous; committed dates are immutable; maximum 90 missing dates and
25,000 planned records per publication bundle; one writer per dataset version;
scheduled runs perform zero AMS mutations

**Scale/Scope**: Existing authorized sandbox roster, currently mapped event
forms, a rolling operational horizon usually under 90 days, and one logical
dataset version at a time

## Constitution Check

*GATE: Passed before Phase 0 research and rechecked against the Phase 1 design.*

- **Python-only runtime — PASS**: The engine, stores, CLI, connector calls, and
  Databricks deployment are Python-only.
- **Direct AMS/Smartabase API use — PASS**: The synthesis package uses the
  installed generic Python connector; no R bridge or copied HTTP client is added.
- **Mutation safety — PASS**: `prepare` is the default and scheduled ceiling;
  `publish` is a separate interactive command over immutable plans.
- **Destructive production restriction — PASS**: Update, upsert, overwrite,
  profile mutation, and deletion are excluded. Unknown environments fail closed.
- **Auditability — PASS**: Hash-linked daily commits, upload plans, redacted
  publication results, and reconciliation evidence preserve intent and outcome.
- **Library-first design — PASS**: The state engine, storage, planning, and
  publishing policies live in an installable package; root scripts become thin
  compatibility wrappers.
- **Stable interfaces — PASS**: The existing batch generator and synchronization
  interfaces remain during migration; new artifact schemas carry explicit
  versions and canonical hashing rules.
- **Testing — PASS**: Offline determinism, restart, conflict, concurrency,
  confirmation, and partial-result tests are required before rollout.
- **Data protection — PASS**: Runtime artifacts remain ignored/access-controlled;
  secrets never enter manifests, parameters, logs, or test fixtures.
- **Reviewability and documentation — PASS**: Work is split into small phases,
  with generation correctness completed before upload orchestration and
  Databricks deployment.

**Post-design gate**: PASS. No constitutional exception is required. Fully
unattended AMS publication would fail Principles III and IV and is explicitly
outside this plan.

## Project Structure

### Documentation (this feature)

```text
specs/002-daily-data-pipeline/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── artifact-contracts.md
│   └── cli-contract.md
└── tasks.md                  # created later by speckit-tasks
```

### Source Code (implementation target)

```text
../ams-sandbox-data-synthesis/
├── pyproject.toml
├── src/ams_sandbox_synthesis/
│   ├── __init__.py
│   ├── cli.py                # init, prepare, status, publish, reconcile, report
│   ├── config.py             # versioned dataset/config loading and hashing
│   ├── models.py             # explicit state, commit, and publication models
│   ├── engine.py             # initialize and advance one athlete/day
│   ├── orchestration.py      # scan, catch up, validate, and commit dates
│   ├── storage.py            # portable store protocol and local/Volume store
│   ├── planning.py           # remote scope classification and immutable plans
│   ├── publishing.py         # interactive master-plan execution/reconciliation
│   └── reporting.py          # optional aggregate reports, off the daily path
├── generate_sandbox_data.py  # compatibility wrapper during migration
├── refresh_sandbox_data.py   # compatibility wrapper during migration
├── sync_smartabase_generated_data.py
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── fixtures/             # synthetic/redacted only

ams-python-connector/
├── src/ams_smartabase/       # existing generic API client, unchanged for MVP
└── tests/                    # changed only if a generic batched-read gap is proven
```

**Structure Decision**: Put organization-specific synthesis and destination
policy in the synthesis package. Reuse connector public APIs for discovery,
range reads, payload creation, and event insertion. Do not move daily workflow
policy into `ams-python-connector`. Keep root scripts as compatibility shims so
the package can be extracted without one large breaking rewrite.

## Architecture And Data Flow

```text
target date
    |
    v
validate commit chain -> generate missing dates -> commit day + after-state
                                                   |
                                                   v
                                     classify exact AMS date scopes
                                      /          |            \
                                 empty      known match      conflict/read error
                                   |             |                    |
                                   v             v                    v
                              freeze plans   reconcile/skip        block date
                                   |
                    scheduled run stops here (zero writes)
                                   |
                                   v
                     interactive publish master plan
                                   |
                    final scope recheck + typed confirmation
                                   |
                                   v
                       ordered event inserts; stop on uncertainty
```

Generation state and AMS publication state are deliberately separate. A date
can be generated but unpublished without blocking generation of later dates.
This allows irregular preparation while preserving causal simulation history.

## Implementation Phases

### Phase 1 — Characterize And Freeze Existing Behavior

1. Add golden tests for template schemas, routing, complaint duration, recent
   practice effects, weekly totals, and representative pattern distributions.
2. Capture the legacy generator version and document intended compatibility
   changes; do not promise byte-for-byte equivalence with the current global RNG.
3. Add package metadata and a thin CLI without changing current script entry
   points.

**Exit evidence**: Existing tests pass, golden fixtures are synthetic, and every
intentional output change needed by the stateful engine is reviewed.

### Phase 2 — Build The Deterministic Daily Engine

1. Freeze an effective-dated athlete simulation profile keyed by stable AMS
   user ID; stop deriving identity or pattern from registry position.
2. Implement `initialize_simulation`, `build_week_plan`,
   `generate_athlete_day`, and `generate_date`; implement range generation only
   as repeated date transitions.
3. Replace the shared RNG and global counters with SHA-256-derived RNG streams
   and stable date/athlete/component identifiers. Version stream names and draw
   order.
4. Replace range-relative seasonal progression with an absolute simulation
   epoch/campaign phase.
5. Carry fatigue, complaint state, bounded recent-practice history, complete
   Monday-Sunday plan context, and future-dated pending events across days.
6. Move weekly calculations and IDs into the engine so renderers only render
   already-decided entities.

**Exit evidence**: One 90-day invocation equals 90 serialized one-day
invocations at every daily manifest and final state hash.

### Phase 3 — Add Durable Catch-Up Storage And Commands

1. Implement the store protocol, versioned artifact schemas, canonical JSON
   hashing, staging directories, commit-marker-last behavior, and chain
   validation.
2. Implement `init`, `prepare`, and `status`. Default `prepare` target is the
   previous completed calendar day in `Europe/Amsterdam`; `--through-date`
   remains explicit for reproducibility and irregular runs.
3. On normal runs generate `head + 1 ... through_date`. Treat an interior hole
   followed by later commits as corruption, not as an independently fillable
   gap; provide read-only diagnostics and rebuild guidance.
4. Add a local exclusive lock and a store-level compare-before-commit check.
   Configure Databricks job maximum concurrent runs to one; use a conditional
   Delta claim/commit for the Databricks adapter before allowing scheduled and
   manually triggered runs to share a dataset root.
5. Make report generation a separate `report` command/task. The daily hot path
   writes compact validation summaries, not self-contained Plotly dashboards.

**Exit evidence**: No-op, crash recovery, tamper detection, incompatible version,
and two-writer tests all fail safe without rewriting a commit.

### Phase 4 — Add Date-Scoped Planning And Interactive Publication

1. Reuse the existing connector and upload-plan builders. Split payloads into
   child plans of at most 500 records and request batches of at most 100.
2. Query all authorized athletes for one mapped form and the complete candidate
   date range in one paginated read when contract tests prove result
   completeness and attribution. Otherwise retain the existing smaller queries;
   request minimization must not weaken correctness.
3. Partition read results by date, athlete, and form, then classify each daily
   target as empty, matching a prior immutable publication, unexpected, or
   read-uncertain. Any unexpected row blocks that date as a unit.
4. Freeze one ordered catch-up master plan across the earliest contiguous ready
   prefix only, binding dates and complete hashes. A blocked earlier date cannot
   be skipped. Reject bundles above 90 days or 25,000 records.
5. Implement `publish <master-plan>` as TTY-only, with a fresh whole-range read,
   full preview, existing hash-derived typed confirmation, immutable child
   revalidation, and one-time ordered authorization.
6. Preserve the connector's reviewed mutation-state policy: a confirmed result
   may continue, and an explicitly classified accepted-but-unverified result may
   finish only the already-authorized bundle before mandatory reconciliation.
   Stop later writes after mismatch, partial success, unknown, contradictory, or
   unclassified results. Recovery starts with `reconcile`, never an automatic
   retry; a changed remainder requires a new immutable plan and fresh human
   review.

**Exit evidence**: Offline doubles prove zero writes for scheduled, non-TTY,
conflicting, read-uncertain, changed-plan, mismatched-confirmation, repeated,
partial, and unknown-result cases.

### Phase 5 — Deploy The Prepare Job To Databricks

1. Build and install a pinned wheel for the synthesis package plus a pinned
   internal connector wheel; run the same CLI entry point as local execution.
2. Provision an access-controlled Unity Catalog Volume for datasets and plans.
   Store code in Git/workspace deployment assets, not in the Volume.
3. Retrieve the AMS secret through a Databricks credential adapter into memory.
   Do not write a `.env` file or pass plaintext credentials as task parameters.
4. Use a serverless Python wheel task with Standard performance mode, maximum
   concurrent runs `1`, queueing, no mutation task, and alerts on failure,
   conflict, partial/unknown state, duration, or backlog-limit breach.
5. Schedule for the required freshness, using `Europe/Amsterdam` and a
   through-date of yesterday. Start weekly to amortize startup overhead; move to
   daily only if daily sandbox freshness is worth the additional cold starts.
6. Add a separate optional weekly report task after successful preparation.

**Exit evidence**: A deployed prepare job catches up a synthetic test dataset in
a non-production workspace, produces the same hashes as local execution, emits
zero AMS writes, and passes secret/artifact inspection.

### Phase 6 — Documentation, Rollout, And Cleanup

1. First update `agents.md`, `project_requirements.md`, and user documentation to
   define lightweight daily validation plus periodic/on-demand dashboards. This
   deliberately resolves the current instruction that every local generation
   produces full Plotly output; implementation must not silently bypass it.
2. Document initialization, local and Databricks preparation, interactive
   publication, status interpretation, roster changes, dataset-version cutover,
   retention, and recovery.
3. State beside every execution command that this independent project is not
   affiliated with, endorsed by, or maintained by Teamworks and that operators
   remain responsible for authorization and policy compliance.
4. Run both workflows in shadow prepare-only mode, compare daily outputs and
   distribution checks, then enable interactive incremental publication.
5. Keep the legacy 90-day refresh available during a bounded rollback window;
   remove it only in a separate reviewed change after the new pipeline proves
   stable.

## Validation Matrix

| Area | Required evidence |
|---|---|
| Determinism | one-shot vs daily/resumed equality; registry reorder stability; independent RNG streams |
| Longitudinal behavior | fatigue, complaints, recent practice, week boundary, pending next-day event, campaign phase |
| Storage | stage/commit crash points, hash chain, orphan cleanup, immutable rerun, incompatible version, lock contention |
| Dates | leap day, month/year boundary, DST transition, target before head, no-op, long outage |
| AMS reads | pagination, all requested users/forms, missing users, range attribution, incomplete/ambiguous response |
| Planning | empty/matching/unexpected/read-uncertain scopes, 500-child and bundle limits, canonical plan hashes |
| Publication | sandbox verification, final recheck, TTY gate, confirmation mismatch, changed child/order, partial/unknown stop, no retry |
| Protection | no secrets in logs/manifests; generated and fetched athlete artifacts ignored; redacted fixtures only |
| Portability | identical local and Volume manifest hashes from identical state/config; wheel smoke test on Databricks |

## Rollout And Operational Recommendation

Start with local `prepare` and `status`, then deploy the identical prepare command
weekly in Databricks. Keep `publish` local and interactive. Once operational
evidence shows the generator is fast and stable, choose frequency solely from
freshness needs: every run catches up causally, so running seven missing days at
once is valid and usually costs less than seven Databricks cold starts.

Do not pre-generate a year: that freezes future roster/config choices, stores
unused athlete data, and makes longitudinal corrections awkward. Do not rebuild
and delete 90 days: it is the most expensive option and introduces a Critical
destructive workflow. A rolling 90-day consumer view should be a query/filter,
not scheduled deletion.

## Complexity Tracking

No constitution violations are planned. The two storage adapters are justified
by the explicit local/Databricks portability requirement; both implement one
small artifact-store protocol and share canonical schemas. The Databricks
adapter adds a compact Delta control ledger because job concurrency settings do
not coordinate every possible manual writer. The planned reporting change is a
reviewed update to lower-level synthesis guidance, not a constitutional
exception; it must land before the daily hot path stops producing dashboards.
