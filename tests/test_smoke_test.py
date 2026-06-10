from argparse import Namespace
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.config import SmartabaseCredentials
from ams_smartabase.smoke_test import resolve_credentials, run_smoke_test


class StubEndpoints:
    def __init__(self):
        self.aliases = {"eventsearch": "customEvent"}


class StubClient:
    def __init__(self):
        self.calls = []

    def login(self):
        self.calls.append(("login",))
        return {"status": "ok"}

    def discover_endpoints(self):
        self.calls.append(("discover_endpoints",))
        return StubEndpoints()

    def get_group(self):
        self.calls.append(("get_group",))
        return ["First Team"]

    def get_user(self, *, user_key, user_value):
        self.calls.append(("get_user", user_key, user_value))
        return [{"about": "Ada Lovelace"}]


class SmokeTestTests(unittest.TestCase):
    def test_resolve_credentials_uses_env_then_prompts_for_password(self):
        args = Namespace(url=None, username=None, password=None)
        prompted = []
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = Path.cwd()
            try:
                os.chdir(tmp)
                credentials = resolve_credentials(
                    args,
                    env={"SMARTABASE_URL": "example.com", "SMARTABASE_USERNAME": "user"},
                    password_prompt=lambda prompt: prompted.append(prompt) or "secret",
                )
            finally:
                os.chdir(old_cwd)

        self.assertEqual(credentials, SmartabaseCredentials("example.com", "user", "secret"))
        self.assertEqual(prompted, ["Smartabase password: "])

    def test_resolve_credentials_falls_back_to_local_dotenv(self):
        args = Namespace(url=None, username=None, password=None)
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "SMARTABASE_URL=example.com\nSMARTABASE_USERNAME=user\nSMARTABASE_PASSWORD=secret\n",
                encoding="utf-8",
            )
            old_cwd = Path.cwd()
            try:
                os.chdir(tmp)
                credentials = resolve_credentials(args, env={}, password_prompt=lambda prompt: "unused")
            finally:
                os.chdir(old_cwd)

        self.assertEqual(credentials, SmartabaseCredentials("example.com", "user", "secret"))

    def test_run_smoke_test_calls_requested_operations(self):
        client = StubClient()
        results = run_smoke_test(
            SmartabaseCredentials("example.com", "user", "secret"),
            discover_endpoints=True,
            list_groups=True,
            group_name="Athletes",
            client=client,
        )

        self.assertEqual(results["login"], {"status": "ok"})
        self.assertEqual(results["endpoints"], {"eventsearch": "customEvent"})
        self.assertEqual(results["groups"], ["First Team"])
        self.assertEqual(results["group_users"], [{"about": "Ada Lovelace"}])
        self.assertEqual(
            client.calls,
            [
                ("login",),
                ("discover_endpoints",),
                ("get_group",),
                ("get_user", "group", "Athletes"),
            ],
        )

    def test_run_smoke_test_defaults_to_login_only(self):
        client = StubClient()
        results = run_smoke_test(
            SmartabaseCredentials("example.com", "user", "secret"),
            client=client,
        )

        self.assertEqual(results, {"login": {"status": "ok"}})
        self.assertEqual(client.calls, [("login",)])


if __name__ == "__main__":
    unittest.main()
