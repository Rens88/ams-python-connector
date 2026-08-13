# Quickstart: Planned Incremental Pipeline

> This is a design-validation quickstart for the interface to be implemented.
> The `sandbox-data` command does not exist yet.

This independent project is not affiliated with, endorsed by, or maintained by
Teamworks. The operator remains responsible for authorization, privacy,
security, organizational policy, and every live AMS mutation.

## Recommended Operating Pattern

```text
weekly or daily: prepare through yesterday -> inspect status/plan -> notify
when desired:    interactive publish -> reconcile
```

Preparation may run locally or as a Databricks job. Publication is event-insert
only and remains interactive under current governance. A scheduled job must not
upload, update, upsert, overwrite, or delete AMS data.

## Prerequisites After Implementation

- Python 3.10 or newer.
- The synthesis wheel and exact approved connector wheel installed.
- An authorized sandbox athlete registry, templates, and exact form map.
- A protected, ignored local state directory, or a restricted Unity Catalog
  Volume and managed Delta control table.
- Credentials supplied by the approved local credential mechanism or a
  Databricks secret provider. Never put credentials in commands, notebooks,
  `.env` files on a Volume, or operation artifacts.

## Local Workflow

### 1. Initialize Once

```powershell
sandbox-data init --dataset "rowing-sandbox" --dataset-version "v1" --state-root "C:\secure\ams-sandbox-state" --roster "sandbox_state\athletes.csv" --templates "data_formats" --form-map "smartabase_form_map.json" --simulation-epoch "2026-01-01" --seed "20260429"
```

Review the frozen dataset/config, athlete-profile assignments, routing summary,
and hashes. If any output-affecting input changes later, create a new dataset
version or a reviewed effective-dated cutover.

### 2. Generate Missing Dates Without AMS Access

```powershell
sandbox-data prepare --dataset "rowing-sandbox" --state-root "C:\secure\ams-sandbox-state" --through-date "2026-08-10" --remote-check skip
```

Expected first-run behavior:

- validates the current commit chain;
- generates dates oldest first, at most 90 per invocation;
- commits each date independently;
- records `UNPLANNED` publication state; and
- performs zero AMS requests and mutations.

Run the same command again to validate the no-op. If more than 90 days remain,
rerun; the next invocation resumes at the next causal date.

### 3. Prepare A Publication Bundle

Load credentials through the existing protected local mechanism, then run:

```powershell
sandbox-data prepare --dataset "rowing-sandbox" --state-root "C:\secure\ams-sandbox-state" --through-date "2026-08-10" --remote-check require --credential-provider local
```

This reuses committed data, reads only the earliest contiguous unpublished AMS
interval, classifies every exact date/athlete/form scope, and freezes plans for
empty scopes. It performs zero writes. A remote read error or unexpected row
blocks the affected date and all later dates from that publication bundle.

### 4. Inspect Status And Artifacts

```powershell
sandbox-data status --dataset "rowing-sandbox" --state-root "C:\secure\ams-sandbox-state"
```

Verify at minimum:

- exact normalized URL is the intended `/sandbox` environment;
- dataset and generator versions are expected;
- generation dates form one hash-valid contiguous chain;
- planned dates are the earliest unpublished dates;
- athlete IDs, forms, fields, counts, and child hashes are expected;
- no profile/update/upsert/delete operation is present; and
- total scope is within 90 dates, 25,000 records, 500 records per child, and 100
  records per request batch.

### 5. Publish Separately And Interactively

Use the exact plan path printed by `status`:

```powershell
sandbox-data publish --publication-plan "C:\secure\ams-sandbox-state\datasets\rowing-sandbox\v1\bundles\BUNDLE_ID\master_upload_plan.json" --execute --credential-provider local
```

The command performs a fresh read, prints the complete scope, and asks for the
plan-derived typed phrase. Type it yourself only after reviewing the preview.
Do not pipe it, script it, store it, or ask an agent to provide it.

If the command reports partial, unknown, contradictory, or read-uncertain state,
do not rerun it. Start with the read-only command:

```powershell
sandbox-data reconcile --publication-plan "C:\secure\ams-sandbox-state\datasets\rowing-sandbox\v1\bundles\BUNDLE_ID\master_upload_plan.json" --credential-provider local
```

## Databricks Prepare Job

### 1. Provision Protected State

Create:

- a restricted managed Unity Catalog Volume for inputs and immutable artifacts;
- a managed Delta control table keyed by dataset version and event date;
- a dedicated secret scope readable only by the job principal;
- preferably a read-only AMS credential for scheduled scope checks; and
- a restricted serverless network policy allowing only the reviewed AMS sandbox
  FQDN and approved package source.

Do not copy the local `.env` file into the Volume. Serverless jobs use a runtime
credential adapter and in-memory credentials.

### 2. Deploy The Pinned Wheels And Saved Job

```bash
databricks bundle validate -t prod
databricks bundle deploy -t prod
```

The bundle defines one saved serverless Python wheel task using Standard
performance mode, `max_concurrent_runs: 1`, queueing, timeout/duration warnings,
failure notifications, and non-sensitive cost tags. Its command is equivalent
to:

```text
sandbox-data prepare --dataset DATASET_ID --state-root /Volumes/CATALOG/SCHEMA/VOLUME --remote-check require --credential-provider databricks
```

The job has no `publish` task and no mutation-capable parameter.

### 3. Validate Manually Before Scheduling

Run the saved job for an explicit historical test date in a non-production
workspace. Confirm:

- local and Databricks runs from identical initial state produce the same daily
  manifest hashes;
- the Delta ledger points only at hash-valid Volume manifests;
- no credentials appear in task parameters, logs, Volume files, or Delta rows;
- no AMS mutation method is called; and
- a second run is a validated no-op.

### 4. Schedule For Freshness, Not Correctness

Start weekly in timezone `Europe/Amsterdam`; each run targets yesterday and
catches up all missing dates in one task. Move to daily only if one-day freshness
is required. Missing-date calculation is authoritative, so a delayed or skipped
trigger does not lose a date.

### 5. Human Publication Of Databricks-Prepared Plans

For the initial Databricks rollout, use a secure interactive terminal with
access to the authoritative Volume and run the same `sandbox-data publish`
command against its exact plan path. This may be a tightly controlled
Databricks web terminal on interactive compute. Do not convert a notebook/job
parameter into confirmation.

If workstation publication of a Databricks-owned dataset is required, implement
and review a remote artifact-store/export-result adapter before rollout. Do not
advance one dataset from a copied, unsynchronized local directory. A wholly
local dataset remains fully supported by the local workflow above.

## Periodic Reports

Build the heavier self-contained Plotly inspection output separately:

```powershell
sandbox-data report --dataset "rowing-sandbox" --state-root "C:\secure\ams-sandbox-state" --from-date "2026-08-01" --through-date "2026-08-10"
```

Daily preparation retains lightweight validation summaries. Before implementing
this split, update the synthesis repository's existing reporting requirements so
the daily exception and periodic reporting obligation are explicit.

## Acceptance Smoke Test

From one synthetic initial dataset version:

1. Prepare 90 dates in one invocation and save manifest hashes.
2. Reset only the synthetic test store and prepare the same period with 90
   one-day invocations, serializing/reloading after each.
3. Assert every daily manifest and the ending checkpoint match.
4. Repeat the final `prepare`; assert a no-op and zero AMS requests.
5. Reorder registry rows; assert existing athlete profiles and output stay the
   same.
6. Inject an unexpected AMS row in an offline double; assert zero mutation calls
   and a blocked date.
7. Invoke `publish` without a TTY; assert refusal before any mutation method.
