from pathlib import Path
import sys
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


if __name__ == "__main__":
    unittest.main()
