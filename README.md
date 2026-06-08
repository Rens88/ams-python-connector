# AMS Python Connector

Python-only client utilities for Teamworks AMS/Smartabase.

This project is being built as a standalone replacement for older R bridge
scripts. The implementation should make Smartabase HTTP requests directly from
Python and keep live writes behind explicit dry-run/confirmation workflows.

## Current Status

The first scaffold includes:

- configuration and credential helpers
- endpoint alias handling
- request builders for users, groups, events, profiles, sync, imports, and
  deletes
- generic response flattening helpers
- local operation manifest writers
- a small HTTP client wrapper
- offline unit tests that do not require Smartabase credentials

## Setup

```bash
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

If you only want to run the current offline tests without installing the
package, use:

```bash
.venv/Scripts/python.exe -m unittest discover -s tests
```

## Environment

Preferred variables:

- `SMARTABASE_URL`
- `SMARTABASE_USERNAME`
- `SMARTABASE_PASSWORD`

Legacy aliases are read as a fallback:

- `SB_URL`
- `SB_USER`
- `SB_PASS`

Passwords are never written into operation configs by the package helpers.

## Example

```python
from ams_smartabase import SmartabaseClient, SmartabaseCredentials

credentials = SmartabaseCredentials.from_env()
client = SmartabaseClient(credentials)
client.login()

users = client.get_user(user_key="group", user_value="Athletes")
```

Write and delete helpers currently build inspectable payload packages. Calling
live write endpoints should stay opt-in and explicit.
