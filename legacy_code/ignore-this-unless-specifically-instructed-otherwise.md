# AGENTS.md

This file is the stable operating manual for AI agents working in this repository.

## Core principle

Build from the current repo standard. Treat archived repositories as source material, not as architecture to preserve.

Old code may contain useful ideas, data examples, UI concepts, or domain logic, but it should not be copied blindly.

## Human-first structure

The folder structure exists so humans can quickly understand the project.

Expected structure:

```text
docs/                 Stable project knowledge: what is true
project-brain/        Evolving memory: how we got here
prototypes/           Disposable explorations and standalone prototypes
app/                  Application entry points and user-facing app shells
src/                  Reusable domain, service, data, and utility code
tests/                Unit, integration, and end-to-end tests
data/example/         Safe sample data that can be committed
data/private/         Local private data; must not be committed
assets/               Images, static files, design assets
scripts/              Developer and automation scripts
infra/                Docker, Azure, and pipeline files
skills/               Repo-owned AI skills or skill drafts
archive/              Old repositories or reference material
```

## Documentation authority

When documents conflict, trust the higher document in this order:

1. `docs/CONSTITUTION.md`
2. `docs/DECISIONS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/USER-STORIES.md`
5. `docs/FEATURES.md`
6. `docs/ROADMAP.md`
7. `docs/RISKS.md`
8. `project-brain/MEMORY.md`
9. `project-brain/AI-NOTES.md`

Important rule:

- `MEMORY.md` is history.
- `DECISIONS.md` is truth.
- `CONSTITUTION.md` overrides everything.

## Document ownership

### Human-governed

`docs/CONSTITUTION.md`

Agents may propose changes, but must not edit it automatically without explicit approval.

### Agent-maintained, human-reviewed

- `docs/DECISIONS.md`
- `docs/ARCHITECTURE.md`
- `docs/BACKLOG.md`
- `docs/USER-STORIES.md`
- `docs/FEATURES.md`
- `docs/FAQ.md`
- `docs/ROADMAP.md`
- `docs/RISKS.md`
- `docs/migration-notes.md`

### Agent-maintained memory

- `project-brain/MEMORY.md`
- `project-brain/AI-NOTES.md`
- `project-brain/AGENT-PLANS.txt`
- `project-brain/session-summaries/`

### Human-maintained memory
- `project-brain/HUMAN-FEEDBACK.md`
Consider this as offline feedback for the agent. 
This was either written when there were no more tokens.
Or when the human was testing the app elaborately.
Check this file at the start of a new session to see if the human left instructions/ideas/suggestions there for the agent.
The feedback in this file is not necessarily spec-compliant.
The agent should internalize the feedback and decide whether these are:
* suggested tasks
* suggested features
* suggested user-stories
* .. or anything else that fits the specify terminology
The agent must criticerally reflect on this feedback whether it doesn't conflict with any other specs.
The agent must ask for clarification when instructions are ambiguous.
The agent can never change this file, instead makes a dated copy of this file (with prefix "YYYYMMDD_HHMMSS_" denoting the time of generating the file).
In this dated copy:
The agent must not change the original text, but can change lists (* , + or -) into checkboxes, indicating to the human that the items with checkboxes can be inspected and reviewd.
The agent can add updates, clarifications, task-references below each listed item, but must always start a sentence with "→ AGENT SAID: "

## Maturity levels

Use the lightest structure that fits the goal.

### Rapid prototype

Goal: show or discuss an idea quickly.

Typical folders:

```text
prototypes/html/
assets/
docs/
```

Rules:
- Prefer standalone HTML when speed matters.
- Generated files should go to `prototypes/html/build/`.
- Do not over-engineer.

### Proof of concept

Goal: let users interact with real logic, data, or workflows.

Typical folders:

```text
app/streamlit/
src/
data/example/
tests/unit/
```

Rules:
- Streamlit is the default POC app surface for Python/data work.
- Move reusable logic out of `app/streamlit/app.py` and into `src/`.
- Keep example data safe and small.

### MVP / PRD app

Goal: create a maintainable app with clearer separation and deployment potential.

Typical folders:

```text
app/frontend/
app/backend/
src/
tests/
infra/
```

Rules:
- Use clear frontend/backend boundaries.
- Add automated tests.
- Add Docker and CI/CD only when the app is ready for repeatable deployment.

## Working with archived repos

If `archive/` contains an older repo:

1. Inspect it.
2. Summarize useful concepts.
3. Identify risky or outdated patterns.
4. Propose a redesign plan.
5. Wait for approval before copying or rewriting major parts.
6. Rebuild into the new standard structure.

Do not mutate archived source material unless explicitly asked.

## Data handling

- `data/example/` may contain safe, small, fake, anonymized, or public sample data.
- `data/private/` may contain local private data and must never be committed.
- Never place credentials, tokens, or personal data in committed files.
- Use `.env.example` for variable names only.
- Use `.env` for local secrets; `.env` must remain ignored.

## Skills

Repo-owned skills live in:

```text
skills/
```

Tool-specific installations may mirror them elsewhere, for example:

```text
.claude/skills/
```

Before starting specialized work, inspect `skills/` for relevant repo-owned skills.

Do not put private data, secrets, or environment-specific credentials in skills.

## Agent workflow

### Startup and close-off summaries

These summaries are explicit workflows, not assumptions about the user's intent. Trigger detection is case-insensitive.

#### Startup trigger and confirmation

If a prompt is only a greeting, or begins with a greeting and does not contain a more specific task, recognize `Good morning`, `Hello`, `Goedemorgen`, `Hi`, `Hey`, and equivalent greetings in any language as a startup-summary request. Do not run the sequence immediately. First ask:

> I detected a startup greeting. Would you like me to run the startup summary and session handoff check?

Run the startup sequence only after the human confirms. If the greeting also contains a concrete task, ask whether the startup summary should be run and then handle the concrete task according to the human's answer; do not silently treat every greeting as authorization for the sequence.

#### Previous-session selection (mandatory)

At the start of every confirmed startup sequence, enumerate every regular file directly inside `project-brain/session-summaries/` and select the newest one before preparing the summary. Use a leading `YYYYMMDD_HHMMSS` filename prefix as the chronological key; for legacy filenames without that prefix, use a leading ISO date when available and otherwise the file's modification time. Sort the candidates by that key in descending order, read the selected file in full, and use it as the previous session to continue. Report its exact path under `Previous session to continue`.

Do not select a summary from an unsorted directory listing, from the current Git commit date, or from prior chat context. If the directory is empty, state that no previous session summary was found; if two candidates cannot be ordered reliably, state the ambiguity and inspect the tied candidates before choosing.

#### Startup summary template

After confirmation, provide a concise, evidence-based summary using this structure:

```markdown
# Startup summary — YYYY-MM-DD HH:MM TZ

## Current state
- Current branch: `<branch>`; working tree: clean / dirty.
- Uncommitted changes: `<short scoped summary>`; identify changes that appear user-owned and must not be touched.
- Latest commit on the current branch: `<hash> <date> <subject>`.

## Last five commits
- `<hash>` — `<date>` — `<subject>`
- `<hash>` — `<date>` — `<subject>`
- `<hash>` — `<date>` — `<subject>`
- `<hash>` — `<date>` — `<subject>`
- `<hash>` — `<date>` — `<subject>`

Generate this list from `git log -5 --date=iso-strict` on the reported branch. It is the repository cross-check for the app side-panel Git value. If the side-panel value differs, report both values and state that the repository HEAD/log is authoritative; do not silently replace either value.

## Branch and PR status
- Most recently changed branch: `<branch>`, based on the newest local/remote branch commit found; explain if this differs from the current branch.
- PR status: `<open, merged into <branch>, closed, no PR found, or unknown>`.
- Evidence checked: `<remote refs, GitHub PR metadata if available, merge commit, or other source>`.

## Human review status
- Latest changes: `<commits and/or uncommitted files, with a plain-language summary>`.
- Human inspection: `<confirmed with evidence, partially evidenced, not evidenced, or unknown>`.
- Evidence: `<review notes, HUMAN-FEEDBACK, session summary, PR review, human-authored commit, or explicit user statement>`.

## Continuation and next steps
- Previous session to continue: `<session-summary path and reason, or none found>`.
- Active plan/tasks: `<path and current pending or blocked items>`.
- Recommended next steps: `<ordered short list>`.
- Open blockers or decisions needed: `<items, or none>`.
```

Use read-only Git and repository inspection to fill this in. Check recent commits and branch refs, the relevant remote/PR metadata when available, `project-brain/session-summaries/`, `project-brain/AGENT-PLANS.txt`, `project-brain/MEMORY.md`, `project-brain/AI-NOTES.md`, and `project-brain/HUMAN-FEEDBACK.md`. Do not claim that a human inspected changes merely because a commit exists or because an agent-authored note says so. Distinguish committed changes from uncommitted changes and state when PR or review evidence is unavailable. At the start of a new session, preserve the human feedback by making a timestamped copy named `project-brain/YYYYMMDD_HHMMSS_HUMAN-FEEDBACK.md`; never edit the original.

For continuation planning, treat historical session summaries and agent-authored completion claims as provisional. Reconcile them against the current feature specification, unchecked task list, source code, validation evidence, explicit human corrections, and the newest remote baseline. If the human requests a fresh baseline, fetch `origin/main` and work from a separate copy or worktree based on that ref; do not reset or overwrite a dirty worktree.

#### Close-off trigger and confirmation

If a prompt is only a goodbye, recognize `tot de volgende`, `good evening`, `bye`, `goed weekend`, `ciao`, and equivalent goodbye greetings in any language as a close-off-summary request. Detection is case-insensitive. Do not run the sequence immediately. First ask:

> I detected a close-off greeting. Would you like me to run the close-off summary, preserve the handoff, and commit/push my changes where required?

Run the close-off sequence only after the human confirms. If a goodbye accompanies a concrete task, ask whether close-off should happen after that task and do not close the session prematurely.

#### Close-off summary template

After confirmation, finish the current session with this sequence and report:

```markdown
# Close-off summary — YYYY-MM-DD HH:MM TZ

## Completed this session
- `<plain-language accomplishment>`

## Files and decisions
- Changed files: `<files changed by this session>`.
- Documentation, plans, memory, and feedback copies updated: `<paths>`.
- Important decisions or deferred work: `<items>`.

## Validation
- Tests/checks run: `<commands and results>`.
- Browser or manual validation: `<result, or why not run>`.
- Remaining risks: `<items, or none>`.

## Git handoff
- Branch: `<branch>`.
- Commit: `<hash and subject, or no commit needed>`.
- Push: `<remote/branch and result, or exact blocker>`.
- Work intentionally left untouched: `<unrelated user-owned changes>`.

## Next session
- Resume from: `<session summary, plan, spec, or task path>`.
- First recommended action: `<one concrete next step>`.
```

Before presenting the close-off summary, update the applicable plan entry and durable session handoff (`project-brain/session-summaries/`), run relevant validation and `git diff --check`, and inspect the final diff. On a feature branch other than `main` or `agents-main`, stage only this session's repository changes, commit them, and push the matching remote feature branch. Never stage unrelated user changes, private data, credentials, or generated artifacts. If commit or push cannot safely complete, report the exact blocker; never imply that it succeeded. On `main` or `agents-main`, commit and push only when the human explicitly requests it.

### Plan preservation

When an agent suggests a plan, append it to `project-brain/AGENT-PLANS.txt` so valuable planning context survives chat history loss.

Each saved plan entry must include:

- creation date and time in ISO 8601 format, including timezone when available
- the agent or session context if known
- the plan title or short purpose
- each suggested step
- the current status of each step, such as `proposed`, `approved`, `in progress`, `done`, `blocked`, or `superseded`
- a brief explanation of why each step matters, written clearly enough for a future AI agent to understand

Update the same plan entry as work progresses. If a later plan replaces an earlier one, mark the older plan or affected steps as `superseded` and link or name the newer plan.

### Backlog and FAQ maintenance

Record new product feedback in `docs/BACKLOG.md` before implementation. Link backlog items to the relevant feature specification, task list, or plan when one exists. Keep `docs/FEATURES.md` and `docs/ROADMAP.md` aligned with backlog priority and status. Maintain `docs/FAQ.md` as user-facing behavior changes: add questions that reverse-engineer important workflows, answer only behavior supported by the current implementation, and label planned or unavailable behavior clearly.

Before implementing:

1. Read `docs/CONSTITUTION.md`.
2. Read `docs/DECISIONS.md`.
3. Read `docs/ARCHITECTURE.md`.
4. Read `docs/README.md`.
5. Read `AGENTS_INIT.md` if present.
6. Inspect the current file tree.
7. If archive material exists, inspect it as reference material.
8. Propose a short plan.
9. Ask for approval when the task affects architecture, data handling, deployment, or public behavior.

During implementation:

1. Keep changes small and reviewable.
2. Prefer simple code over clever code.
3. Keep app entry points thin.
4. Put reusable logic in `src/`.
5. Add or update tests when behavior changes.
6. Update docs when decisions change.
7. Update `project-brain/MEMORY.md` when project context changes.
8. After every app edit, update `app/streamlit/app_identity.toml` with the edit time and a `recent_edit` summary of five words or fewer.

### Feature-branch commit and push rule

When the current branch is a feature branch other than `main` or `agents-main`, every agent turn that edits repository files MUST finish by committing and pushing the agent's changes before awaiting further user instruction.

- Check the branch name before committing.
- Stage only the changes made for the current task; preserve unrelated user-owned edits and leave them unstaged.
- Never commit private data, credentials, generated artifacts, or unrelated workspace changes.
- Run relevant validation and `git diff --check` before committing.
- Push to the matching remote feature branch after the commit.
- If commit or push cannot safely complete, report the exact blocker instead of claiming completion.

No automatic commit or push is required on `main` or `agents-main`; do so there only when the user explicitly requests it.

Before finishing:

1. Run relevant tests or explain why they were not run.
2. Summarize changed files.
3. Note open risks or next steps.
4. Avoid claiming success without validation.

## Browser and UI validation

When the project has a browser UI, prefer Playwright for end-to-end validation.

Typical commands:

```bash
npm install -D @playwright/test
npx playwright install
npx playwright test
```

Use browser validation for:
- navigation
- forms
- visual regressions
- key user flows
- app startup checks

## Docker and Azure

Only add Docker or Azure deployment files when there is a real deployment need.

Preferred locations:

```text
infra/docker/
infra/azure/
infra/pipelines/
```

Keep deployment assumptions documented in `docs/ARCHITECTURE.md`.

## Coding style

- Favor boring, readable, maintainable code.
- Do not introduce heavy frameworks without a reason.
- Do not create large abstractions before the project needs them.
- Prefer explicit names and small modules.
- Keep generated files separate from source files.

## Safety rules

Do not:
- commit private data
- expose secrets
- overwrite existing work without explicit approval
- restructure the repo without explaining the plan
- copy archived code blindly
- add unnecessary dependencies
- edit `docs/CONSTITUTION.md` without explicit approval
