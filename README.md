# AMS Python Connector

Python-only client utilities for Teamworks AMS/Smartabase. The package is intended to let users discover AMS terminology, fetch data, upload new data, and perform carefully controlled mutations without requiring the legacy R connector at runtime.

This is an independent, unofficial project. It is not affiliated with,
endorsed by, or maintained by Teamworks. Users remain responsible for ensuring
that their access and use are authorized and comply with applicable security,
privacy, retention, and organizational policies. Installing or using this
package does not by itself guarantee that compliance.

## Project Documentation

Authoritative project documents:

- [PROJECT_AIMS.md](PROJECT_AIMS.md): desired product outcomes and success criteria.
- [RISK_MODEL.md](RISK_MODEL.md): risk levels, trigger scenarios, safeguards, and agent behavior.
- [docs/connector-caller-diagnostics-boundary.md](docs/connector-caller-diagnostics-boundary.md): provider-versus-caller ownership for validation, warnings, errors, and recovery decisions.
- [docs/roadmap.md](docs/roadmap.md): implementation progress for each project aim.
- [.specify/memory/constitution.md](.specify/memory/constitution.md): durable engineering and safety principles.
- [CONTRIBUTING.md](CONTRIBUTING.md): human collaboration, testing, credential, and pull request guidance.
- [agent-docs/README.md](agent-docs/README.md): coding-agent documentation index.

Destructive-operation safeguards are central to this repository. Live delete and modify operations are restricted to Smartabase sandbox URLs in the current implementation. On non-sandbox sites, only dry-run inspection is allowed unless that guard is intentionally changed in code and reviewed as a high-risk change.

The connector remains a generic Python client; interactive and scheduled
workflow policy belongs to callers. Scheduled workflows must not modify or
delete existing AMS data. Where they create derived data, they should use a
separate destination form by default to preserve the source data, while the
destination and its naming remain workflow decisions. This does not relax the
constitution's dry-run and explicit-confirmation requirements for live
mutations.

## Current Capabilities

The current scaffold includes:

- configuration and credential helpers
- endpoint alias handling
- request builders for users, groups, events, profiles, sync, imports, and deletes
- generic response flattening helpers
- roster fetch and user ID resolution helpers
- a Python-only sandbox athlete initializer with stable CSV and metadata output
- payload builders for event insert/update/upsert, profile upsert, nested table rows, and deletes
- local operation manifest writers
- a small HTTP client wrapper
- auditable example workflows for count, preflight diff, targeted delete or sandbox full-range delete, upload, and recount
- offline unit tests that do not require Smartabase credentials
- read-only live smoke-test entrypoints

See [docs/roadmap.md](docs/roadmap.md) for limitations and remaining work. In particular, broader multi-form orchestration, richer profile planning, durable sync-state handling, attachment download, and opt-in live integration coverage are still incomplete or require verification.

## Quick Start

Activate the virtual environment in PowerShell inside VS Code:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the package and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Run the offline Python test suite:

```powershell
python -m unittest discover -s tests
```

Run the live Python smoke test with credentials from the repo-root `.env`:

```powershell
python examples/smoke_test_connection.py --discover-endpoints --list-groups
```

The Python smoke test is read-only. It uses the repo-root `.env` file when present through the normal credential-loading path.

Create a validated local athlete registry from a named sandbox group:

```powershell
ams-initialize-sandbox-athletes --env-file .env --group-name "Exact Athlete Group"
```

The command is read-only in Smartabase, refuses URLs that do not contain
`sandbox`, and writes or replaces local files under `sandbox_state/`. Those
files contain athlete identifiers and personal data: keep the directory
ignored and access-controlled, and remove it when no longer needed.

## Environment

Preferred variables:

- `SMARTABASE_URL`
- `SMARTABASE_USERNAME`
- `SMARTABASE_PASSWORD`

Optional initializer variables:

- `SMARTABASE_USER_KEY`
- `SMARTABASE_USER_VALUE`
- `SMARTABASE_ATHLETE_GROUP`
- `SMARTABASE_INCLUDE_ALL_COLS`

Legacy aliases:

- `SB_URL`
- `SB_USER`
- `SB_PASS`

Local secrets should go in the repo-root `.env`. Use `.env.example` as the template if present. Never commit real credentials, fetched AMS data, generated run artifacts, or Smartabase operation outputs.

## Library Use

The distribution name is `ams-python-connector`, but the Python import package is `ams_smartabase`.

For editable development from another repo:

```powershell
python -m pip install -e "C:\path\to\ams-python-connector"
```

For a regular install from a local checkout:

```powershell
python -m pip install "C:\path\to\ams-python-connector"
```

Minimal downstream usage:

```python
from ams_smartabase import SmartabaseClient, SmartabaseCredentials

credentials = SmartabaseCredentials.from_env()
client = SmartabaseClient(credentials)
client.login()

users = client.get_user(user_key="group", user_value="Athletes")
```

### Diagnostics And Caller Responsibilities

The connector exposes stable diagnostic types and structured context for
generic AMS behavior. Calling applications should catch these types, add their
own file/run/stage context, and perform source-specific corrections without
parsing error-message text. For example, invalid or ambiguous date strings are
rejected before transport:

```python
from ams_smartabase import AMSDateFormatError, parse_ams_date

try:
    start_date = parse_ams_date(source_value, field="start_date", row_index=12)
except AMSDateFormatError as error:
    print(error.as_dict())  # includes DD/MM/YYYY and no_request_sent
    raise
```

`discover_endpoint_provenance(...)` provides a typed, sanitized fallback
warning plus the exact aliases that were discovered or defaulted.
`require_exact_event_ids(...)` fails closed when a read response cannot prove
deletable event IDs. `assess_operation_execution(...)` distinguishes
`confirmed_complete`, `accepted_unverified`, `partial_or_unknown`, and
`no_request_sent`; callers must reconcile `accepted_unverified` rather than
claiming success or retrying automatically.

The complete provider-versus-caller decision rules and dated examples are in
[the diagnostics boundary record](docs/connector-caller-diagnostics-boundary.md).

Initialize a generator-compatible athlete registry without R:

```python
from pathlib import Path

from ams_smartabase import (
    SmartabaseClient,
    initialize_sandbox_athletes,
    load_credentials,
)

credentials = load_credentials(env_path=Path(".env"))
result = initialize_sandbox_athletes(
    SmartabaseClient(credentials),
    output_csv=Path("sandbox_state/athletes.csv"),
    output_json=Path("sandbox_state/athletes_metadata.json"),
    group_name="Exact Athlete Group",
    list_groups=True,
)
print(f"Exported {result.row_count} athletes")
```

The default CSV contract is:

```text
user_id,about,first_name,last_name,username,email
```

Rows are validated for required identity fields and duplicate IDs/names before
the existing athlete registry is replaced. The metadata JSON records only
non-secret operation details; it does not store credentials, session headers,
cookies, or raw API responses. Endpoint discovery falls back to known endpoint
names with a warning.

All requested files are staged before any destination is replaced. If groups
are requested, replacement order is groups, metadata, then the primary athlete
CSV last. Multi-file replacement cannot be perfectly transactional: a rare
interruption or operating-system replacement failure can leave newer ancillary
files beside the previous athlete CSV. The metadata records
`output_csv_sha256` (and `groups_csv_sha256` when applicable), so consumers can
verify that each CSV matches the completed export; rerun initialization if a
digest does not match.

Omitting a selector exports every user accessible to the account and emits a
scope warning. `--include-all-cols` (or `include_all_cols=True`) is
experimental: tenant-specific fields can contain more sensitive profile data,
top-level credential-like extended fields are excluded, credential-like keys
inside nested values are redacted, and nested values are serialized as
deterministic JSON cells. Confirm a redacted sandbox response shape before
depending on those extra columns.

The literal `sandbox` URL check is a conservative naming heuristic and refusal
guard, not independent verification that a tenant is non-production. Confirm
the environment and your authorization before running the initializer.

Run the opt-in, read-only live initializer verification only against an
authorized named sandbox group:

```powershell
$env:SMARTABASE_RUN_LIVE_INITIALIZER_TEST = "1"
$env:SMARTABASE_ATHLETE_GROUP = "Exact Sandbox Test Group"
python -m unittest tests.test_initializer_live -v
```

The live test writes to a temporary directory and reports only the row count,
not roster contents.

Write helpers accept rows of mappings, CSV paths, and dataframe-like objects that support `to_dict("records")`.

```python
from ams_smartabase import SmartabaseClient, SmartabaseCredentials

credentials = SmartabaseCredentials.from_env()
client = SmartabaseClient(credentials)

result = client.insert_event("training_load.csv", form="Training Load", dry_run=True)
```

If write rows do not already contain `user_id`, client write calls can resolve them through Smartabase lookups:

```python
result = client.insert_event(
    [{"username": "ada", "Score": 42}],
    form="Wellness",
    resolve_user_ids=True,
    dry_run=True,
)
```

The package exposes the same initializer API through editable and wheel
installs, and the console command uses paths relative to the caller's current
working directory.

## Safety Modes

Every write method accepts an optional `mode` (`ams_smartabase.SafetyMode` or
the strings `"default"`, `"human"`, `"auto"`; unrecognized values fail
closed). Full behavior and rationale: `specs/001-api-safety-modes/spec.md`.

- **`default`** (the default when `mode` is omitted): unchanged behavior —
  the existing `dry_run`/`confirm` booleans.
- **`human`**: create-only writes (`insert_event` only) get a single
  yes/no decision instead of the full confirmation flow, but only when this
  process is attached to a real interactive terminal. A script, CI job, or
  coding agent cannot satisfy this — there is no way to supply that decision
  programmatically. A destination collision (an existing record for the same
  identity) is checked before the prompt and always refuses the write.
- **`auto`**: create-only writes with no prompt at all, gated behind an
  `AutoQualification` (see `ams_smartabase.modes`) that a human must grant
  interactively in advance, bound to a specific runner identity via the
  `AMS_AUTO_RUNNER_ID` environment variable. `update_event`, `upsert_event`,
  `upsert_profile`, and `delete_event` reject `human`/`auto` outright,
  regardless of scope — those operations always use the full `default` path.

```python
result = client.insert_event(
    [{"user_id": 150176, "start_date": "07/08/2026", "AC Short": 0.98}],
    form="HRV AC Ratios",
    mode="human",  # prompts once, live, in your own terminal — never from a script
)
```

None of these modes validate the *meaning* of the data being written (for
example, whether a submitted value is a plausible reading for its field).
That is deliberately out of scope for the connector — see AGENTS.md — and
remains the calling workflow's responsibility.

## Example Workflows

Run the example event replay workflow in dry-run mode. This writes a preflight diff artifact before any delete or insert step:

```powershell
python examples/replay_form_entries.py
```

Run the same workflow live against sandbox, with explicit confirmation:

```powershell
python examples/replay_form_entries.py --execute --confirm --discover-endpoints
```

Force sandbox-only full-range deletion for the specific form/user/date range before upload:

```powershell
python examples/replay_form_entries.py --execute --confirm --discover-endpoints --delete-all-in-range
```

Run a delete-only workflow against the same example target, without uploading replacement data:

```powershell
python examples/delete_form_entries.py --execute --confirm --discover-endpoints
```

Override `.env` values explicitly for a read-only smoke test:

```powershell
python examples/smoke_test_connection.py --url "teamnl.smartabase.nl/sandbox/" --username "your.username" --discover-endpoints --list-groups
```

Legacy R scripts remain in [legacy_code](legacy_code/) as reference material and smoke-test comparisons only. They are not runtime dependencies for the Python package.
