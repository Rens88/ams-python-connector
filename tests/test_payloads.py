from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.payloads import (
    build_delete_payloads,
    build_event_import_payloads,
    build_profile_upsert_payloads,
    coerce_records_input,
    select_metadata,
    suggest_nested_table_candidates,
)
from ams_smartabase.diagnostics import AMSDateFormatError


class FakeDataFrame:
    def __init__(self, records):
        self._records = records

    def to_dict(self, orient):
        if orient != "records":
            raise AssertionError(f"Unexpected orient: {orient}")
        return self._records


class PayloadTests(unittest.TestCase):
    def test_event_insert_removes_event_id_from_payload_pairs(self):
        package = build_event_import_payloads(
            [{"User_ID": 123, "Event_ID": 999, "Score": 42}],
            form="Wellness",
            mode="insert",
            now=datetime(2026, 5, 7, 10, 30),
        )
        event = package.body["events"][0]
        self.assertNotIn("existingEventId", event)
        self.assertEqual(event["userId"], {"userId": 123})
        self.assertEqual(event["startDate"], "07/05/2026")
        self.assertEqual(event["rows"][0]["pairs"], [{"key": "Score", "value": "42"}])

    def test_event_update_requires_event_id(self):
        with self.assertRaises(ValueError):
            build_event_import_payloads([{"user_id": 123, "Score": 42}], form="Wellness", mode="update")

    def test_event_upsert_splits_insert_and_update_operations(self):
        package = build_event_import_payloads(
            [
                {"user_id": 1, "event_id": 10, "Score": 5},
                {"user_id": 2, "event_id": "", "Score": 6},
            ],
            form="Wellness",
            mode="upsert",
            now=datetime(2026, 5, 7, 10, 30),
        )
        self.assertEqual([row["operation"] for row in package.row_operations], ["update", "insert"])
        self.assertEqual(package.body["events"][0]["existingEventId"], 10)

    def test_profile_upsert_payload(self):
        package = build_profile_upsert_payloads([{"user_id": 1, "Height": 180}], form="Profile")
        self.assertEqual(package.endpoint, "profileimport")
        self.assertEqual(package.body[0]["rows"][0]["pairs"], [{"key": "Height", "value": "180"}])

    def test_coerce_records_input_reads_csv_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "records.csv"
            csv_path.write_text("user_id,Score\n1,42\n", encoding="utf-8")

            records = coerce_records_input(csv_path)

        self.assertEqual(records, [{"user_id": "1", "Score": "42"}])

    def test_coerce_records_input_accepts_dataframe_like_objects(self):
        records = coerce_records_input(FakeDataFrame([{"user_id": 1, "Score": 42}]))
        self.assertEqual(records, [{"user_id": 1, "Score": 42}])

    def test_event_import_payload_accepts_csv_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "records.csv"
            csv_path.write_text("user_id,Score\n123,42\n", encoding="utf-8")

            package = build_event_import_payloads(
                csv_path,
                form="Wellness",
                mode="insert",
                now=datetime(2026, 5, 7, 10, 30),
            )

        event = package.body["events"][0]
        self.assertEqual(event["userId"], {"userId": 123})
        self.assertEqual(event["rows"][0]["pairs"], [{"key": "Score", "value": "42"}])

    def test_event_import_rejects_noncanonical_date_with_source_row(self):
        with self.assertRaises(AMSDateFormatError) as raised:
            build_event_import_payloads(
                [
                    {"user_id": 1, "start_date": "01/05/2026", "Score": 5},
                    {"user_id": 2, "start_date": "2026-05-02", "Score": 6},
                ],
                form="Wellness",
                now=datetime(2026, 5, 7, 10, 30),
            )

        self.assertEqual(raised.exception.field, "start_date")
        self.assertEqual(raised.exception.row_index, 1)
        self.assertFalse(raised.exception.request_sent)

    def test_profile_upsert_payload_accepts_dataframe_like_objects(self):
        package = build_profile_upsert_payloads(FakeDataFrame([{"user_id": 1, "Height": 180}]), form="Profile")
        self.assertEqual(package.body[0]["rows"][0]["pairs"], [{"key": "Height", "value": "180"}])

    def test_delete_payloads_are_explicit_event_ids(self):
        package = build_delete_payloads(["10", 11])
        self.assertEqual(package.body, [{"eventId": 10}, {"eventId": 11}])

    def test_select_metadata_returns_preferred_order_original_names(self):
        columns = ["Score", "Event_ID", "User ID", "About"]
        self.assertEqual(select_metadata(columns), ["About", "User ID", "Event_ID"])

    def test_event_import_payload_can_group_nested_table_rows(self):
        package = build_event_import_payloads(
            [
                {
                    "user_id": 123,
                    "start_date": "07/05/2026",
                    "Session Type": "Lab Test",
                    "CSV results": "raw-factor",
                    "Exercise": "Squat",
                    "Sets": 5,
                },
                {
                    "user_id": 123,
                    "start_date": "07/05/2026",
                    "Session Type": "Lab Test",
                    "CSV results": "raw-factor",
                    "Exercise": "Bench",
                    "Sets": 4,
                },
            ],
            form="Gym Session",
            nested_table_identifiers=["Session Type", "CSV results"],
            now=datetime(2026, 5, 7, 10, 30),
        )

        self.assertEqual(package.attempted_count, 1)
        self.assertEqual(package.row_operations[0]["source_row_indices"], [0, 1])
        event = package.body["events"][0]
        self.assertEqual(
            event["rows"],
            [
                {
                    "row": 0,
                    "pairs": [
                        {"key": "Session Type", "value": "Lab Test"},
                        {"key": "CSV results", "value": "raw-factor"},
                    ],
                },
                {
                    "row": 1,
                    "pairs": [
                        {"key": "Exercise", "value": "Squat"},
                        {"key": "Sets", "value": "5"},
                    ],
                },
                {
                    "row": 2,
                    "pairs": [
                        {"key": "Exercise", "value": "Bench"},
                        {"key": "Sets", "value": "4"},
                    ],
                },
            ],
        )

    def test_event_import_payload_keeps_same_day_rows_separate_without_nested_identifiers(self):
        package = build_event_import_payloads(
            [
                {"user_id": 123, "start_date": "07/05/2026", "start_time": "09:00", "Score": 1},
                {"user_id": 123, "start_date": "07/05/2026", "start_time": "09:00", "Score": 2},
            ],
            form="Training Load",
            now=datetime(2026, 5, 7, 10, 30),
        )

        self.assertEqual(package.attempted_count, 2)

    def test_suggest_nested_table_candidates_summarizes_shared_and_nested_columns(self):
        suggestions = suggest_nested_table_candidates(
            [
                {
                    "form": "Lab Testing",
                    "user_id": 123,
                    "start_date": "07/05/2026",
                    "About": "Ada",
                    "Athlete": "Ada",
                    "CSV results": "factor",
                    "Exercise": "Squat",
                    "Sets": 5,
                },
                {
                    "form": "Lab Testing",
                    "user_id": 123,
                    "start_date": "07/05/2026",
                    "About": "Ada",
                    "Athlete": "Ada",
                    "CSV results": "factor",
                    "Exercise": "Bench",
                    "Sets": 4,
                },
            ]
        )

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(
            suggestions[0]["candidate_identifier_columns"],
            ["Date", "About", "Athlete", "CSV results"],
        )
        self.assertEqual(suggestions[0]["nested_columns"], ["Exercise", "Sets"])
        self.assertEqual(
            suggestions[0]["main_table"],
            {"Date": "07/05/2026", "About": "Ada", "Athlete": "Ada", "CSV results": "factor"},
        )
        self.assertEqual(
            suggestions[0]["nested_table"],
            [
                {"Exercise": "Squat", "Sets": 5},
                {"Exercise": "Bench", "Sets": 4},
            ],
        )

    def test_grouped_nested_rows_require_consistent_event_id(self):
        with self.assertRaisesRegex(ValueError, "multiple event_id values"):
            build_event_import_payloads(
                [
                    {"user_id": 123, "start_date": "07/05/2026", "event_id": 1, "Factor": "A", "Step": "One"},
                    {"user_id": 123, "start_date": "07/05/2026", "event_id": 2, "Factor": "A", "Step": "Two"},
                ],
                form="Lab Testing",
                mode="upsert",
                nested_table_identifiers=["Factor"],
                now=datetime(2026, 5, 7, 10, 30),
            )


if __name__ == "__main__":
    unittest.main()
