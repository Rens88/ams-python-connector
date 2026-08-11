# Artifact Contracts

## Store Layout

```text
STATE_ROOT/
└── datasets/DATASET_ID/VERSION/
    ├── dataset.json
    ├── profiles/athletes.json
    ├── inputs/
    │   ├── templates/...
    │   ├── roster/athletes.csv
    │   └── form-map.json
    ├── staging/ATTEMPT_ID/...
    ├── days/date=YYYY-MM-DD/
    │   ├── csv/...
    │   ├── validation.json
    │   ├── state.json
    │   └── manifest.json
    ├── publication/date=YYYY-MM-DD/
    │   ├── plans/CHILD_ID/operation_plan.json
    │   ├── snapshots/...
    │   └── records/...
    ├── bundles/BUNDLE_ID/master_upload_plan.json
    ├── reports/...
    └── audit/...
```

`days/.../manifest.json` is written last and is the only generation commit
marker. `execution_results.json` or its versioned successor is exclusively
created before the first live request and may not be reused.

## Store Protocol

The platform-neutral engine depends on this logical protocol:

```python
class StateStore(Protocol):
    def load_dataset(self, dataset_id: str) -> DatasetVersion: ...
    def scan_commits(self, dataset_id: str) -> Sequence[DailyCommitManifest]: ...
    def read_checkpoint(self, manifest: DailyCommitManifest) -> StateCheckpoint: ...
    def stage_day(self, attempt: StagedDay) -> StagedDayRef: ...
    def compare_and_commit(self, expected_head_hash: str | None, staged: StagedDayRef) -> DailyCommitManifest: ...
    def save_immutable_plan(self, plan: DailyUploadPlan) -> PlanRef: ...
    def reserve_publication(self, bundle: PublicationBundle) -> PublicationReservation: ...
    def append_publication_record(self, record: PublicationRecord) -> None: ...
```

Implementations:

- `FilesystemStateStore`: local path, exclusive lock, same-filesystem staging,
  exclusive commit marker, and compare-before-commit.
- `DatabricksStateStore`: immutable artifacts on a Unity Catalog Volume and
  conditional claim/commit in a managed Delta control table. The Delta row is
  an index/lease; the manifest hash remains authoritative.

If cross-process exclusivity cannot be demonstrated for a backend, that backend
is prepare-read-only and cannot commit or publish.

## Canonical Hashing

- SHA-256 lowercase hexadecimal.
- UTF-8 JSON, sorted object keys, compact separators, Unicode preserved.
- Dates are `YYYY-MM-DD`; timestamps are UTC RFC 3339 with a `Z` suffix.
- Paths stored in hashed plans are normalized relative paths beneath the
  immutable bundle/dataset root.
- Hash fields are omitted while their containing object is hashed.
- Operational timestamps, host/run IDs, and staging attempt IDs live in separate
  audit/index records and are excluded from deterministic content and plan
  fingerprints.
- Arrays retain semantic order. Set-like collections are sorted before encoding.
- Floating-point values use one documented finite decimal encoding; NaN and
  infinity are invalid.
- Every schema and row canonicalization policy has an explicit version. A policy
  change cannot reinterpret an already signed plan.

## Daily Commit Sequence

1. Acquire/claim `(dataset_version, event_date)` against the expected prior head.
2. Write all output, validation, and after-state files to a unique staging path.
3. Re-open and validate schemas, counts, relationships, routing, IDs, and hashes.
4. Build a manifest binding prior manifest, before/after states, files, inputs,
   versions, and validation.
5. Copy/move immutable content to the final date partition.
6. Create the final manifest exclusively.
7. Commit the final path/hash to the control ledger when that adapter is used.
8. Release the claim. Orphan staging is diagnostic and never authoritative.

A crash before step 6 leaves no committed date. A crash after step 6 is
recoverable by rebuilding the ledger/index from the manifest chain.

## Remote Scope Snapshot

A read-only snapshot binds:

- normalized exact sandbox URL and environment verification evidence;
- requested date interval, stable user IDs, event form names, and fields;
- connector/request schema version and pagination/completeness evidence;
- per-date/form/athlete result counts and canonical row-multiset hashes;
- zero-result scopes explicitly, not by omission;
- timestamp and redacted response/request metadata.

Raw credentials and unnecessary raw event values are excluded. If stable athlete
attribution, pagination completeness, or any requested zero-result scope cannot
be proven, classification is `READ_UNCERTAIN`.

## Upload Plan Compatibility

The pipeline extends rather than replaces the existing immutable upload-plan
contract. Existing plan hash, prepared payload, exact target, batch, confirmation,
execution-reservation, and mutation-state rules remain authoritative. New daily
lineage fields are versioned and included in the hash.

Allowed operation: event insert.

Disallowed operations: profile import, event update/upsert/replace, overwrite,
archive, and delete.

## Publication Bundle Validation

Before confirmation and again before each child:

- resolve every relative child path beneath the bundle directory;
- validate full child hash and affected count;
- validate strictly increasing child sequence and nondecreasing event date;
- validate one exact sandbox target and event-only operations;
- validate all child execution results are absent/unconsumed;
- validate date count `<=90`, total records `<=25,000`, child records `<=500`,
  and request batches `<=100`;
- verify the fresh remote snapshot covers the exact bundle scope and remains
  empty for new dates; and
- reserve the master and child execution records before the first mutation.

The earliest blocked unpublished date terminates the ready prefix. Later dates
are not added to a bundle around it.

## Secret And Data Classification

| Artifact | Contains athlete data | Contains credentials | Source-control eligible |
|---|---:|---:|---:|
| Dataset/profile/generated CSV/checkpoint | Yes | Never | No |
| Prepared upload payload/remote snapshot | Yes or sensitive metadata | Never | No |
| Daily/master plan and execution result | Potentially | Never | No |
| Delta/control ledger | Aggregate identifiers/hashes only | Never | No |
| Synthetic/redacted schema fixtures | Reviewed synthetic only | Never | Yes |
| Documentation | Placeholders only | Never | Yes |

Local stores require restrictive permissions and existing ignore rules.
Databricks stores require least-privilege Unity Catalog grants. Retention and
cleanup are explicit operator policies; cleanup must never delete AMS records.
