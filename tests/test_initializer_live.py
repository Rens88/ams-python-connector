"""Opt-in, read-only live verification for the sandbox athlete initializer."""

import os
from pathlib import Path
import tempfile
import unittest

from ams_smartabase import SmartabaseClient, load_credentials
from ams_smartabase.initializer import initialize_sandbox_athletes
from ams_smartabase.roster import BASE_ROSTER_COLUMNS


_TRUE_VALUES = {"1", "true", "yes", "on"}
_LIVE_FLAG = "SMARTABASE_RUN_LIVE_INITIALIZER_TEST"
_GROUP_VARIABLE = "SMARTABASE_ATHLETE_GROUP"


@unittest.skipUnless(
    os.environ.get(_LIVE_FLAG, "").strip().casefold() in _TRUE_VALUES,
    f"set {_LIVE_FLAG}=1 to run the read-only live sandbox initializer test",
)
class LiveInitializerTests(unittest.TestCase):
    def test_named_sandbox_group_exports_valid_base_registry(self):
        group_name = os.environ.get(_GROUP_VARIABLE, "").strip()
        self.assertTrue(
            group_name,
            f"{_GROUP_VARIABLE} must name an authorized sandbox test group",
        )

        credentials = load_credentials()
        self.assertIn(
            "sandbox",
            credentials.url.casefold(),
            "live initializer verification is restricted to sandbox URLs",
        )

        with tempfile.TemporaryDirectory(prefix="ams-initializer-live-") as tmp:
            temporary_root = Path(tmp)
            result = initialize_sandbox_athletes(
                SmartabaseClient(credentials),
                output_csv=temporary_root / "athletes.csv",
                output_json=temporary_root / "athletes_metadata.json",
                group_name=group_name,
            )

            self.assertGreater(result.row_count, 0)
            self.assertEqual(
                result.columns[: len(BASE_ROSTER_COLUMNS)],
                BASE_ROSTER_COLUMNS,
            )
            self.assertTrue(result.output_csv.is_file())
            self.assertTrue(result.output_json.is_file())

        print(
            "Read-only live initializer verification exported "
            f"{result.row_count} sandbox athlete rows."
        )


if __name__ == "__main__":
    unittest.main()
