# Agent Guidance - Python Smartabase Client

Last updated: 2026-06-10

## Project Aim

This repository provides a Python-only client for Teamworks AMS/Smartabase data.
Despite the historical `python_fetcher` name, the scope is no longer limited to
fetching. The Python client should mirror the useful behavior exposed by
Teamworks `smartabaseR`: reading data, synchronising changed data, inserting new
event data, updating existing event data, upserting event data, upserting profile
data, deleting event data, authentication helpers, metadata helpers, and
deprecated wrapper compatibility where practical.

The implementation must be standalone Python. Do not require R, Rscript, an R
runtime, or the `smartabaseR` R package at runtime. `smartabaseR` may be used
only as reference material for endpoint names, payload shape, response
flattening, validation rules, and safety behavior. Production code should make
HTTP requests directly from Python.

## Sources Inspected

The current guidance is based on Teamworks public `smartabaseR` documentation and
the public GitHub source inspected on 2026-06-10:

- https://teamworksapp.github.io/smartabaseR/
- https://teamworksapp.github.io/smartabaseR/reference/index.html
- https://teamworksapp.github.io/smartabaseR/articles/exporting-data.html
- https://teamworksapp.github.io/smartabaseR/articles/importing-data.html
- https://teamworksapp.github.io/smartabaseR/articles/deleting-data.html
- https://teamworksapp.github.io/smartabaseR/articles/synchronising-with-smartabase.html
- https://teamworksapp.github.io/smartabaseR/articles/helper-functions.html
- https://github.com/Teamworksapp/smartabaseR/blob/main/NAMESPACE
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/export.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/export_body.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/export_filter.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/export_option.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/export_validate.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/import.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/import_body.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/import_clean.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/import_handler.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/import_option.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/import_result.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/import_split.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/import_validate.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/delete.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/login.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/login_option.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/pull_smartabase.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/push_smartabase.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/utils.R
- https://github.com/Teamworksapp/smartabaseR/blob/main/R/sb_class.R

When changing API behavior, re-check the Teamworks docs and source first. This
API can change independently of this repository.

## Task Handoff

When looking for the next implementation tasks, read `agent-docs/open-work.md`
first. Treat that file as the current work queue and project-direction note for
this repository.

## Python-Only Boundary

- Do not call `Rscript`.
- Do not generate temporary `.R` scripts.
- Do not import or shell out to `smartabaseR`.
- Do not require users to install R packages.
- Do use `requests` or another explicit Python HTTP client.
- Do keep all credentials in environment variables, local `.env` files, keyring,
  or another local secret manager. Never commit real credentials.
- Do keep exported athlete/user/profile/event data out of git.

The broader repository may still contain older R-bridge scripts. This file is
the guidance for the Python-only Smartabase client and any replacement of those
bridges.

## Required Functionality Coverage

The Python client should cover every exported `smartabaseR` behavior below:

- `sb_login()` and `sb_login_option()`: validate credentials, obtain login
  metadata, support quiet/non-interactive mode, and discover endpoint aliases.
- `sb_get_user()` with `sb_get_user_filter()` and `sb_get_user_option()`: export
  Smartabase user data.
- `sb_get_group()` with `sb_get_group_option()`: export accessible group names.
- `sb_get_event()` with `sb_get_event_filter()` and `sb_get_event_option()`:
  export event-form data by form, date range, time range, user filters, data
  filters, result limits, and attachment options.
- `sb_get_profile()` with `sb_get_profile_filter()` and
  `sb_get_profile_option()`: export profile-form data.
- `sb_sync_event()` with `sb_sync_event_filter()` and
  `sb_sync_event_option()`: export event records inserted or updated since a
  previous sync timestamp and persist the returned `new_sync_time`.
- `sb_insert_event()` with `sb_insert_event_option()`: insert only new event
  records, never update existing events.
- `sb_update_event()` with `sb_update_event_option()`: update existing event
  records and require valid `event_id` values.
- `sb_upsert_event()` with `sb_upsert_event_option()`: update rows with
  `event_id` and insert rows where `event_id` is missing, matching
  `smartabaseR` split behavior.
- `sb_upsert_profile()` with `sb_upsert_profile_option()`: upsert profile-form
  rows through the profile import endpoint.
- `sb_delete_event()` with `sb_delete_event_option()`: delete event records by
  explicit Smartabase `event_id`.
- `sb_date_range()`: create day-first date ranges from a duration and end date.
- `sb_select_metadata()`: identify metadata columns present in a data frame.
- `print(<sb_df>)`: expose request/status/import/export metadata in Python
  result objects or manifests.
- Deprecated `pull_smartabase()`: support as a compatibility alias to the modern
  get/sync methods when useful, but prefer explicit method names.
- Deprecated `push_smartabase()`: support as a compatibility alias to the modern
  insert/update/upsert methods when useful, but prefer explicit method names.
- Deprecated `get_metadata_names()`: alias to `sb_select_metadata()`.
- Deprecated `save_credentials()`: do not reproduce `.Renviron` behavior, but
  document compatible environment variables and safer Python alternatives.

Do not invent unexported functions. For example, current public exports include
`sb_upsert_profile()` but not a separate `sb_update_profile()`. Implement a
separate profile update method only if the live API behavior is confirmed.

## HTTP Behavior

Normalize Smartabase URLs to `https://...`.

Authentication and endpoint discovery:

- `POST /api/v2/user/loginUser`
- Body includes `username`, `password`, and `loginProperties` with the
  Smartabase site/app name and a `clientTime` string in `YYYY-MM-DDTHH:MM`
  format.
- Use HTTP Basic Auth with Smartabase username and password.
- Use a Python user agent such as `ams-python-smartabase-client`.
- Set `X-GWT-Permutation: HostedMode` on login and endpoint-discovery requests.
- Preserve `session-header` and login cookies from login when needed.
- Optionally call `GET /api/v3/endpoints?version=v1` after login to discover
  endpoint aliases instead of assuming endpoint names forever.
- Endpoint discovery requests should reuse HTTP Basic Auth plus the login
  `session-header` and `JSESSIONID` cookie. If discovery is unavailable for a
  tenant or account, fall back to the known default endpoint names and warn
  rather than breaking all read operations.

Most v1 data operations use:

`POST /api/v1/<endpoint>?informat=json&format=json`

Known endpoint names from current `smartabaseR` source:

- `usersearch`: user search by `about`, `user_id`, `username`, or `email`.
- `groupmembers`: users in a named group.
- `currentgroup`: users in the currently loaded Smartabase group.
- `listgroups`: group names accessible to the logged-in user.
- `eventsearch`: event export without form data filters.
- `filteredeventsearch`: event export with form data filters.
- `profilesearch`: profile export.
- `synchronise`: event sync since server timestamp.
- `eventsimport`: event insert/update/upsert.
- `profileimport`: profile upsert.
- `deleteevent`: event deletion.

Treat endpoints as configurable when the endpoint-discovery API returns aliases.
Fail loudly if a required endpoint is missing.

## User And Group Export

Implement `get_user` behavior:

- If no filter is provided, call `usersearch` with `{"identification": null}`.
- `user_key = "about"` builds identification entries with `firstName` and
  `lastName` split from the full name.
- `user_key = "user_id"` builds entries with numeric `userId`.
- `user_key = "username"` builds entries with `username`.
- `user_key = "email"` builds entries with `emailAddress`.
- `user_key = "group"` calls `groupmembers` with `{"name": "<group>"}`.
- `user_key = "current_group"` calls `currentgroup` with `{"name": ""}` and
  ignores `user_value`.

Implement `get_group` behavior:

- Call `listgroups` with `{"name": ""}`.
- Return a flat table of accessible group names.

For user exports, support:

- `include_all_cols`: include extended user fields where the API returns them,
  such as phone, address, date of birth, groups, roles, UUIDs, and profile
  identifiers.
- `include_missing_user`: preserve missing-user behavior where relevant.
- `guess_col_type`: default may infer types, but raw CSV export should be able
  to keep all values as strings.
- `interactive_mode`: quiet mode for automation.
- `cache`: cache login and user lookup data per Python process when safe.

## Event/Profile Export

Event export request body:

```json
{
  "formNames": "Example Form",
  "userIds": [12345],
  "startDate": "01/03/2026",
  "finishDate": "07/03/2026",
  "startTime": "12:00 am",
  "finishTime": "11:59 pm"
}
```

Profile export request body:

```json
{
  "formNames": "Athlete Profile",
  "userIds": [12345]
}
```

Sync request body:

```json
{
  "formName": "Example Form",
  "userIds": [12345],
  "lastSynchronisationTimeOnServer": 1672531200000
}
```

Export rules:

- `date_range` is required for event export and must be two strings in
  `dd/mm/yyyy` format.
- `time_range` defaults to `12:00 am` through `11:59 pm` and must be two strings
  in `h:mm AM/PM` style.
- `start_date` must be on or before `end_date`.
- For exports with `include_user_data = false`, require `user_key = "user_id"`
  and explicit user IDs.
- If user filters are omitted, warn that future `smartabaseR` versions expect
  explicit `user_key` and `user_value`.
- `include_missing_user` should add empty rows for requested users with no event
  data where the API supports it.
- `include_uuid` should attach user-defined UUID values where supported.
- `download_attachment` should download file-upload attachments and include
  useful file metadata. Store attachments in a run-local folder and record file
  paths in the manifest.
- `guess_col_type = false` should keep exported values as strings except
  metadata IDs where the API clearly returns numeric identifiers.

Flatten event/profile JSON into rows by preserving metadata and expanding
`rows -> pairs`. Preserve raw JSON alongside flattened CSV when a response
cannot be flattened losslessly.

Preferred metadata columns:

- `about`
- `user_id`
- `form`
- `start_date`
- `end_date`
- `start_time`
- `end_time`
- `entered_by_user_id`
- `event_id`
- `uuid`
- `export`
- `synchronise`

## Filters

Supported user keys:

- `user_id`
- `about`
- `username`
- `email`
- `group`
- `current_group`

Event data filters are supported only for event exports, not profile exports.
Use:

- `data_key`: Smartabase field name.
- `data_value`: comparison value.
- `data_condition`: comparison operator.

Supported data conditions and Smartabase numeric codes:

- `equal_to` or `=` -> `1`
- `not_equal_to` or `!=` -> `2`
- `contains` or `%in%` -> `3`
- `less_than` or `<` -> `4`
- `greater_than` or `>` -> `5`
- `less_than_or_equal_to` or `<=` -> `6`
- `greater_than_or_equal_to` or `>=` -> `7`

Filtered event request bodies include:

```json
{
  "filter": [
    {
      "formName": "Example Form",
      "filterSet": [
        {"key": "Duration", "value": "35", "filterCondition": 5}
      ]
    }
  ]
}
```

Support multiple data filters when `data_key`, `data_value`, and
`data_condition` lengths are compatible. Follow current source behavior by
rejecting duplicate `data_key` values unless a real sandbox response proves the
site supports duplicate keys safely.

Support `events_per_user` by sending `resultsPerUser`.

## Import, Update, And Upsert

All push behavior must be explicit, inspectable, and safe. Default to a dry-run
package that writes request payloads, row counts, and a manifest locally. Do not
call Smartabase write endpoints unless the user passes an explicit confirmation
flag for the exact operation.

Event import endpoint:

`POST /api/v1/eventsimport?informat=json&format=json`

Profile import endpoint:

`POST /api/v1/profileimport?informat=json&format=json`

Event import payloads use an `events` array. Each event contains:

- `formName`
- `startDate`
- `finishDate`
- `startTime`
- `finishTime`
- `enteredByUserId`
- `userId`: nested object with numeric `userId`
- `existingEventId` for update actions
- `rows`: list of row objects with zero-based `row` and `pairs`

Profile import payloads use profile records directly rather than an `events`
wrapper. Profile records include:

- `formName`
- `enteredByUserId`
- `userId`: nested object with numeric `userId`
- `rows`: list of row objects with zero-based `row` and `pairs`

Input data handling:

- Accept pandas data frames, CSV paths, or lists of dictionaries.
- Treat the upload frame as string-oriented; convert missing non-ID values to
  empty strings.
- Remove or reject protected identity field names `First Name` and `Last Name`
  before import payload construction, matching `smartabaseR` safety behavior.
- Normalize ID column names such as `User_ID`, `About`, `Username`, `Email`, and
  `Event_ID` to lower-case internal names.
- Metadata columns removed from field pairs are `user_id`, `about`, `form`,
  `username`, `email`, `start_date`, `end_date`, `start_time`, `end_time`,
  `entered_by_user_id`, and `event_id`.
- `id_col` defaults to `user_id` and may be `about`, `username`, or `email`.
- If `id_col` is not `user_id`, resolve `user_id` through `get_user` and fail on
  duplicate full-name matches.
- Dates for Smartabase write payloads are `dd/mm/yyyy` strings.
- Times for Smartabase write payloads are `h:mm AM/PM` strings.
- If `start_date` or `start_time` is absent, default to the current date/time.
- If `end_date` or `end_time` is absent, default to one hour after the start.
- If only an end date/time exists without the matching start date/time, fail.

`sb_insert_event()` behavior:

- Remove any supplied `event_id` before constructing payloads.
- Insert all rows as new events.
- Never update an existing event.

`sb_update_event()` behavior:

- Require an `event_id` column.
- Fail if any row selected for update has a missing `event_id`.
- Add `existingEventId` to each event payload.
- Update existing events only.

`sb_upsert_event()` behavior:

- Require an `event_id` column to opt into upsert mode.
- Rows with non-missing `event_id` are update payloads.
- Rows with missing `event_id` are insert payloads.
- Return a manifest that preserves which rows were inserted versus updated.

`sb_upsert_profile()` behavior:

- Upsert one profile record per input row.
- Do not require event date/time metadata for profile imports.
- Use `profileimport`, not `eventsimport`.
- Treat profile upsert as potentially overwriting existing profile values; keep
  it behind the same dry-run and confirmation workflow as event writes.

Table field behavior:

- `table_field` is a list of column names that belong to Smartabase table rows.
- If `table_field` is provided, non-table fields populate only the first row of
  a same-user same-date event and table fields populate subsequent row indices.
- If `table_field` is absent but duplicate `user_id` plus `start_date` pairs are
  present for event imports, split the data into multiple API calls so each call
  has unique `user_id` plus `start_date` pairs.
- Validate that every `table_field` exists as a column before sending data.

Import results:

- Return a structured result with request path, HTTP status, import result,
  per-row status, errors, `entered_by_user_id`, import time, attempted count,
  success count, and API call count.
- Capture returned event IDs when the API supplies them.
- Mark missing Smartabase fields clearly in the result manifest.

## Deletion

Event deletion endpoint:

`POST /api/v1/deleteevent?informat=json&format=json`

Request body:

```json
{"eventId": 16517}
```

Deletion rules:

- Delete only by explicit `event_id`.
- Never delete by broad name/date/form filters alone.
- Require a manifest or explicit event ID list.
- Require an explicit confirmation flag before calling the API.
- Record every requested event ID, status, response message, timestamp, and any
  error in a delete results manifest.
- Treat deletion as irreversible.

## Deprecated Wrapper Compatibility

Do not build new primary APIs around deprecated wrappers, but support their
behavior as aliases when it helps migration.

`pull_smartabase()` maps to:

- `type = "event"` -> `get_event`
- `type = "profile"` -> `get_profile`
- `type = "synchronise"` -> `sync_event`
- `download_attachment` -> event attachment download option
- `start_date`, `end_date`, `start_time`, `end_time` -> event range arguments
- `filter_user_*` and `filter_data_*` -> modern filter arguments
- `include_missing_user`, `guess_col_type`, `get_uuid`, `cloud_mode` -> modern
  options

`push_smartabase()` maps to:

- `type = "event"` with `edit_event = false` -> `insert_event`
- `type = "event"` with `edit_event = true` -> `update_event` or `upsert_event`
  depending on missing event IDs
- `type = "profile"` -> `upsert_profile`
- `match_id_to_column` -> `id_col`
- `table_fields` -> `table_field`
- `cloud_mode` -> `interactive_mode = false`

`save_credentials()` compatibility:

- Do not open or write `.Renviron`.
- Support reading `SB_USER`, `SB_PASS`, and `SB_URL` only as optional legacy
  aliases.
- Prefer `SMARTABASE_USERNAME`, `SMARTABASE_PASSWORD`, and `SMARTABASE_URL`.
- Never write secrets to tracked files.

## Output Rules

Fetched data belongs under `fetched_data/`, ignored by git.

Write/delete dry-run and execution artifacts should be stored under a local
operation folder, also ignored by git. Reuse an existing generated run metadata
folder when the operation is tied to `generated_data/<run_id>/`; otherwise use a
standalone folder such as `smartabase_runs/<timestamp>_<operation>/`.

Every operation folder should include:

- `operation_config.json`: URL, operation, forms, filters, date/time ranges,
  options, and confirmation flags. Do not include passwords.
- `operation_manifest.csv`: one row per request or form with operation type,
  endpoint, form, output path, row count, status, and error message.
- `raw_json/`: raw API responses when enabled or needed for debugging.
- `payloads/`: dry-run write/delete payloads before confirmation.
- `attachments/`: downloaded attachment files when requested.
- Operation-specific CSVs such as `users.csv`, `groups.csv`,
  `events/<form>.csv`, `profiles/<form>.csv`, `import_results.csv`, and
  `delete_results.csv`.

Always preserve enough metadata to audit what was requested and what the API
returned.

## Secrets

Expected variables:

- `SMARTABASE_URL`
- `SMARTABASE_USERNAME`
- `SMARTABASE_PASSWORD`

Optional compatibility variables:

- `SB_URL`
- `SB_USER`
- `SB_PASS`

Optional behavior variables:

- `SMARTABASE_FORM_MAP`
- `SMARTABASE_DEFAULT_START_DATE`
- `SMARTABASE_DEFAULT_END_DATE`
- `SMARTABASE_USER_AGENT`

Never print passwords, write passwords into configs, or include real
credentials in tests, fixtures, comments, manifests, or examples.

## Testing

Default tests must not require live Smartabase access.

Unit tests should cover:

- URL normalization.
- Credential loading and secret redaction.
- Login request body construction.
- Endpoint-discovery parsing.
- User/group request body construction for every `user_key`.
- Event/profile/sync export request body construction.
- Data filter condition mapping.
- Event/profile response flattening, including multi-row table data.
- Attachment metadata handling without live downloads.
- Date range generation.
- Metadata column selection.
- Insert, update, upsert, profile upsert, and delete payload construction.
- Table field behavior and duplicate `user_id` plus `start_date` splitting.
- Manifest writing for success, partial failure, and API errors.
- Safe output folder names.

Integration tests that call Smartabase must be opt-in and skipped by default
unless all of the following are true:

- Required environment variables are available through the normal credential
  loading path. Real credentials may be used only through local `.env`-backed
  application behavior or environment variables; the agent must never read `.env`
  directly as a file.
- The configured Smartabase URL contains `sandbox`.
- An explicit live-test flag is set.

Write and delete integration tests must also require a second explicit
confirmation variable.

Live tests should be designed so they can run safely against a sandbox tenant
without broad side effects, and should prefer smoke-test coverage plus tightly
scoped cleanup over long-lived fixture data.

## Implementation Discipline

- Keep request construction, HTTP transport, response flattening, payload
  writing, and manifest writing in separable functions.
- Prefer Python standard library plus `requests`. Add heavier dependencies only
  when they remove real complexity.
- Preserve backward-compatible CLI flags once users rely on them.
- Make destructive and mutating operations boringly explicit: dry run first,
  inspect artifacts, then confirm.
- Keep generated or fetched athlete data out of source control.
- If a live API response differs from this guidance, save a redacted fixture,
  document the difference, and update tests before broadening behavior.
