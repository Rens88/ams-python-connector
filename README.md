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

4. If you want to override `.env` values explicitly:

```powershell
python examples/smoke_test_connection.py --url "teamnl.smartabase.nl/sandbox/" --username "your.username" --discover-endpoints --list-groups
```

5. Run the legacy R login smoke test from an R session:

```r
source("./legacy_code/smoke_test_login.R")
```

6. Run the legacy R group smoke test from an R session:

```r
source("./legacy_code/smoke_test_groups.R")
```

7. Run the legacy R user/profile smoke test from an R session:

```r
source("./legacy_code/connect_ams.R")
```

The Python and legacy R smoke tests are read-only. They use the repo-root `.env`
file when present.

## Current Status

The current scaffold includes:

- configuration and credential helpers
- endpoint alias handling
- request builders for users, groups, events, profiles, sync, imports, and deletes
- generic response flattening helpers
- local operation manifest writers
- a small HTTP client wrapper
- offline unit tests that do not require Smartabase credentials
- read-only live smoke tests for Python and legacy R

## Setup

Install the package and development dependencies if needed:

```powershell
python -m pip install -e ".[dev]"
```

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
