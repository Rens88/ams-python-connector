from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.roster import RosterEntry, fetch_roster, flatten_roster_response, resolve_user_ids


class StubRosterClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_user(self, *, user_key=None, user_value=None):
        self.calls.append((user_key, user_value))
        return self.payload


class RosterTests(unittest.TestCase):
    def test_flatten_roster_response_normalizes_common_user_fields(self):
        payload = {
            "users": [
                {
                    "userId": 123,
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                    "username": "ada",
                    "emailAddress": "ada@example.com",
                    "groupNames": ["Athletes", "First Team"],
                }
            ]
        }

        roster = flatten_roster_response(payload)

        self.assertEqual(
            roster,
            [
                RosterEntry(
                    user_id=123,
                    about="Ada Lovelace",
                    first_name="Ada",
                    last_name="Lovelace",
                    username="ada",
                    email="ada@example.com",
                    group_names=["Athletes", "First Team"],
                    raw=payload["users"][0],
                )
            ],
        )

    def test_flatten_roster_response_recurses_through_nested_payloads(self):
        payload = {"response": {"results": [{"user_id": "42", "about": "Grace Hopper", "group": "Coaches"}]}}

        roster = flatten_roster_response(payload)

        self.assertEqual(roster[0].user_id, 42)
        self.assertEqual(roster[0].about, "Grace Hopper")
        self.assertEqual(roster[0].group_names, ["Coaches"])

    def test_fetch_roster_uses_group_lookup(self):
        client = StubRosterClient([{"userId": 10, "about": "Ada Lovelace"}])

        roster = fetch_roster(client, group_name="Athletes")

        self.assertEqual(client.calls, [("group", "Athletes")])
        self.assertEqual(roster[0].about, "Ada Lovelace")

    def test_fetch_roster_supports_current_group_lookup(self):
        client = StubRosterClient([{"userId": 10, "about": "Ada Lovelace"}])

        fetch_roster(client, current_group=True)

        self.assertEqual(client.calls, [("current_group", None)])

    def test_fetch_roster_rejects_conflicting_selectors(self):
        client = StubRosterClient([])

        with self.assertRaisesRegex(ValueError, "Choose only one roster selector"):
            fetch_roster(client, group_name="Athletes", user_key="user_id", user_value=1)

    def test_resolve_user_ids_fills_missing_user_ids_from_username_email_and_about(self):
        class ResolverClient:
            def __init__(self):
                self.calls = []

            def get_user(self, *, user_key=None, user_value=None):
                self.calls.append((user_key, user_value))
                if user_key == "username":
                    return [{"userId": 10, "username": "ada"}]
                if user_key == "email":
                    return [{"userId": 11, "emailAddress": "grace@example.com"}]
                if user_key == "about":
                    return [{"userId": 12, "about": "Katherine Johnson"}]
                return []

        client = ResolverClient()

        resolved = resolve_user_ids(
            client,
            [
                {"username": "ada", "Score": 1},
                {"email": "grace@example.com", "Score": 2},
                {"about": "Katherine Johnson", "Score": 3},
                {"user_id": 20, "Score": 4},
            ],
        )

        self.assertEqual([row["user_id"] for row in resolved], [10, 11, 12, 20])
        self.assertEqual(
            client.calls,
            [
                ("username", ["ada"]),
                ("email", ["grace@example.com"]),
                ("about", ["Katherine Johnson"]),
            ],
        )


if __name__ == "__main__":
    unittest.main()
