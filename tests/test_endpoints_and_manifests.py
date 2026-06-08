from datetime import datetime
from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.endpoints import EndpointMap
from ams_smartabase.manifests import create_operation_folder, safe_slug, write_manifest_csv, write_operation_config


class EndpointAndManifestTests(unittest.TestCase):
    def test_endpoint_discovery_updates_aliases(self):
        endpoints = EndpointMap.from_discovery({"endpoints": [{"name": "eventsearch", "path": "/api/v1/customEvent"}]})
        self.assertEqual(endpoints.resolve("eventsearch"), "customEvent")

    def test_manifest_helpers_write_expected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = create_operation_folder("Event Export", base_dir=tmp, timestamp=datetime(2026, 5, 7, 20, 0))
            self.assertTrue((folder / "payloads").exists())
            config_path = write_operation_config(folder, {"password": "secret", "operation": "export"})
            manifest_path = write_manifest_csv(folder, [{"operation": "export", "endpoint": "eventsearch", "row_count": 2}])
            self.assertIn('"password": "***"', config_path.read_text(encoding="utf-8"))
            self.assertIn("eventsearch", manifest_path.read_text(encoding="utf-8"))

    def test_safe_slug(self):
        self.assertEqual(safe_slug("Event Export!"), "event_export")


if __name__ == "__main__":
    unittest.main()
