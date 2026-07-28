# Python Sandbox Athlete Initializer Plan

Status: implementation handoff  
Branch: `python-initializer`  
Prepared: 2026-07-28

## Objective

Add a Python-only sandbox athlete initializer to the installable
`ams-python-connector` package. A user with valid AMS/Smartabase credentials
must be able to fetch the users available to that account, optionally restrict
the fetch to an athlete group, and write a generator-compatible
`sandbox_state/athletes.csv` plus non-secret metadata without installing or
running R.

The implementation must be usable in two ways:

1. As an importable package API for downstream repositories.
2. As a packaged command-line entry point for the current synthesis workflow.

Do not shell out to R, generate temporary R scripts, import `smartabaseR`, or
make R an optional dependency. This is a direct Python HTTP implementation
built on the connector's existing client.

## Scope

In scope:

- read-only Smartabase login and endpoint discovery;
- user/athlete roster export;
- optional user filtering by the keys already supported by the connector;
- optional export of accessible Smartabase groups;
- a stable athlete-registry CSV;
- a non-secret metadata JSON document;
- package exports and a console entry point;
- offline unit tests and an opt-in sandbox smoke test;
- documentation for package and cross-repository use.

Out of scope:

- fetching athlete profile-form data;
- generating synthetic data;
- uploading, updating, or deleting Smartabase data;
- changing the synthesis generator's athlete validation rules;
- reproducing every `smartabaseR::sb_get_user_option()` feature in the first
  increment;
- retaining R as a fallback runtime.

## Sources Inspected

Local connector sources:

- `legacy_code/connect_ams.R`
- `legacy_code/smoke_test_login.R`
- `legacy_code/smoke_test_groups.R`
- `src/ams_smartabase/client.py`
- `src/ams_smartabase/config.py`
- `src/ams_smartabase/endpoints.py`
- `src/ams_smartabase/filters.py`
- `src/ams_smartabase/roster.py`
- `src/ams_smartabase/manifests.py`
- `src/ams_smartabase/smoke_test.py`
- `tests/test_client.py`
- `tests/test_config.py`
- `tests/test_roster.py`
- `tests/test_smoke_test.py`

Downstream synthesis sources:

- `../ams-sandbox-data-synthesis/initialize_sandbox_athletes.py`
- `../ams-sandbox-data-synthesis/connect_ams.R`
- `../ams-sandbox-data-synthesis/generate_sandbox_data.py`
- `../ams-sandbox-data-synthesis/README.md`

Primary upstream references:

- <https://teamworksapp.github.io/smartabaseR/reference/sb_get_user.html>
- <https://teamworksapp.github.io/smartabaseR/reference/sb_get_user_option.html>
- <https://teamworksapp.github.io/smartabaseR/reference/sb_get_group.html>
- <https://teamworksapp.github.io/smartabaseR/articles/helper-functions.html>
- <https://github.com/Teamworksapp/smartabaseR/blob/main/R/export.R>
- <https://github.com/Teamworksapp/smartabaseR/blob/main/R/export_filter.R>
- <https://github.com/Teamworksapp/smartabaseR/blob/main/R/export_option.R>
- <https://github.com/Teamworksapp/smartabaseR/blob/main/R/login.R>

Before changing HTTP payload or response handling, re-check the primary
upstream sources because the service can change independently of this package.

## Existing Initialization Behavior

### Credential and configuration resolution

The legacy R scripts load the repository-root `.env` and read:

- `SMARTABASE_URL`
- `SMARTABASE_USERNAME`
- `SMARTABASE_PASSWORD`
- `SMARTABASE_USER_KEY`
- `SMARTABASE_USER_VALUE`
- `SMARTABASE_ATHLETE_GROUP` as a fallback user value
- `SMARTABASE_INCLUDE_ALL_COLS`

The synthesis bridge also accepts the legacy `SB_URL`, `SB_USER`, and `SB_PASS`
aliases in Python before passing normalized environment variables to R.

The package already has `load_credentials()` and `load_dotenv()`, but
`load_credentials()` always looks for `.env` in the current working directory.
The initializer CLI needs an explicit `--env-file` path without mutating
`os.environ` or reading secrets into logs.

Recommended precedence:

1. explicit library arguments or safe CLI arguments;
2. process environment;
3. values from `--env-file`;
4. legacy `SB_*` aliases only when preferred names are absent.

Do not add a password command-line option to the new initializer. Command-line
passwords can leak through process listings and shell history. Use the
environment, `.env`, or an interactive password prompt.

### Login and endpoints

The R implementation logs in through `smartabaseR`, which caches login data and
resolves API endpoint aliases. The Python package already implements:

- `POST /api/v2/user/loginUser`;
- preservation of `session-header` and login cookie metadata;
- optional `GET /api/v3/endpoints?version=v1`;
- known default v1 endpoint aliases.

The initializer should explicitly log in and attempt endpoint discovery before
fetching users. If discovery is unavailable, it should warn and fall back to
the known endpoint names, as required by `AGENTS.python_connector.md`. A failed
login must stop the operation before any output is replaced.

### User selection

The local R code creates an empty user filter by default, which returns all
users visible to the account. When configured, it supports:

- `about`
- `user_id`
- `username`
- `email`
- `group`
- `current_group`

`current_group` ignores `user_value`; all other non-empty keys require a value.

The Python connector already models these payloads in `build_user_request()`:

- no filter -> `usersearch` with `{"identification": null}`;
- `group` -> `groupmembers` with `{"name": "<group>"}`;
- `current_group` -> `currentgroup` with `{"name": ""}`;
- identifier lookups -> `usersearch` identification objects.

It also has `fetch_roster()`, which normalizes common API response shapes into
`RosterEntry`.

### User export shape

The existing synthesis initializer documents these base columns:

1. `user_id`
2. `about`
3. `first_name`
4. `last_name`
5. `username`
6. `email`

The synthesis generator requires exact lowercase `user_id`, `first_name`, and
`last_name` headers. It rejects empty files, missing required values, duplicate
`user_id` values, and duplicate `(first_name, last_name)` pairs.

`smartabaseR` keeps values string-oriented when `guess_col_type = FALSE`. With
`include_all_cols = TRUE`, it can expose fields such as date of birth, middle
name, known-as name, sex, phone, address, groups, roles, and UUIDs. Some of
those fields are nested list/table values.

The current R bridge flattens nested values into single CSV cells. The Python
package currently preserves the raw mapping on each `RosterEntry`, but it has
no stable extended-column serialization contract.

### Group export

`smartabaseR::sb_get_group()` returns accessible group names. The synthesis
bridge optionally writes these to `sandbox_state/groups.csv`. The Python client
already calls `listgroups`, but it does not yet normalize all plausible group
response envelopes into a stable one-column table.

### Local output and metadata

The synthesis bridge creates:

- `sandbox_state/athletes.csv`;
- `sandbox_state/athletes_metadata.json`;
- `sandbox_state/groups.csv` when requested;
- `sandbox_state/README.md` when absent.

Its metadata records path, row count, columns, creation time, source, URL,
filter, and `include_all_cols`. It does not include a password.

The current bridge writes the athlete CSV before all optional work and
validation finishes. The Python replacement should improve this by validating
and staging all requested artifacts before replacing existing files.

## Existing Python Gaps

The package has most of the transport and normalization foundation, but the
following pieces are missing:

- no importable initialization workflow;
- no console script in `pyproject.toml`;
- no stable roster-to-CSV serializer;
- no stable groups-to-CSV normalizer;
- no initialization result/metadata model;
- no explicit `.env` path in `load_credentials()`;
- no atomic multi-artifact write;
- no generator-compatible validation before writing;
- no documented behavior for nested extended user fields;
- no tests for initialization output, failure preservation, or secret
  redaction;
- no downstream migration from the synthesis repo's R bridge.

Also verify the v1 error path while implementing. `post_v1()` currently checks
HTTP status but does not apply the login RPC-exception check. An API error must
not be mistaken for an empty roster and then written as a valid export.

## Proposed Public API

Create `src/ams_smartabase/initializer.py` with an importable function whose
transport can be dependency-injected:

```python
from pathlib import Path

from ams_smartabase import (
    SmartabaseClient,
    initialize_sandbox_athletes,
    load_credentials,
)

credentials = load_credentials(env_path=Path(".env"))
client = SmartabaseClient(credentials)

result = initialize_sandbox_athletes(
    client,
    output_csv=Path("sandbox_state/athletes.csv"),
    output_json=Path("sandbox_state/athletes_metadata.json"),
    group_name="Athletes",
    list_groups=True,
)
```

Recommended signature:

```python
def initialize_sandbox_athletes(
    client: SmartabaseClient,
    *,
    output_csv: str | Path = "sandbox_state/athletes.csv",
    output_json: str | Path = "sandbox_state/athletes_metadata.json",
    group_name: str | None = None,
    current_group: bool = False,
    user_key: str | None = None,
    user_value: object | None = None,
    include_all_cols: bool = False,
    list_groups: bool = False,
    discover_endpoints: bool = True,
) -> AthleteInitializationResult:
    ...
```

Use the existing roster selector conflict rules: only one of `group_name`,
`current_group`, or `user_key` may select users.

Return a frozen result dataclass containing:

- output paths;
- row count;
- CSV columns;
- selected filter;
- normalized URL;
- creation timestamp;
- whether endpoint discovery succeeded or default endpoints were used;
- optional group row count/path.

Export the function and result type from `ams_smartabase.__init__`.

## Proposed CLI

Add a package entry point in `pyproject.toml`:

```toml
[project.scripts]
ams-initialize-sandbox-athletes = "ams_smartabase.initializer:main"
```

Also keep `python -m ams_smartabase.initializer` functional.

Target usage:

```powershell
ams-initialize-sandbox-athletes `
  --env-file .env `
  --group-name "Exact Smartabase Athlete Group"
```

Compatibility-oriented options:

- `--env-file PATH`
- `--output-csv PATH`
- `--output-json PATH`
- `--group-name NAME`
- `--current-group`
- `--user-key {about,user_id,username,email,group,current_group}`
- `--user-value VALUE`
- `--include-all-cols`
- `--list-groups`
- `--groups-csv PATH`
- `--discover-endpoints` / `--no-discover-endpoints`
- `--url` and `--username` as non-secret explicit overrides

The defaults should be relative to the caller's current working directory, not
the installed package directory. This allows the command to be run from the
synthesis repository and naturally produce `sandbox_state/athletes.csv`.

Because the command is specifically a sandbox initializer, default to refusing
a URL that does not contain `sandbox`. If general user export is needed later,
add a separately named generic command instead of silently broadening this
command. The library function should enforce the same rule unless a future API
is deliberately designed for general exports.

Exit non-zero on configuration, authentication, API, validation, or output
errors. Print only paths, row counts, selected non-secret filters, and concise
status messages.

## CSV Contract

The default CSV must always contain the six base columns in this order:

```text
user_id,about,first_name,last_name,username,email
```

Rules:

- serialize every cell as text;
- use UTF-8 and standard CSV quoting;
- use an empty string for missing optional values;
- derive `about` from trimmed first and last names only when the API omits it;
- do not invent `user_id`, first name, or last name;
- preserve Unicode names;
- sort rows deterministically by numeric/text `user_id`, without changing
  identity values;
- do not write raw response JSON by default because it may contain additional
  personal data.

Before writing, fail with row-specific diagnostics for:

- no roster rows;
- missing `user_id`;
- missing `first_name` or `last_name`;
- duplicate `user_id`;
- duplicate `(first_name, last_name)`.

This deliberately aligns the initializer with the downstream generator's
current acceptance rules.

For `include_all_cols=True`:

- retain the six base columns first;
- append normalized extra keys in deterministic sorted order;
- exclude aliases already represented by a base column;
- encode nested mappings/lists as compact, deterministic JSON in one cell;
- never use Python `repr()` for nested data;
- document that extended values can contain sensitive profile information.

Before finalizing extended-column behavior, capture a redacted live sandbox
fixture through the opt-in test path. Do not guess that every tenant uses the
same response keys.

## Metadata Contract

Write JSON with at least:

```json
{
  "source": "ams-python-connector",
  "operation": "initialize_sandbox_athletes",
  "url": "https://example.smartabase.nl/sandbox",
  "created_at": "ISO-8601 timestamp",
  "output_csv": "sandbox_state/athletes.csv",
  "row_count": 0,
  "columns": [],
  "selector": {
    "user_key": "group",
    "user_value": "Athletes"
  },
  "include_all_cols": false,
  "endpoint_discovery": "discovered"
}
```

Never include:

- password;
- authentication headers;
- session header;
- cookies;
- full raw API payloads.

Use the existing redaction helper before serialization as a defense in depth.

## Implementation Steps

### 1. Make credential loading path-aware

Update `load_credentials()` and `SmartabaseCredentials.from_env()` to accept an
optional `env_path` while preserving all current call signatures and
environment precedence.

Add tests for:

- explicit environment over `.env`;
- explicit `.env` path;
- preferred names over legacy aliases;
- missing configuration errors;
- password redaction.

### 2. Harden read response handling

Ensure v1 reads detect Smartabase RPC-exception payloads and raise a useful
error. Do not allow an error envelope to normalize to an empty roster.

Keep this change small and covered by client tests.

### 3. Extend roster/group normalization

In `roster.py` or a small dedicated serialization module:

- expose a base-row conversion for `RosterEntry`;
- normalize API aliases consistently;
- normalize group response envelopes to `{"group": "<name>"}` rows;
- add deterministic nested-value serialization for extended columns;
- preserve raw mappings only in memory.

Do not put file-writing behavior in `SmartabaseClient`; keep transport and
local persistence separable.

### 4. Add the initialization workflow

Implement `initializer.py` with:

1. sandbox URL validation;
2. login;
3. endpoint discovery with warning/fallback;
4. roster fetch through `fetch_roster()`;
5. optional group fetch;
6. normalization and validation;
7. metadata construction;
8. staging of all requested artifacts;
9. atomic replacement of final paths only after all staging succeeds;
10. a structured result.

Use temporary files in each target file's directory so `Path.replace()` stays
on the same filesystem. Clean up staged files after errors. If an older
registry exists, a failed refresh must leave it unchanged.

Do not create or update a consumer repository's `.gitignore` automatically.
Document that `sandbox_state/` contains sensitive local data and must be
ignored.

### 5. Add the CLI and package exports

- implement `build_parser()`, credential resolution, and `main()` in the new
  module;
- add the console entry point;
- support `python -m ams_smartabase.initializer`;
- export the public API in `src/ams_smartabase/__init__.py`;
- keep password input out of arguments and logs.

### 6. Add offline tests

Create `tests/test_initializer.py` using stub clients and temporary
directories. Cover:

- default six-column CSV and column order;
- group, current-group, and identifier selectors;
- conflicting selectors;
- optional groups CSV;
- endpoint discovery success and fallback;
- no live HTTP access;
- empty roster rejection;
- required-field rejection;
- duplicate ID and duplicate-name rejection;
- Unicode and CSV quoting;
- deterministic row ordering;
- deterministic nested extended-column JSON;
- metadata fields and secret exclusion;
- preservation of an existing registry when any later step fails;
- CLI exit codes and concise output;
- sandbox URL enforcement.

Extend existing roster, client, config, and packaging tests where appropriate.
The default test suite must remain:

```powershell
python -m unittest discover -s tests
```

### 7. Add opt-in live sandbox verification

Add a narrowly scoped read-only smoke test that runs only when:

- credentials are available through normal package configuration;
- the normalized URL contains `sandbox`;
- an explicit live-test flag is set.

The agent must not inspect `.env` directly. The smoke test should:

1. log in;
2. discover endpoints or record fallback;
3. fetch a named test athlete group;
4. write only to a temporary ignored folder;
5. assert the required base columns and non-empty IDs/names;
6. report counts without printing roster contents.

Do not require R or compare against a live R invocation. If response-shape
parity needs confirmation, use redacted fixtures derived from an authorized
sandbox run.

### 8. Document package usage

Update:

- `README.md` with library and CLI examples;
- `.env.example` with optional athlete-group settings;
- `.gitignore` to include `sandbox_state/` for users who run the CLI in this
  repository;
- `agent-docs/open-work.md` after the feature is complete.

Explicitly state that the operation is read-only remotely but writes or
replaces local registry files.

### 9. Migrate the synthesis repository separately

After the connector feature is tested and installable:

1. install the connector into the synthesis environment using its normal
   editable or pinned dependency workflow;
2. replace
   `ams-sandbox-data-synthesis/initialize_sandbox_athletes.py` with a thin
   Python wrapper around the package API, or update synthesis documentation to
   invoke the package console command directly;
3. remove all Rscript discovery, temporary R generation, and `smartabaseR`
   installation requirements from that initializer path;
4. preserve the existing synthesis CLI flags where practical;
5. verify `generate_sandbox_data.py` accepts the resulting CSV unchanged;
6. update synthesis README and `.env.example`;
7. keep `sandbox_state/` ignored.

Do not make the connector import the synthesis repository. Dependency direction
must remain synthesis -> connector.

## Verification Checklist

- [ ] No production module imports or invokes R.
- [ ] The feature works on a machine with no R installation.
- [ ] The initializer is importable from `ams_smartabase`.
- [ ] The installed console command works outside the connector checkout.
- [ ] Login and endpoint discovery occur before roster export.
- [ ] Endpoint-discovery failure falls back safely and is recorded.
- [ ] Default export is the stable six-column CSV.
- [ ] The synthesis generator accepts the output without transformation.
- [ ] Group-filtered and all-accessible-user exports are covered.
- [ ] Invalid or duplicate athlete data cannot replace a valid existing file.
- [ ] Optional groups export has a stable `group` column.
- [ ] Metadata contains no password, cookie, or session token.
- [ ] Offline unit tests pass.
- [ ] Opt-in sandbox smoke test passes without printing personal data.
- [ ] Wheel and editable installs expose the same API and command.
- [ ] README documents local overwrite and sensitive-data behavior.

## Risks and Decisions to Revisit

### Live response shape

`RosterEntry` handles several common aliases, but a real tenant may return a
different envelope or nested identity shape. Obtain a redacted fixture before
broadening normalization.

### `include_all_cols`

The upstream option includes sensitive and nested fields. The first increment
may safely ship the stable base export while keeping `include_all_cols`
experimental or deferred. Do not claim full parity until tested.

### Duplicate names

Smartabase can theoretically contain two users with the same first and last
name. The current synthesis generator rejects that state. Preserve that
restriction for generator compatibility and provide an actionable error
listing row numbers and non-secret IDs.

### Sandbox naming

Checking for the literal substring `sandbox` matches the connector's existing
mutation safety convention but may not cover every legitimate test tenant.
If a real sandbox uses another URL convention, add an explicit, documented
override rather than silently removing the guard.

### Atomic multi-file output

Replacing several files cannot be perfectly transactional across arbitrary
filesystems. Stage every file first, replace the primary CSV last, and document
the ordering. Keep metadata sufficient to identify the completed export.

## Definition of Done

This feature is complete when a downstream project with only Python and the
installed `ams-python-connector` package can run one documented command or call
one documented function to produce a validated
`sandbox_state/athletes.csv`, optionally produce `groups.csv`, inspect
non-secret metadata, and immediately run the synthesis generator without any R
runtime or manual CSV transformation.
