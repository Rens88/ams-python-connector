import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.config import (
    SmartabaseCredentials,
    load_credentials,
    load_dotenv,
    normalize_url,
    redact_secrets,
)


class ConfigTests(unittest.TestCase):
    def test_normalize_url_adds_https_and_strips_trailing_slash(self):
        self.assertEqual(normalize_url("teamnl.smartabase.nl/sandbox/"), "https://teamnl.smartabase.nl/sandbox")

    def test_normalize_url_forces_https(self):
        self.assertEqual(normalize_url("http://example.smartabase.com"), "https://example.smartabase.com")

    def test_load_credentials_uses_legacy_aliases(self):
        credentials = load_credentials({"SB_URL": "example.com", "SB_USER": "user", "SB_PASS": "secret"})
        self.assertEqual(credentials.url, "https://example.com")
        self.assertEqual(credentials.username, "user")
        self.assertEqual(credentials.password, "secret")

    def test_load_dotenv_parses_simple_key_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                'SMARTABASE_URL=example.com\nSMARTABASE_USERNAME="user"\nSMARTABASE_PASSWORD=\'secret\'\n',
                encoding="utf-8",
            )
            self.assertEqual(
                load_dotenv(env_path),
                {
                    "SMARTABASE_URL": "example.com",
                    "SMARTABASE_USERNAME": "user",
                    "SMARTABASE_PASSWORD": "secret",
                },
            )

    def test_load_credentials_falls_back_to_local_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "SMARTABASE_URL=example.com\nSMARTABASE_USERNAME=user\nSMARTABASE_PASSWORD=secret\n",
                encoding="utf-8",
            )
            old_cwd = Path.cwd()
            try:
                os.chdir(tmp)
                credentials = load_credentials({})
            finally:
                os.chdir(old_cwd)
            self.assertEqual(credentials, SmartabaseCredentials("example.com", "user", "secret"))

    def test_redacts_passwords(self):
        credentials = SmartabaseCredentials("example.com", "user", "secret")
        self.assertEqual(credentials.redacted_dict()["password"], "***")
        self.assertEqual(redact_secrets({"nested": {"password": "secret"}}), {"nested": {"password": "***"}})


if __name__ == "__main__":
    unittest.main()
