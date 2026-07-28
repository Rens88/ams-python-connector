# Risk Model

## Purpose

This document defines the safety and misuse risks associated with the project aims in [`PROJECT_AIMS.md`](PROJECT_AIMS.md).

It is normative for the design, implementation, documentation, testing, and review of this repository. Contributors and coding agents must identify which project aim an intended change supports, review the corresponding risks in this document, and design safeguards before implementing the change.

This risk model does not replace organizational privacy, information-security, legal, or Teamworks AMS access policies. Users remain responsible for ensuring that their use of the connector and the data they access is authorized and appropriate.

## How To Use This Document

For every proposed change:

1. Identify the relevant project aim IDs.
2. Review the applicable risk level, trigger scenarios, and required safeguards.
3. Include the safeguards in the design, implementation, tests, examples, and documentation.
4. Escalate uncertainty rather than silently reducing or bypassing a safeguard.
5. Treat the highest applicable risk level as controlling when a change supports multiple aims.

Coding agents must not treat confirmation prompts, dry-run behavior, environment checks, scope limits, audit artifacts, or credential protections as optional usability details. They are safety requirements.

## Risk Levels

| Level | Meaning |
|---|---|
| **Low** | Primarily read-only or informational behavior. Failure is usually recoverable, but incomplete results or unintended metadata exposure can still cause harm. |
| **Medium** | Behavior can expose sensitive data, credentials, or local artifacts, or can encourage unsafe downstream processing. |
| **High** | Behavior can create or change Teamworks AMS data at meaningful scale. Mistakes may affect many athletes, forms, or records. |
| **Critical** | Behavior can destructively modify, overwrite, replace, or delete existing data. Consequences may be difficult or impossible to reverse. |

Risk levels describe the highest credible impact, not the expected frequency of failure.

## Cross-Cutting Safety Principles

The following principles apply across all project aims:

- **Least privilege:** request and use only the access and data needed for the task.
- **Explicit scope:** make the target environment, athletes, groups, forms, fields, records, and date ranges visible before an operation.
- **Safe defaults:** default to read-only behavior, dry runs, previews, and non-production environments.
- **Human control:** a coding agent may prepare and explain a mutating operation, but must not autonomously approve or execute a high-risk or critical operation.
- **Credential hygiene:** credentials must not be embedded in source code, notebooks, examples, logs, generated applications, or committed configuration.
- **Data minimization:** avoid fetching, retaining, logging, caching, or exporting data that is not needed.
- **Auditability:** retain enough non-secret context to understand what was requested, what scope was selected, and what the API reported.
- **Environment clarity:** never infer that an environment is a sandbox. Treat an unknown environment as production until it is explicitly and reliably identified.
- **No safeguard bypasses:** examples, tests, convenience wrappers, and agent-generated code must not bypass the protections required for normal use.
- **Honest limitations:** the package must not imply that using it automatically makes a workflow secure, privacy-compliant, authorized, or endorsed by Teamworks.

---

## A. Discover Available Teamworks AMS Terminology

**Related aims:** `A1`-`A5`
**Risk level:** Low

### Why This Risk Exists

Discovery helpers are read-only and mainly retrieve metadata, but metadata may still reveal internal structure, identifiers, group membership, form names, field names, or permission-related information. Incomplete or misleading discovery results can also cause later read or write operations to target the wrong resources.

### Trigger Scenarios

- A discovery call returns only part of the available metadata, and a user assumes the result is complete.
- Different metadata types or pagination modes are handled inconsistently.
- Internal identifiers, athlete or group relationships, form names, or field names are printed or logged more broadly than intended.
- A discovery helper exposes secrets, authorization headers, or raw diagnostic details.
- A user selects a similarly named athlete, group, form, or field because the output does not make identifiers and resource types clear.
- An agent proceeds to a later operation without first resolving ambiguous names to stable identifiers.

### Required Safeguards

Implementations and tests must:

- Test completeness, pagination, empty results, partial responses, and the supported metadata categories.
- Clearly distinguish names, stable identifiers, resource types, and environments.
- Avoid logging credentials, authorization headers, or unnecessary response content.
- Make uncertainty and incomplete discovery visible to the caller.
- Prefer stable IDs over ambiguous display names for later operations.
- Provide examples that inspect and verify discovered targets before using them in read or write workflows.
- Treat discovery output as sensitive when it reveals athlete, group, form, or organizational structure.

---

## B. Pull Data From Teamworks AMS

**Related aims:** `B1`-`B9`
**Risk level:** Medium

### Why This Risk Exists

Read access enables useful analysis, but it also makes it easy to copy sensitive Teamworks AMS data into less controlled environments. Generated applications, notebooks, temporary files, caches, logs, exports, and public deployments can expose athlete or organizational data. The package may appear authoritative, causing users to assume that any enabled workflow is automatically safe or compliant.

### Trigger Scenarios

- A coach uses an AI coding agent to create an application and embeds Teamworks AMS credentials directly in the source code.
- The generated application is deployed publicly without adequate authentication or authorization.
- The application repeatedly pulls data and makes the results publicly accessible.
- Sensitive data is downloaded or processed on a shared or public computer, such as a library computer.
- Temporary files, caches, notebook outputs, logs, crash reports, or browser downloads remain after the task.
- A broad or incorrect filter retrieves more athletes, groups, forms, fields, or dates than intended.
- Raw API responses contain more sensitive information than the flattened output the user expected.
- Audit artifacts accidentally contain credentials or full sensitive datasets.
- Users assume that the connector guarantees privacy, policy compliance, or authorization for downstream processing.

### Required Safeguards

Implementations, documentation, and examples must:

- Use environment variables, secret stores, or equivalent secure injection for credentials.
- Never include inline credentials in examples, tests, generated applications, or committed files.
- Fail clearly when required credentials are unavailable; do not introduce insecure credential fallbacks.
- Prefer in-memory processing and avoid local persistence unless it is explicit and necessary.
- Document any caching, temporary-file, export, logging, or audit-artifact behavior.
- Minimize retained data and provide cleanup guidance where local artifacts are created.
- Require precise filters where practical and make the requested scope inspectable.
- Make broad pulls visible, especially when many athletes, groups, forms, fields, or dates are involved.
- Avoid printing sensitive data by default.
- Separate non-sensitive request metadata from sensitive response data in audit artifacts.
- Explain that users are responsible for authorization, secure deployment, privacy, and organizational-policy compliance.
- Include agent-facing guardrails that prompt users to consider credentials, deployment exposure, data scope, retention, and access controls before generating an application.

### Agent Behavior

Before generating code that pulls Teamworks AMS data, an agent must:

1. Identify where credentials will come from.
2. Establish the intended environment and deployment context.
3. Minimize the requested data scope.
4. Warn when the proposed design may persist, publish, cache, or log sensitive data.
5. Avoid presenting a public-facing application as safe without an explicit access-control design.
6. Ask for human review when the user appears unaware of the privacy or deployment consequences.

---

## C. Push New Data To Teamworks AMS

**Related aims:** `C1`-`C8`
**Risk level:** High

### Why This Risk Exists

Create operations can add incorrect, duplicated, malformed, or excessive data. A wrong athlete mapping, form mapping, environment, filter, or payload can affect many records and may require difficult cleanup. Large uploads can also overload or spam the Teamworks AMS API.

### Trigger Scenarios

- A payload targets the wrong athlete, group, form, field, or environment.
- A user unintentionally uploads hundreds or thousands of rows.
- A retry or repeated agent action creates duplicate records.
- Malformed values are accepted but have a different meaning than intended.
- A broad batch request places avoidable load on the API.
- A generated workflow immediately performs a live write without first showing a preview.
- A user repeatedly accepts generic confirmation prompts without understanding the scope.
- Local operation artifacts retain sensitive payload data or credentials.
- An agent interprets an ambiguous instruction and chooses the affected records without human verification.

### Required Safeguards

Create workflows must:

- Default to dry-run or validation-only behavior.
- Resolve and display the target environment, athletes or groups, forms, fields, record count, and relevant date range before execution.
- Validate payload schemas, required fields, identifiers, value types, and supported limits.
- Detect or clearly address duplicate and retry behavior.
- Use bounded batches, rate-limit handling, and retry behavior that does not duplicate writes.
- Display a human-readable preview and summary before live execution.
- Require explicit, separate confirmation for live execution.
- Use stronger confirmation when the operation is unusually broad or ambiguous.
- Produce an operation manifest and response summary without recording secrets.
- Make partial success and partial failure visible and recoverable.
- Never let a coding agent supply its own approval for a live write.

A confirmation must describe the concrete operation. A generic `yes/no` prompt is insufficient for a large or unusual write.

Example:

```text
Environment: production
Action: create records
Athletes affected: 73
Forms affected: Wellness
Rows to submit: 842

Type CREATE 842 ROWS to continue:
```

### Testing Expectations

Tests should cover:

- Dry-run as the default.
- Schema and identifier validation.
- Duplicate prevention or documented idempotency behavior.
- Batch limits and rate-limit responses.
- Partial failure.
- Confirmation mismatch.
- Attempts to bypass confirmation.
- Sandbox and production environment handling.

---

## D. Modify Or Delete Existing Data With Maximum Care

**Related aims:** `D1`-`D12`
**Risk level:** Critical

### Why This Risk Exists

Update, upsert, replace, overwrite, archive, and delete operations can damage or permanently remove existing Teamworks AMS data. The affected data may be difficult or impossible to restore. Automation increases the risk because an agent can act quickly, repeat an operation, make incorrect assumptions, or understate the consequences.

Production deletion is not assumed to be an ordinary supported workflow. It may be appropriate in a designated Teamworks AMS sandbox, but enabling it against a real production environment requires an explicit project decision and safeguards beyond a normal confirmation prompt.

### Trigger Scenarios

- An incorrect filter modifies or deletes the wrong athlete group or form.
- An upsert unexpectedly overwrites existing values.
- A replace operation removes records or fields that were not present in the replacement payload.
- An agent hallucinates or assumes the intended target scope.
- A user clicks through repeated confirmation prompts without reviewing them.
- Documentation or examples make destructive behavior appear routine.
- A sandbox-only workflow is accidentally pointed at production.
- An environment cannot be reliably identified, but the operation continues.
- A batch operation affects far more records than the user expected.
- A timeout or retry repeats part of a destructive operation.
- A preview is generated from different criteria than the live operation.
- Audit artifacts contain sensitive deleted or modified data.
- An agent executes a destructive command on its own initiative.

### Required Safeguards

All modify and delete workflows must:

- Default to dry-run and preview-only behavior.
- Treat an unknown or unverified environment as production.
- Bind the preview and execution to the same immutable operation plan.
- Display the exact environment, operation type, athletes or groups, forms or tables, fields, IDs, and affected record count.
- Clearly distinguish modifications from deletions in terminal and UI output.
- Use accessible emphasis in addition to color; color must not be the only warning mechanism.
- Require an explicit typed confirmation phrase that includes the operation and target scope.
- Reject generic approval such as `yes`, `accept`, or `confirm`.
- Require a fresh confirmation when the operation plan or affected count changes.
- Prevent unattended, non-interactive, or agent-supplied confirmation for critical operations.
- Use exact stable identifiers for deletion and avoid deletion by ambiguous names or broad filters.
- Apply conservative maximum-scope limits and require an additional escalation mechanism to exceed them.
- Record an operation manifest, preview summary, confirmation context, and API response summary without recording secrets.
- Make partial execution, recovery options, and non-recoverability explicit.
- Never conceal, downgrade, or bypass these safeguards in convenience functions, examples, tests, or agent instructions.

Example confirmation:

```text
CRITICAL DESTRUCTIVE OPERATION

Environment: production
Action: delete event records
Athletes affected: 12
Form: Wellness
Exact event IDs: 842

This operation may be irreversible.
Type DELETE 842 WELLNESS EVENTS to continue:
```

For a narrowly scoped operation, the confirmation may instead require the exact athlete, group, form, or other target name. The phrase must be derived from the reviewed operation plan, not supplied silently by an agent.

### Agent Autonomy Rule

A coding agent must never independently execute or approve a critical operation.

An agent may:

- inspect relevant metadata;
- construct a dry-run plan;
- validate identifiers and scope;
- show the preview;
- explain the consequences;
- generate code that preserves the required human confirmation gate.

An agent must stop before live execution and obtain explicit human approval through the package's confirmation mechanism. It must not type, inject, infer, or programmatically bypass the confirmation phrase.

### Sandbox And Production Policy

- Destructive testing is permitted in an explicitly identified Teamworks AMS sandbox when it uses synthetic or approved test data.
- Sandbox status must be established explicitly and reliably.
- Production modification must remain narrowly scoped, previewed, and confirmed.
- Production deletion must remain disabled by default and should not be implemented as a normal capability without an explicit governance decision.
- Tests and examples must never rely on a real production environment.

### Open Governance Decision

Before production deletion is implemented, maintainers must decide and document:

1. Whether production deletion is in scope at all.
2. Which roles are permitted to use it.
3. Which recovery or backup guarantees exist.
4. Which maximum-scope limits apply.
5. Whether a second human approval is required.
6. How the environment is verified.
7. How the action is audited without retaining unnecessary sensitive data.

Until these questions are resolved, agents and contributors should assume that production deletion is out of scope.

---

## E. Documentation And Examples

**Related aims:** `E1`-`E10`
**Risk level:** Medium, with Critical implications when documenting destructive operations

### Why This Risk Exists

Documentation and examples are executable guidance. Users and coding agents may copy them without understanding their assumptions. Unsafe examples can normalize hardcoded credentials, broad data access, production writes, or confirmation bypasses. Weak warnings may cause agents to underemphasize serious risks.

### Trigger Scenarios

- An example contains inline credentials or secrets.
- A quick-start performs a live operation by default.
- A destructive example is more prominent or easier to run than its safety explanation.
- A user copies sandbox code into production.
- Documentation describes a confirmation gate that the code does not actually enforce.
- An agent reads only a nearby example and misses a separate safety document.
- Examples retain data in files, notebooks, caches, or logs without stating this.
- The package appears officially affiliated with or endorsed by Teamworks.

### Required Safeguards

Documentation and examples must:

- Link relevant project aim IDs to this risk model.
- Put safety requirements next to the operation they govern, not only in a distant document.
- Use placeholders and environment-based credential loading.
- Default examples to read-only, dry-run, preview, or sandbox behavior.
- Clearly label environment assumptions.
- Never demonstrate confirmation bypasses or agent-supplied approval.
- Explain local artifact, logging, caching, and cleanup behavior.
- State that the connector is an independent project and is not affiliated with, endorsed by, or maintained by Teamworks.
- State that users remain responsible for authorization, privacy, security, policy compliance, and the consequences of their use.
- Keep warnings concise but unmissable, especially for high-risk and critical operations.
- Ensure examples and documentation remain synchronized with implemented safeguards.

---

## F. Package Usability And Distribution

**Related aims:** `F1`-`F10`
**Risk level:** Medium

### Why This Risk Exists

A package that is easy to install and use is also easy to use outside its intended context. Public distribution can create an appearance of official support and can spread unsafe versions or examples. Agentic coding can further reduce the friction between installation and access to sensitive data or destructive operations.

### Trigger Scenarios

- A user installs the package and assumes it is an official Teamworks product.
- A public package release is mistaken for production-ready or security-reviewed software.
- An agent imports the package and generates a live workflow without reading repository safety guidance.
- Different package versions provide inconsistent safeguards.
- Internal credentials, endpoints, examples, or operational assumptions are accidentally included in a public release.
- A dedicated coding skill or agent workflow bypasses the repository's risk model.

### Required Safeguards

Package design and distribution must:

- Prioritize safe internal distribution; publication to PyPI is optional rather than a success requirement.
- Preserve safety defaults and confirmation behavior across the public API.
- Provide a clear, stable import surface without exposing unsafe shortcuts.
- Clearly state that the project is independent and not affiliated with, endorsed by, or maintained by Teamworks.
- Include an appropriate disclaimer that use is at the user's own risk, without implying that such a disclaimer replaces good engineering safeguards.
- Avoid packaging credentials, sensitive examples, private endpoints, generated operation artifacts, or real Teamworks AMS data.
- Ensure versioning and release notes call out safety-relevant behavior changes.
- Consider a dedicated agent skill for work with this package.
- If such a skill is created, require it to apply this risk model and the project aims; it must not weaken or bypass repository safeguards.

### Agentic Coding Requirement

When an agent is asked to use or modify this package, it should be directed through repository-level instructions such as `AGENTS.md`. Those instructions should require the agent to:

- identify the applicable project aim IDs;
- read this risk model before designing the change;
- state the relevant risks and safeguards in its plan;
- preserve safe defaults;
- stop before autonomous live writes or destructive actions;
- flag conflicts between requested behavior and repository safety requirements.

---

## Risk Review Checklist

Before merging a change, reviewers should be able to answer:

- Which project aim IDs does this change support?
- What is the highest applicable risk level?
- Which trigger scenarios apply?
- Which safeguards are implemented in code?
- Which safeguards are verified by tests?
- Are examples and documentation safe by default?
- Can an agent or caller bypass a required confirmation or environment check?
- Does the change write sensitive data to files, caches, logs, notebooks, or audit artifacts?
- Could retries duplicate or repeat a mutation?
- Is the preview guaranteed to match the executed operation?
- Is the environment explicitly and reliably identified?
- Does the change create or strengthen an appearance of official Teamworks affiliation?
- Are unresolved governance decisions made visible rather than silently assumed?

A change affecting high-risk or critical behavior is incomplete until its safeguards and tests are included.

## Known Open Questions

The following points require explicit maintainer decisions as implementation progresses:

- How will the package reliably distinguish sandbox from production?
- What record-count thresholds require stronger or secondary confirmation?
- Should production deletion remain permanently out of scope?
- Which operation artifacts may be stored, where, for how long, and with what redaction?
- What idempotency guarantees are available for Teamworks AMS create and mutation endpoints?
- Which recovery mechanisms exist for accidental updates, replacements, or deletions?
- Should high-risk or critical production operations require approval by a second human?
- How will a dedicated agent skill be distributed and enforced in supported agentic workflows?

Until a question is resolved, implementations must choose the safer, more restrictive behavior.
