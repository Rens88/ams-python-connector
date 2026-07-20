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

### 1. Mutation execution and example workflows now exist; broader workflow coverage is next

The repo now has:

- live client execution methods for event delete/insert/update/upsert and profile upsert
- dry-run plus confirm gating
- sandbox-only protection for live delete/modify operations
- auditable example workflows for:
  - replay: `examples/replay_form_entries.py`
  - delete-only: `examples/delete_form_entries.py`

The next gap is not basic mutation execution anymore. The next gap is extending
this pattern beyond the example single-athlete workflow into reusable fetch,
plan, delete, and upload orchestration for larger synthetic-data runs.

### 2. Synthetic-data workflow support is now a first-class requirement

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

Current status:

- roster fetching now has a normalized helper through `fetch_roster`
- missing `user_id` values can now be resolved from `username`, `email`, or `about`
- generalized event target grouping, deletion planning, and replace workflow helpers now exist

Still open:

- profile-oriented planning/fetch helpers beyond the current user roster helper
- generator-specific mapping from fetched roster data into synthetic-data inputs
- broader multi-form orchestration that ties fetch, generation, delete, and upload together end to end

### 3. Deletion behavior is now modeled beyond example workflows

The synthetic-data use case introduces a decision that is not fully encoded in
the current library:

- delete only overlapping records, or
- delete all target-form data for the selected athletes

This choice is now modeled in both the example workflows and the generalized
planning helpers through targeted deletion versus full-range delete mode.
What is still open is applying that planner to broader synthetic-data pipelines
that span more than the current event-record replacement path.

### 4. Packaging and cross-repo library use should be treated as a requirement

The user wants to be able to import this repository as a Python library from a
different repository. That means the project should be maintained as an
installable package, not just a collection of local scripts.

Current status:

- editable and regular local installs have been validated from an external consumer context
- README usage now documents that the distribution name is `ams-python-connector`
  while the import package is `ams_smartabase`

Remaining follow-up tasks for that goal:

- keep example scripts optional convenience entrypoints, not the only way to use functionality
- decide whether to narrow and stabilize the supported downstream import surface further
- consider adding an automated packaging/integration check so external-consumer validation does not stay manual

### 5. Write-input handling is still narrow

The guidance expects support for pandas data frames, CSV paths, and alternate ID
resolution (`about`, `username`, `email`), plus table-field behavior and
duplicate `user_id + start_date` splitting.

Current status:

- event/profile write paths now accept:
  - sequences of mappings
  - CSV paths
  - DataFrame-like objects supporting `to_dict("records")`
- client write calls can optionally resolve missing `user_id` values through
  Smartabase lookups using `username`, `email`, or `about`

Still not implemented:

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

1. Add table-field row grouping and duplicate event splitting for richer write inputs.
2. Extend roster/profile fetch helpers for generator-specific athlete selection inputs.
3. Add a broader sandbox-safe end-to-end workflow that ties fetch -> generate -> delete -> upload together.
4. Add opt-in live integration tests for the workflow above.

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
