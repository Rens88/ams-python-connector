# AMS Python Connector

Python-only client utilities for Teamworks AMS/Smartabase. The package is intended to let users discover AMS terminology, fetch data, upload new data, and perform carefully controlled mutations without requiring the legacy R connector at runtime.

## Project Documentation

Authoritative project documents:

- [PROJECT_AIMS.md](PROJECT_AIMS.md): desired product outcomes and success criteria.
- [docs/roadmap.md](docs/roadmap.md): implementation progress for each project aim.
- [.specify/memory/constitution.md](.specify/memory/constitution.md): durable engineering and safety principles.
- [CONTRIBUTING.md](CONTRIBUTING.md): human collaboration, testing, credential, and pull request guidance.
- [agent-docs/README.md](agent-docs/README.md): coding-agent documentation index.

Destructive-operation safeguards are central to this repository. Live delete and modify operations are restricted to Smartabase sandbox URLs in the current implementation. On non-sandbox sites, only dry-run inspection is allowed unless that guard is intentionally changed in code and reviewed as a high-risk change.

## Current Capabilities

The current scaffold includes:

- configuration and credential helpers
- endpoint alias handling
- request builders for users, groups, events, profiles, sync, imports, and deletes
- generic response flattening helpers
- roster fetch and user ID resolution helpers
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

## Environment

Preferred variables:

- `SMARTABASE_URL`
- `SMARTABASE_USERNAME`
- `SMARTABASE_PASSWORD`

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

External-consumer validation has been checked manually with isolated editable and wheel installs from outside this repository. An automated packaging/integration check is still recommended.

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
