# Feature Specification: Tiered API Safety Modes

**Feature Branch**: `docs/2-api-safety-modes`

**Created**: 2026-07-29

**Status**: Draft — governance review required before planning

**Input**: User description: "Define `--default`, `--human`, and `--auto` safety modes so cautious exploration retains all current guardrails, reviewed interactive workflows require less repetitive approval, and thoroughly reviewed automation can run unattended while preserving a strict Form A to separate Form B, no-replacement workflow."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preserve the Safe Default (Priority: P1)

As a user exploring AMS data or running an unfamiliar workflow, I receive all
existing safeguards unless I deliberately select another mode, so an omission
or typo cannot silently reduce protection.

**Why this priority**: Safe fallback behavior is the foundation for every other
mode and protects new users, coding-agent users, and existing callers.

**Independent Test**: Run representative read, create, modify, and delete
requests without a mode and verify that each request behaves exactly as
`--default`, including dry-run, preview, environment, scope, and confirmation
requirements.

**Acceptance Scenarios**:

1. **Given** no mode is specified, **When** a workflow starts, **Then** it uses `--default` and reports that choice before any AMS request with side effects.
2. **Given** an unknown, malformed, or contradictory mode selection, **When** a workflow starts, **Then** it fails closed before any live mutation.
3. **Given** `--default` is selected, **When** a live operation is requested, **Then** all safeguards required by the current project governance remain active.

---

### User Story 2 - Streamline a Supervised, Known Workflow (Priority: P2)

As an informed user supervising reviewed code, I can select `--human` and make
one clear approval decision for an eligible create-only operation after seeing
its full impact, without losing validation, preview, audit, or no-replacement
safeguards.

**Why this priority**: Repeated use of known workflows should require less
friction while preserving a meaningful human decision at execution time.

**Independent Test**: Select `--human` for a reviewed create-only workflow that
reads Form A and targets a distinct, non-colliding scope in Form B; verify that
the complete preview is shown and exactly one explicit yes/no decision controls
the live create.

**Acceptance Scenarios**:

1. **Given** a valid immutable plan for a create-only write to a separate destination scope, **When** the user selects `--human`, **Then** the workflow shows the complete impact preview and accepts one explicit yes/no decision.
2. **Given** the user rejects the preview or provides an unrecognized answer, **When** approval is evaluated, **Then** no live mutation occurs.
3. **Given** an update, upsert, replace, overwrite, archive, or delete is requested, **When** `--human` is active, **Then** the mode does not reduce the current critical-operation safeguards.
4. **Given** the plan changes after approval, **When** execution is attempted, **Then** the prior approval is invalid and a new preview and approval are required.

---

### User Story 3 - Run Qualified Create-Only Automation (Priority: P3)

As an end user responsible for reviewed automation, I can qualify a narrowly
scoped workflow and run it in `--auto` without a prompt on each execution,
provided it only reads source data and creates derived records in a separate,
non-colliding destination scope.

**Why this priority**: Unattended execution enables reliable recurring
workflows, but it must never become a path to alter or remove existing AMS data.

**Independent Test**: Qualify a reviewed Form A to Form B workflow, run it
unattended, and verify that it completes without interactive input while still
enforcing the reviewed environment, identities, form separation, scope limits,
validation, duplicate controls, and audit requirements.

**Acceptance Scenarios**:

1. **Given** a current human-owned qualification matching the exact workflow and operation plan boundaries, **When** `--auto` runs a create-only operation, **Then** it requires no interactive response and retains every non-approval safeguard.
2. **Given** no valid qualification exists, **When** `--auto` is requested, **Then** the workflow fails closed before a live mutation.
3. **Given** the source and destination have the same stable form identifier, **When** `--auto` is requested, **Then** execution is refused.
4. **Given** an existing destination record collides with an intended record or collision status cannot be established, **When** `--auto` is requested, **Then** execution is refused without changing the existing record.
5. **Given** an update, upsert, replace, overwrite, archive, or delete is requested, **When** `--auto` is active, **Then** execution is refused regardless of prior review or qualification.

---

### User Story 4 - Review, Audit, and Revoke Elevated Modes (Priority: P4)

As a maintainer or accountable end user, I can see why a workflow is eligible
for `--human` or `--auto`, identify what was executed, and revoke or invalidate
that eligibility when the reviewed code or scope changes.

**Why this priority**: Reduced interaction is safe only while review evidence
and runtime behavior remain aligned and attributable to a responsible human.

**Independent Test**: Review a qualification, change each governed element in
turn, and verify that eligibility is invalidated and that past runs remain
auditable without exposing credentials or unnecessary athlete data.

**Acceptance Scenarios**:

1. **Given** reviewed code or governed configuration changes, **When** the next elevated-mode run starts, **Then** the earlier qualification is rejected.
2. **Given** a qualification is revoked or expires, **When** the next `--auto` run starts, **Then** it fails closed before live mutation.
3. **Given** a completed or failed run, **When** an authorized reviewer inspects its audit record, **Then** the reviewer can determine the selected mode, qualification, plan, execution result, and partial failures without seeing credentials.
4. **Given** a coding agent helped prepare the workflow, **When** qualification is granted, **Then** the accountable human—not the agent—is recorded as the reviewer and authorizer.

### Edge Cases

- No mode, more than one mode, an unknown mode, or a mode supplied with
  inconsistent capitalization or spelling.
- `--human` or `--auto` is requested from a non-interactive environment that
  cannot satisfy that mode's eligibility rules.
- A workflow or coding agent attempts to select, qualify, renew, or approve its
  own reduced-guardrail mode.
- Source and destination names differ but resolve to the same stable form ID.
- Form B already contains data outside the intended scope, or gains a
  colliding record between preview and execution.
- Two unattended runs overlap, or a timeout causes the caller to retry an
  operation whose result is not yet known.
- Reviewed code, dependencies, configuration, credentials, environment,
  schema, fields, athletes, date range, batch limit, or destination changes.
- AMS environment identity cannot be verified or differs from the qualified
  environment.
- The preview and live operation do not resolve to the same immutable plan.
- Validation or collision discovery is incomplete because of pagination,
  permissions, network failure, or an ambiguous identifier.
- A batch is partly accepted and partly rejected.
- Audit evidence would contain credentials, raw sensitive responses, or more
  athlete data than necessary.

## Requirements *(mandatory)*

### Mode Safety Boundary

| Operation | `--default` | `--human` | `--auto` |
|---|---|---|---|
| Read or discovery | Current safeguards | Current safeguards | Current safeguards |
| Dry run or preview | Current safeguards | Current safeguards | Current safeguards |
| Create in a separate, non-colliding destination scope | Current confirmation rules | One post-preview yes/no decision, subject to governance approval | No per-run prompt after human qualification, subject to governance approval |
| Update, upsert, replace, overwrite, or archive | Current Critical safeguards and restrictions | No reduction from current Critical safeguards | Prohibited |
| Delete | Current Critical safeguards and production restrictions | No reduction from current Critical safeguards | Prohibited |

### Functional Requirements

#### Mode Selection and Visibility

- **FR-001**: The initiating workflow MUST expose exactly three mutually exclusive safety modes named `--default`, `--human`, and `--auto`.
- **FR-002**: An omitted mode MUST resolve to `--default`.
- **FR-003**: Unknown, malformed, or conflicting mode selections MUST fail closed before any live mutation.
- **FR-004**: The selected mode, effective operation class, environment, and whether the run is interactive MUST be visible before execution.
- **FR-005**: Mode semantics MUST be consistent across supported public workflow entry points; no convenience entry point may provide weaker behavior.
- **FR-006**: Credentials, role membership, or access to a machine MUST NOT implicitly select or elevate a mode.

#### Safeguards That No Mode May Remove

- **FR-007**: Every mode MUST preserve credential hygiene, least privilege, data minimization, secure artifact handling, and responsibility disclosures.
- **FR-008**: Every live mutation MUST use a validated, immutable operation plan that identifies the environment, operation, athletes or groups, source and destination forms, fields, date or record scope, stable IDs where relevant, and affected record count.
- **FR-009**: Every mode MUST validate schemas, required fields, identifiers, value types, permissions, supported scope limits, and environment identity before live execution.
- **FR-010**: An unknown or unverified environment MUST be treated as production and MUST NOT receive elevated-mode permission.
- **FR-011**: Every mode MUST retain bounded batches, rate-limit handling, duplicate prevention, retry safety, and explicit partial-success and partial-failure reporting.
- **FR-012**: Preview and execution MUST use the same immutable operation plan, and any plan change MUST invalidate prior approval or qualification.
- **FR-013**: Every live operation MUST produce a redacted audit record sufficient to reconstruct what was qualified, planned, attempted, and reported by AMS.
- **FR-014**: No mode may permit a coding agent to authorize a live high-risk or critical operation, generate its own approval evidence, or weaken a safeguard.
- **FR-015**: A statement that the user accepts risk MUST NOT substitute for validation, environment verification, scope enforcement, no-replacement guarantees, or auditability.

#### Permanent Source-Preservation Boundary

- **FR-016**: A coding-agent-assisted derived-data workflow MUST read from a source form and write only to a separate destination form identified by a different stable form ID.
- **FR-017**: The destination operation MUST be create-only; update, upsert, replace, overwrite, archive, and delete behavior MUST be unavailable in the reduced-guardrail path.
- **FR-018**: Existing source records and existing destination records MUST never be modified or deleted by the reduced-guardrail path.
- **FR-019**: Before create execution, the workflow MUST establish that the intended destination record identity and scope do not collide with an existing record.
- **FR-020**: If non-collision cannot be established completely and unambiguously, the workflow MUST fail closed.
- **FR-021**: Retries and concurrent runs MUST NOT create a second record for the same reviewed record identity merely because the prior outcome is unknown.
- **FR-022**: The source form, destination form, and no-collision rule MUST be explicit workflow policy; the generic connector MUST NOT guess organization-specific destinations or naming conventions.

#### `--default`

- **FR-023**: `--default` MUST retain all safeguards described by the governance and API documentation in effect for the installed version.
- **FR-024**: `--default` MUST remain dry-run or read-only by default and MUST retain the existing operation-specific confirmation rules for live mutations.
- **FR-025**: Existing callers that do not select a mode MUST NOT receive weaker protection as a result of this feature.

#### `--human`

- **FR-026**: `--human` MUST remain interactive and MUST display the same complete preview required by `--default`.
- **FR-027**: Subject to the governance approval identified in this specification, an eligible create-only, separate-destination live write MAY use one explicit yes/no decision instead of an operation-specific typed phrase.
- **FR-028**: The yes/no decision MUST be requested only after the immutable plan has been displayed and MUST be separate from credentials and mutation parameters.
- **FR-029**: A missing, negative, malformed, timed-out, pre-supplied, or non-human response MUST cancel live execution.
- **FR-030**: In the initial scope, `--human` MUST NOT simplify confirmation for update, upsert, replace, overwrite, archive, or delete operations.

#### `--auto`

- **FR-031**: `--auto` MUST require no human interaction during an eligible execution.
- **FR-032**: `--auto` live writes MUST remain disabled until repository governance is explicitly amended to permit qualified unattended create-only writes.
- **FR-033**: After such approval, `--auto` MUST permit only read operations, dry runs, and qualified create-only writes to a separate, non-colliding destination scope.
- **FR-034**: `--auto` MUST refuse all update, upsert, replace, overwrite, archive, and delete operations in every environment, including sandboxes.
- **FR-035**: `--auto` MUST require a current qualification created and owned by an accountable human reviewer; a coding agent or running workflow MUST NOT create or renew its own qualification.
- **FR-036**: A qualification MUST bind the reviewed workflow identity to its allowed environment, credentials or service identity, source and destination form IDs, fields, athlete or group scope, date or record scope, operation type, batch limits, and duplicate/retry policy.
- **FR-037**: A qualification MUST include review evidence, reviewer identity, review time, expiry or re-review condition, and revocation state without storing credentials or unnecessary sensitive data.
- **FR-038**: A change to any bound element, an expired or revoked qualification, or an inability to verify identity and scope MUST prevent the live write.
- **FR-039**: The workflow MUST expose a non-mutating way to verify whether a proposed `--auto` execution would qualify and why.
- **FR-040**: Repeated `--auto` runs MUST remain within the qualified maximum scope and MUST NOT aggregate into an unreviewed broader mutation.

#### Governance and Review Gate

- **FR-041**: The proposal MUST receive explicit maintainer design review before implementation because it changes High- and Critical-risk approval behavior.
- **FR-042**: Before planning or implementation of unattended live creates, maintainers MUST reconcile the proposal with Constitution Principle IV, the operational constraints, `C8`, the Risk Model's Aim C safeguards, and the scheduled-workflow responsibility boundary.
- **FR-043**: A simple yes/no confirmation MUST NOT be allowed for critical modify or delete operations unless the constitution, project aims, risk model, and agent instructions are deliberately amended first.
- **FR-044**: Automated modification or deletion MUST remain out of scope even if other governance documents are amended to permit unattended create-only writes.
- **FR-045**: Until all required governance decisions are approved and synchronized, current runtime behavior and safeguards MUST remain unchanged.

### Governance Context

**Applicable aim IDs**: `B8`, `B9`, `C3`, `C5`-`C8`, `D1`,
`D4`-`D12`, `E4`, `E6`, `E7`, `E9`, `F6`, and `F8`.

**Highest applicable risk level**: **Critical**. Although the intended
automated path is create-only and therefore High risk, the proposal explicitly
changes approval behavior and discusses the highest-risk operations. Any
incorrect mode classification or bypass could expose Critical behavior.

**Relevant trigger scenarios**:

- A mode is omitted, misspelled, or selected by an agent and silently weakens
  safeguards.
- A reviewed create is retried or duplicated, writes to the wrong athlete or
  form, or grows beyond its approved scope.
- A destination believed to be empty contains existing or concurrently created
  records.
- Code, configuration, schemas, permissions, or environments drift after
  review.
- An unattended workflow is used to update, replace, or delete data.
- Review or audit evidence exposes secrets or sensitive athlete data.

**Current governance conflicts**:

1. Constitution Principle IV and the operational constraints require explicit
   confirmation before every live mutation. `--auto` live creation without a
   per-run human decision therefore requires a prior governance amendment.
2. Aim `D7` and the Risk Model require operation-specific typed confirmation
   and reject generic yes/no approval for Critical operations. The requested
   simplification cannot apply to those operations under current governance.
3. The Risk Model forbids scheduled modification or deletion. This
   specification preserves that prohibition permanently for `--auto`.

This specification records the proposed direction but does not amend those
governance documents and does not authorize implementation.

### Constitution Impact

- **Runtime boundary**: No runtime change is made in this descriptive phase. Any later implementation remains Python-only.
- **AMS/Smartabase API use**: Future behavior would continue to use direct, explicit AMS API operations; no API request is made by this specification.
- **Mutation safety**: Material impact. The proposal would reduce per-run confirmation for some live creates and therefore conflicts with current Principle IV until amended. Dry-run-first behavior, immutable preview, source preservation, environment checks, and the Critical-operation restrictions remain mandatory.
- **Auditability**: Future elevated-mode runs require redacted qualification, plan, execution, and partial-failure evidence.
- **Public interfaces**: The proposal adds the stable mode names `--default`, `--human`, and `--auto`, with equivalent semantics at supported initiating workflow surfaces.
- **Testing evidence**: No behavior changes occur now. Any later behavior change requires offline automated mode-matrix, bypass, drift, collision, retry, partial-failure, and fail-closed tests plus opt-in guarded sandbox integration evidence.
- **Credentials and athlete data**: No credentials or AMS data are added. Future qualification and audit evidence must exclude credentials and minimize athlete data.
- **Documentation**: Future implementation must update user, maintainer, agent, API, safety, and migration documentation together.

### Key Entities

- **Safety Mode**: The explicitly selected oversight profile, including its permitted operation classes and required approval behavior.
- **Operation Class**: A read, dry run, create, modify, or delete classification determined from actual effects rather than caller labels.
- **Immutable Operation Plan**: The complete reviewed intent for one execution, including environment, operation, targets, stable identifiers, fields, scope, and affected count.
- **Source Scope**: The Form A data that may be read and processed but never changed by the reduced-guardrail path.
- **Destination Scope**: The separate Form B record identity and range that may receive create-only derived data when proven non-colliding.
- **Automation Qualification**: Human-owned, revocable evidence that a specific reviewed workflow may perform a bounded unattended create-only operation.
- **Review Identity**: The accountable human and reviewed workflow version associated with elevated-mode eligibility.
- **Run Audit Record**: Redacted evidence linking the selected mode, qualification, immutable plan, attempted execution, and AMS outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested entry points, omitting a mode produces the same safeguards and outcome as explicitly selecting `--default`.
- **SC-002**: In 100% of tested invalid, conflicting, unqualified, expired, revoked, drifted, or unverifiable elevated-mode cases, no live mutation request is sent.
- **SC-003**: In 100% of tested same-form, existing-record-collision, ambiguous-identity, incomplete-discovery, retry, and concurrent-run cases, existing AMS data is not modified, deleted, or replaced.
- **SC-004**: A qualified create-only `--auto` test run completes with zero interactive prompts, while 100% of attempted modify and delete operations are rejected before an AMS mutation request.
- **SC-005**: An eligible `--human` create-only test requires exactly one explicit yes/no decision after the full immutable preview; rejection or plan change results in zero live mutation requests.
- **SC-006**: Every elevated-mode run produces reviewable evidence linking one selected mode, one valid qualification where required, one immutable plan, and one outcome, with no credentials present.
- **SC-007**: Reviewers can identify the mode, permitted operation, target environment, source and destination, affected count, and remaining safeguards from the preview in under two minutes in at least 90% of acceptance reviews.
- **SC-008**: Before planning begins, all current governance conflicts are either resolved through approved synchronized amendments or recorded as blockers that keep the affected behavior disabled.

## Assumptions

- This phase produces a specification and review guidelines only; it does not
  change runtime behavior, governance, examples, or API documentation.
- The three mode names are user requirements and are intended to be stable
  public concepts, while their exact presentation across supported entry points
  is a planning decision.
- `--human` and `--auto` reduce only approval interaction. They never reduce
  validation, scope, environment, duplicate/retry, source-preservation,
  auditability, credential, or data-minimization safeguards.
- For recurring automation, "empty Form B" means the intended destination
  record identity and scope are non-colliding at execution time; the destination
  form may contain records from prior successful runs outside that scope.
- Human review of code alone is insufficient. The qualification also covers
  governed configuration, environment, service identity, source, destination,
  scope, limits, and failure behavior.
- Qualification is an accountable human governance action, not a capability
  that a coding agent, scheduled job, or possession of credentials can grant.
- Any future decision to simplify confirmation for Critical operations is a
  separate governance change and is excluded from the initial mode feature.
- Production deletion remains outside normal project scope, and unattended
  modification or deletion remains prohibited.
