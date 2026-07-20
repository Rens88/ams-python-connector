# AMS Python Connector

Python-only client utilities for Teamworks AMS/Smartabase.

## Test Current Functionality

1. Activate the virtual environment in PowerShell inside VS Code:

```powershell
.\.venv\Scripts\Activate.ps1
```

2. Run the offline Python test suite:

```powershell
python -m unittest discover -s tests
```

3. Run the live Python smoke test with credentials from the repo-root `.env`:

```powershell
python examples/smoke_test_connection.py --discover-endpoints --list-groups
```

4. Run the example event replay workflow in dry-run mode. This now writes a preflight diff artifact before any delete/insert step:

```powershell
python examples/replay_form_entries.py
```

5. Run the same workflow live against sandbox, with explicit confirmation:

```powershell
python examples/replay_form_entries.py --execute --confirm --discover-endpoints
```

To force the older sandbox behavior and delete every existing event in the specific form/user/date range before upload:

```powershell
python examples/replay_form_entries.py --execute --confirm --discover-endpoints --delete-all-in-range
```

To run a delete-only workflow against the same example target, without uploading any data:

```powershell
python examples/delete_form_entries.py --execute --confirm --discover-endpoints
```

6. If you want to override `.env` values explicitly:

```powershell
python examples/smoke_test_connection.py --url "teamnl.smartabase.nl/sandbox/" --username "your.username" --discover-endpoints --list-groups
```

7. Run the legacy R login smoke test from an R session:

```r
source("./legacy_code/smoke_test_login.R")
```

8. Run the legacy R group smoke test from an R session:

```r
source("./legacy_code/smoke_test_groups.R")
```

9. Run the legacy R user/profile smoke test from an R session:

```r
source("./legacy_code/connect_ams.R")
```

The Python and legacy R smoke tests are read-only. They use the repo-root `.env`
file when present.

Live delete/modify operations are restricted to Smartabase sandbox URLs. On non-sandbox sites, only dry-run inspection is allowed unless that guard is intentionally changed in code.

## Current Status

The current scaffold includes:

- configuration and credential helpers
- endpoint alias handling
- request builders for users, groups, events, profiles, sync, imports, and deletes
- generic response flattening helpers
- local operation manifest writers
- a small HTTP client wrapper
- an auditable example workflow for count -> preflight diff -> targeted delete or full-range sandbox delete -> count -> upload -> count on one event form/user/date range
- offline unit tests that do not require Smartabase credentials
- read-only live smoke tests for Python and legacy R

## Setup

Install the package and development dependencies if needed:

```powershell
python -m pip install -e ".[dev]"
```

## Library Use From Another Repo

The distribution name is `ams-python-connector`, but the Python import package
is `ams_smartabase`.

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
```

Write helpers accept:

- rows of mappings such as `list[dict]`
- a CSV path
- a pandas-style DataFrame object that supports `to_dict("records")`
- optional user resolution from `username`, `email`, or `about` during client write calls

Example:

```python
from ams_smartabase import SmartabaseClient, SmartabaseCredentials

credentials = SmartabaseCredentials.from_env()
client = SmartabaseClient(credentials)

result = client.insert_event("training_load.csv", form="Training Load", dry_run=True)
```

If write rows do not already contain `user_id`, client write calls can resolve
them through Smartabase lookups:

```python
result = client.insert_event(
    [{"username": "ada", "Score": 42}],
    form="Wellness",
    resolve_user_ids=True,
    dry_run=True,
)
```

External-consumer validation has been checked with isolated editable and wheel
installs from outside this repository.

## Environment

Preferred variables:

- `SMARTABASE_URL`
- `SMARTABASE_USERNAME`
- `SMARTABASE_PASSWORD`

Legacy aliases:

- `SB_URL`
- `SB_USER`
- `SB_PASS`

Local secrets should go in the repo-root `.env`. Use `.env.example` as the template.

## Example

```python
from ams_smartabase import SmartabaseClient, SmartabaseCredentials

credentials = SmartabaseCredentials.from_env()
client = SmartabaseClient(credentials)
client.login()

users = client.get_user(user_key="group", user_value="Athletes")
```

Write and delete helpers currently build inspectable payload packages. Live
write endpoints should stay opt-in and explicit.
