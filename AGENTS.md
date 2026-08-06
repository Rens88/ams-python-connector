# AGENTS.md

This file is the repository entrypoint for coding agents. It summarizes required
workflow only; the linked governance documents are canonical.

## Startup And Close-Off

Startup and close-off summaries are explicit workflows. Do not infer permission
to run them from ordinary work requests.

If a prompt is only a greeting, or starts with a greeting and contains no
specific task, ask whether to run a startup summary and session handoff check
before doing so. Recognize greetings such as `Good morning`, `Hello`,
`Goedemorgen`, `Hi`, `Hey`, and equivalent greetings in any language.

For a confirmed startup summary, use read-only inspection and report:

- current branch, working-tree state, latest commit, and last five commits;
- uncommitted changes, especially changes that appear user-owned;
- active branch or PR status when available;
- current status and next work from [agent-docs/current-work.md](agent-docs/current-work.md),
  [docs/roadmap.md](docs/roadmap.md), and any active `specs/*` artifacts;
- unresolved governance or safety questions.

If a prompt is only a goodbye, ask whether to run the close-off summary before
doing so. Recognize goodbyes such as `tot de volgende`, `good evening`, `bye`,
`goed weekend`, `ciao`, and equivalent greetings in any language.

For a confirmed close-off summary, finish current work first, then report:

- completed work, changed files, and decisions made;
- validation commands and results, including `git diff --check` when files
  changed;
- remaining risks, blockers, and the first recommended next action;
- whether commits or pushes were requested, performed, skipped, or blocked.

Do not commit, push, reset, overwrite, or stage unrelated files unless the human
explicitly asks or a repository-specific workflow instruction requires it. Never
commit credentials, fetched AMS data, operation artifacts, or unrelated
user-owned changes.

When suggesting a durable implementation plan, record or update it in the
appropriate handoff location, currently [agent-docs/current-work.md](agent-docs/current-work.md)
or the active Spec Kit artifacts.

## Governance Hierarchy

Use these documents in this order when deciding what a change may do:

1. [PROJECT_AIMS.md](PROJECT_AIMS.md) defines what the repository is intended
   to achieve and provides stable aim IDs.
2. [RISK_MODEL.md](RISK_MODEL.md) defines risks, trigger scenarios,
   safeguards, and agent behavior that govern how aims may be implemented.
3. [.specify/memory/constitution.md](.specify/memory/constitution.md) defines
   permanent engineering principles and takes precedence over temporary plans,
   roadmap entries, handoff notes, and implementation details.
4. [docs/roadmap.md](docs/roadmap.md) and
   [agent-docs/current-work.md](agent-docs/current-work.md) describe
   implementation status and priorities, but may not override the aims, risk
   model, or constitution.
5. [agent-docs/implementation-guidance.md](agent-docs/implementation-guidance.md),
   [docs/connector-caller-diagnostics-boundary.md](docs/connector-caller-diagnostics-boundary.md),
   [CONTRIBUTING.md](CONTRIBUTING.md), Spec Kit files, and local examples guide
   execution within those higher-level constraints.

When instructions conflict, follow the safer and more restrictive
interpretation and explicitly report the conflict.

## Required Workflow For Every Change

Before implementing any code, test, example, documentation, or Spec Kit change:

1. Identify the applicable aim IDs from [PROJECT_AIMS.md](PROJECT_AIMS.md).
2. Read the corresponding sections of [RISK_MODEL.md](RISK_MODEL.md).
3. Determine the highest applicable risk level.
4. Identify relevant trigger scenarios.
5. Include required safeguards in the implementation plan.
6. Implement safeguards in code, tests, examples, and documentation where
   applicable.
7. Verify that the change does not weaken or bypass existing safeguards.
8. Report unresolved safety or governance questions instead of silently making
   permissive assumptions.

Mention the applicable aim IDs and highest risk level in the implementation
plan or final summary.

## Risk-Based Agent Behavior

Treat safeguards in [RISK_MODEL.md](RISK_MODEL.md) as design requirements, not
optional recommendations.

Agents must:

- default to read-only behavior, dry runs, previews, and sandbox environments;
- treat an unknown or unverified Teamworks AMS environment as production;
- use least privilege and minimize accessed or retained data;
- never place credentials in source code, notebooks, examples, logs, generated
  applications, or committed configuration;
- avoid unnecessary temporary files, caches, exports, notebook outputs, and
  sensitive logs;
- preserve auditability without storing credentials or unnecessary sensitive
  data;
- use stable identifiers rather than ambiguous names for write or delete
  operations;
- design retries so they cannot silently duplicate or repeat mutations;
- ensure previews and live operations use the same immutable operation plan;
- keep safeguards in convenience functions, examples, tests, and generated
  code;
- flag requests that conflict with repository safety requirements.

## High-Risk And Critical Operations

Agents may inspect, validate, prepare, preview, explain, and generate safe code
for mutating operations. An agent must never independently:

- authorize a live write;
- execute or approve a destructive operation;
- type, inject, infer, or programmatically provide a confirmation phrase;
- bypass a dry run, preview, environment check, scope limit, or confirmation
  gate;
- treat production deletion as an ordinary supported workflow;
- assume an environment is a sandbox;
- reduce typed confirmation to a generic `yes/no` prompt;
- conceal or understate the number or type of affected records.

For high-risk and critical operations, require a human-readable preview showing
the environment, operation, athletes or groups, forms or tables, fields, stable
IDs where relevant, and affected record count.

Critical operations require typed, operation-specific human confirmation. A
fresh confirmation is required whenever the planned scope changes. Production
deletion is out of scope unless repository governance explicitly permits it.

Agents must distinguish the generic connector from the calling workflow. Do
not add organization-specific destination-form conventions to the connector.
Interactive workflows own the required preview and human confirmation.
When changing validation, exceptions, warnings, mutation states, or suggested
remediation, apply the decision rules and preserve the dated decisions in
[docs/connector-caller-diagnostics-boundary.md](docs/connector-caller-diagnostics-boundary.md).
Scheduled workflows must not modify or delete existing AMS data; when they
create derived data, they should use a separate destination form by default to
preserve source data. Scheduling must never be used to bypass the
constitution's dry-run or explicit-confirmation requirements.

## Documentation And Examples

Documentation and examples are part of the safety boundary. They must:

- load credentials securely;
- default to read-only, dry-run, preview, or verified-sandbox behavior;
- clearly state environment assumptions;
- never demonstrate confirmation bypasses;
- explain relevant local persistence and cleanup;
- place warnings next to the operation they govern;
- state that the project is not affiliated with, endorsed by, or maintained by
  Teamworks;
- avoid implying that package use automatically guarantees authorization,
  security, privacy compliance, or organizational-policy compliance.

## Testing Expectations

Choose tests based on the highest applicable risk. Cover relevant safeguards for:

- safe defaults and missing credentials;
- pagination, incomplete discovery results, and ambiguous identifiers;
- payload and schema validation;
- environment verification and sandbox-versus-production behavior;
- dry-run behavior, preview accuracy, and immutable preview-to-live plans;
- confirmation mismatch and attempts to bypass confirmation;
- batch and scope limits;
- rate limiting, retries, duplicate behavior, partial success, and partial
  failure;
- sensitive logging or artifact leakage;
- consistency between documented and implemented safeguards.

A high-risk or critical feature is not complete until its safeguards are covered
by tests.

## Completion Checklist

Before considering work complete, verify:

- applicable aim IDs identified;
- highest risk level identified;
- trigger scenarios reviewed;
- required safeguards implemented;
- safeguards tested;
- documentation and examples remain safe by default;
- no credentials or unnecessary sensitive data are persisted;
- no agent-controlled approval path exists for live high-risk or critical
  operations;
- governance links and paths remain valid;
- open safety decisions are explicitly reported.
