from datetime import datetime
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.payloads import (
    build_delete_payloads,
    build_event_import_payloads,
    build_profile_upsert_payloads,
    select_metadata,
)


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

    def test_delete_payloads_are_explicit_event_ids(self):
        package = build_delete_payloads(["10", 11])
        self.assertEqual(package.body, [{"eventId": 10}, {"eventId": 11}])

    def test_select_metadata_returns_preferred_order_original_names(self):
        columns = ["Score", "Event_ID", "User ID", "About"]
        self.assertEqual(select_metadata(columns), ["About", "User ID", "Event_ID"])


if __name__ == "__main__":
    unittest.main()
