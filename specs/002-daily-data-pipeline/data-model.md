# Data Model: Incremental Synthetic Data Pipeline

## Model Principles

- Generation is an append-only, causally contiguous chain per dataset version.
- Publication is a separate append-only chain; generation never depends on AMS
  upload status.
- JSON used for hashing is UTF-8 canonical JSON with sorted keys, no insignificant
  whitespace, ISO dates, and an explicit schema version.
- Names, credentials, payload values, and raw AMS responses do not belong in the
  compact control ledger. Athlete data stays in the protected artifact store.
- `latest` pointers and indexes are caches. Hash-valid immutable manifests are
  authoritative.

## Entity Relationships

```text
DatasetVersion 1 ─── * AthleteSimulationProfile
       │
       ├── 1 ─── * DailyCommit ─── 1 StateCheckpoint
       │                 │
       │                 ├── * GeneratedFile
       │                 └── * PendingEvent (inside checkpoint until due)
       │
       └── 1 ─── * PublicationDay ─── * UploadChildPlan
                                      └── 0..1 PublicationAttempt

PublicationBundle 1 ─── * ordered UploadChildPlan references
```

## DatasetVersion

Immutable identity for one synthetic timeline.

| Field | Type | Rules |
|---|---|---|
| `schema_version` | string | Required artifact contract version |
| `dataset_id` | string | Operator-facing stable name; path-safe and non-secret |
| `dataset_version` | string | Unique immutable version identifier |
| `generator_version` | string | Pins algorithm, RNG streams, and renderer policy |
| `base_seed` | integer/string | Stored as non-secret generation input |
| `simulation_epoch` | ISO date | Absolute origin for seasonal/campaign phase |
| `timezone` | IANA name | `Europe/Amsterdam` by default |
| `template_manifest_sha256` | SHA-256 | Binds every source template and schema |
| `form_map_sha256` | SHA-256 | Binds exact mapped destination forms |
| `roster_snapshot_sha256` | SHA-256 | Binds effective-dated athlete profiles |
| `generator_config_sha256` | SHA-256 | Hash of all future-output-affecting settings |
| `created_at` | UTC timestamp | Audit metadata excluded from deterministic config/content fingerprints |

Changing the seed, generator algorithm, simulation epoch, templates, form map,
or an output-affecting policy requires a new version or an explicit effective-
dated cutover model that has its own hash. It may not silently alter this entity.

## AthleteSimulationProfile

Frozen synthetic identity keyed by a stable AMS sandbox user ID.

| Field | Type | Rules |
|---|---|---|
| `athlete_id` | stable ID | Required; never use row position or display name as identity |
| `organization` | enum | `KNLTB`, `WSV`, or reviewed shared-only classification |
| `pattern_id` | string | Frozen pattern family/version |
| `profile_slot` | integer/string | Stable source for synthetic attributes; never recomputed after reorder |
| `synthetic_attributes` | object | Age, squad, physiology, location, and other frozen properties |
| `effective_from` | ISO date | First date eligible for generation |
| `effective_to` | ISO date/null | Last eligible date; removal preserves history |
| `source_registry_hash` | SHA-256 | Registry evidence used when the profile was adopted |

Names needed in generated CSVs remain in the protected profile artifact, not in
the Delta/control ledger or status logs.

## AthleteState

Minimal state required to generate one athlete's next day.

| Field | Type | Rules |
|---|---|---|
| `athlete_id` | stable ID | Must match one frozen profile |
| `last_generated_date` | ISO date/null | Must equal the checkpoint date after commit |
| `fatigue` | number | Validated finite bounded value |
| `previous_complaint` | boolean | Explicit legacy behavior state |
| `active_complaint` | object/null | Stable complaint ID, start/end dates, area, cause, version |
| `recent_practiced_dates` | date array | Bounded to the generator's lookback window |
| `week_plan` | object/null | Complete Monday-Sunday plan and week-start key |
| `pending_events` | object array | Future-dated decisions not emitted yet |

Python `random.Random.getstate()`, a global session counter, registry index, and
invocation-relative day index are deliberately absent. Random streams and IDs
are derived from dataset version, athlete ID, absolute date, component name,
and per-day ordinal.

## StateCheckpoint

Immutable aggregate after-state for a committed date.

| Field | Type | Rules |
|---|---|---|
| `checkpoint_date` | ISO date | The committed simulation date |
| `dataset_version` | string | Required exact match |
| `athletes` | map | Stable athlete ID to `AthleteState`, sorted canonically |
| `pending_event_count` | integer | Must equal all queued entries |
| `checkpoint_sha256` | SHA-256 | Hash over canonical content excluding this field |

The next generation transition takes exactly this checkpoint as its before-
state. Inactive athletes may be retained for audit but are not advanced after
their `effective_to` date.

## DailyGeneration And GeneratedFile

A date-level materialization containing all rows whose actual event date equals
the partition date. An event decided earlier is emitted from the pending queue
only when due.

| Field | Type | Rules |
|---|---|---|
| `event_date` | ISO date | Partition key; CSV values still render `dd/mm/yyyy` |
| `forms` | map | Mapped form name to generated file metadata |
| `record_count` | integer | Sum of rendered records |
| `validation_summary` | object | Schema, routing, relation, ID collision, and distribution checks |

Each `GeneratedFile` records relative path, form name, schema hash, row count,
byte count, and SHA-256. A lightweight daily statistics file is allowed. Plotly
HTML is a separate periodic/report artifact.

## DailyCommitManifest

The commit marker written only after every other artifact validates.

| Field | Type | Rules |
|---|---|---|
| `event_date` | ISO date | Exactly previous committed date plus one |
| `previous_manifest_sha256` | SHA-256/null | Null only for the initial checkpoint |
| `before_state_sha256` | SHA-256 | Must equal prior checkpoint hash |
| `after_state_path` | relative path | Must remain under the dataset root |
| `after_state_sha256` | SHA-256 | Must match checkpoint content |
| `generated_files` | array | Complete `GeneratedFile` set in canonical order |
| `dataset_config_sha256` | SHA-256 | Must match `DatasetVersion` |
| `roster_snapshot_sha256` | SHA-256 | Exact effective roster used for this date |
| `validation_status` | enum | Must be `passed` to commit |
| `manifest_sha256` | SHA-256 | Canonical manifest hash |

Attempt IDs, wall-clock timestamps, host names, and Databricks run IDs belong in
separate audit/index records and are excluded from the deterministic daily
manifest. This is required for one-shot, resumed, local, and Databricks runs to
produce the same manifest fingerprint.

### Generation State Transitions

```text
ABSENT -> STAGED -> VALIDATED -> COMMITTED
             |          |
             +--------> FAILED
```

- `STAGED`, `VALIDATED`, and `FAILED` attempts are never authoritative.
- `COMMITTED` is immutable.
- A repeat with the same hash is a no-op; a different hash is a conflict.
- An interior missing/corrupt commit followed by later commits is `CORRUPT_CHAIN`
  and cannot be filled as an ordinary gap.

## DailyUploadPlan

Existing immutable connector upload-plan schema plus the daily lineage needed by
the caller.

| Field | Type | Rules |
|---|---|---|
| `operation` | enum | Event insert only |
| `environment` | enum | Must be verified `sandbox` |
| `target_url` | URL | Exact normalized URL containing reviewed `/sandbox` path |
| `event_date` | ISO date | One daily scope only |
| `daily_manifest_sha256` | SHA-256 | Binds generated source |
| `scopes` | array | Stable athlete IDs, forms, fields, and exact date |
| `prepared_records` | array | Existing canonical prepared payload rows |
| `affected_count` | integer | `1..500` per child |
| `batch_size` | integer | `1..100` |
| `canonicalization_version` | string | Exact read-back comparison policy |
| `plan_sha256` | SHA-256 | Existing immutable plan fingerprint |

One date may require several child plans. Every child for that date is either
included in an authorized publication bundle or none is executed.

## PublicationBundle

One reviewed, bounded, ordered authorization scope for the earliest contiguous
ready prefix.

| Field | Type | Rules |
|---|---|---|
| `bundle_id` | string | Immutable identifier |
| `start_date` / `end_date` | ISO date | Contiguous daily interval |
| `target_url` | URL | Same verified sandbox for every child |
| `children` | array | Relative path, full SHA-256, count, date, and sequence |
| `date_count` | integer | `1..90` |
| `child_plan_count` | integer | Must equal child list length |
| `affected_count` | integer | Must equal child totals and be `<=25,000` |
| `bundle_sha256` | SHA-256 | Binds exact ordered scope |

The expected confirmation is derived from this plan, for example
`UPLOAD 2500 RECORDS IN 5 PLANS f59c0e`; it is never accepted from a flag,
environment variable, notebook parameter, or agent.

## PublicationRecord

Append-only, redacted outcome lineage. It never changes generation commits.

| Field | Type | Rules |
|---|---|---|
| `event_date` | ISO date | Daily status key |
| `daily_manifest_sha256` | SHA-256 | Source generation |
| `bundle_sha256` | SHA-256/null | Authorizing master |
| `child_plan_hashes` | array | Exact attempted children |
| `scope_snapshot_sha256` | SHA-256 | Fresh pre-execution read evidence, recorded without changing the immutable bundle |
| `status` | enum | State below |
| `accepted_count` | integer | Connector-classified count only |
| `unknown_count` | integer | Must be visible when nonzero |
| `response_summary` | object | Redacted status/attempt metadata, no payload values |
| `created_at` | UTC timestamp | Audit ordering |

### Publication State Transitions

```text
UNPLANNED
  ├──> READ_UNCERTAIN --------------------------> BLOCKED
  ├──> UNEXPECTED_NONEMPTY ---------------------> BLOCKED
  ├──> MATCHING_WITH_LINEAGE -------------------> RECONCILED
  └──> READY -> AWAITING_HUMAN -> IN_PROGRESS
                                      ├──> RECONCILED
                                      ├──> ACCEPTED_UNVERIFIED -> RECONCILE_REQUIRED
                                      ├──> PARTIAL_OR_UNKNOWN -> RECONCILE_REQUIRED
                                      └──> RECONCILIATION_MISMATCH -> BLOCKED
```

Only `RECONCILED` is terminal success. No mutation state automatically returns
to `READY`. A reviewed continuation after a known partial parent uses a new
remainder plan, fresh snapshot, preview, and confirmation; an unexplained subset
without parent lineage is a conflict.

## Databricks Control Ledger

The optional managed Delta table is an index/coordination layer with one row per
dataset version and event date. It stores hashes, relative paths, aggregate
counts/statuses, Databricks run ID, and audit timestamps—never names, generated
row values, credentials, or raw API responses. A conditional `MERGE` claims or
commits a date. Immutable Volume manifests remain the content authority.

Recommended key: `(dataset_version, event_date)`. Required constraints are one
terminal generation commit per key and no transition out of a terminal
publication result except by appending a new reconciliation record.
