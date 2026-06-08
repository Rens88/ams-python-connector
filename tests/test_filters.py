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


if __name__ == "__main__":
    unittest.main()
