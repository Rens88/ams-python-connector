# Current Work

This file is the current milestone and handoff note for coding agents. It should stay short and should not duplicate the long-term roadmap in [../docs/roadmap.md](../docs/roadmap.md).

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
3. Extend roster/profile fetch helpers for generator-specific athlete selection inputs.
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
- Generalized planning/workflow helpers exist: `build_event_write_targets`, `plan_event_deletions`, and `run_event_replace_workflow`.

Verification noted in the prior handoff:

- `python3 -m unittest discover -s tests -v`
- 61/61 tests passed at that time.

Run the current test suite again before claiming current verification.
