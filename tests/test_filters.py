from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.filters import (
    DataFilter,
    build_event_export_request,
    build_group_request,
    build_profile_export_request,
    build_sync_request,
    build_user_request,
    sb_date_range,
)
from ams_smartabase.diagnostics import AMSDateFormatError, AMSInputValidationError


class FilterTests(unittest.TestCase):
    def test_user_request_without_filter(self):
        self.assertEqual(build_user_request(), ("usersearch", {"identification": None}))

    def test_user_request_about_splits_name(self):
        endpoint, body = build_user_request("about", "Ada Lovelace")
        self.assertEqual(endpoint, "usersearch")
        self.assertEqual(body["identification"], [{"firstName": "Ada", "lastName": "Lovelace"}])

    def test_group_requests(self):
        self.assertEqual(build_user_request("group", "First Team"), ("groupmembers", {"name": "First Team"}))
        self.assertEqual(build_user_request("current_group"), ("currentgroup", {"name": ""}))
        self.assertEqual(build_group_request(), ("listgroups", {"name": ""}))

    def test_event_request_with_data_filter(self):
        endpoint, body = build_event_export_request(
            "Session",
            [10],
            ("01/03/2026", "07/03/2026"),
            data_filters=[DataFilter("Duration", 35, ">")],
            events_per_user=5,
        )
        self.assertEqual(endpoint, "filteredeventsearch")
        self.assertEqual(body["resultsPerUser"], 5)
        self.assertEqual(body["filter"][0]["filterSet"][0]["filterCondition"], 5)

    def test_profile_and_sync_requests(self):
        self.assertEqual(build_profile_export_request("Profile", [1])[1], {"formNames": "Profile", "userIds": [1]})
        self.assertEqual(
            build_sync_request("Session", [1], 1672531200000)[1]["lastSynchronisationTimeOnServer"],
            1672531200000,
        )

    def test_date_range_is_day_first_and_inclusive(self):
        self.assertEqual(sb_date_range(7, date(2026, 3, 7)), ("01/03/2026", "07/03/2026"))

    def test_event_request_reports_actionable_date_contract_before_transport(self):
        with self.assertRaises(AMSDateFormatError) as raised:
            build_event_export_request("Session", [10], ("2026-03-01", "07/03/2026"))

        self.assertEqual(raised.exception.field, "start_date")
        self.assertFalse(raised.exception.request_sent)
        self.assertIn("DD/MM/YYYY", str(raised.exception))

    def test_reversed_date_range_is_a_structured_pre_transport_error(self):
        with self.assertRaises(AMSInputValidationError) as raised:
            build_event_export_request("Session", [10], ("07/03/2026", "01/03/2026"))

        self.assertEqual(raised.exception.code, "reversed_date_range")
        self.assertFalse(raised.exception.request_sent)


if __name__ == "__main__":
    unittest.main()
