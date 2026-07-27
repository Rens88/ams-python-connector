# Project Aims

This repository should become a Python-only connector for Teamworks AMS/Smartabase. It exists so users can work with AMS data from Python without needing the older R connector at runtime.

The legacy R scripts and `smartabaseR` behavior remain useful reference material, but the production library should call the AMS/Smartabase API directly from Python.

## Primary Goal

Build a safe, well-documented Python package that lets authenticated users discover AMS terminology, fetch AMS data, upload new data, and, where appropriate, modify or delete existing AMS data.

The connector should be usable as an installable Python library from other repositories and should include runnable examples for common workflows.

## A. Discover Available AMS Terminology

Users need read-only discovery helpers before they can safely fetch or write data. The package should help them understand which identifiers and names AMS expects.

- `A1` Athlete and group discovery: fetch information about athletes or groups of athletes, including Smartabase user IDs and other available identifiers.
- `A2` Form and dataset discovery: fetch information about existing forms, profile forms, event forms, datasets, groups, and other terminology exposed by the API.
- `A3` Terminology usability: return results in Python-friendly structures that make it clear which IDs, names, and fields should be used in later fetch, upload, update, or delete calls.
- `A4` Discovery examples: provide examples showing how to inspect available athletes, groups, forms, and required metadata before running larger workflows.

## B. Pull Data From AMS

Users should be able to retrieve AMS data with precise filters and predictable output shapes.

- `B1` Single-athlete single-form pull: pull data for one athlete and one form.
- `B2` Multi-athlete multi-form pull: pull data for multiple athletes and multiple forms in one planned workflow.
- `B3` Event and profile exports: support event-form and profile-form data where the API allows it.
- `B4` Fetch filters: support date ranges, time ranges, user filters, group filters, form filters, and form-data filters where practical.
- `B5` Analysis-ready output: return both raw response information and flattened tabular data suitable for downstream Python analysis.
- `B6` Pull auditability: preserve enough metadata in results or manifests to make each pull auditable.

## C. Push New Data To AMS

Users should be able to insert new data into AMS through explicit, inspectable Python workflows.

- `C1` Common write inputs: build event/profile import payloads from lists of dictionaries, CSV files, and dataframe-like objects.
- `C2` Athlete identifier resolution: resolve athlete identifiers from stable metadata such as `user_id`, username, email, or `about` where supported.
- `C3` Safe upload execution: run in dry-run mode by default, require explicit confirmation for live writes, and save local operation artifacts.
- `C4` Upload examples: include examples for inserting one form, inserting multiple forms, and uploading data for multiple athletes.

## D. Modify Or Delete Existing Data With Maximum Care

Modify and delete operations are inherently risky and must be designed around safety first.

- `D1` Update and upsert workflows: support explicit update, upsert, and replace workflows while keeping live execution gated.
- `D2` Exact-ID deletion: delete existing event data only by explicit Smartabase event IDs gathered or supplied intentionally.
- `D3` Sandbox batch deletion: allow batch deletion in sandbox AMS environments for development, replay, and synthetic-data workflows.
- `D4` Production deletion restriction: treat production deletion as a nuclear option that is narrowly scoped, explicit, heavily confirmed, and impossible to trigger accidentally.
- `D5` Mutation auditability: save operation configs, payloads, manifests, and response summaries for destructive or mutating workflows.

## E. Documentation And Examples

The repository should be easy to understand for future users and future maintainers.

- `E1` Human setup documentation: provide clear setup, installation, credential, and quick-start instructions.
- `E2` Usage examples: provide examples for discovery, pulling data, pushing new data, replacing data, and sandbox deletion.
- `E3` Terminology documentation: explain AMS terminology such as athletes, groups, forms, datasets, event forms, profile forms, user IDs, event IDs, and field names.
- `E4` Safety documentation: explain dry-run mode, confirmation gates, sandbox-only destructive behavior, and production restrictions.
- `E5` Maintainer handoff documentation: maintain a roadmap and agent-facing handoff notes showing what exists, what is incomplete, and what should come next.

## F. Package Usability

The connector should work as a normal Python dependency, not only as scripts inside this repository.

- `F1` Installable package: support editable and regular installation from a checkout.
- `F2` Stable import surface: expose a clear Python package import path and avoid unnecessary public API churn.
- `F3` Library-first examples: keep example scripts as demonstrations of reusable library functions, not as the only implementation of important behavior.

## Success Criteria

The repository is successful when a user with valid AMS credentials can:

- Inspect available athletes, groups, forms, and identifiers.
- Pull data for one or many athletes and one or many forms.
- Upload new AMS data from common Python data sources.
- Safely plan replacements or updates before execution.
- Delete data only under strict safeguards, especially outside sandbox.
- Understand the workflow from documentation and examples without reading the source code first.
- Install the package into another Python project and use it as a normal dependency.

Implementation status for these aims is tracked in [docs/roadmap.md](docs/roadmap.md).
