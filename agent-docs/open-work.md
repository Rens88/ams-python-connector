# Open Work

This file is the current handoff document for the next implementation tasks in
this repository. Read it before starting new feature work.

## Current Direction

The immediate direction is no longer just generic `smartabaseR` parity. The next
major workflow to enable is a sandbox-safe synthetic-data pipeline:

1. Fetch athlete information so the system knows for which athletes synthetic
   data should be generated.
2. Generate synthetic data for those athletes.
3. Delete existing data for those athletes, either:
   - only records whose dates overlap with the newly generated data, or
   - all records for the affected athletes and forms.
4. Upload the generated data back into Smartabase.

The repository already contains example synthetic-data outputs and templates
under `use_case_examples/synthetic_data/`. In particular, use
`use_case_examples/synthetic_data/csv/athlete profile template 1777445810248.csv`
as a concrete reference for athlete-profile shape and metadata.

If future code changes need more detail about the synthetic generator, deletion
scope, form coverage, or required realism rules, ask the user for that
information explicitly before inventing behavior.

## Updated Status Of Open Work

### 1. Live mutation support is still the biggest functional gap

The repo can build payloads for insert, update, upsert, profile upsert, and
delete, but there are still no client methods that actually execute:

- `insert_event`
- `update_event`
- `upsert_event`
- `upsert_profile`
- `delete_event`

Those methods still need the dry-run, manifest, and explicit confirmation
workflow described in `AGENTS.python_connector.md`.

### 2. End-to-end operation runners are still missing

The repo still lacks a higher-level runner that can:

- create operation folders
- write payload artifacts
- persist raw API responses
- emit import/delete result manifests
- coordinate dry run versus confirmed execution

This is especially important for the synthetic-data workflow, because fetch,
delete, and upload should be auditable as a single run.

### 3. Synthetic-data workflow support is now a first-class requirement

The next workflow should support these phases cleanly:

- fetch athlete roster and identifying metadata from Smartabase
- select which athletes should receive synthetic data
- map those athletes into generator inputs
- generate form-specific CSV or row payloads
- determine deletion scope before upload
- delete overlapping or all targeted records
- upload the generated replacement data
- save run metadata so the workflow can be repeated or rolled forward safely

Likely implementation pieces:

- a fetch helper for athlete/user/profile metadata
- a planning step that resolves Smartabase `user_id` and relevant identifiers
- a deletion planner that can compute overlap windows by athlete and form
- an upload planner that maps generated CSV columns into Smartabase payloads
- a top-level workflow runner for sandbox execution

### 4. Deletion behavior needs workflow-level design

The synthetic-data use case introduces a decision that is not fully encoded in
the current library:

- delete only overlapping records, or
- delete all target-form data for the selected athletes

The library should model this choice explicitly rather than burying it inside
ad hoc scripts. The deletion mode should be obvious in manifests and operation
configs.

### 5. Write-input handling is still narrow

The guidance expects support for pandas data frames, CSV paths, and alternate ID
resolution (`about`, `username`, `email`), plus table-field behavior and
duplicate `user_id + start_date` splitting.

Current payload builders still accept only sequences of mappings and do not yet
implement:

- CSV ingestion helpers
- pandas integration
- alternate-ID resolution through Smartabase lookups
- table-field row grouping
- duplicate event splitting

These capabilities are needed for realistic synthetic-data imports.

### 6. Sync is still only partially implemented

The request builder and basic client method exist, but there is still no durable
handling of returned `new_sync_time` values. That matters for repeated fetch or
incremental synthetic refresh workflows.

### 7. Several parity features remain unimplemented

The following still look open:

- attachment download
- `include_all_cols`
- `include_missing_user`
- `include_uuid`
- `guess_col_type`
- caching
- deprecated wrapper compatibility for `pull_smartabase`
- deprecated wrapper compatibility for `push_smartabase`
- deprecated wrapper compatibility for `get_metadata_names`

Not all of these are equally urgent for the synthetic-data workflow. Prioritize
the ones that directly support fetch, delete, and upload orchestration.

### 8. Test coverage is better, but live integration coverage is still incomplete

The repo now has offline unit tests and live smoke-test entrypoints, but still
lacks a proper set of opt-in live integration tests for:

- login plus endpoint discovery
- user/group reads
- event/profile reads
- deletion in sandbox
- upload/update/upsert in sandbox
- fetch-delete-upload workflow orchestration

Live tests are allowed only through the normal credential-loading path and only
when the Smartabase URL contains `sandbox`. The agent must not inspect `.env`
directly.

### 9. Environment/tooling note

`pytest` is declared in dev dependencies, but the current working practice in
this repo is still `python -m unittest discover -s tests`. Keep that path
working unless the project explicitly standardizes on `pytest`.

## Suggested Next Implementation Order

1. Add client execution methods for delete and upload operations, behind dry-run
   and explicit confirmation gates.
2. Add CSV/data-frame ingestion helpers for write paths.
3. Add a roster-fetch helper for athlete selection and synthetic generator
   inputs.
4. Add a deletion planner that supports `overlap_only` versus `delete_all_for_targets`.
5. Add a sandbox-only end-to-end workflow runner for fetch -> delete -> upload.
6. Add opt-in live integration tests for the workflow above.

## Questions The Agent Should Ask When Needed

Ask the user for more detail before proceeding if any of these are unclear:

- Which Smartabase forms should be generated first?
- Should deletion happen by exact `event_id`, by fetched overlap window, or by
  full athlete/form wipe in sandbox?
- Which athlete identifiers are authoritative for generation: `user_id`,
  `about`, username, email, federation number, or personal code?
- Should profile data be regenerated as part of the workflow, or only event
  forms?
- What output format should the synthetic generator consume and emit?
- How should overlapping date windows be defined for each form?
