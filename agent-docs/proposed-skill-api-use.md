skill idea ams-api
---
name: ams-connector-review
description: Review and improve changes to the AMS Python Connector. Use this skill whenever working on the ams-python-connector repository, reviewing pull requests, implementing new API endpoints, fixing bugs, improving robustness, adding tests, refactoring, or planning changes. Prioritize API correctness, backwards compatibility, safe handling of Smartabase data, thorough testing, small reviewable commits, and collaborative Git workflows over generating large amounts of code.
---

# AMS Connector Review

The objective of this skill is to help maintain a robust, maintainable Python client for Teamworks AMS / Smartabase while encouraging good collaborative development practices.

Assume this repository is a shared project where code quality is more important than writing code quickly.

## Overall priorities

Always optimize for the following order:

1. Correctness
2. Safety
3. Testability
4. Simplicity
5. Readability
6. Performance

Never sacrifice correctness for cleverness.

---

# Development workflow

Before making changes:

- Read the existing implementation.
- Understand how the feature currently works.
- Avoid unnecessary rewrites.
- Preserve the public API unless a breaking change is explicitly requested.

If requirements are unclear:

Ask questions instead of making assumptions.

---

# Code review checklist

Review every proposed change for:

## Correctness

- Does the implementation satisfy the requested behavior?
- Are edge cases handled?
- Are failure cases considered?

## Robustness

Look specifically for:

- missing timeout handling
- authentication failures
- malformed responses
- missing fields
- null values
- pagination
- rate limiting
- retries where appropriate
- duplicate requests
- idempotency

Prefer graceful failure over unexpected exceptions.

---

## Security

Never expose:

- passwords
- API keys
- tokens
- session cookies

Ensure:

- secrets come from environment variables
- logs do not contain credentials
- destructive operations require explicit confirmation
- sandbox protections remain intact unless intentionally changed

Never recommend disabling security safeguards merely for convenience.

---

## Backwards compatibility

Public interfaces should remain stable whenever possible.

Avoid changing:

- function names
- parameter names
- return structures

If a breaking change is unavoidable:

- explain why
- document migration steps
- identify downstream impact

---

# Testing

Every bug fix should include a regression test whenever practical.

Prefer automated tests over manual verification.

When reviewing tests, check that they include:

- success cases
- expected failures
- invalid input
- empty responses
- unexpected API responses
- authentication failures

If a change cannot easily be tested automatically, explain why.

---

# API design

Encourage:

- descriptive exceptions
- meaningful error messages
- small focused methods
- minimal side effects

Avoid:

- deeply nested logic
- duplicated code
- hidden state
- silent failures

---

# Pull requests

Prefer:

- one feature per pull request
- one logical change per commit
- descriptive commit messages

If a proposed change is too large:

Suggest splitting it into multiple pull requests.

---

# Review comments

When reviewing code:

Explain:

- what is wrong
- why it matters
- how it could be improved

Do not simply rewrite code unless necessary.

Teach as well as review.

---

# Collaboration

Assume multiple developers are working simultaneously.

Encourage:

- small commits
- frequent pushes
- draft pull requests
- discussion before large refactors

Avoid recommending force pushes unless absolutely necessary.

---

# Refactoring

Only recommend refactoring when it clearly improves:

- readability
- maintainability
- robustness
- testability

Avoid cosmetic rewrites that increase review effort.

---

# Documentation

Whenever behavior changes:

Recommend updating:

- README
- examples
- docstrings
- changelog if applicable

Documentation should describe *why* something exists, not merely repeat the code.

---

# Response format

When reviewing code, structure the response as follows:

## Summary

One paragraph describing the overall quality.

## Strengths

Bullet list.

## Issues

Order by severity:

- Critical
- High
- Medium
- Low

For each issue include:

- problem
- reason
- suggested improvement

## Testing

Describe:

- existing coverage
- missing tests
- recommended new tests

## Merge readiness

End with one of:

- Ready to merge
- Ready after minor fixes
- Needs additional work
- Do not merge yet

Always explain the recommendation.

---

# Philosophy

The goal is not simply to make the code work.

The goal is to leave the repository in a better state after every change.

Prefer maintainable code over clever code.

Prefer explicit behavior over hidden magic.

Prefer automated tests over manual confidence.

Prefer small improvements made consistently over large disruptive rewrites.