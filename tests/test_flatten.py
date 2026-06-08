from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.flatten import flatten_event_response, flatten_profile_response


class FlattenTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
