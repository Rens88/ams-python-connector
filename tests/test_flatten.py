from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase import find_event_records, find_profile_records
from ams_smartabase.flatten import flatten_event_response, flatten_profile_response, flatten_records


class FlattenTests(unittest.TestCase):
    def test_strict_record_finders_are_available_from_the_public_package(self):
        event = {"eventId": 10, "pairs": [{"key": "Score", "value": "5"}]}
        profile = {"userId": 7, "pairs": [{"key": "Height", "value": "180"}]}

        self.assertEqual(find_event_records({"results": [event]}), [event])
        self.assertEqual(find_profile_records({"results": [profile]}), [profile])

    def test_flattens_event_rows_and_pairs(self):
        payload = {
            "events": [
                {
                    "event_id": 10,
                    "user_id": 1,
                    "rows": [
                        {"row": 0, "pairs": [{"key": "Score", "value": "5"}]},
                        {"row": 1, "pairs": [{"key": "Score", "value": "6"}]},
                    ],
                }
            ]
        }
        rows = flatten_event_response(payload)
        self.assertEqual(rows[0]["event_id"], 10)
        self.assertEqual(rows[1]["row_index"], 1)
        self.assertEqual(rows[1]["Score"], "6")

    def test_flattens_profile_pairs(self):
        payload = {"profiles": [{"user_id": 1, "pairs": [{"key": "Height", "value": "180"}]}]}
        self.assertEqual(flatten_profile_response(payload), [{"user_id": 1, "Height": "180"}])

    def test_flattens_nested_event_result_batches_without_treating_batches_as_events(self):
        payload = {
            "results": [
                {
                    "search": {"form": "Synthetic Wellness"},
                    "results": [
                        {
                            "eventId": 10,
                            "rows": [{"row": 0, "pairs": [{"key": "Score", "value": "5"}]}],
                        }
                    ],
                },
                {
                    "search": {"form": "Synthetic Recovery"},
                    "results": [
                        {
                            "eventId": 11,
                            "rows": [{"row": 0, "pairs": [{"key": "Score", "value": "6"}]}],
                        }
                    ],
                },
            ]
        }

        rows = flatten_event_response(payload)

        self.assertEqual([row["eventId"] for row in rows], [10, 11])
        self.assertEqual([row["Score"] for row in rows], ["5", "6"])
        self.assertTrue(all("search" not in row and "results" not in row for row in rows))

    def test_flattens_nested_profile_result_batches(self):
        payload = {
            "response": {
                "results": [
                    {
                        "search": {"form": "Synthetic Profile"},
                        "results": [
                            {
                                "userId": 1,
                                "pairs": [{"key": "Height", "value": "180"}],
                            }
                        ],
                    }
                ]
            }
        }

        self.assertEqual(flatten_profile_response(payload), [{"userId": 1, "Height": "180"}])

    def test_accepts_empty_nested_result_batches(self):
        payload = {"results": [{"search": {"form": "Synthetic Wellness"}, "results": []}]}

        self.assertEqual(flatten_event_response(payload), [])

    def test_keeps_flat_results_response_compatibility(self):
        payload = {
            "results": [
                {"eventId": 10, "pairs": [{"key": "Score", "value": "5"}]},
                {"eventId": 11, "pairs": [{"key": "Score", "value": "6"}]},
            ]
        }

        rows = flatten_event_response(payload)

        self.assertEqual([row["eventId"] for row in rows], [10, 11])

    def test_keeps_permissive_generic_flatten_records_compatibility(self):
        self.assertEqual(flatten_records(["value"], ("results",)), [{"value": "value"}])

    def test_rejects_mixed_direct_records_and_nested_batches(self):
        payload = {
            "results": [
                {"eventId": 10},
                {"search": {"form": "Synthetic"}, "results": [{"eventId": 11}]},
            ]
        }

        with self.assertRaisesRegex(ValueError, "direct records and nested result batches were mixed"):
            flatten_event_response(payload)

    def test_rejects_malformed_nested_batch_without_exposing_values(self):
        sentinel = "sensitive-synthetic-selector"
        payload = {
            "results": [
                {
                    "search": {"about": sentinel},
                    "results": {"eventId": 10},
                }
            ]
        }

        with self.assertRaises(ValueError) as caught:
            flatten_event_response(payload)

        self.assertIn("nested results must be a list", str(caught.exception))
        self.assertNotIn(sentinel, str(caught.exception))

    def test_rejects_search_batch_missing_nested_results(self):
        payload = {"results": [{"search": {"form": "Synthetic Wellness"}}]}

        with self.assertRaisesRegex(ValueError, "result batch is missing its nested results list"):
            flatten_event_response(payload)

        with self.assertRaisesRegex(ValueError, "result batch is missing its nested results list"):
            flatten_event_response({"search": {"form": "Synthetic Wellness"}})

    def test_rejects_non_object_nested_results(self):
        payload = {"results": [{"results": [{"eventId": 10}, "not-an-event"]}]}

        with self.assertRaisesRegex(ValueError, "nested results must contain objects only"):
            flatten_event_response(payload)

    def test_rejects_unrecognized_objects_inside_nested_results(self):
        payload = {"results": [{"results": [{"status": "ok"}]}]}

        with self.assertRaisesRegex(ValueError, "recognizable event objects only"):
            flatten_event_response(payload)

    def test_plain_generic_id_does_not_make_an_object_an_event_record(self):
        with self.assertRaisesRegex(ValueError, "recognizable event objects only"):
            flatten_event_response({"results": [{"id": 10}]})


if __name__ == "__main__":
    unittest.main()
