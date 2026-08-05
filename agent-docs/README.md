# Agent Documentation Index

Coding agents should read these files in this order before making non-trivial changes:

1. [../README.md](../README.md): human entrypoint, quick start, current capabilities, limitations, and links.
2. [../PROJECT_AIMS.md](../PROJECT_AIMS.md): desired product outcomes and stable aim IDs.
3. [../RISK_MODEL.md](../RISK_MODEL.md): risk levels, trigger scenarios, required safeguards, and agent behavior.
4. [../.specify/memory/constitution.md](../.specify/memory/constitution.md): durable engineering and safety principles.
5. [../docs/roadmap.md](../docs/roadmap.md): authoritative status for each project aim.
6. [current-work.md](current-work.md): current milestone, immediate tasks, blockers, unresolved questions, and handoff notes.
7. [implementation-guidance.md](implementation-guidance.md): detailed Python, AMS/Smartabase, HTTP, compatibility, and implementation guidance.

## Document Ownership

- `README.md` is the human-facing entrypoint. Keep it concise and practical.
- `PROJECT_AIMS.md` describes desired outcomes only. Do not record implementation status there.
- `RISK_MODEL.md` defines risk levels, triggers, safeguards, and agent constraints.
- `.specify/memory/constitution.md` stores durable principles only. Do not add temporary tasks, endpoint details, or status updates there.
- `docs/roadmap.md` is the long-term progress tracker for aim IDs.
- `agent-docs/current-work.md` is the short-term handoff. Do not duplicate the full roadmap there.
- `agent-docs/implementation-guidance.md` contains detailed implementation guidance for coding agents.
- `CONTRIBUTING.md` is human collaboration guidance for issues, branches, commits, pull requests, testing, credentials, and destructive-operation safety.

## Safety Defaults

Keep destructive-operation safeguards prominent in any agent-authored change. Do not inspect `.env` directly, do not commit real credentials or AMS data, and do not weaken sandbox-only mutation guards without explicit user approval and review.
