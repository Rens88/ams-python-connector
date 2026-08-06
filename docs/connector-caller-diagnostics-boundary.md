# Connector And Caller Diagnostics Boundary

This document records which validation, diagnostics, warnings, and recovery
processes belong to the reusable AMS Connector and which belong to applications
that use it, such as the Synthetic Data repository. It is both a human guide
and a durable decision record for coding agents.

The governing sources are [PROJECT_AIMS.md](../PROJECT_AIMS.md),
[RISK_MODEL.md](../RISK_MODEL.md), and the
[constitution](../.specify/memory/constitution.md). This guide applies those
principles to concrete implementation decisions; it does not weaken them.

## Short Decision Rule

Put a rule in **AMS Connector** when it follows from the generic AMS API
contract: accepted input types, wire formats, endpoint behavior, identifiers,
response shapes, or whether an API request started.

Put a rule in the **calling repository** when it follows from source-data
semantics, business purpose, organization policy, pipeline sequencing, user
interaction, or a source-specific correction.

The connector explains what is invalid and what AMS accepts. The caller adds
workflow context and performs the actual source transformation or recovery.
The connector must never silently guess an ambiguous value merely to make a
request succeed.

## Three Layers

1. **Low-level connector primitives** build requests, validate the generic AMS
   contract, execute transport calls, and return structured results. They do
   not prompt a terminal user.
2. **Generic connector workflows** may build dry-run plans, expose preview
   data, classify generic AMS results, and preserve redacted audit context.
   They do not choose organization-specific forms or recovery policy.
3. **Calling applications** render user-facing previews and confirmations,
   choose workflow limits, transform their source data, sequence operations,
   and decide whether a later stage should run.

For a live mutation, the connector must preserve its dry-run and explicit
execution guards. The calling interactive workflow owns the human prompt and
must not reduce those safeguards to an unattended or agent-supplied approval.

## Error, Warning, And Status Rules

- Raise an **exception** when input is invalid or the operation cannot continue
  safely. Invalid dates and missing exact deletion IDs are errors, not warnings.
- Emit a typed **warning** only when the connector can continue through a
  documented generic fallback, such as using known endpoint aliases after
  discovery fails.
- Return a structured **status** for non-fatal API outcomes such as
  `accepted_unverified`; callers must not infer completion from acceptance.
- Diagnostics must say whether no request was sent, a request started, or the
  state is partial/unknown. They must not expose credentials or unnecessary AMS
  values.
- Public exceptions and warnings need stable types and machine-readable codes.
  A caller may add context without parsing the human-readable message.

## Responsibility Matrix

| Concern | AMS Connector (API provider) | Calling repository (API user) |
|---|---|---|
| Date values | Accept documented Python types and canonical `DD/MM/YYYY`; reject invalid or ambiguous strings with field/row context | Convert its CSV, dataframe, or domain dates before calling the connector |
| Required fields and AMS schemas | Validate generic AMS names, identifiers, types, and payload structure | Decide which source columns map to those generic inputs |
| Endpoint discovery | Discover aliases, provide typed fallback warning and provenance, never expose raw private error text | Decide whether its workflow can continue and explain the affected stage |
| Exact event IDs | Recognize verified AMS event-ID fields and raise a structured error when exact IDs are unavailable | Stop unsafe deletion/replacement and mark dependent stages skipped |
| API technical limits | Enforce a verified server or payload constraint | Choose conservative plan sizes and confirmation boundaries |
| Retry semantics | Expose whether a request started and whether retry may duplicate a mutation | Choose workflow retry/reconciliation policy; never auto-retry an uncertain mutation |
| Preview data | Expose generic target, identifiers, fields, dates, counts, and dry-run payloads | Render the application-specific preview and obtain human confirmation |
| Mutation response | Return sanitized responses and a generic mutation state | Reconcile domain scope and decide whether the complete pipeline succeeded |
| Logging | Provide safe structured diagnostics and generic messages | Add run, file, row, stage, and remediation context without changing the meaning |
| CLI arguments | No knowledge of application flags | Validate `--days`, reconciliation attempts/delay, local paths, and similar policy |
| Destination forms | Expose supplied form names without inventing conventions | Select destination forms and organization-specific naming |

## Decisions And Examples

### DIAG-001: Date formatting

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** AMS Connector owns parsing and validation of the AMS date
  contract. It accepts `date`, `datetime`, or an exact day-first string in
  `DD/MM/YYYY` (`%d/%m/%Y`) format. It does not guess ISO, US month-first, or
  other ambiguous strings.
- **Caller responsibility:** Synthetic Data converts its own generated CSV
  values to the connector contract. Its error output may name the CSV and row.
- **Rationale:** The accepted wire format is generic AMS knowledge; the source
  representation and transformation are application-specific.
- **Safeguards:** Validate before transport and state that no request was sent.
- **Relevant aims:** C6, E6, F2, F6.
- **Revisit when:** Verified AMS documentation or integration evidence changes
  the accepted wire format.

### DIAG-002: Endpoint discovery fallback

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** The connector owns the fallback warning text, warning category,
  and endpoint provenance. The raw discovery exception type may be retained;
  its private message must not be printed by default.
- **Caller responsibility:** Explain which application stage used fallback
  endpoints and decide whether workflow policy permits continuation.
- **Rationale:** Endpoint aliases are connector knowledge. Pipeline stages are
  not.
- **Relevant aims:** B6, E6, F2.
- **Revisit when:** Endpoint discovery becomes mandatory or defaults are no
  longer verified.

### DIAG-003: Exact event IDs

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** The connector owns the verified event-ID key set and strict
  exact-ID extraction. Generic `id`, athlete IDs, and profile IDs are not
  deletable event IDs without separate verification.
- **Caller responsibility:** A replacement workflow stops deletion and upload
  when the connector cannot establish exact IDs. It reports each skipped stage.
- **Rationale:** Event-ID semantics are part of the AMS contract; replacement
  sequencing is application policy.
- **Safeguards:** Fail closed, do not log event values, never convert an
  ambiguous identifier into a deletion target.
- **Relevant aims:** D2, D5, D12, F6.
- **Revisit when:** An authorized response fixture or documentation proves an
  additional exact event-ID field.

### DIAG-004: Batch and scope limits

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** A verified AMS technical limit belongs in the connector. A
  conservative operational cap, plan size, or confirmation boundary belongs
  to the caller unless elevated into generic connector governance.
- **Example:** The connector may reject a payload above a documented server
  maximum. Synthetic Data may independently cap deletion plans at 100 IDs.
- **Relevant aims:** C6, C7, D9, F6.
- **Revisit when:** Server limits or connector-wide governance are verified.

### DIAG-005: Preview and human confirmation

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** The connector exposes inspectable dry-run plans and enforces
  that live execution is explicit. It does not read from `input()` or decide
  whether the caller is interactive. The interactive caller prints the final
  operation-specific preview and obtains human confirmation.
- **Rationale:** This keeps the package reusable without allowing callers to
  bypass dry-run, immutable-plan, environment, or human-control safeguards.
- **Relevant aims:** C3, C5, C8, D6-D10, F3, F6.
- **Revisit when:** A separate generic interactive package layer is designed
  and reviewed.

### DIAG-006: Accepted but unverified mutation responses

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** The connector exposes sanitized response evidence and mutation
  state. It must distinguish acceptance from confirmed completion when AMS does
  not return an authoritative count.
- **Caller responsibility:** Synthetic Data performs read-only reconciliation
  over its reviewed athlete/form/date scope and is complete only after it
  matches.
- **Rationale:** AMS response semantics are generic; the expected domain scope
  and reconciliation policy are caller-specific.
- **Relevant aims:** C7, D5, D12, F6.
- **Revisit when:** AMS provides an authoritative operation-status endpoint or
  response contract.

### DIAG-007: Pipeline arguments and remediation

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** Constraints such as generation days, historical replacement
  windows, reconciliation attempts, delays, and local artifact paths remain in
  Synthetic Data.
- **Rationale:** These are workflow policy and have no generic AMS meaning.
- **Relevant aims:** E6, F3.

### DIAG-008: Empty-scope upload policy

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** The connector exposes read-only event counts, verified exact
  event IDs, immutable mutation inputs, and generic mutation safeguards. It
  does not prohibit inserting into a non-empty event scope because appending
  events is valid generic AMS behavior.
- **Caller responsibility:** Synthetic Data requires its generated n-day range
  to be empty before upload. Existing events block the complete refresh and are
  offered only through separately executed exact-ID deletion plans. Records
  before the generated range remain untouched.
- **Rationale:** Whether existing data constitutes a collision follows from the
  caller's synthetic-data purpose and pipeline sequencing, not the AMS API
  contract. A read-before-write check is not an atomic server guarantee, so the
  caller repeats it immediately before its first upload and reports that
  limitation honestly.
- **Safeguards:** No partial conflict-free upload, no automatic deletion, fresh
  refresh after remediation, separate preview and human-confirmed execution
  commands for every exact-ID delete plan, final read-only empty-range recheck,
  and existing connector dry-run, sandbox, exact-ID, immutable-plan, and
  confirmation gates.
- **Relevant aims:** C3, C5, C7, D2, D6-D10, E6, F3.

### DIAG-009: Exact-ID delete success messages

- **Date:** 2026-08-06
- **Status:** Accepted
- **Decision:** AMS Connector recognizes the verified delete-endpoint response
  `{"message": "Deleted <event-id>"}` as successful only when the message
  exactly matches that shape and the returned positive integer equals the
  requested event ID. Similar free-form text, mismatched IDs, and responses
  containing error fields remain partial or unknown.
- **Caller responsibility:** Synthetic Data explains the structured reason and
  safe next step when a deletion remains partial or unknown. It must not
  automatically retry an uncertain mutation.
- **Rationale:** The delete endpoint's response grammar and exact-ID meaning are
  generic AMS API behavior. Human-facing recovery instructions depend on the
  caller's immutable plan and pipeline sequence.
- **Safeguards:** Strict full-message matching, exact requested-ID comparison,
  fail-closed handling for ambiguous/error responses, redacted audit output,
  and no automatic retry.
- **Relevant aims:** D2, D5, D6, D12, F6.
- **Revisit when:** Authorized API evidence establishes an additional delete
  success response shape.

## Agent Decision Checklist

Before adding or moving a diagnostic, an agent must answer:

1. Does the rule come from verified AMS behavior or from one caller's workflow?
2. Can the connector describe the problem without knowing a CSV layout,
   pipeline stage, organization, or destination-form convention?
3. Is this a fatal error, a safe fallback warning, or a result status?
4. Can the diagnostic state whether a request or mutation started?
5. Does it avoid secrets, response values, and unnecessary athlete data?
6. Does the public type/code remain stable for downstream callers?
7. Does the caller add context rather than duplicate AMS-specific rules?
8. Are offline connector tests and at least one downstream contract test added?
9. Are the applicable aim IDs, risk level, and decision entry recorded?

If the answer is uncertain, preserve the stricter existing safeguard and add a
new dated decision entry before moving behavior across the repository boundary.

## Maintaining This Record

Do not rewrite an accepted decision merely because the implementation changes.
Append a new decision that supersedes it, identify the old decision ID, explain
why the evidence changed, and link the relevant tests or reviewed integration
evidence. Never include credentials, tenant-private response values, or real
athlete data in this document.
