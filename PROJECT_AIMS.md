# Project Aims

This repository should become a Python-only connector for Teamworks AMS/Smartabase. It exists so users can work with AMS data from Python without needing the older R connector at runtime.

The legacy R scripts and `smartabaseR` behavior remain useful reference material, but the production library should call the AMS/Smartabase API directly from Python.

## Primary Goal

Build a safe, well-documented Python package that lets authenticated users discover AMS terminology, fetch AMS data, upload new data, and, where appropriate, modify or delete existing AMS data.

The connector should be usable as an installable Python library from other repositories and should also include runnable examples for common workflows.

## Core Capabilities

### A. Discover Available AMS Terminology

Users need read-only discovery helpers before they can safely fetch or write data. The package should help them understand which identifiers and names AMS expects.

Required discovery workflows:

- Fetch information about athletes or groups of athletes, including Smartabase user IDs and other available identifiers.
- Fetch information about existing forms, profile forms, event forms, datasets, groups, and other terminology exposed by the API.
- Return results in Python-friendly structures that make it clear which IDs, names, and fields should be used in later fetch, upload, update, or delete calls.
- Provide examples showing how to inspect available athletes, groups, forms, and required metadata before running larger workflows.

### B. Pull Data From AMS

Users should be able to retrieve AMS data with precise filters and predictable output shapes.

Required fetch workflows:

- Pull data for one athlete and one form.
- Pull data for specific athletes and specific forms.
- Pull data for multiple athletes and multiple forms in one planned workflow.
- Support event-form and profile-form data where the API allows it.
- Support date ranges, time ranges, user filters, group filters, form filters, and form-data filters where practical.
- Return both raw response information and flattened tabular data suitable for downstream Python analysis.
- Preserve enough metadata in results or manifests to make each pull auditable.

### C. Push New Data To AMS

Users should be able to insert new data into AMS through explicit, inspectable Python workflows.

Required upload workflows:

- Build event/profile import payloads from lists of dictionaries, CSV files, and dataframe-like objects.
- Resolve athlete identifiers from stable metadata such as `user_id`, username, email, or `about` where supported.
- Run in dry-run mode by default so users can inspect payloads before sending them.
- Require explicit confirmation for live writes.
- Save local operation manifests and payload artifacts for audit and debugging.
- Include examples for inserting one form, inserting multiple forms, and uploading data for multiple athletes.

### D. Modify Or Delete Existing Data With Maximum Care

Modify and delete operations are inherently risky and must be designed around safety first.

Required safety model:

- Dry-run should be the default for update, replace, and delete workflows.
- Live mutation should require explicit user confirmation.
- Destructive operations should be auditable, with saved operation configs, payloads, manifests, and response summaries.
- Deletion should prefer exact Smartabase event IDs gathered by a preflight fetch rather than broad name/date/form filters.
- Sandbox AMS environments may allow batch deletion for development, replay, and synthetic-data workflows.
- Production AMS environments must not expose broad batch deletion through normal public workflows.
- In production, deletion should be treated as a nuclear option: if it exists at all, it should be narrowly scoped, explicit, heavily confirmed, and impossible to trigger accidentally.
- Existing safeguards that restrict live delete/modify behavior to sandbox URLs should remain a core design constraint unless the project deliberately changes that policy.

### E. Documentation And Examples

The repository should be easy to understand for future users and future maintainers.

Required documentation:

- Clear setup instructions for installing and using the package.
- Clear credential guidance that never encourages committing real secrets.
- Examples for discovery, pulling data, pushing new data, replacing data, and sandbox deletion.
- Explanations of AMS terminology such as athletes, groups, forms, datasets, event forms, profile forms, user IDs, event IDs, and field names.
- Examples for both simple single-athlete workflows and larger multi-athlete, multi-form workflows.
- Safety documentation explaining dry-run mode, confirmation gates, sandbox-only destructive behavior, and production restrictions.
- A roadmap or open-work document showing what exists, what is incomplete, and which implementation tasks should come next.

## Design Principles

- Python-only runtime: do not require R, Rscript, or `smartabaseR` at runtime.
- Direct API use: call AMS/Smartabase HTTP endpoints from Python.
- Safe by default: read-only and dry-run behavior should be the default posture.
- Explicit mutation: writes, updates, upserts, and deletes must be intentional and visible.
- Auditable workflows: local artifacts should make it possible to reconstruct what was planned and what was executed.
- Practical outputs: provide both raw API context and flattened data suitable for analysis.
- Library-first structure: examples should demonstrate the library, not contain the only implementation of important behavior.
- Compatibility where useful: mirror proven `smartabaseR` behavior where it helps users migrate, but prefer clear Python method names and Python data structures.

## Success Criteria

The repository is successful when a user with valid AMS credentials can:

- Inspect available athletes, groups, forms, and identifiers.
- Pull data for one or many athletes and one or many forms.
- Upload new AMS data from common Python data sources.
- Safely plan replacements or updates before execution.
- Delete data only under strict safeguards, especially outside sandbox.
- Understand the workflow from documentation and examples without reading the source code first.
- Install the package into another Python project and use it as a normal dependency.

## Relationship To Existing Repo Files

- `README.md` should remain the quick-start entrypoint.
- `AGENTS.python_connector.md` contains detailed implementation guidance for coding agents.
- `agent-docs/open-work.md` tracks current implementation gaps and handoff notes.
- `legacy_code/` contains R-based reference scripts, not runtime dependencies.
- `examples/` should contain runnable examples that demonstrate the library safely.
