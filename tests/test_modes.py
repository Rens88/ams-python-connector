"""Tests for the tiered safety modes (specs/001-api-safety-modes/spec.md)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.client import SmartabaseClient
from ams_smartabase.config import SmartabaseCredentials
from ams_smartabase.modes import (
    RUNNER_IDENTITY_ENV_VAR,
    AutoQualification,
    DestinationCollisionError,
    MissingQualificationError,
    ModeNotAllowedForOperationError,
    NonInteractiveEnvironmentError,
    QualificationMismatchError,
    SafetyMode,
    UnknownSafetyModeError,
    check_auto_eligibility,
    check_destination_non_collision,
    compute_confirmation_phrase,
    load_qualification,
    require_interactive_confirmation,
    require_operation_allowed,
    resolve_mode,
    write_qualification_interactively,
)


class StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class RoutingSession:
    """Returns different bodies for eventsearch (collision check) vs eventsimport."""

    def __init__(self, *, existing_events=None, import_response=None):
        self.existing_events = existing_events if existing_events is not None else []
        self.import_response = import_response or {"result": {"state": "SUCCESSFULLY_IMPORTED"}, "ids": [1]}
        self.post_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        if url.endswith("/eventsearch"):
            return StubResponse({"events": self.existing_events})
        return StubResponse(self.import_response)


def make_client(session=None) -> SmartabaseClient:
    return SmartabaseClient(
        SmartabaseCredentials("https://teamnl.smartabase.nl/sandbox", "user", "secret"),
        session=session or RoutingSession(),
    )


VALID_RECORD = {"user_id": 1, "start_date": "07/08/2026", "HRV": "60"}


class ResolveModeTests(unittest.TestCase):
    def test_omitted_mode_resolves_to_default(self):
        self.assertIs(resolve_mode(None), SafetyMode.DEFAULT)

    def test_known_modes_resolve_case_and_dash_insensitively(self):
        self.assertIs(resolve_mode("HUMAN"), SafetyMode.HUMAN)
        self.assertIs(resolve_mode("--auto"), SafetyMode.AUTO)
        self.assertIs(resolve_mode(SafetyMode.HUMAN), SafetyMode.HUMAN)

    def test_unknown_mode_fails_closed(self):
        with self.assertRaises(UnknownSafetyModeError):
            resolve_mode("yolo")


class OperationAllowlistTests(unittest.TestCase):
    def test_default_allows_every_operation(self):
        for operation in ("insert_event", "update_event", "upsert_event", "upsert_profile", "delete_event"):
            require_operation_allowed(SafetyMode.DEFAULT, operation)  # must not raise

    def test_human_and_auto_allow_only_create(self):
        require_operation_allowed(SafetyMode.HUMAN, "insert_event")
        require_operation_allowed(SafetyMode.AUTO, "insert_event")

    def test_human_and_auto_refuse_modify_and_delete(self):
        for mode in (SafetyMode.HUMAN, SafetyMode.AUTO):
            for operation in ("update_event", "upsert_event", "upsert_profile", "delete_event"):
                with self.subTest(mode=mode, operation=operation):
                    with self.assertRaises(ModeNotAllowedForOperationError):
                        require_operation_allowed(mode, operation)


class InteractiveConfirmationTests(unittest.TestCase):
    def test_refuses_when_not_a_real_tty(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(NonInteractiveEnvironmentError):
                require_interactive_confirmation("confirm? ")

    def test_accepts_exact_yes_from_a_real_tty(self):
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="yes"):
            self.assertTrue(require_interactive_confirmation("confirm? "))

    def test_rejects_anything_other_than_exact_yes(self):
        with mock.patch("sys.stdin.isatty", return_value=True):
            for reply in ("y", "Yes", "sure", "", "  yes  "):
                with self.subTest(reply=reply):
                    with mock.patch("builtins.input", return_value=reply):
                        self.assertFalse(require_interactive_confirmation("confirm? "))

    def test_eof_is_treated_as_a_decline_not_a_crash(self):
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(require_interactive_confirmation("confirm? "))


class ConfirmationPhraseTests(unittest.TestCase):
    def test_phrase_is_deterministic_and_reflects_the_plan(self):
        phrase = compute_confirmation_phrase(
            operation="delete_event", form="Garmin HRV Summary", count=1, scope="event 34368029"
        )
        self.assertEqual(phrase, "DELETE 1 ROW INTO GARMIN HRV SUMMARY FOR EVENT 34368029")


class AutoQualificationTests(unittest.TestCase):
    def _qualification(self, **overrides) -> AutoQualification:
        fields = dict(
            workflow_id="hrv-ac-ratios",
            environment_url="https://teamnl.smartabase.nl/sandbox",
            runner_identity="platform-runner-1",
            source_form="Garmin HRV Summary",
            destination_form="HRV AC Ratios",
            operation="insert_event",
            batch_limit=50,
            reviewer="rens88",
            reviewed_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        fields.update(overrides)
        return AutoQualification(**fields)

    def test_not_expired_without_an_expiry(self):
        self.assertFalse(self._qualification().is_expired())

    def test_expired_when_past_expires_at(self):
        past = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
        self.assertTrue(self._qualification(expires_at=past).is_expired())

    def test_load_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_qualification(Path(tmp) / "missing.json"))

    def test_load_malformed_file_returns_none_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not valid json", encoding="utf-8")
            self.assertIsNone(load_qualification(path))

    def test_write_qualification_refuses_without_a_real_tty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qualification.json"
            with mock.patch("sys.stdin.isatty", return_value=False):
                with self.assertRaises(NonInteractiveEnvironmentError):
                    write_qualification_interactively(self._qualification(), path=path)
            self.assertFalse(path.exists())

    def test_write_qualification_succeeds_after_interactive_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qualification.json"
            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="yes"):
                write_qualification_interactively(self._qualification(), path=path)
            self.assertTrue(path.exists())
            self.assertEqual(load_qualification(path).workflow_id, "hrv-ac-ratios")

    def test_check_auto_eligibility_requires_runner_identity_env_var(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(RUNNER_IDENTITY_ENV_VAR, None)
            with self.assertRaises(MissingQualificationError):
                check_auto_eligibility(
                    environment_url="https://teamnl.smartabase.nl/sandbox",
                    destination_form="HRV AC Ratios",
                    operation="insert_event",
                    batch_count=1,
                )

    def test_check_auto_eligibility_requires_a_qualification_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {RUNNER_IDENTITY_ENV_VAR: "platform-runner-1"}):
                with self.assertRaises(MissingQualificationError):
                    check_auto_eligibility(
                        environment_url="https://teamnl.smartabase.nl/sandbox",
                        destination_form="HRV AC Ratios",
                        operation="insert_event",
                        batch_count=1,
                        qualification_path=Path(tmp) / "missing.json",
                    )

    def test_check_auto_eligibility_matches_a_valid_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qualification.json"
            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="yes"):
                write_qualification_interactively(self._qualification(), path=path)
            with mock.patch.dict(os.environ, {RUNNER_IDENTITY_ENV_VAR: "platform-runner-1"}):
                result = check_auto_eligibility(
                    environment_url="https://teamnl.smartabase.nl/sandbox",
                    destination_form="HRV AC Ratios",
                    operation="insert_event",
                    batch_count=1,
                    qualification_path=path,
                )
            self.assertEqual(result.workflow_id, "hrv-ac-ratios")

    def test_check_auto_eligibility_rejects_mismatched_runner_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qualification.json"
            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="yes"):
                write_qualification_interactively(self._qualification(), path=path)
            with mock.patch.dict(os.environ, {RUNNER_IDENTITY_ENV_VAR: "some-agent-session"}):
                with self.assertRaises(QualificationMismatchError):
                    check_auto_eligibility(
                        environment_url="https://teamnl.smartabase.nl/sandbox",
                        destination_form="HRV AC Ratios",
                        operation="insert_event",
                        batch_count=1,
                        qualification_path=path,
                    )

    def test_check_auto_eligibility_rejects_batch_over_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qualification.json"
            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="yes"):
                write_qualification_interactively(self._qualification(batch_limit=5), path=path)
            with mock.patch.dict(os.environ, {RUNNER_IDENTITY_ENV_VAR: "platform-runner-1"}):
                with self.assertRaises(QualificationMismatchError):
                    check_auto_eligibility(
                        environment_url="https://teamnl.smartabase.nl/sandbox",
                        destination_form="HRV AC Ratios",
                        operation="insert_event",
                        batch_count=6,
                        qualification_path=path,
                    )

    def test_check_auto_eligibility_rejects_same_source_and_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qualification.json"
            same_form_qualification = self._qualification(
                source_form="Garmin HRV Summary", destination_form="Garmin HRV Summary"
            )
            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="yes"):
                write_qualification_interactively(same_form_qualification, path=path)
            with mock.patch.dict(os.environ, {RUNNER_IDENTITY_ENV_VAR: "platform-runner-1"}):
                with self.assertRaises(QualificationMismatchError):
                    check_auto_eligibility(
                        environment_url="https://teamnl.smartabase.nl/sandbox",
                        destination_form="Garmin HRV Summary",
                        operation="insert_event",
                        batch_count=1,
                        qualification_path=path,
                    )


class DestinationCollisionTests(unittest.TestCase):
    def test_passes_when_destination_has_no_matching_record(self):
        client = make_client(RoutingSession(existing_events=[]))
        check_destination_non_collision(client, form="HRV AC Ratios", user_id=1, start_date="07/08/2026")

    def test_raises_when_destination_already_has_a_record(self):
        client = make_client(
            RoutingSession(
                existing_events=[
                    {
                        "formName": "HRV AC Ratios",
                        "startDate": "07/08/2026",
                        "userId": 1,
                        "rows": [{"row": 0, "pairs": [{"key": "AC Short", "value": "1.0"}]}],
                    }
                ]
            )
        )
        with self.assertRaises(DestinationCollisionError):
            check_destination_non_collision(client, form="HRV AC Ratios", user_id=1, start_date="07/08/2026")

    def test_fails_closed_when_the_read_itself_errors(self):
        class BrokenSession(RoutingSession):
            def post(self, url, **kwargs):
                raise RuntimeError("network is down")

        client = make_client(BrokenSession())
        with self.assertRaises(DestinationCollisionError):
            check_destination_non_collision(client, form="HRV AC Ratios", user_id=1, start_date="07/08/2026")


class ClientModeIntegrationTests(unittest.TestCase):
    def test_insert_event_default_mode_is_unchanged_dry_run_behavior(self):
        client = make_client()
        result = client.insert_event([VALID_RECORD], form="HRV AC Ratios")
        self.assertTrue(result.dry_run)
        self.assertFalse(result.executed)

    def test_insert_event_human_mode_without_tty_refuses(self):
        client = make_client(RoutingSession(existing_events=[]))
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(NonInteractiveEnvironmentError):
                client.insert_event([VALID_RECORD], form="HRV AC Ratios", mode="human")

    def test_insert_event_human_mode_declines_without_a_live_write(self):
        client = make_client(RoutingSession(existing_events=[]))
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="no"):
            result = client.insert_event([VALID_RECORD], form="HRV AC Ratios", mode="human")
        self.assertFalse(result.executed)

    def test_insert_event_human_mode_refuses_on_destination_collision_before_any_prompt(self):
        client = make_client(
            RoutingSession(
                existing_events=[
                    {"formName": "HRV AC Ratios", "startDate": "07/08/2026", "userId": 1, "rows": []}
                ]
            )
        )
        with mock.patch("builtins.input") as mocked_input:
            with self.assertRaises(DestinationCollisionError):
                client.insert_event([VALID_RECORD], form="HRV AC Ratios", mode="human")
            mocked_input.assert_not_called()

    def test_insert_event_auto_mode_without_qualification_refuses(self):
        client = make_client(RoutingSession(existing_events=[]))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(RUNNER_IDENTITY_ENV_VAR, None)
            with self.assertRaises(MissingQualificationError):
                client.insert_event([VALID_RECORD], form="HRV AC Ratios", mode="auto")

    def test_update_event_refuses_human_and_auto_regardless_of_other_arguments(self):
        client = make_client()
        for mode in ("human", "auto"):
            with self.subTest(mode=mode):
                with self.assertRaises(ModeNotAllowedForOperationError):
                    client.update_event([dict(VALID_RECORD, event_id=1)], form="HRV AC Ratios", mode=mode)

    def test_delete_event_refuses_human_and_auto_regardless_of_other_arguments(self):
        client = make_client()
        for mode in ("human", "auto"):
            with self.subTest(mode=mode):
                with self.assertRaises(ModeNotAllowedForOperationError):
                    client.delete_event([1], mode=mode)

    def test_upsert_profile_refuses_human_and_auto(self):
        client = make_client()
        for mode in ("human", "auto"):
            with self.subTest(mode=mode):
                with self.assertRaises(ModeNotAllowedForOperationError):
                    client.upsert_profile([VALID_RECORD], form="HRV AC Ratios", mode=mode)


if __name__ == "__main__":
    unittest.main()
