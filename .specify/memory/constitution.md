# Engineering Constitution

This file records durable engineering and safety principles for the AMS Python Connector. It should not contain temporary tasks, endpoint details, implementation status, or milestone handoff notes.

## Python-Only Runtime

The connector must run from Python without requiring R, Rscript, or the `smartabaseR` package at runtime. Legacy R code may be kept as reference material, but production functionality should use Python HTTP calls and Python data structures.

## Safety First

Read-only and dry-run behavior should be the default posture. Writes, updates, upserts, replacements, and deletes must require explicit user intent and must be designed so accidental destructive execution is difficult.

Production deletion is a nuclear option. Broad production deletion should not be exposed through normal public workflows. Any change that weakens destructive-operation safeguards requires explicit review and strong justification.

## Credentials And Data Protection

Real credentials must never be committed. Fetched AMS data, generated operation artifacts, and Smartabase run outputs should stay out of source control unless they are intentionally reviewed, non-secret examples.

Documentation, tests, fixtures, and examples must not include real passwords or live secret values. Any stored API fixture should be redacted before it is committed.

## Auditability

Mutating workflows should produce enough local metadata to reconstruct what was planned, what was executed, and what the API returned. Operation configs, payloads, manifests, and response summaries should avoid secrets while preserving useful debugging context.

## Evidence-Based Changes

Implementation claims should be backed by repository evidence such as source code, tests, examples, or documented sandbox verification. If live API behavior differs from existing assumptions, update documentation and tests before broadening behavior.

## Maintainable Boundaries

Keep request construction, HTTP transport, response flattening, payload construction, workflow planning, and manifest writing separable. Prefer simple dependencies and clear Python APIs over script-only workflows.

## Compatibility With Care

Mirror useful `smartabaseR` behavior where it helps users migrate, but do not build new primary APIs around deprecated wrapper names. Prefer explicit Python method names and stable, documented data shapes.
