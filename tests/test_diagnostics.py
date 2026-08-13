from datetime import date, datetime
from pathlib import Path
import sys
import unittest
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase import (
    AMSEndpointFallbackWarning,
    AMSDateFormatError,
    EndpointMap,
    MutationState,
    OperationExecution,
    assess_operation_execution,
    discover_endpoint_provenance,
    format_ams_date,
    parse_ams_date,
    response_confirms_success,
    smartabase_acceptance_state,
)


class DiscoveryClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def discover_endpoints(self):
        if self.error is not None:
            raise self.error
        return self.result


class DiagnosticTests(unittest.TestCase):
    def test_date_parser_accepts_only_canonical_ams_text_or_date_objects(self):
        self.assertEqual(parse_ams_date("06/08/2026"), date(2026, 8, 6))
        self.assertEqual(parse_ams_date(date(2026, 8, 6)), date(2026, 8, 6))
        self.assertEqual(
            parse_ams_date(datetime(2026, 8, 6, 14, 30)),
            date(2026, 8, 6),
        )
        self.assertEqual(format_ams_date(date(2026, 8, 6)), "06/08/2026")

        for invalid in ("2026-08-06", "6/8/2026", "31/13/2026", 20260806):
            with self.subTest(invalid=invalid):
                with self.assertRaises(AMSDateFormatError) as raised:
                    parse_ams_date(invalid, field="start_date", row_index=4)

                diagnostic = raised.exception
                self.assertEqual(diagnostic.code, "invalid_date_format")
                self.assertEqual(diagnostic.field, "start_date")
                self.assertEqual(diagnostic.row_index, 4)
                self.assertEqual(diagnostic.mutation_state, MutationState.NO_REQUEST_SENT)
                self.assertFalse(diagnostic.request_sent)
                self.assertIn("DD/MM/YYYY", str(diagnostic))
                self.assertIn("No API request was sent", str(diagnostic))

    def test_endpoint_discovery_failure_returns_sanitized_typed_warning(self):
        private_text = "private-token-value"
        client = DiscoveryClient(error=RuntimeError(private_text))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            provenance = discover_endpoint_provenance(
                client,
                required_aliases={"eventsearch", "deleteevent"},
            )

        self.assertEqual(provenance.source, "defaults")
        self.assertEqual(provenance.error_type, "RuntimeError")
        self.assertEqual(provenance.defaulted_aliases, ("deleteevent", "eventsearch"))
        self.assertEqual(len(caught), 1)
        self.assertIs(caught[0].category, AMSEndpointFallbackWarning)
        self.assertNotIn(private_text, str(caught[0].message))
        self.assertNotIn(private_text, str(provenance.as_dict()))

    def test_partial_endpoint_discovery_names_discovered_and_defaulted_aliases(self):
        endpoint_map = EndpointMap()
        endpoint_map.update({"eventsearch": "custom-event-search"})

        provenance = discover_endpoint_provenance(
            DiscoveryClient(result=endpoint_map),
            required_aliases={"eventsearch", "deleteevent"},
            emit_warning=False,
        )

        self.assertEqual(provenance.source, "partial")
        self.assertEqual(provenance.discovered_aliases, ("eventsearch",))
        self.assertEqual(provenance.defaulted_aliases, ("deleteevent",))

    def test_successfully_imported_is_accepted_but_not_confirmed(self):
        execution = OperationExecution(
            endpoint="eventsimport",
            attempted_count=2,
            dry_run=False,
            executed=True,
            body={},
            row_operations=[],
            responses=[{"result": '{"state":"SUCCESSFULLY_IMPORTED"}'}],
        )

        assessment = assess_operation_execution(
            execution,
            expected_count=2,
            operation="insert_event",
        )

        self.assertEqual(assessment.state, MutationState.ACCEPTED_UNVERIFIED)
        self.assertFalse(assessment.confirmed)
        self.assertEqual(assessment.acceptance_states, ("SUCCESSFULLY_IMPORTED",))
        self.assertTrue(assessment.as_dict()["accepted_unverified"])

    def test_authoritative_count_is_confirmed_complete(self):
        execution = OperationExecution(
            endpoint="eventsimport",
            attempted_count=2,
            dry_run=False,
            executed=True,
            body={},
            row_operations=[],
            responses=[{"status": "ok", "inserted": 2}],
        )

        assessment = assess_operation_execution(
            execution,
            expected_count=2,
            operation="insert_event",
        )

        self.assertEqual(assessment.state, MutationState.CONFIRMED_COMPLETE)
        self.assertTrue(assessment.confirmed)

    def test_lossy_or_boolean_counts_are_not_success_evidence(self):
        for value in (True, 1.9, "1.9", "+1", -1):
            with self.subTest(value=value):
                self.assertFalse(
                    response_confirms_success(
                        {"status": "ok", "inserted": value},
                        1,
                        "insert_event",
                    )
                )

    def test_delete_message_confirms_only_the_exact_requested_event_id(self):
        execution = OperationExecution(
            endpoint="deleteevent",
            attempted_count=1,
            dry_run=False,
            executed=True,
            body=[{"eventId": 123}],
            row_operations=[],
            responses=[{"message": "Deleted 123"}],
        )

        assessment = assess_operation_execution(
            execution,
            expected_count=1,
            operation="delete_event",
            expected_event_id=123,
        )

        self.assertEqual(assessment.state, MutationState.CONFIRMED_COMPLETE)
        self.assertTrue(assessment.confirmed)
        self.assertEqual(assessment.event_ids, (123,))

        mismatch = assess_operation_execution(
            execution,
            expected_count=1,
            operation="delete_event",
            expected_event_id=999,
        )
        self.assertEqual(mismatch.state, MutationState.PARTIAL_OR_UNKNOWN)
        self.assertFalse(mismatch.confirmed)
        self.assertEqual(mismatch.reason_code, "delete_event_id_mismatch")

    def test_delete_message_parser_rejects_ambiguous_or_error_responses(self):
        for response in (
            {"message": "Deletion queued 123"},
            {"message": "Deleted 123 extra"},
            {"message": "Deleted 0"},
            {"message": "Deleted 123", "error": "permission denied"},
        ):
            with self.subTest(response=response):
                execution = OperationExecution(
                    endpoint="deleteevent",
                    attempted_count=1,
                    dry_run=False,
                    executed=True,
                    body=[{"eventId": 123}],
                    row_operations=[],
                    responses=[response],
                )
                assessment = assess_operation_execution(
                    execution,
                    expected_count=1,
                    operation="delete_event",
                    expected_event_id=123,
                )
                self.assertEqual(assessment.state, MutationState.PARTIAL_OR_UNKNOWN)
                self.assertFalse(assessment.confirmed)

    def test_insert_response_with_plain_ids_list_is_confirmed_complete(self):
        # Reproduces a real Smartabase eventsimport success response observed
        # against a sandbox tenant: the new event ID comes back as a plain
        # "ids" list, not under any of the previously-recognized event-ID keys.
        execution = OperationExecution(
            endpoint="eventsimport",
            attempted_count=1,
            dry_run=False,
            executed=True,
            body={},
            row_operations=[],
            responses=[
                {
                    "result": {"state": "SUCCESSFULLY_IMPORTED"},
                    "eventImportResultForForm": [
                        {
                            "formName": "Garmin HRV Summary",
                            "eventImportResults": {
                                "state": "SUCCESSFULLY_IMPORTED",
                                "message": "1 out of 1 records successfully imported.",
                                "ids": [34368286],
                            },
                        }
                    ],
                }
            ],
        )

        assessment = assess_operation_execution(
            execution,
            expected_count=1,
            operation="insert_event",
        )

        self.assertEqual(assessment.state, MutationState.CONFIRMED_COMPLETE)
        self.assertTrue(assessment.confirmed)
        self.assertEqual(assessment.event_ids, (34368286,))

    def test_delete_response_with_plain_success_state_and_exact_message_is_confirmed(self):
        # Reproduces a real Smartabase deleteevent success response: no
        # structured event-ID field at all, only free text plus a bare
        # "state": "SUCCESS". The connector deliberately does not parse the
        # free-text message for an ID (message text is not a stable
        # contract), so this stops short of CONFIRMED_COMPLETE — but it must
        # no longer be misclassified as an unrecognized/error-shaped response.
        response = {"message": "Deleted 34368029", "state": "SUCCESS"}
        self.assertEqual(smartabase_acceptance_state(response), "SUCCESS")
        self.assertTrue(response_confirms_success(response, 1, "delete_event"))

        execution = OperationExecution(
            endpoint="deleteevent",
            attempted_count=1,
            dry_run=False,
            executed=True,
            body={},
            row_operations=[],
            responses=[response],
        )

        assessment = assess_operation_execution(
            execution,
            expected_count=1,
            operation="delete_event",
            expected_event_id=34368029,
        )

        self.assertEqual(assessment.state, MutationState.CONFIRMED_COMPLETE)
        self.assertTrue(assessment.confirmed)
        self.assertEqual(assessment.event_ids, (34368029,))
        self.assertEqual(assessment.reason_code, "confirmed_complete")

    def test_acceptance_parser_rejects_error_envelopes(self):
        self.assertEqual(
            smartabase_acceptance_state({"state": "SUCCESSFULLY_IMPORTED"}),
            "SUCCESSFULLY_IMPORTED",
        )
        self.assertIsNone(
            smartabase_acceptance_state(
                {"state": "SUCCESSFULLY_IMPORTED", "error": "failed"}
            )
        )


if __name__ == "__main__":
    unittest.main()
