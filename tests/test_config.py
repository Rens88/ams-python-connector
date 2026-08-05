import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.config import (
    ConfigurationError,
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

    def test_normalize_url_rejects_embedded_credentials(self):
        with self.assertRaisesRegex(ConfigurationError, "embedded credentials"):
            normalize_url("https://user:secret@example.smartabase.com/sandbox")

    def test_invalid_url_error_does_not_echo_possible_userinfo(self):
        malformed = "https:///user:do-not-expose@example.smartabase.com"

        with self.assertRaises(ConfigurationError) as caught:
            normalize_url(malformed)

        self.assertEqual(str(caught.exception), "Invalid Smartabase URL.")
        self.assertNotIn("do-not-expose", str(caught.exception))

    def test_load_credentials_uses_legacy_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            credentials = load_credentials(
                {"SB_URL": "example.com", "SB_USER": "user", "SB_PASS": "secret"},
                Path(tmp) / "missing.env",
            )
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

    def test_from_env_accepts_explicit_env_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "credentials.env"
            env_path.write_text(
                "SMARTABASE_URL=from-file.example\n"
                "SMARTABASE_USERNAME=file-user\n"
                "SMARTABASE_PASSWORD=file-secret\n",
                encoding="utf-8",
            )

            credentials = SmartabaseCredentials.from_env({}, env_path=env_path)

        self.assertEqual(
            credentials,
            SmartabaseCredentials("from-file.example", "file-user", "file-secret"),
        )

    def test_load_credentials_applies_global_preferred_name_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "credentials.env"
            env_path.write_text(
                "SMARTABASE_URL=file-preferred.example\n"
                "SMARTABASE_USERNAME=file-preferred-user\n"
                "SB_PASS=file-legacy-secret\n",
                encoding="utf-8",
            )
            source = {
                "SMARTABASE_URL": "process-preferred.example",
                "SB_URL": "process-legacy.example",
                "SB_USER": "process-legacy-user",
                "SB_PASS": "process-legacy-secret",
            }

            credentials = load_credentials(source, env_path)

        self.assertEqual(credentials.url, "https://process-preferred.example")
        self.assertEqual(credentials.username, "file-preferred-user")
        self.assertEqual(credentials.password, "process-legacy-secret")

    def test_load_credentials_does_not_mutate_process_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "credentials.env"
            env_path.write_text(
                "SMARTABASE_URL=file-preferred.example\n"
                "SMARTABASE_USERNAME=file-preferred-user\n"
                "SMARTABASE_PASSWORD=file-preferred-secret\n",
                encoding="utf-8",
            )
            process_values = {
                "SB_URL": "process-legacy.example",
                "SB_USER": "process-legacy-user",
                "SB_PASS": "process-legacy-secret",
            }
            with patch.dict(os.environ, process_values, clear=True):
                before = dict(os.environ)

                credentials = load_credentials(env_path=env_path)

                self.assertEqual(dict(os.environ), before)

        self.assertEqual(credentials.url, "https://file-preferred.example")
        self.assertEqual(credentials.username, "file-preferred-user")
        self.assertEqual(credentials.password, "file-preferred-secret")

    def test_missing_configuration_error_does_not_expose_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigurationError) as context:
                load_credentials(
                    {"SMARTABASE_PASSWORD": "do-not-expose"},
                    Path(tmp) / "missing.env",
                )

        self.assertIn("URL is required", str(context.exception))
        self.assertNotIn("do-not-expose", str(context.exception))

    def test_redacts_passwords(self):
        credentials = SmartabaseCredentials("example.com", "user", "secret")
        self.assertEqual(credentials.redacted_dict()["password"], "***")
        self.assertNotIn("secret", repr(credentials))
        self.assertNotIn("secret", str(credentials))
        self.assertEqual(redact_secrets({"nested": {"password": "secret"}}), {"nested": {"password": "***"}})
        self.assertEqual(
            redact_secrets(
                {
                    "session-header": "session-secret",
                    "access_token": "token-secret",
                    "sessionToken": "camel-token-secret",
                    "profile": {
                        "clientSecret": "nested-client-secret",
                        "safe": "value",
                    },
                    "safe": "value",
                }
            ),
            {
                "session-header": "***",
                "access_token": "***",
                "sessionToken": "***",
                "profile": {
                    "clientSecret": "***",
                    "safe": "value",
                },
                "safe": "value",
            },
        )


if __name__ == "__main__":
    unittest.main()
