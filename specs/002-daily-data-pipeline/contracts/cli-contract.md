# CLI Contract: `sandbox-data`

This contract describes the intended interface after implementation. It is not
yet available in the current scripts.

## Global Rules

- Every command identifies one `--dataset` and one authoritative `--state-root`.
- The same dataset version must not be advanced from unsynchronized local and
  Databricks copies. Moving execution contexts requires a complete hash-valid
  export/import or a shared store adapter.
- Paths are explicit; no command relies on the repository working directory.
- Default behavior is read-only with respect to AMS.
- Credentials are resolved by a provider. CLI flags, task parameters, logs,
  manifests, and dataset files never accept or contain plaintext passwords.
- Machine-readable output uses `--output json`; secrets and row values remain
  excluded.

## `init`

Create a new immutable dataset version and initial checkpoint.

```text
sandbox-data init \
  --dataset DATASET_ID \
  --dataset-version VERSION \
  --state-root PATH \
  --roster PATH \
  --templates PATH \
  --form-map PATH \
  --simulation-epoch YYYY-MM-DD \
  --seed VALUE
```

Rules:

- Validates registered-athlete identity and organization routing.
- Freezes athlete simulation profiles and all output-affecting hashes.
- Refuses to reuse an existing version with different content.
- Does not call AMS and does not generate a day.

## `prepare`

Validate state, generate missing dates, and optionally prepare read-only-verified
upload plans.

```text
sandbox-data prepare \
  --dataset DATASET_ID \
  --state-root PATH \
  [--through-date YYYY-MM-DD] \
  [--remote-check auto|require|skip] \
  [--credential-provider local|databricks]
```

Rules:

- `--through-date` defaults to yesterday in the dataset's IANA timezone.
- The command validates the complete hash chain before doing work.
- It advances at most 90 missing dates per invocation, oldest first. If more
  remain, it reports the next date and requires another invocation; there is no
  unlimited override.
- A committed target is validated and becomes a no-op.
- `auto` performs remote classification when credentials are available;
  otherwise generation succeeds but publication remains `UNPLANNED`.
- `require` fails closed if AMS cannot be classified completely.
- `skip` performs no AMS calls and cannot produce a ready publication bundle.
- It performs no live AMS mutation under any option.
- It plans only the earliest contiguous unpublished interval. A blocked earlier
  date prevents a bundle from silently skipping ahead.
- It refuses publication bundles above 90 dates or 25,000 total records.

## `status`

Validate and summarize generation and publication state without mutation.

```text
sandbox-data status --dataset DATASET_ID --state-root PATH [--output text|json]
```

The summary includes dataset/generator versions, contiguous generation head,
next missing date, generated-but-unpublished dates, immutable plan hashes,
blocked/reconcile-required dates, and redacted artifact paths. It does not print
athlete row values or credentials.

## `publish`

Interactively execute one exact immutable publication bundle.

```text
sandbox-data publish --publication-plan PATH --execute --credential-provider local
```

Rules:

- Requires a real interactive terminal. Piped input, Databricks job parameters,
  environment variables, agents, and programmatic callbacks cannot supply the
  confirmation.
- Requires `--execute` so selecting a plan remains distinct from mutation intent.
- Revalidates bundle and child hashes, exact sandbox URL, event-only operations,
  limits, unconsumed execution results, and current credentials.
- Performs one fresh whole-scope read immediately before preview/confirmation.
- Displays environment, operation, dates, athletes/groups, forms, fields, child
  hashes, child/record counts, and exact typed phrase derived from the plan.
- Consumes one confirmation only for the frozen child order.
- Does not retry live mutations. Any mismatch, partial/unknown result, or
  unclassified response stops later children.
- Never updates, upserts, overwrites, or deletes.

There is deliberately no `--yes`, `--confirm`, `--force`, `--auto-upload`,
confirmation environment variable, or scheduled publish mode.

## `reconcile`

Read AMS and compare exact canonical row multisets against a known immutable
publication lineage.

```text
sandbox-data reconcile --publication-plan PATH --credential-provider local
```

Rules:

- Always read-only.
- `RECONCILED` requires matching plan/execution lineage and exact versioned row
  canonicalization.
- An unexplained non-empty or subset scope remains blocked.
- A known partial parent may produce a new immutable remainder proposal only
  through the existing reviewed continuation policy; it is never executed by
  this command.

## `report`

Build inspection dashboards from committed partitions without advancing state or
calling AMS.

```text
sandbox-data report --dataset DATASET_ID --state-root PATH [--from-date YYYY-MM-DD] [--through-date YYYY-MM-DD]
```

This command preserves the project's Plotly inspection requirements while
keeping self-contained HTML generation off the daily prepare path.

## Exit Status Contract

| Code | Meaning |
|---|---|
| `0` | Completed, including a validated no-op |
| `2` | Invalid input, incompatible version, or failed local validation |
| `3` | Corrupt chain, hash conflict, concurrent commit, or unexpected AMS data |
| `4` | AMS read incomplete/uncertain or reconciliation required |
| `5` | Live mutation partial/unknown/contradictory; stop and reconcile |
| `6` | Per-run or publication-bundle hard limit reached |

Status `5` must never be configured as an automatic retry condition.
