# Contributing

This repository contains a Python-only AMS/Smartabase connector. Contributions should preserve safety, auditability, and the ability to use the package from other Python projects.

## Issues

Use issues to describe the workflow, AMS object type, affected aim IDs from [PROJECT_AIMS.md](PROJECT_AIMS.md), and any known safety impact. Do not include real credentials, passwords, access tokens, or sensitive athlete data.

For destructive-operation requests, state whether the request is sandbox-only or intended for a real AMS environment. Production delete behavior must be treated as a high-risk design topic, not an ordinary feature request.

## Branches

Use short descriptive branch names such as `docs/roadmap`, `feature/roster-discovery`, or `fix/delete-preflight`. Keep documentation-only branches separate from runtime behavior changes when practical.

## Commits

Make commits focused and reviewable. Prefer messages that describe the user-facing or maintainer-facing outcome, for example `Document project aims` or `Add roster discovery helper`.

Do not commit generated run outputs, fetched AMS data, local credentials, virtual environments, or build artifacts.

## Pull Requests

Every pull request should use [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md). Include:

- a short summary
- linked issue or reason for change
- relevant aim IDs
- safety impact
- testing performed
- backwards compatibility notes
- documentation changes
- reviewer notes

Changes that alter mutation, deletion, credential handling, endpoint behavior, or public APIs need especially clear review notes.

## Testing

Default tests must not require live Smartabase access:

```powershell
python -m unittest discover -s tests
```

Live integration tests must be opt-in, skipped by default, and use credentials only through the normal credential-loading path. They must run against sandbox URLs unless the project explicitly approves a different policy.

Write and delete integration tests require an additional explicit confirmation mechanism beyond normal credential availability.

## Credentials

Preferred environment variables:

- `SMARTABASE_URL`
- `SMARTABASE_USERNAME`
- `SMARTABASE_PASSWORD`

Legacy aliases:

- `SB_URL`
- `SB_USER`
- `SB_PASS`

Use local environment variables, local `.env` files, keyring, or another local secret manager. Never commit real credentials or paste them into issues, pull requests, examples, tests, fixtures, manifests, or documentation.

## Destructive-Operation Safety

Dry-run should be the default for writes, updates, upserts, replacements, and deletes. Live mutation should require explicit confirmation.

Deletion should use explicit Smartabase event IDs gathered by a preflight fetch or supplied intentionally. Do not implement broad production deletion by names, forms, or date ranges as a normal workflow.

Batch deletion is acceptable in sandbox workflows when it is explicit, auditable, and guarded. Production deletion is a nuclear option and requires deliberate design review before any policy change.
