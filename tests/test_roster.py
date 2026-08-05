from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.roster import (
    BASE_ROSTER_COLUMNS,
    RosterEntry,
    fetch_roster,
    flatten_roster_response,
    normalize_group_response,
    resolve_user_ids,
    roster_entry_to_row,
    roster_to_rows,
)


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

    def test_flatten_roster_response_unwraps_official_user_result_batches(self):
        first_user = {
            "userId": 123,
            "firstName": "Ada",
            "lastName": "Lovelace",
            "username": "ada",
            "groupsAndRoles": {
                "role": [{"id": 700, "name": "Synthetic Role"}],
            },
        }
        second_user = {
            "userId": 456,
            "firstName": "Grace",
            "lastName": "Hopper",
            "username": "grace",
        }
        payload = {
            "results": [
                {
                    "search": {"username": "synthetic-selector"},
                    "results": [first_user],
                },
                {
                    "search": {"username": "another-selector"},
                    "results": [second_user],
                },
            ]
        }

        roster = flatten_roster_response(payload)

        self.assertEqual([entry.user_id for entry in roster], [123, 456])
        self.assertEqual(
            [(entry.first_name, entry.last_name) for entry in roster],
            [("Ada", "Lovelace"), ("Grace", "Hopper")],
        )
        self.assertIs(roster[0].raw["groupsAndRoles"], first_user["groupsAndRoles"])
        self.assertNotIn("search", roster[0].raw)

    def test_flatten_roster_response_accepts_empty_official_user_result_batch(self):
        payload = {
            "results": [
                {
                    "search": {"username": "synthetic-selector"},
                    "results": [],
                }
            ]
        }

        self.assertEqual(flatten_roster_response(payload), [])

    def test_flatten_roster_response_preserves_flat_legacy_id_and_name_aliases(self):
        roster = flatten_roster_response([{"id": 42, "name": "Ada Lovelace"}])

        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0].user_id, 42)
        self.assertEqual(roster[0].about, "Ada Lovelace")

    def test_flatten_roster_response_rejects_ambiguous_or_malformed_batches(self):
        sentinel = "must-not-appear-in-error"
        cases = (
            {
                "results": [
                    {"userId": 1, "firstName": "Ada", "lastName": "Lovelace"},
                    {
                        "search": {"username": sentinel},
                        "results": [
                            {
                                "userId": 2,
                                "firstName": "Grace",
                                "lastName": "Hopper",
                            }
                        ],
                    },
                ]
            },
            {
                "results": [
                    {
                        "search": {"username": sentinel},
                        "results": [sentinel],
                    }
                ]
            },
            {
                "results": [
                    {
                        "username": sentinel,
                        "results": [
                            {
                                "userId": 2,
                                "firstName": "Grace",
                                "lastName": "Hopper",
                            }
                        ],
                    }
                ]
            },
            {
                "results": [
                    {
                        "search": {"username": sentinel},
                        "results": [{"id": 700, "name": sentinel}],
                    }
                ]
            },
            {
                "results": [
                    {
                        "search": {"username": sentinel},
                        "results": [
                            {
                                "groupsAndRoles": {
                                    "role": [{"id": 700, "name": sentinel}],
                                }
                            }
                        ],
                    }
                ]
            },
            {"results": [{"search": {"username": sentinel}}]},
        )

        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError) as caught:
                flatten_roster_response(payload)

            self.assertRegex(
                str(caught.exception),
                "Smartabase roster response",
            )
            self.assertNotIn(sentinel, str(caught.exception))

    def test_roster_entry_to_row_has_stable_six_column_base_contract(self):
        entry = RosterEntry(
            user_id=7,
            about="Ada Lovelace",
            first_name="Ada",
            last_name="Lovelace",
            username="ada",
            email="ada@example.com",
            group_names=["Athletes"],
            raw={"userId": 7, "privateProfileField": "not exported"},
        )

        row = roster_entry_to_row(entry)

        self.assertEqual(
            BASE_ROSTER_COLUMNS,
            ("user_id", "about", "first_name", "last_name", "username", "email"),
        )
        self.assertEqual(list(row), list(BASE_ROSTER_COLUMNS))
        self.assertEqual(
            row,
            {
                "user_id": "7",
                "about": "Ada Lovelace",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "username": "ada",
                "email": "ada@example.com",
            },
        )
        self.assertNotIn("raw", row)
        self.assertNotIn("private_profile_field", row)

    def test_roster_entry_to_row_preserves_raw_textual_user_ids(self):
        roster = flatten_roster_response(
            [
                {"userId": "00042", "firstName": "Ada", "lastName": "Lovelace"},
                {"smartabase_user_id": "athlete-A", "firstName": "Grace", "lastName": "Hopper"},
                {"userId": {"userId": "00007"}, "firstName": "Katherine", "lastName": "Johnson"},
                {"User ID": "00009", "First Name": "Mary", "Last Name": "Jackson"},
            ]
        )

        self.assertEqual([entry.user_id for entry in roster], [42, None, 7, 9])
        self.assertEqual(
            [roster_entry_to_row(entry)["user_id"] for entry in roster],
            ["00042", "athlete-A", "00007", "00009"],
        )
        self.assertEqual((roster[-1].first_name, roster[-1].last_name), ("Mary", "Jackson"))

    def test_roster_entry_to_row_normalizes_and_serializes_extended_columns(self):
        raw = {
            "user_id": "0007",
            "userId": "ignored alias",
            "id": "ignored alias",
            "smartabase_user_id": "ignored alias",
            "about": "Ada Lovelace",
            "name": "ignored alias",
            "first_name": "Ada",
            "firstName": "ignored alias",
            "last_name": "Lovelace",
            "lastName": "ignored alias",
            "username": "ada",
            "user_name": "ignored alias",
            "login": "ignored alias",
            "email": "ada@example.com",
            "email_address": "ignored alias",
            "emailAddress": "ignored alias",
            "Date Of Birth": "1815-12-10",
            "profileInfo": {
                "z": 2,
                "a": ["é", {"b": 2, "a": 1}],
                "sessionToken": "must-not-export",
                "clientSecret": "must-not-export",
            },
            "roles": ["Athlete", "Analyst"],
            "shirt-size": None,
            "session-header": "must-not-export",
            "authToken": "must-not-export",
            "clientSecret": "must-not-export",
            "profilePasswordHash": "must-not-export",
        }
        entry = flatten_roster_response([raw])[0]

        row = roster_entry_to_row(entry, include_all_cols=True)

        self.assertEqual(
            list(row),
            [
                *BASE_ROSTER_COLUMNS,
                "date_of_birth",
                "profile_info",
                "roles",
                "shirt_size",
            ],
        )
        self.assertEqual(row["user_id"], "0007")
        self.assertEqual(row["date_of_birth"], "1815-12-10")
        self.assertEqual(
            row["profile_info"],
            '{"a":["é",{"a":1,"b":2}],"clientSecret":"***",'
            '"sessionToken":"***","z":2}',
        )
        self.assertEqual(row["roles"], '["Athlete","Analyst"]')
        self.assertEqual(row["shirt_size"], "")
        self.assertNotIn("session_header", row)
        self.assertNotIn("auth_token", row)
        self.assertNotIn("client_secret", row)
        self.assertNotIn("profile_password_hash", row)
        for alias in (
            "id",
            "name",
            "user_name",
            "login",
            "email_address",
            "smartabase_user_id",
        ):
            self.assertNotIn(alias, row)

    def test_roster_entry_to_row_rejects_normalized_extra_column_collisions(self):
        entry = RosterEntry(
            user_id=7,
            about="Ada Lovelace",
            first_name="Ada",
            last_name="Lovelace",
            username="ada",
            email="ada@example.com",
            group_names=[],
            raw={"userId": 7, "shirtSize": "S", "shirt-size": "M"},
        )

        with self.assertRaisesRegex(
            ValueError,
            "shirtSize.*shirt-size.*shirt_size",
        ):
            roster_entry_to_row(entry, include_all_cols=True)

    def test_roster_entry_to_row_rejects_non_json_nested_values_without_repr_fallback(self):
        entry = RosterEntry(
            user_id=7,
            about="Ada Lovelace",
            first_name="Ada",
            last_name="Lovelace",
            username="ada",
            email="ada@example.com",
            group_names=[],
            raw={"userId": 7, "profile": {"invalid": {1, 2}}},
        )

        with self.assertRaisesRegex(ValueError, "cannot be encoded as JSON"):
            roster_entry_to_row(entry, include_all_cols=True)

    def test_roster_to_rows_returns_union_of_sorted_extras_and_fills_missing_cells(self):
        first, second = flatten_roster_response(
            [
                {
                    "userId": "002",
                    "firstName": "Grace",
                    "lastName": "Hopper",
                    "zField": 2,
                },
                {
                    "userId": "alpha",
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                    "aField": 1,
                },
            ]
        )

        columns, rows = roster_to_rows([first, second], include_all_cols=True)

        self.assertEqual(columns, [*BASE_ROSTER_COLUMNS, "a_field", "z_field"])
        self.assertEqual(list(rows[0]), columns)
        self.assertEqual(list(rows[1]), columns)
        self.assertEqual(rows[0]["user_id"], "002")
        self.assertEqual(rows[0]["a_field"], "")
        self.assertEqual(rows[0]["z_field"], "2")
        self.assertEqual(rows[1]["user_id"], "alpha")
        self.assertEqual(rows[1]["a_field"], "1")
        self.assertEqual(rows[1]["z_field"], "")

    def test_roster_to_rows_empty_input_keeps_base_columns(self):
        columns, rows = roster_to_rows([], include_all_cols=True)

        self.assertEqual(columns, list(BASE_ROSTER_COLUMNS))
        self.assertEqual(rows, [])

    def test_normalize_group_response_supports_flat_mapping_and_nested_envelopes(self):
        expected = [{"group": "Alpha"}, {"group": "beta"}]
        payloads = [
            ["beta", "Alpha", "Alpha"],
            {"groups": [{"name": "Alpha"}, {"groupName": "beta"}]},
            {"response": {"data": {"items": [{"group": "beta"}, "Alpha"]}}},
            {"wrapper": {"groupNames": ["beta", "Alpha"]}},
            [{"group": {"name": "Alpha"}}, {"group_name": "beta"}],
        ]

        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertEqual(normalize_group_response(payload), expected)

    def test_normalize_group_response_ignores_empty_and_unrelated_payloads(self):
        self.assertEqual(normalize_group_response(None), [])
        self.assertEqual(normalize_group_response({"groups": []}), [])
        for payload in ({"status": "ok"}, {"groups": ["", None, 123]}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "Unrecognized"):
                    normalize_group_response(payload)

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
                {"Smartabase User Id": 21, "Score": 5},
            ],
        )

        self.assertEqual(
            [
                row.get("user_id", row.get("Smartabase User Id"))
                for row in resolved
            ],
            [10, 11, 12, 20, 21],
        )
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
