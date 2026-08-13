# Research: Incremental Synthetic Data Pipeline

## Decision 1 — Use Stateful Incremental Catch-Up

**Decision**: Generate only the causally missing interval from the last
hash-valid committed checkpoint through the requested date, one date at a time.

**Rationale**: The current generator already carries longitudinal values inside
one invocation—fatigue, complaint state, practice history, and active complaints—
but loses them between invocations. Making that state explicit produces the same
pattern behavior without regenerating or deleting prior dates. It also makes a
daily, weekly, or irregular run the same operation.

**Alternatives considered**:

- **Regenerate/delete/upload 90 days**: rejected. It repeats nearly all compute
  and network work and turns ordinary maintenance into a Critical destructive
  workflow.
- **Generate one independent day with the current function**: rejected. The
  current global RNG, counters, registry indexes, range-relative day index, and
  in-memory history reset, so dates are not longitudinally equivalent.
- **Pre-generate a year and release one partition per day**: rejected. It has
  cheap daily reads but freezes future roster/config choices, retains unused
  athlete data, complicates correction, and still needs durable publication
  state.
- **Stateful incremental generation**: selected. Its work is proportional to
  missed dates and it naturally supports irregular schedules.

## Decision 2 — Make One Day A Pure Versioned Transition

**Decision**: Refactor into `generate_athlete_day(profile, state, day,
week_plan, rng_streams)` and `generate_date(simulation_state, day)`. A range is
only repeated daily transitions.

**Rationale**: The current athlete-outer/day-inner loop uses a shared
`random.Random(seed)` and global counters. Reversing loops alone changes random
draw order and does not create restart equivalence. Explicit transitions make
state serializable and independently testable.

The checkpoint carries fatigue, previous-complaint flag, complete active
complaint details, bounded recent practiced dates, the full Monday-Sunday plan,
and future-dated pending events. A Sunday complaint can currently decide a
Monday consultation, so an output partition must be based on actual event date,
not only decision date.

**Alternatives considered**:

- Persist `Random.getstate()` and counters: smaller initial edit, but brittle to
  changes in iteration order and unrelated random draws.
- Replay all history before each day: deterministic but reintroduces linear
  historical compute and makes corruption recovery opaque.

## Decision 3 — Derive Random Streams And IDs From Stable Inputs

**Decision**: Seed independent component streams with SHA-256 over canonical
`(generator_version, base_seed, athlete_id, ISO date, stream_name)` and derive
stable IDs from the same identity plus per-day ordinal.

**Rationale**: This removes registry-order, invocation-length, and global-counter
dependencies. Separate plan, outcome, complaint, wellness, and Garmin streams
prevent a new draw in one component from perturbing unrelated output.

Python `hash()` is excluded because it is process-randomized. Numeric IDs use a
documented bounded digest mapping plus collision validation. Any change to
stream names, draw order, or ID policy increments `generator_version`.

## Decision 4 — Freeze Absolute Pattern And Roster Context

**Decision**: Use a stable simulation epoch/campaign phase and an effective-
dated `AthleteSimulationProfile` keyed by AMS user ID.

**Rationale**: The current seasonal factor depends on `day_index / total_days`,
so the same date changes when invocation length changes. Current pattern,
synthetic age, squad, physiology, location, and some IDs depend on registry row
position. Freezing those inputs retains pattern character across resumed runs
and registry reorder.

New athletes receive explicit `effective_from` profiles and fresh baseline
state. Removed athletes receive `effective_to`; their history is retained.
Pattern or profile changes are new versions or explicit future cutovers, never
silent historical reinterpretation.

## Decision 5 — Use Hash-Linked Daily Commits

**Decision**: Stage all artifacts, validate and hash them, then write an
immutable daily commit manifest last. Each manifest binds its predecessor and
before/after checkpoints.

**Rationale**: A filename alone cannot distinguish complete from interrupted
generation. Commit-marker-last behavior allows safe recovery from orphan
staging, prevents rewriting a committed date, and detects hidden interior gaps.

The normal missing range is `contiguous_head + 1 ... through_date`. A missing
date behind a later commit is corruption because later state may depend on it;
it is not independently synthesized. A deterministic repair is allowed only in
a separately designed repair mode that proves the regenerated after-state hash
equals the already recorded successor.

## Decision 6 — Keep Generation And Publication State Separate

**Decision**: Later dates may be generated while earlier dates await human
publication. Publication itself advances only through the earliest contiguous
ready prefix.

**Rationale**: Generation is a causal local simulation concern; publication is
a high-risk remote mutation concern. Coupling them would make a transient AMS
read or unavailable operator block future state. Allowing publication to skip a
blocked earlier date would create a silent remote gap, so only the contiguous
ready prefix enters a master plan.

## Decision 7 — Prepare On Schedule, Publish Interactively

**Decision**: The unified command exposes `prepare`, `status`, `publish`, and
`reconcile`, but scheduled Databricks execution stops after preparation.

**Rationale**: Connector governance requires dry-run planning and separate
human confirmation for live writes. Scheduled workflows cannot supply that
confirmation. Existing synthesis code also rejects live upload from a non-TTY.
The interactive publisher reuses the existing immutable master-plan,
hash-derived typed-confirmation, child revalidation, execution reservation, and
partial/unknown-stop behavior.

**Alternative considered**: A job parameter or secret containing confirmation
was rejected because it converts confirmation into credentials/configuration
and bypasses the required human decision. A future unattended insert workflow
requires a separate governance decision, dedicated derived destination forms,
least-privileged credentials, and a new design; it is not an implementation
phase of this feature.

## Decision 8 — Classify Exact Daily AMS Scopes Before Planning

**Decision**: Classify candidate scopes as `EMPTY`,
`MATCHING_WITH_LINEAGE`, `UNEXPECTED_NONEMPTY`, or `READ_UNCERTAIN`.

**Rationale**: Empty scopes can safely produce insert plans. A matching scope is
safe only when immutable local plan/execution lineage exists and exact
versioned row-multiset reconciliation succeeds. Existing AMS records without
that lineage may be unrelated and must block rather than be adopted or deleted.
Incomplete reads, missing stable athlete attribution, or pagination uncertainty
also block.

The pipeline retains the initial read, fresh pre-execution read, and final
reconciliation. These requests are safety controls. Partial or unknown mutation
results never retry automatically. A known exact subset can enter only the
existing reviewed continuation model with a new immutable remainder plan and
fresh authorization.

## Decision 9 — Batch Read-Only Checks By Form And Interval When Proven

**Decision**: Aim for one authenticated paginated read per mapped form over the
earliest candidate interval, with all stable athlete IDs, then partition locally.

**Rationale**: The connector accepts multiple `user_ids`, while the current
fetch caller loops athlete by form. For 11 forms, a complete batched pass can be
roughly form-count requests rather than athlete-count multiplied by form-count,
subject to pagination. One client/session is reused per stage.

**Constraint**: This optimization is gated by offline and live-sandbox contract
evidence proving server limits, pagination, zero-result coverage, and stable
athlete attribution. If completeness cannot be proven, the caller retains
smaller requests. Request reduction never weakens fail-closed classification.

## Decision 10 — Use Filesystem Artifacts Locally, Volume Plus Delta On Databricks

**Decision**: Keep one logical `StateStore`. Use a local directory with tested
exclusive locking for workstation datasets. Use a restricted managed Unity
Catalog Volume for non-tabular artifacts and a small managed Delta control
table for claims, commit/status indexing, and optimistic conflict detection in
Databricks.

**Rationale**: Unity Catalog Volumes are designed for governed path-based files
and expose `/Volumes/<catalog>/<schema>/<volume>/...`, which fits the existing
CSV/JSON/`pathlib` model. Delta supplies ACID commits for coordination when a
scheduled and manually triggered run might overlap. Immutable manifest content,
not the Delta index, remains authoritative. See [Unity Catalog
Volumes](https://learn.microsoft.com/en-us/azure/databricks/volumes/) and
[Delta Lake ACID guarantees](https://learn.microsoft.com/en-us/azure/databricks/lakehouse/acid).

**Alternatives considered**:

- Volume JSON pointer only: acceptable for a prototype only after testing
  exclusive-create/replace semantics across processes; not assumed for the
  durable job.
- Store every generated row in Delta: stronger tabular querying but adds Spark
  coupling to the local core and disrupts the current CSV/template workflow.
- SQLite on the Volume: rejected because shared/network filesystem locking is
  the wrong concurrency primitive.

One dataset version has one authoritative state root. Unsynchronized local and
Databricks copies cannot both advance it. Operational local control of a
Databricks-owned dataset should trigger the saved job or use a reviewed complete
store transfer, not create a competing history.

## Decision 11 — Package A Wheel And Run One Serverless Job Task

**Decision**: Convert reusable synthesis behavior to an installable wheel, pin
the connector wheel, and deploy one saved serverless Python wheel job through a
Databricks Asset Bundle/Declarative Automation Bundle.

**Rationale**: One task processes all missing dates and pays startup overhead
once. Databricks documents wheel tasks as a reliable packaged job form and
supports building/deploying them through Bundles. See [Python wheel tasks](https://learn.microsoft.com/en-us/azure/databricks/jobs/how-to/use-python-wheels-in-workflows)
and [Bundle wheel workflow](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/python-wheel).

Use serverless Standard performance mode for cost efficiency. Databricks notes
that it uses fewer DBUs but can add roughly four to six minutes of startup, a
good trade for a non-urgent prepare job. Use a saved Job, because standard mode
is not available to one-off `runs/submit` executions. See [Run serverless
Jobs](https://learn.microsoft.com/en-us/azure/databricks/jobs/run-serverless-jobs).

Set maximum concurrent runs to one, enable queueing, add timeout/duration
warnings and failure notifications, and tag runs for cost attribution. See
[job concurrency and queueing](https://learn.microsoft.com/en-gb/azure/databricks/jobs/configure-job),
[job notifications](https://learn.microsoft.com/en-us/azure/databricks/jobs/notifications),
and [Jobs system tables](https://learn.microsoft.com/en-us/azure/databricks/admin/system-tables/jobs).

Generation retries remain disabled initially and may be enabled only after
deterministic crash/retry tests. Any future mutation task must have no retries,
no timeout retry, and serverless auto-optimization retries disabled; Databricks
specifically calls this out for at-most-once tasks in the [serverless Jobs
documentation](https://learn.microsoft.com/en-us/azure/databricks/jobs/run-serverless-jobs).

## Decision 12 — Prefer Weekly Scheduling Unless Daily Freshness Is Required

**Decision**: Start with a weekly prepare schedule; use daily only when the
sandbox must be no more than one day behind.

**Rationale**: Missing-date catch-up makes frequency a freshness decision, not a
correctness decision. A lightweight Python generation is likely shorter than
serverless startup, so processing seven dates in one weekly run usually costs
less than seven cold starts. The target remains yesterday in
`Europe/Amsterdam`; explicit missing-date calculation is authoritative even if
daylight-saving behavior changes a trigger time. Databricks supports named
timezones and documents DST caveats in [scheduled
Jobs](https://learn.microsoft.com/en-us/azure/databricks/jobs/scheduled).

The implementation records wall time, DBUs/cost attribution metadata, generated
dates, rows, and AMS request counts. Revisit cadence after four weeks of actual
runs rather than assuming generation is the cost driver.

## Decision 13 — Inject Credentials; Never Create `.env` On A Volume

**Decision**: The core accepts a credential provider or constructed client.
Local execution may use the existing protected environment/credential flow.
Databricks retrieves a narrowly scoped secret at runtime and passes credentials
only in memory.

**Rationale**: Serverless compute does not support configured environment
variables, so copying the local `.env` convention is neither supported nor
safe. See [serverless compute
limitations](https://learn.microsoft.com/en-us/azure/databricks/compute/serverless/limitations)
and [Databricks secret management](https://learn.microsoft.com/en-us/azure/databricks/security/secrets/).

Use a dedicated read-only AMS principal for scheduled classification if the AMS
authorization model permits. Interactive publication uses separately controlled
write credentials. Grant the job principal only the minimum Volume, Delta, and
secret-scope privileges. A Key Vault-backed secret scope is appropriate where
central rotation already exists; otherwise a dedicated Databricks-backed scope
is simpler.

With serverless egress controls, allow only the reviewed AMS sandbox FQDN and
approved package source, while retaining the application's exact `/sandbox`
verification. See [serverless egress
policies](https://learn.microsoft.com/en-us/azure/databricks/security/network/serverless-network-security/network-policies).

## Decision 14 — Move Heavy Reports Off The Daily Hot Path

**Decision**: Daily commits store lightweight validation/statistics. The
self-contained Plotly dashboard is generated weekly, per publication bundle, or
on demand by `report`.

**Rationale**: The current generator renders all dashboards for every run. That
is disproportionate for a one-day task and creates unnecessary CPU and files.
Separating reporting preserves inspection without coupling it to causal state.

**Repository-policy impact**: Current synthesis guidance says local generation
also produces timeline/PDF dashboards. Before implementation, update
`agents.md`, `project_requirements.md`, and user documentation in a reviewed
change to define the daily lightweight exception and periodic report obligation.
This is an explicit prerequisite, not a silent bypass.

## Decision 15 — Bound Work Without A Force Flag

**Decision**: Advance at most 90 generation dates per invocation and freeze no
publication bundle above 90 dates or 25,000 records. Existing child plans remain
at most 500 records and request batches at most 100.

**Rationale**: Bounds keep previews reviewable, limit one authorization's blast
radius, and avoid runaway catch-up after a configuration mistake. A backlog over
90 dates is processed in repeated validated invocations; a publication backlog
is split into separately reviewed contiguous bundles. There is no `--force` or
unlimited override.

The 25,000-record figure is a project safeguard, not an asserted AMS limit. Any
change requires documented safety review and tests.
