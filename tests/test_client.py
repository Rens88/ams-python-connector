from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.client import SmartabaseClient
from ams_smartabase.config import SmartabaseCredentials


class StubResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class StubSession:
    def __init__(self):
        self.post_calls = []
        self.get_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return StubResponse(
            {"status": "ok"},
            headers={"session-header": "abc123", "Set-Cookie": "JSESSIONID=abc123; Path=/"},
        )

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return StubResponse({"endpoints": [{"name": "eventsearch", "path": "/api/v1/customEvent"}]})


class ResolverClient(SmartabaseClient):
    def __init__(self):
        super().__init__(SmartabaseCredentials("https://teamnl.smartabase.nl/sandbox/", "user", "secret"), session=StubSession())
        self.user_calls = []

    def get_user(self, user_key: str | None = None, user_value: object | None = None):
        self.user_calls.append((user_key, user_value))
        if user_key == "username":
            return [{"userId": 123, "username": "ada"}]
        return []


class ClientTests(unittest.TestCase):
    def test_login_body_uses_site_name_and_client_time(self):
        client = SmartabaseClient(SmartabaseCredentials("https://teamnl.smartabase.nl/sandbox/", "user", "secret"))

        body = client.login_body()

        self.assertEqual(body["loginProperties"]["appName"], "sandbox")
        self.assertIn("clientTime", body["loginProperties"])
        self.assertNotIn("clientTimestamp", body["loginProperties"])

    def test_login_stores_session_metadata(self):
        session = StubSession()
        client = SmartabaseClient(SmartabaseCredentials("example.com/site", "user", "secret"), session=session)

        payload = client.login()

        self.assertEqual(client.session_header, "abc123")
        self.assertEqual(payload["session_header"], "abc123")
        self.assertIn("JSESSIONID=abc123", payload["cookie"])

    def test_login_raises_rpc_exception_detail(self):
        class RpcSession:
            def post(self, url, **kwargs):
                return StubResponse(
                    {"__is_rpc_exception__": True, "value": {"detailMessage": "application known as bad-app"}},
                    headers={},
                )

        client = SmartabaseClient(SmartabaseCredentials("example.com/site", "user", "secret"), session=RpcSession())

        with self.assertRaisesRegex(RuntimeError, "application known as bad-app"):
            client.login()

    def test_discover_endpoints_uses_login_session_headers_and_auth(self):
        session = StubSession()
        client = SmartabaseClient(SmartabaseCredentials("example.com/site", "user", "secret"), session=session)

        endpoints = client.discover_endpoints()

        self.assertEqual(endpoints.resolve("eventsearch"), "customEvent")
        self.assertEqual(len(session.post_calls), 1)
        self.assertEqual(len(session.get_calls), 1)
        _, kwargs = session.get_calls[0]
        self.assertEqual(kwargs["auth"], ("user", "secret"))
        self.assertEqual(kwargs["headers"]["X-GWT-Permutation"], "HostedMode")
        self.assertEqual(kwargs["headers"]["session-header"], "abc123")
        self.assertEqual(kwargs["headers"]["Cookie"], "JSESSIONID=abc123")

    def test_event_insert_dry_run_does_not_require_transport(self):
        client = SmartabaseClient(SmartabaseCredentials("example.com/site", "user", "secret"))

        result = client.insert_event(
            [{"user_id": 123, "Score": 42}],
            form="Wellness",
            dry_run=True,
        )

        self.assertTrue(result.dry_run)
        self.assertFalse(result.executed)
        self.assertEqual(result.attempted_count, 1)
        self.assertEqual(result.responses, [])

    def test_event_insert_dry_run_accepts_csv_path(self):
        client = SmartabaseClient(SmartabaseCredentials("example.com/site", "user", "secret"))
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "records.csv"
            csv_path.write_text("user_id,Score\n123,42\n", encoding="utf-8")

            result = client.insert_event(
                csv_path,
                form="Wellness",
                dry_run=True,
            )

        self.assertTrue(result.dry_run)
        self.assertEqual(result.attempted_count, 1)
        self.assertEqual(result.body["events"][0]["rows"][0]["pairs"], [{"key": "Score", "value": "42"}])

    def test_event_insert_can_resolve_user_ids_before_building_payloads(self):
        client = ResolverClient()

        result = client.insert_event(
            [{"username": "ada", "Score": 42}],
            form="Wellness",
            resolve_user_ids=True,
            dry_run=True,
        )

        self.assertEqual(client.user_calls, [("username", ["ada"])])
        self.assertEqual(result.body["events"][0]["userId"], {"userId": 123})

    def test_event_insert_accepts_nested_table_identifiers(self):
        client = SmartabaseClient(SmartabaseCredentials("example.com/site", "user", "secret"))

        result = client.insert_event(
            [
                {"user_id": 123, "start_date": "07/05/2026", "Factor": "A", "Step": "One"},
                {"user_id": 123, "start_date": "07/05/2026", "Factor": "A", "Step": "Two"},
            ],
            form="Lab Testing",
            nested_table_identifiers=["Factor"],
            dry_run=True,
        )

        self.assertEqual(result.attempted_count, 1)
        self.assertEqual(result.body["events"][0]["rows"][0]["pairs"], [{"key": "Factor", "value": "A"}])
        self.assertEqual(result.body["events"][0]["rows"][1]["pairs"], [{"key": "Step", "value": "One"}])

    def test_delete_event_requires_confirm_for_live_execution(self):
        client = SmartabaseClient(SmartabaseCredentials("example.com/site", "user", "secret"), session=StubSession())

        with self.assertRaisesRegex(PermissionError, "sandbox"):
            client.delete_event([10], dry_run=False, confirm=False)

    def test_live_mutations_are_blocked_outside_sandbox(self):
        client = SmartabaseClient(SmartabaseCredentials("example.com/site", "user", "secret"), session=StubSession())

        with self.assertRaisesRegex(PermissionError, "sandbox"):
            client.insert_event([{"user_id": 10, "Score": 42}], form="Wellness", dry_run=False, confirm=True)

    def test_delete_event_executes_each_payload_when_confirmed_in_sandbox(self):
        session = StubSession()
        client = SmartabaseClient(SmartabaseCredentials("https://teamnl.smartabase.nl/sandbox/", "user", "secret"), session=session)

        result = client.delete_event([10, 11], dry_run=False, confirm=True)

        self.assertTrue(result.executed)
        self.assertEqual(result.attempted_count, 2)
        self.assertEqual(len(result.responses), 2)
        self.assertEqual(len(session.post_calls), 2)
        first_url, first_kwargs = session.post_calls[0]
        self.assertIn("/api/v1/deleteevent", first_url)
        self.assertEqual(first_kwargs["json"], {"eventId": 10})


if __name__ == "__main__":
    unittest.main()
