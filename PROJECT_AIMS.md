# Project Aims

This repository should become a Python-only connector for Teamworks AMS. It exists so users can work with Teamworks AMS data from Python without needing the older R connector at runtime.

The legacy R scripts and `smartabaseR` behavior remain useful reference material, but the production library should call the Teamworks AMS API directly from Python.

## Governing Safety Model

The project aims define what the repository is intended to achieve. [`RISK_MODEL.md`](RISK_MODEL.md) defines the risks, trigger scenarios, safeguards, and agent behavior that govern how those aims may be implemented.

Every implementation, test, example, or documentation change must:

1. Reference one or more project aim IDs.
2. Review the corresponding section of `RISK_MODEL.md`.
3. Preserve or add the required safeguards.
4. Apply the highest risk level when multiple aims are involved.

A project aim is not complete merely because the underlying API behavior works. It is complete only when the relevant safeguards, tests, and documentation are also in place.

## Primary Goal

Build a safe, well-documented Python package that lets authenticated users discover Teamworks AMS terminology, fetch Teamworks AMS data, upload new data, and, where explicitly permitted, modify or delete existing Teamworks AMS data.

The connector should be usable as an installable Python library from other repositories and should include runnable, safe-by-default examples for common workflows.

## Responsibility Boundaries

The Python connector is a generic communication layer over the Teamworks AMS
API. It exposes clear, inspectable operations and results, but does not decide
whether a caller is interactive or scheduled, choose a destination form, or
embed organization-specific conventions.

Interactive workflows built on the connector own their user-facing preview and
human-confirmation experience. Scheduled workflows are also outside the
connector: they must not modify or delete existing AMS data. When a scheduled
workflow creates derived data, it should preserve the source data by writing to
a separate destination form by default; selecting that form and its naming
remains workflow policy. These boundaries do not weaken the dry-run and
explicit-confirmation requirements in the repository constitution.

## A. Discover Available Teamworks AMS Terminology

**Risk profile:** Low. See [Risk Model: Aim A](RISK_MODEL.md#a-discover-available-teamworks-ams-terminology).

Users need read-only discovery helpers before they can safely fetch or write data. The package should help them understand which identifiers and names Teamworks AMS expects.

- `A1` Athlete and group discovery: fetch information about athletes or groups of athletes, including Teamworks AMS user IDs and other available identifiers.
- `A2` Form and dataset discovery: fetch information about existing forms, profile forms, event forms, datasets, groups, and other terminology exposed by the API.
- `A3` Terminology usability: return results in Python-friendly structures that make it clear which IDs, names, and fields should be used in later fetch, upload, update, or delete calls.
- `A4` Discovery examples: provide examples showing how to inspect available athletes, groups, forms, and required metadata before running larger workflows.
- `A5` Discovery completeness: test pagination, empty and partial results, supported metadata categories, and ambiguity between similarly named resources.

## B. Pull Data From Teamworks AMS

**Risk profile:** Medium. See [Risk Model: Aim B](RISK_MODEL.md#b-pull-data-from-teamworks-ams).

Users should be able to retrieve Teamworks AMS data with precise filters, predictable output shapes, secure credential handling, and controlled local persistence.

- `B1` Single-athlete single-form pull: pull data for one athlete and one form.
- `B2` Multi-athlete multi-form pull: pull data for multiple athletes and multiple forms in one planned workflow.
- `B3` Event and profile exports: support event-form and profile-form data where the API allows it.
- `B4` Fetch filters: support date ranges, time ranges, user filters, group filters, form filters, and form-data filters where practical.
- `B5` Analysis-ready output: return both raw response information and flattened tabular data suitable for downstream Python analysis.
- `B6` Pull auditability: preserve enough non-secret metadata in results or manifests to make each pull auditable.
- `B7` Credential safety: require credentials to be supplied through environment variables, secret stores, or equivalent secure mechanisms; never rely on inline credentials.
- `B8` Data minimization and persistence: avoid unnecessary data retrieval, logging, caching, temporary files, or exports, and document any persistence that does occur.
- `B9` Agentic-use guardrails: ensure examples and agent guidance address deployment exposure, authentication, data scope, retention, and public access before generating applications that pull Teamworks AMS data.

## C. Push New Data To Teamworks AMS

**Risk profile:** High. See [Risk Model: Aim C](RISK_MODEL.md#c-push-new-data-to-teamworks-ams).

Users should be able to insert new data into Teamworks AMS through explicit, inspectable, safe-by-default Python workflows.

- `C1` Common write inputs: build event or profile import payloads from lists of dictionaries, CSV files, and dataframe-like objects.
- `C2` Athlete identifier resolution: resolve athlete identifiers from stable metadata such as `user_id`, username, email, or `about` where supported.
- `C3` Safe upload support: expose inspectable upload scope and appropriately redacted results so calling workflows can satisfy the required dry-run and explicit-confirmation safeguards for live writes.
- `C4` Upload examples: include examples for inserting one form, inserting multiple forms, and uploading data for multiple athletes.
- `C5` Preflight preview: display the target environment, athletes or groups, forms, fields, dates, and row count before live execution.
- `C6` Input validation: validate schemas, required fields, identifiers, value types, supported limits, and ambiguous mappings before submission.
- `C7` Duplicate and retry safety: define and test idempotency, duplicate prevention, batching, rate-limit handling, and partial-failure behavior.
- `C8` Human authorization: prevent coding agents and unattended workflows from supplying their own confirmation for live writes.

## D. Modify Or Delete Existing Data With Maximum Care

**Risk profile:** Critical. See [Risk Model: Aim D](RISK_MODEL.md#d-modify-or-delete-existing-data-with-maximum-care).

Modify, upsert, replace, overwrite, archive, and delete operations are inherently dangerous and must be designed around safety first. They belong in interactive workflows, not scheduled workflows. Production deletion is not an assumed project capability and requires a separate governance decision before implementation.

- `D1` Update and upsert workflows: support explicit update, upsert, and replace workflows while keeping live execution gated.
- `D2` Exact-ID deletion: where deletion is permitted, delete existing event data only by explicit Teamworks AMS event IDs gathered or supplied intentionally.
- `D3` Sandbox destructive testing: allow controlled destructive testing only in explicitly identified Teamworks AMS sandbox environments using synthetic or approved test data.
- `D4` Production deletion restriction: keep production deletion disabled by default and out of normal scope until maintainers explicitly approve and document it.
- `D5` Mutation auditability: save redacted operation configs, immutable plans, payload manifests, confirmation context, and response summaries for destructive or mutating workflows.
- `D6` Immutable preview-to-execution plan: ensure that the live operation executes exactly the scope that was previewed and confirmed.
- `D7` Typed confirmation: require an operation-specific typed phrase derived from the reviewed scope; reject generic approval.
- `D8` Visible impact summary: prominently display the environment, operation type, affected athletes or groups, forms or tables, fields, exact IDs, and record count. Use text and structure in addition to color.
- `D9` Scope limits and escalation: apply conservative limits and require stronger approval when a mutating or destructive operation exceeds them.
- `D10` Human-only approval: prevent an agent from independently executing, approving, typing, injecting, inferring, or bypassing the confirmation for a critical operation.
- `D11` Environment fail-closed behavior: treat an unknown or unverified environment as production and refuse destructive behavior when the required environment guarantees cannot be established.
- `D12` Recovery clarity: make reversibility, backup assumptions, partial execution, and recovery options explicit before execution.

## E. Documentation And Examples

**Risk profile:** Medium, with Critical implications for destructive operations. See [Risk Model: Aim E](RISK_MODEL.md#e-documentation-and-examples).

The repository should be easy to understand for future users, maintainers, contributors, and coding agents. Documentation and examples are part of the safety design because users and agents may execute or copy them directly.

- `E1` Human setup documentation: provide clear setup, installation, credential, and quick-start instructions.
- `E2` Usage examples: provide safe-by-default examples for discovery, pulling data, pushing new data, replacing data, and sandbox-only destructive testing.
- `E3` Terminology documentation: explain Teamworks AMS terminology such as athletes, groups, forms, datasets, event forms, profile forms, user IDs, event IDs, and field names.
- `E4` Safety documentation: explain dry-run mode, preview and confirmation gates, credential handling, local persistence, sandbox-only destructive behavior, and production restrictions.
- `E5` Maintainer handoff documentation: maintain a roadmap and agent-facing handoff notes showing what exists, what is incomplete, and what should come next.
- `E6` Co-located warnings: place relevant safeguards next to the code or example they govern rather than relying only on a distant safety document.
- `E7` Safe examples: prohibit inline credentials, live-write defaults, confirmation bypasses, and unlabeled environment assumptions.
- `E8` Independent-project disclosure: clearly state that this repository is not affiliated with, endorsed by, or maintained by Teamworks.
- `E9` Responsibility disclosure: explain that users remain responsible for authorization, privacy, security, policy compliance, and the consequences of their use.
- `E10` Agent navigation: ensure coding agents can find `PROJECT_AIMS.md`, `RISK_MODEL.md`, the roadmap, and other governance instructions from a clear agent-facing index or `AGENTS.md`.

## F. Package Usability And Distribution

**Risk profile:** Medium. See [Risk Model: Aim F](RISK_MODEL.md#f-package-usability-and-distribution).

The connector should work as a normal Python dependency, not only as scripts inside this repository. Safe internal distribution is sufficient for project success; publishing a public package to PyPI is optional.

- `F1` Installable package: support editable and regular installation from a checkout and other approved internal distribution methods.
- `F2` Stable import surface: expose a clear Python package import path and avoid unnecessary public API churn.
- `F3` Library-first examples: keep example scripts as demonstrations of reusable library functions, not as the only implementation of important behavior.
- `F4` Internal distribution first: make the package straightforward to distribute and use internally without requiring a public PyPI release.
- `F5` Public-release hygiene: ensure no credentials, private endpoints, real Teamworks AMS data, or sensitive operation artifacts are included in distributions.
- `F6` Safety-preserving API: ensure convenience functions and the public import surface cannot bypass dry runs, scope checks, environment verification, or required confirmations.
- `F7` Independent-project status: make clear in package metadata and documentation that the project is not affiliated with, endorsed by, or maintained by Teamworks.
- `F8` User responsibility: include an appropriate use-at-your-own-risk disclaimer while continuing to implement strong engineering safeguards.
- `F9` Agent skill evaluation: evaluate creating a dedicated skill for agentic coding with this package.
- `F10` Agent skill enforcement: if a dedicated skill is created, require supported agent workflows to use it and ensure that it applies `PROJECT_AIMS.md`, `RISK_MODEL.md`, and repository-level agent instructions.

## Success Criteria

The repository is successful when a user with valid Teamworks AMS credentials can:

- Inspect available athletes, groups, forms, fields, and identifiers.
- Pull data for one or many athletes and one or many forms without insecure credential handling or hidden local persistence.
- Upload new Teamworks AMS data from common Python data sources through a previewed, validated, explicitly confirmed workflow.
- Safely plan replacements or updates before execution.
- Perform destructive testing only in an explicitly verified sandbox under strict safeguards.
- Encounter production deletion as disabled by default unless a later governance decision explicitly permits it.
- Understand workflows, risks, and responsibilities from documentation and examples without reading the source code first.
- Install the package into another Python project and use it as a normal dependency.
- Use coding agents without allowing them to bypass safeguards or autonomously perform live high-risk or critical operations.
- Trace each implementation and pull request to stable project aim IDs and the corresponding risk requirements.

Implementation status for these aims is tracked in [docs/roadmap.md](docs/roadmap.md).
