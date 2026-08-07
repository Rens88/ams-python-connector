<!--
Sync Impact Report
Version change: 1.0.0 -> 1.1.0
Modified principles (this amendment):
- IV. Explicit Confirmation For Live Mutation — added the HUMAN-mode
  create-only exception (tiered safety modes, specs/001-api-safety-modes/spec.md;
  issue #5). Update/upsert/replace/overwrite/archive/delete keep the full
  typed-phrase requirement in every mode, unchanged.
Templates requiring updates (this amendment):
- RISK_MODEL.md Category C (done, same PR)
- AGENTS.md (done, same PR — agent may draft an AUTO qualification only under
  active human supervision, never invoke or approve AUTO itself)
Follow-up TODOs (this amendment):
- The AUTO-mode runner-identity binding mechanism (specs/001-api-safety-modes/spec.md)
  is implemented as a first proposal and is explicitly flagged for maintainer
  decision, not treated as settled by this amendment.

---
Version change: unversioned -> 1.0.0
Modified principles:
- Python-Only Runtime -> I. Python-Only Runtime
- Safety First -> III. Safe Defaults And Dry-Run-First Mutation Workflows
- Safety First -> IV. Explicit Confirmation For Live Mutation
- Safety First -> V. Destructive Production Behavior Is Restricted
- Credentials And Data Protection -> X. No Committed Credentials Or Athlete Data
- Auditability -> VI. Auditable Operations
- Evidence-Based Changes -> IX. Automated Tests For Behavior Changes
- Maintainable Boundaries -> VII. Library-First Design
- Compatibility With Care -> VIII. Stable Public Interfaces
Added principles:
- II. Direct AMS/Smartabase API Use
- XI. Small, Reviewable Pull Requests
- XII. Documentation Updated Alongside Behavior Changes
Added sections:
- Operational Constraints
- Development Workflow
- Governance
Removed sections:
- None
Templates requiring updates:
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
- ✅ .agents/skills/speckit-tasks/SKILL.md
- ✅ .agents/skills/speckit-specify/SKILL.md
- ✅ .agents/skills/speckit-*/SKILL.md reviewed; no other updates required
- ✅ README.md, PROJECT_AIMS.md, CONTRIBUTING.md, docs/roadmap.md, and agent-docs reviewed; no updates required
Follow-up TODOs:
- None
-->
# AMS Python Connector Constitution

## Core Principles

### I. Python-Only Runtime

Runtime functionality MUST execute from Python without requiring R, Rscript, or
the `smartabaseR` package. Historical R code may remain as reference material,
but production behavior MUST NOT shell out to R or require users to install R
packages.

Rationale: the connector exists as a Python dependency, and runtime dependence
on the legacy R connector would make packaging, testing, and downstream use
less reliable.

### II. Direct AMS/Smartabase API Use

Production functionality MUST call AMS/Smartabase APIs directly from Python
through explicit HTTP behavior or well-scoped Python client abstractions. The
project MAY use public Smartabase documentation and legacy connector behavior as
reference material, but it MUST NOT make the legacy connector the execution path
for production behavior.

Rationale: direct API use keeps behavior inspectable, testable, and controlled
inside this repository.

### III. Safe Defaults And Dry-Run-First Mutation Workflows

Workflows that write, update, upsert, replace, import, or delete AMS data MUST
default to read-only or dry-run behavior. Mutation planning MUST produce
inspectable intent before any live API mutation occurs. A feature that changes
mutation behavior MUST preserve dry-run-first operation unless the constitution
is amended first.

Rationale: AMS data changes can affect real athlete records, so accidental live
execution must be hard to trigger.

### IV. Explicit Confirmation For Live Mutation

Live mutation MUST require explicit confirmation separate from credentials and
separate from choosing mutation parameters. Confirmation MUST be visible in the
public workflow or API surface that initiates the live operation.

**HUMAN-mode exception (added with the tiered safety modes feature, see
`specs/001-api-safety-modes/spec.md`):** for create-only writes to a distinct,
non-colliding destination scope, a single explicit yes/no decision MAY replace
an operation-specific typed phrase, provided that decision is made in a real
interactive terminal session (verified by the runtime, not merely claimed) and
is requested only after the complete immutable operation plan has been shown.
This exception applies to create-only writes exclusively; update, upsert,
replace, overwrite, archive, and delete retain the full typed-phrase
requirement in every mode, with no exception.

Rationale: valid credentials prove access, not intent. Live mutation needs an
independent user decision at execution time. The HUMAN-mode exception trades
phrase-typing friction for a stronger guarantee — a verified live human
terminal session — for the one operation class (create-only, to a separate,
checked destination) where a mistake is a duplicate row rather than lost or
altered data.

### V. Destructive Production Behavior Is Restricted

Destructive production behavior MUST be treated as high risk. Broad production
deletion MUST NOT be exposed through normal public workflows. Any change that
weakens production destructive-operation safeguards MUST receive explicit design
review, documented safety rationale, and focused tests before merge.

Rationale: production deletion is irreversible in practical terms and has a
higher duty of care than ordinary data retrieval or dry-run planning.

### VI. Auditable Operations

Read and mutation workflows MUST preserve enough non-secret metadata to
reconstruct what was requested, what was planned, what was executed, and what
the AMS/Smartabase API returned. Audit artifacts MUST redact secrets and avoid
committing real athlete data.

Rationale: auditability supports debugging, review, recovery, and responsible
handling of sensitive workflows.

### VII. Library-First Design

Reusable behavior MUST live in the Python package before it is exposed through
examples, scripts, or agent workflows. Examples and scripts MUST demonstrate
library APIs rather than becoming the only implementation of important
behavior.

Rationale: downstream users need a stable installable library, and duplicated
script logic is harder to test and maintain.

### VIII. Stable Public Interfaces

Public import paths, documented method names, result shapes, command flags, and
operation artifact schemas MUST be changed deliberately. Backward-incompatible
changes MUST be documented, reviewed, and justified; compatibility aliases MAY
exist when they reduce migration risk, but new primary APIs MUST use explicit
Python names.

Rationale: this connector is intended for use from other repositories, so API
churn creates avoidable downstream breakage.

### IX. Automated Tests For Behavior Changes

Every behavior change MUST include automated tests at the appropriate level.
Default tests MUST run offline without live Smartabase credentials. Live
integration tests MUST be opt-in and guarded so they cannot run accidentally
against unsafe environments.

Rationale: automated evidence is the minimum standard for changing data access,
payload construction, mutation safety, credential handling, or public
interfaces.

### X. No Committed Credentials Or Athlete Data

Real credentials, passwords, access tokens, fetched AMS data, generated athlete
data, operation outputs, and unredacted fixtures MUST NOT be committed.
Documentation, examples, tests, fixtures, and manifests MUST use placeholders,
synthetic data, or reviewed redacted examples.

Rationale: the repository must not leak secrets or sensitive athlete
information through source control.

### XI. Small, Reviewable Pull Requests

Pull requests MUST be focused, reviewable, and scoped to a coherent behavior or
documentation change. Changes that affect mutation, deletion, credentials,
endpoint behavior, public interfaces, or audit artifacts MUST call out safety,
testing, compatibility, and documentation impacts during review.

Rationale: smaller reviews make high-risk behavior easier to reason about and
reduce the chance of mixing governance-sensitive changes with unrelated churn.

### XII. Documentation Updated Alongside Behavior Changes

Behavior changes MUST update relevant user, maintainer, and agent-facing
documentation in the same change set. Documentation MUST distinguish durable
principles, desired aims, implementation status, and temporary work items in
their appropriate files.

Rationale: users and maintainers need current guidance, especially for safety
rules and public interfaces.

## Operational Constraints

The project runtime is Python-only and direct AMS/Smartabase API access is the
approved production integration pattern. Credentials and sensitive AMS data MUST
remain outside source control. Generated artifacts MAY be written locally when
needed for auditability, but committed examples and fixtures MUST be synthetic
or redacted.

Mutation workflows MUST start with dry-run planning and MUST require explicit
confirmation before live execution. Destructive production changes require
heightened review and MUST NOT be normalized as routine workflows.

## Development Workflow

Feature specifications, plans, tasks, pull requests, and reviews MUST check
constitution compliance before implementation or merge. Behavior-changing work
MUST include automated tests, documentation updates, and public-interface impact
notes where applicable.

Pull requests MUST stay small enough for reviewers to inspect safety,
auditability, compatibility, testing, and documentation effects. Temporary work
items belong in roadmap or handoff documents, not in this constitution.

## Governance

This constitution supersedes conflicting project practices and templates.
Amendments MUST be proposed as documentation changes that explain the rationale,
safety impact, and migration or review implications. Changes that weaken
mutation safeguards, destructive-production restrictions, credential/data
protection, or public-interface stability require explicit maintainer review
before merge.

Versioning follows semantic versioning for governance changes:

- MAJOR: backward-incompatible principle removals or redefinitions.
- MINOR: new principles, new governance sections, or materially expanded
  obligations.
- PATCH: clarifications, wording improvements, and non-semantic refinements.

Compliance review is required during specification, planning, task generation,
implementation review, and pull request review. A work item that cannot satisfy
a MUST-level principle is blocked until the work changes or this constitution is
amended.

**Version**: 1.1.0 | **Ratified**: 2026-07-27 | **Last Amended**: 2026-08-07
