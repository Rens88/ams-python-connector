"""Tiered API safety modes: --default, --human, --auto.

Implements the behavior specified in specs/001-api-safety-modes/spec.md
(feature request: issue #5, "API modes for different operational purposes").

Design boundary agreed with the maintainer before this was written: these
modes govern MUTATION PROCESS safety only — confirmation, scope, collision,
environment, and audit. They never judge whether an uploaded value is
plausible (an implausible HRV reading, for example, is not this module's
concern). That kind of check belongs to the calling workflow, not the
generic connector; see AGENTS.md and RISK_MODEL.md for the rationale.

Mode semantics (see the spec for the full requirements):

- DEFAULT: current behavior, unchanged. The existing `dry_run`/`confirm`
  boolean contract on SmartabaseClient write methods is untouched by this
  module for backward compatibility (Constitution Principle VIII).
- HUMAN: create-only writes only (never update/upsert/delete). Requires a
  real interactive terminal (`sys.stdin.isatty()`) for the final decision —
  a non-interactive process, including a coding agent driving a subprocess
  or this library directly, cannot satisfy this. There is no code path in
  this module that can supply that decision programmatically.
- AUTO: create-only writes only, requires a pre-existing AutoQualification
  that matches the exact operation plan AND a runner-identity environment
  variable that an interactive human/agent session is not expected to have.
  No interactive prompt is used or possible in this path — that is the
  point of unattended automation — so the human decision is moved entirely
  to qualification creation time (see write_qualification_interactively).

Open design question, deliberately left unresolved here for maintainer
review (see PR description): whether runner-identity binding via an
environment variable is the right long-term mechanism for distinguishing a
human-operated automation platform from a coding agent invoking --auto
directly. This module implements that approach as the current best
proposal, not as a settled decision.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .diagnostics import AMSConnectorError, MutationState


RUNNER_IDENTITY_ENV_VAR = "AMS_AUTO_RUNNER_ID"
DEFAULT_QUALIFICATION_PATH = Path.home() / ".ams_smartabase" / "auto_qualification.json"

CREATE_ONLY_OPERATIONS = {"insert_event"}
NEVER_REDUCED_OPERATIONS = {"update_event", "upsert_event", "upsert_profile", "delete_event"}


class SafetyMode(str, Enum):
    DEFAULT = "default"
    HUMAN = "human"
    AUTO = "auto"


class ModeError(AMSConnectorError):
    """Base class for safety-mode errors. No live mutation may proceed past one."""

    default_code = "mode_error"

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("mutation_state", MutationState.NO_REQUEST_SENT)
        super().__init__(message, **kwargs)


class UnknownSafetyModeError(ModeError):
    default_code = "unknown_safety_mode"


class ModeNotAllowedForOperationError(ModeError):
    """HUMAN/AUTO may never simplify confirmation for modify or delete operations."""

    default_code = "mode_not_allowed_for_operation"


class NonInteractiveEnvironmentError(ModeError):
    """HUMAN mode requires a real interactive terminal; none is present."""

    default_code = "non_interactive_environment"


class MissingQualificationError(ModeError):
    default_code = "missing_auto_qualification"


class QualificationMismatchError(ModeError):
    default_code = "auto_qualification_mismatch"


class DestinationCollisionError(ModeError):
    """A create-only write would land on an identity that already exists."""

    default_code = "destination_collision"


def resolve_mode(value: "SafetyMode | str | None") -> SafetyMode:
    """Resolve a mode selection, failing closed on anything unrecognized (FR-002/003)."""

    if value is None:
        return SafetyMode.DEFAULT
    if isinstance(value, SafetyMode):
        return value
    normalized = str(value).strip().lower().lstrip("-")
    try:
        return SafetyMode(normalized)
    except ValueError as exc:
        raise UnknownSafetyModeError(
            f"Unknown safety mode: {value!r}. Valid modes: "
            f"{', '.join(m.value for m in SafetyMode)}. No API request was sent.",
            code="unknown_safety_mode",
            expected="one of: default, human, auto",
        ) from exc


def require_operation_allowed(mode: SafetyMode, operation: str) -> None:
    """Refuse HUMAN/AUTO for anything except create-only writes (FR-030, FR-034)."""

    if mode is SafetyMode.DEFAULT:
        return
    if operation in NEVER_REDUCED_OPERATIONS:
        raise ModeNotAllowedForOperationError(
            f"{mode.value} mode does not apply to {operation!r}; update, upsert, and "
            "delete always require full DEFAULT-mode confirmation regardless of "
            "selected mode. No API request was sent.",
            code="mode_not_allowed_for_operation",
            details={"mode": mode.value, "operation": operation},
        )
    if operation not in CREATE_ONLY_OPERATIONS:
        raise ModeNotAllowedForOperationError(
            f"{mode.value} mode only applies to create-only operations "
            f"({sorted(CREATE_ONLY_OPERATIONS)}), not {operation!r}.",
            code="mode_not_allowed_for_operation",
            details={"mode": mode.value, "operation": operation},
        )


def is_real_tty() -> bool:
    """Return whether stdin is a genuine interactive terminal.

    This is the mechanical gate a coding agent cannot talk its way around:
    an agent invoking a subprocess, a CI job, a scheduled task, or this
    library called directly from another script all fail this check. Only a
    human typing into a real terminal session passes it.
    """

    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def require_interactive_confirmation(prompt: str) -> bool:
    """Block on a real terminal prompt; raise if stdin is not a tty (FR-029).

    Returns True only for an exact, case-sensitive "yes" response. Anything
    else — including empty input, EOF, or a piped/non-interactive answer —
    is treated as a decline, per FR-029 ("a missing, negative, malformed,
    timed-out, pre-supplied, or non-human response MUST cancel execution").
    """

    if not is_real_tty():
        raise NonInteractiveEnvironmentError(
            "HUMAN mode requires a real interactive terminal for the confirmation "
            "decision. This process is not attached to one (stdin is not a tty), "
            "so no confirmation can be requested. No API request was sent. A "
            "coding agent cannot satisfy this requirement on a human's behalf — "
            "run this command yourself in an interactive terminal.",
            code="non_interactive_environment",
        )
    try:
        response = input(prompt)
    except EOFError:
        return False
    return response == "yes"


def compute_confirmation_phrase(*, operation: str, form: str, count: int, scope: str) -> str:
    """Build the operation-specific typed phrase DEFAULT-mode callers should echo back.

    This exists so DEFAULT's confirmation is tied to the reviewed plan rather
    than a generic boolean — it is intentionally not proof that a human
    supplied it (a caller can compute this phrase programmatically); the
    stronger guarantee that a human specifically decided lives in HUMAN
    mode's tty gate, not here. See RISK_MODEL.md and the PR discussion for
    why DEFAULT keeps this weaker-but-improved shape rather than also
    requiring a tty.
    """

    verb = {"insert_event": "INSERT", "update_event": "UPDATE", "delete_event": "DELETE"}.get(
        operation, operation.upper()
    )
    return f"{verb} {count} ROW{'S' if count != 1 else ''} INTO {form.upper()} FOR {scope.upper()}"


@dataclass(frozen=True)
class AutoQualification:
    """Human-owned, revocable evidence that one exact workflow may run unattended.

    Every field here binds the qualification to one specific plan (FR-036).
    A change to any of them invalidates the qualification; matching is exact,
    not fuzzy, by design.
    """

    workflow_id: str
    environment_url: str
    runner_identity: str
    source_form: str
    destination_form: str
    operation: str
    batch_limit: int
    reviewer: str
    reviewed_at: str
    expires_at: str | None = None
    revoked: bool = False
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "environment_url": self.environment_url,
            "runner_identity": self.runner_identity,
            "source_form": self.source_form,
            "destination_form": self.destination_form,
            "operation": self.operation,
            "batch_limit": self.batch_limit,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
            "notes": self.notes,
        }

    def is_expired(self, *, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = now or datetime.now(tz=timezone.utc)
        return current >= datetime.fromisoformat(self.expires_at)


def load_qualification(path: Path | str = DEFAULT_QUALIFICATION_PATH) -> AutoQualification | None:
    """Load a qualification from a local, non-repo file. Fail closed on any doubt."""

    qualification_path = Path(path)
    if not qualification_path.exists():
        return None
    try:
        payload = json.loads(qualification_path.read_text(encoding="utf-8"))
        return AutoQualification(**payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def write_qualification_interactively(
    qualification: AutoQualification,
    *,
    path: Path | str = DEFAULT_QUALIFICATION_PATH,
) -> None:
    """Save a qualification — but only after a real human confirms it, interactively.

    A coding agent may help assemble the AutoQualification fields (reading
    form names, computing scope, drafting the reviewer/notes text) — that is
    explicitly allowed, see AGENTS.md — but this function is the one place
    that actually grants the qualification, and it refuses to do that
    without a live terminal confirmation naming the exact workflow. An agent
    cannot call this successfully on its own; only a human running it
    interactively can complete it.
    """

    if not is_real_tty():
        raise NonInteractiveEnvironmentError(
            "Granting an --auto qualification requires a real interactive terminal. "
            "An agent may prepare this AutoQualification's fields for review, but "
            "only a human running this step themselves may save it.",
            code="non_interactive_environment",
        )
    summary = (
        f"Qualify workflow {qualification.workflow_id!r} to run unattended:\n"
        f"  environment: {qualification.environment_url}\n"
        f"  source -> destination: {qualification.source_form} -> {qualification.destination_form}\n"
        f"  operation: {qualification.operation}, batch limit: {qualification.batch_limit}\n"
        f"  reviewer: {qualification.reviewer}\n"
    )
    print(summary)
    if not require_interactive_confirmation("Type 'yes' to grant this qualification: "):
        raise NonInteractiveEnvironmentError(
            "Qualification was not confirmed interactively. Nothing was saved.",
            code="non_interactive_environment",
        )
    qualification_path = Path(path)
    qualification_path.parent.mkdir(parents=True, exist_ok=True)
    qualification_path.write_text(json.dumps(qualification.as_dict(), indent=2), encoding="utf-8")


def check_auto_eligibility(
    *,
    environment_url: str,
    destination_form: str,
    operation: str,
    batch_count: int,
    source_form: str | None = None,
    qualification_path: Path | str = DEFAULT_QUALIFICATION_PATH,
) -> AutoQualification:
    """Verify AUTO is eligible for this exact plan; raise closed otherwise (FR-035-040).

    `source_form` is optional because the generic connector's insert_event
    call has no notion of "source" — only a workflow that reads Form A and
    writes Form B knows that pairing (FR-022: the connector must not guess
    organization-specific source/destination policy). When a caller does
    supply it, it is checked against the qualification for extra strictness;
    the qualification's own source != destination rule is always enforced
    regardless.
    """

    runner_identity = os.environ.get(RUNNER_IDENTITY_ENV_VAR)
    if not runner_identity:
        raise MissingQualificationError(
            f"AUTO mode requires the {RUNNER_IDENTITY_ENV_VAR} environment variable "
            "to be set to this run's qualified runner identity. It is not set, so "
            "this process cannot be the qualified runner. No API request was sent.",
            code="missing_auto_qualification",
        )

    qualification = load_qualification(qualification_path)
    if qualification is None:
        raise MissingQualificationError(
            f"No AUTO qualification found at {qualification_path}. "
            "No API request was sent.",
            code="missing_auto_qualification",
        )
    if qualification.revoked:
        raise QualificationMismatchError("The AUTO qualification has been revoked.", code="auto_qualification_mismatch")
    if qualification.is_expired():
        raise QualificationMismatchError("The AUTO qualification has expired.", code="auto_qualification_mismatch")
    if qualification.runner_identity != runner_identity:
        raise QualificationMismatchError(
            "This process's runner identity does not match the qualified runner.",
            code="auto_qualification_mismatch",
        )
    if qualification.environment_url.lower() != environment_url.lower():
        raise QualificationMismatchError("Environment does not match the qualified environment.", code="auto_qualification_mismatch")
    if qualification.destination_form != destination_form:
        raise QualificationMismatchError(
            "Destination form does not match the qualified plan.",
            code="auto_qualification_mismatch",
        )
    if source_form is not None and qualification.source_form != source_form:
        raise QualificationMismatchError(
            "Source form does not match the qualified plan.",
            code="auto_qualification_mismatch",
        )
    if qualification.source_form == qualification.destination_form:
        raise QualificationMismatchError(
            "Source and destination forms must be distinct; AUTO never qualifies "
            "in-place writes.",
            code="auto_qualification_mismatch",
        )
    if qualification.operation != operation:
        raise QualificationMismatchError("Operation does not match the qualified plan.", code="auto_qualification_mismatch")
    if batch_count > qualification.batch_limit:
        raise QualificationMismatchError(
            f"Batch of {batch_count} exceeds the qualified limit of {qualification.batch_limit}.",
            code="auto_qualification_mismatch",
        )
    return qualification


def check_destination_non_collision(
    client: Any,
    *,
    form: str,
    user_id: int,
    start_date: str,
) -> None:
    """Refuse a create if the destination already has a record for this identity.

    This is a structural mutation safeguard (don't silently duplicate or
    overwrite), not a data-plausibility check — it looks only at whether a
    record already exists for this exact user/date/form, never at what
    values that record or the new one contain.

    Fails closed: any ambiguity in the read response is treated as a
    collision, not as an all-clear.
    """

    from .flatten import flatten_event_response  # local import avoids a cycle

    try:
        payload = client.get_event(
            form=form,
            user_ids=[user_id],
            date_range=(start_date, start_date),
        )
        existing = flatten_event_response(payload)
    except Exception as exc:  # noqa: BLE001 - any read failure means we cannot prove non-collision
        raise DestinationCollisionError(
            "Could not verify the destination is free of an existing record for "
            f"this identity ({type(exc).__name__}); failing closed. No write was sent.",
            code="destination_collision",
        ) from exc

    if existing:
        raise DestinationCollisionError(
            f"Destination form {form!r} already has {len(existing)} record(s) for "
            f"user_id={user_id} on {start_date}. AUTO/HUMAN create-only mode never "
            "writes over an existing record. No API request was sent.",
            code="destination_collision",
            details={"existing_count": len(existing)},
        )
