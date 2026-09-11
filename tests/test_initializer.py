import csv
from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ams_smartabase
from ams_smartabase.config import SmartabaseCredentials
from ams_smartabase.initializer import (
    AthleteInitializationResult,
    _resolve_cli_selector,
    _stage_csv,
    _stage_json,
    build_parser,
    initialize_sandbox_athletes,
    main,
)


def user(
    user_id,
    first_name,
    last_name,
    *,
    about=None,
    username="",
    email="",
    **extra,
):
    row = {
        "userId": user_id,
        "firstName": first_name,
        "lastName": last_name,
        "username": username,
        "emailAddress": email,
        **extra,
    }
    if about is not None:
        row["about"] = about
    return row


class StubEndpointMap:
    aliases = {
        "usersearch": "usersearch",
        "groupmembers": "groupmembers",
        "currentgroup": "currentgroup",
        "listgroups": "listgroups",
    }

    def __init__(self, discovered_aliases=None):
        self.discovered_aliases = set(
            self.aliases
            if discovered_aliases is None
            else discovered_aliases
        )


class StubInitializerClient:
    def __init__(
        self,
        users,
        *,
        user_lookup=None,
        groups=None,
        url="https://example.smartabase.test/sandbox",
        discovery_error=None,
        discovery_aliases=None,
        group_error=None,
        login_error=None,
    ):
        self.credentials = SmartabaseCredentials(url, "example-user", "super-secret")
        self.users = users
        self.user_lookup = user_lookup
        self.groups = [] if groups is None else groups
        self.discovery_error = discovery_error
        self.discovery_aliases = discovery_aliases
        self.group_error = group_error
        self.login_error = login_error
        self.calls = []

    def login(self):
        self.calls.append(("login",))
        if self.login_error is not None:
            raise self.login_error
        return {"status": "ok", "session_header": "do-not-persist"}

    def discover_endpoints(self):
        self.calls.append(("discover_endpoints",))
        if self.discovery_error is not None:
            raise self.discovery_error
        return StubEndpointMap(self.discovery_aliases)

    def get_user(self, *, user_key=None, user_value=None):
        self.calls.append(("get_user", user_key, user_value))
        if user_key == "user_id" and self.user_lookup is not None:
            return self.user_lookup
        return self.users

    def get_group(self):
        self.calls.append(("get_group",))
        if self.group_error is not None:
            raise self.group_error
        return self.groups


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


class InitializerWorkflowTests(unittest.TestCase):
    def test_writes_generator_compatible_csv_and_redacted_metadata(self):
        client = StubInitializerClient(
            [
                user(
                    20,
                    "Zoë",
                    'D"Angelo',
                    username="zoe",
                    email="zoe@example.test",
                ),
                user(
                    3,
                    "Ada",
                    "Lovelace",
                    about="Countess, Ada Lovelace",
                    username="ada",
                    email="ada@example.test",
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "sandbox_state" / "athletes.csv"
            output_json = Path(tmp) / "sandbox_state" / "athletes_metadata.json"

            result = initialize_sandbox_athletes(
                client,
                output_csv=output_csv,
                output_json=output_json,
                group_name="Athletes",
            )

            columns, rows = read_csv(output_csv)
            metadata_text = output_json.read_text(encoding="utf-8")
            metadata = json.loads(metadata_text)
            output_digest = hashlib.sha256(output_csv.read_bytes()).hexdigest()

        self.assertEqual(
            columns,
            ["user_id", "about", "first_name", "last_name", "username", "email"],
        )
        self.assertEqual([row["user_id"] for row in rows], ["3", "20"])
        self.assertEqual(rows[0]["about"], "Countess, Ada Lovelace")
        self.assertEqual(rows[1]["first_name"], "Zoë")
        self.assertEqual(rows[1]["last_name"], 'D"Angelo')
        self.assertEqual(
            client.calls,
            [
                ("login",),
                ("discover_endpoints",),
                ("get_user", "group", "Athletes"),
            ],
        )
        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.columns, tuple(columns))
        self.assertEqual(result.endpoint_discovery, "discovered")
        self.assertEqual(metadata["selector"], {"user_key": "group", "user_value": "Athletes"})
        self.assertEqual(metadata["endpoint_discovery"], "discovered")
        self.assertEqual(metadata["source"], "ams-python-connector")
        self.assertEqual(metadata["operation"], "initialize_sandbox_athletes")
        self.assertEqual(metadata["output_csv_sha256"], output_digest)
        self.assertNotIn("super-secret", metadata_text)
        self.assertNotIn("session_header", metadata_text)
        self.assertNotIn("cookie", metadata_text.lower())
        with self.assertRaises(FrozenInstanceError):
            result.row_count = 99
        with self.assertRaises(TypeError):
            result.selector["user_key"] = "username"

    def test_writes_registry_from_official_nested_user_result_batches(self):
        client = StubInitializerClient(
            {
                "results": [
                    {
                        "search": {"group": "Synthetic Athletes"},
                        "results": [
                            user(20, "Grace", "Hopper", username="grace"),
                            user(3, "Ada", "Lovelace", username="ada"),
                        ],
                    }
                ]
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "athletes.csv"
            output_json = Path(tmp) / "metadata.json"

            result = initialize_sandbox_athletes(
                client,
                output_csv=output_csv,
                output_json=output_json,
                group_name="Synthetic Athletes",
            )
            columns, rows = read_csv(output_csv)

        self.assertEqual(result.row_count, 2)
        self.assertEqual(
            columns,
            ["user_id", "about", "first_name", "last_name", "username", "email"],
        )
        self.assertEqual([row["user_id"] for row in rows], ["3", "20"])
        self.assertEqual(
            [(row["first_name"], row["last_name"]) for row in rows],
            [("Ada", "Lovelace"), ("Grace", "Hopper")],
        )

    def test_can_include_live_group_membership_in_registry(self):
        client = StubInitializerClient(
            [
                user(7, "Ada", "Lovelace"),
            ],
            user_lookup=[
                user(
                    7,
                    "Ada",
                    "Lovelace",
                    groupsAndRoles={
                        "athleteGroups": [{"id": 20797, "name": "SSC.KNLTB.G5"}],
                        "role": [{"id": 1272, "name": "Athlete"}],
                    },
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "athletes.csv"
            result = initialize_sandbox_athletes(
                client,
                output_csv=output_csv,
                output_json=Path(tmp) / "metadata.json",
                include_group=True,
            )
            columns, rows = read_csv(output_csv)

        self.assertEqual(columns[-1], "Group")
        self.assertEqual(rows[0]["Group"], "SSC.KNLTB.G5")
        self.assertTrue(result.columns[-1] == "Group")

    def test_group_membership_is_optional_during_registry_initialization(self):
        client = StubInitializerClient(
            [user(7, "Ada", "Lovelace")],
            user_lookup=[user(7, "Ada", "Lovelace")],
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "athletes.csv"
            result = initialize_sandbox_athletes(
                client,
                output_csv=output_csv,
                output_json=Path(tmp) / "metadata.json",
                include_group=True,
            )
            columns, rows = read_csv(output_csv)

        self.assertEqual(result.row_count, 1)
        self.assertEqual(columns[-1], "Group")
        self.assertEqual(rows[0]["Group"], "")

    def test_supports_current_group_identifier_and_all_user_selectors(self):
        cases = [
            ({"current_group": True}, ("current_group", None)),
            (
                {"user_key": "username", "user_value": "ada"},
                ("username", "ada"),
            ),
            ({}, (None, None)),
        ]
        for kwargs, expected_selector in cases:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as tmp:
                client = StubInitializerClient([user(1, "Ada", "Lovelace")])
                with self.assertWarnsRegex(UserWarning, "all users") if not kwargs else _null_context():
                    result = initialize_sandbox_athletes(
                        client,
                        output_csv=Path(tmp) / "athletes.csv",
                        output_json=Path(tmp) / "metadata.json",
                        discover_endpoints=False,
                        **kwargs,
                    )

                self.assertEqual(client.calls[-1], ("get_user", *expected_selector))
                self.assertEqual(result.endpoint_discovery, "defaults")

    def test_rejects_conflicting_or_incomplete_selectors(self):
        client = StubInitializerClient([user(1, "Ada", "Lovelace")])
        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "athletes.csv"
            output_json = Path(tmp) / "metadata.json"
            with self.assertRaisesRegex(ValueError, "only one roster selector"):
                initialize_sandbox_athletes(
                    client,
                    output_csv=output_csv,
                    output_json=output_json,
                    group_name="Athletes",
                    user_key="username",
                    user_value="ada",
                )
            with self.assertRaisesRegex(ValueError, "user_key"):
                initialize_sandbox_athletes(
                    client,
                    output_csv=output_csv,
                    output_json=output_json,
                    user_value="ada",
                )
            for kwargs in (
                {"group_name": ""},
                {"group_name": "   "},
                {"user_key": "group", "user_value": "   "},
                {"user_key": "about"},
                {"user_key": "user_id", "user_value": []},
                {"user_key": "username", "user_value": ""},
                {"user_key": "email", "user_value": "   "},
            ):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaisesRegex(
                        ValueError,
                        "must not be blank|user_value is required",
                    ):
                        initialize_sandbox_athletes(
                            client,
                            output_csv=output_csv,
                            output_json=output_json,
                            **kwargs,
                        )
        self.assertEqual(client.calls, [])

    def test_optional_groups_csv_is_normalized_and_customizable(self):
        client = StubInitializerClient(
            [user(1, "Ada", "Lovelace")],
            groups={"response": {"groups": ["Reserves", "First Team", "Reserves"]}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            groups_csv = Path(tmp) / "exports" / "available-groups.csv"
            result = initialize_sandbox_athletes(
                client,
                output_csv=Path(tmp) / "athletes.csv",
                output_json=Path(tmp) / "metadata.json",
                list_groups=True,
                groups_csv=groups_csv,
            )
            columns, rows = read_csv(groups_csv)
            metadata = json.loads((Path(tmp) / "metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(columns, ["group"])
        self.assertEqual(rows, [{"group": "First Team"}, {"group": "Reserves"}])
        self.assertEqual(result.groups_csv, groups_csv)
        self.assertEqual(result.group_row_count, 2)
        self.assertEqual(metadata["groups_csv"], str(groups_csv))
        self.assertEqual(metadata["group_row_count"], 2)
        self.assertEqual(client.calls[-1], ("get_group",))

    def test_discovery_failure_warns_and_records_default_endpoints(self):
        client = StubInitializerClient(
            [user(1, "Ada", "Lovelace")],
            discovery_error=RuntimeError("endpoint service unavailable"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertWarnsRegex(RuntimeWarning, "default endpoints"):
                result = initialize_sandbox_athletes(
                    client,
                    output_csv=Path(tmp) / "athletes.csv",
                    output_json=Path(tmp) / "metadata.json",
                )
            metadata = json.loads((Path(tmp) / "metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(result.endpoint_discovery, "defaults")
        self.assertEqual(metadata["endpoint_discovery"], "defaults")

    def test_partial_discovery_is_warned_and_recorded(self):
        client = StubInitializerClient(
            [user(1, "Ada", "Lovelace")],
            discovery_aliases={"eventsearch"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertWarnsRegex(RuntimeWarning, "required alias"):
                result = initialize_sandbox_athletes(
                    client,
                    output_csv=Path(tmp) / "athletes.csv",
                    output_json=Path(tmp) / "metadata.json",
                    group_name="Athletes",
                )
            metadata = json.loads(
                (Path(tmp) / "metadata.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result.endpoint_discovery, "partial")
        self.assertEqual(metadata["endpoint_discovery"], "partial")

    def test_unverified_discovery_provenance_warns_and_records_defaults(self):
        client = StubInitializerClient([user(1, "Ada", "Lovelace")])

        def discover_without_provenance():
            client.calls.append(("discover_endpoints",))
            return object()

        client.discover_endpoints = discover_without_provenance
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertWarnsRegex(RuntimeWarning, "required alias"):
                result = initialize_sandbox_athletes(
                    client,
                    output_csv=Path(tmp) / "athletes.csv",
                    output_json=Path(tmp) / "metadata.json",
                    group_name="Athletes",
                )

        self.assertEqual(result.endpoint_discovery, "defaults")

    def test_extended_columns_are_deterministic_and_nested_values_are_json(self):
        client = StubInitializerClient(
            [
                user(
                    "0002",
                    "Grace",
                    "Hopper",
                    customProfile={"z": 2, "a": [3, 1]},
                    **{"Date of Birth": "09/12/1906"},
                ),
                user("A-1", "Ada", "Lovelace", custom_profile={"a": [1], "z": 1}),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            initialize_sandbox_athletes(
                client,
                output_csv=Path(tmp) / "athletes.csv",
                output_json=Path(tmp) / "metadata.json",
                include_all_cols=True,
            )
            columns, rows = read_csv(Path(tmp) / "athletes.csv")

        self.assertEqual(
            columns[:6],
            ["user_id", "about", "first_name", "last_name", "username", "email"],
        )
        self.assertEqual(columns[6:], ["custom_profile", "date_of_birth"])
        self.assertEqual(rows[0]["user_id"], "0002")
        self.assertEqual(rows[0]["custom_profile"], '{"a":[3,1],"z":2}')
        self.assertEqual(rows[1]["user_id"], "A-1")

    def test_invalid_rosters_never_replace_existing_registry(self):
        invalid_cases = [
            ([], "no athlete rows"),
            ([user(None, "Ada", "Lovelace")], "missing user_id"),
            (
                [user(" 0007 ", "Ada", "Lovelace")],
                "user_id contains surrounding whitespace",
            ),
            ([user(1, "", "Lovelace")], "missing first_name"),
            ([user(1, "Ada", "")], "missing last_name"),
            (
                [user(1, "Ada", "Lovelace"), user("1", "Grace", "Hopper")],
                "duplicate user_id",
            ),
            (
                [user(1, "Ada", "Lovelace"), user(2, "Ada", "Lovelace")],
                "duplicate first_name/last_name",
            ),
        ]
        for payload, message in invalid_cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as tmp:
                output_csv = Path(tmp) / "athletes.csv"
                output_json = Path(tmp) / "metadata.json"
                output_csv.write_text("existing-registry\n", encoding="utf-8")
                output_json.write_text('{"existing": true}\n', encoding="utf-8")
                client = StubInitializerClient(payload)

                with self.assertRaisesRegex(ValueError, message) as caught:
                    initialize_sandbox_athletes(
                        client,
                        output_csv=output_csv,
                        output_json=output_json,
                    )
                if message == "duplicate first_name/last_name":
                    self.assertIn("user_ids '1' and '2'", str(caught.exception))

                self.assertEqual(output_csv.read_text(encoding="utf-8"), "existing-registry\n")
                self.assertEqual(output_json.read_text(encoding="utf-8"), '{"existing": true}\n')

    def test_malformed_nested_roster_never_replaces_existing_registry(self):
        sentinel = "must-not-appear-in-error"
        client = StubInitializerClient(
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
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "athletes.csv"
            output_json = Path(tmp) / "metadata.json"
            output_csv.write_text("existing-registry\n", encoding="utf-8")
            output_json.write_text('{"existing": true}\n', encoding="utf-8")

            with self.assertRaises(ValueError) as caught:
                initialize_sandbox_athletes(
                    client,
                    output_csv=output_csv,
                    output_json=output_json,
                    group_name="Synthetic Athletes",
                )

            self.assertIn("Smartabase roster response", str(caught.exception))
            self.assertNotIn(sentinel, str(caught.exception))
            self.assertEqual(
                output_csv.read_text(encoding="utf-8"),
                "existing-registry\n",
            )
            self.assertEqual(
                output_json.read_text(encoding="utf-8"),
                '{"existing": true}\n',
            )
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_empty_username_roster_recommends_an_authorized_group(self):
        client = StubInitializerClient([])
        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "athletes.csv"
            output_json = Path(tmp) / "metadata.json"
            output_csv.write_text("existing-registry\n", encoding="utf-8")
            output_json.write_text('{"existing": true}\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "--group-name") as caught:
                initialize_sandbox_athletes(
                    client,
                    output_csv=output_csv,
                    output_json=output_json,
                    user_key="username",
                    user_value="private-login",
                )

            message = str(caught.exception)
            self.assertIn(
                '--group-name "Exact Authorized Sandbox Athlete Group"',
                message,
            )
            self.assertIn("SMARTABASE_ATHLETE_GROUP", message)
            self.assertIn("No registry files were changed", message)
            self.assertNotIn("private-login", message)
            self.assertEqual(
                output_csv.read_text(encoding="utf-8"),
                "existing-registry\n",
            )
            self.assertEqual(
                output_json.read_text(encoding="utf-8"),
                '{"existing": true}\n',
            )

    def test_other_empty_selectors_keep_generic_error(self):
        selector_cases = (
            {},
            {"group_name": "Missing Athletes"},
            {"current_group": True},
            {"user_key": "email", "user_value": "missing@example.test"},
        )
        for selector in selector_cases:
            with self.subTest(selector=selector), tempfile.TemporaryDirectory() as tmp:
                client = StubInitializerClient([])
                with self.assertRaises(ValueError) as caught:
                    initialize_sandbox_athletes(
                        client,
                        output_csv=Path(tmp) / "athletes.csv",
                        output_json=Path(tmp) / "metadata.json",
                        **selector,
                    )

                self.assertEqual(
                    str(caught.exception),
                    "Smartabase returned no athlete rows.",
                )
                self.assertNotIn("--group-name", str(caught.exception))

    def test_failure_in_optional_group_fetch_preserves_every_existing_artifact(self):
        client = StubInitializerClient(
            [user(1, "Ada", "Lovelace")],
            group_error=RuntimeError("group export failed"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "athletes.csv"
            output_json = Path(tmp) / "metadata.json"
            groups_csv = Path(tmp) / "groups.csv"
            sentinels = {
                output_csv: "existing-athletes\n",
                output_json: "existing-metadata\n",
                groups_csv: "existing-groups\n",
            }
            for path, content in sentinels.items():
                path.write_text(content, encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "group export failed"):
                initialize_sandbox_athletes(
                    client,
                    output_csv=output_csv,
                    output_json=output_json,
                    list_groups=True,
                    groups_csv=groups_csv,
                )

            for path, content in sentinels.items():
                self.assertEqual(path.read_text(encoding="utf-8"), content)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_login_failure_preserves_existing_artifacts(self):
        client = StubInitializerClient(
            [user(1, "Ada", "Lovelace")],
            login_error=RuntimeError("authentication failed"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "athletes.csv"
            output_json = Path(tmp) / "metadata.json"
            output_csv.write_text("existing-athletes\n", encoding="utf-8")
            output_json.write_text("existing-metadata\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "authentication failed"):
                initialize_sandbox_athletes(
                    client,
                    output_csv=output_csv,
                    output_json=output_json,
                    group_name="Athletes",
                )

            self.assertEqual(
                output_csv.read_text(encoding="utf-8"),
                "existing-athletes\n",
            )
            self.assertEqual(
                output_json.read_text(encoding="utf-8"),
                "existing-metadata\n",
            )
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_staging_interruptions_remove_sensitive_temporary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_target = root / "athletes.csv"
            with patch(
                "ams_smartabase.initializer.csv.DictWriter"
            ) as writer_type:
                writer_type.return_value.writeheader.side_effect = KeyboardInterrupt
                with self.assertRaises(KeyboardInterrupt):
                    _stage_csv(csv_target, ["user_id"], [{"user_id": "1"}])

            json_target = root / "metadata.json"
            with patch(
                "ams_smartabase.initializer.json.dump",
                side_effect=KeyboardInterrupt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    _stage_json(json_target, {"row_count": 1})

            self.assertEqual(list(root.glob("*.tmp")), [])
            self.assertFalse(csv_target.exists())
            self.assertFalse(json_target.exists())

    def test_primary_replace_failure_preserves_registry_and_digest_exposes_mismatch(self):
        client = StubInitializerClient([user(1, "Ada", "Lovelace")])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_csv = root / "athletes.csv"
            output_json = root / "metadata.json"
            existing_registry = b"existing-athletes\n"
            output_csv.write_bytes(existing_registry)
            output_json.write_text('{"existing": true}\n', encoding="utf-8")

            def replace_except_primary(source, target):
                if Path(target) == output_csv:
                    raise OSError("simulated primary replacement failure")
                os.replace(source, target)
                return Path(target)

            with patch.object(
                Path,
                "replace",
                autospec=True,
                side_effect=replace_except_primary,
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "simulated primary replacement failure",
                ):
                    initialize_sandbox_athletes(
                        client,
                        output_csv=output_csv,
                        output_json=output_json,
                        group_name="Athletes",
                    )

            metadata = json.loads(output_json.read_text(encoding="utf-8"))
            existing_digest = hashlib.sha256(existing_registry).hexdigest()
            self.assertEqual(output_csv.read_bytes(), existing_registry)
            self.assertNotEqual(metadata["output_csv_sha256"], existing_digest)
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_sandbox_and_output_path_guards_fail_before_login(self):
        production_client = StubInitializerClient(
            [user(1, "Ada", "Lovelace")],
            url="https://example.smartabase.test/production",
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "athletes.csv"
            with self.assertRaisesRegex(PermissionError, "sandbox"):
                initialize_sandbox_athletes(
                    production_client,
                    output_csv=output,
                    output_json=Path(tmp) / "metadata.json",
                )
            sandbox_client = StubInitializerClient([user(1, "Ada", "Lovelace")])
            with self.assertRaisesRegex(ValueError, "distinct"):
                initialize_sandbox_athletes(
                    sandbox_client,
                    output_csv=output,
                    output_json=output,
                )
            overlapping_client = StubInitializerClient(
                [user(1, "Ada", "Lovelace")]
            )
            with self.assertRaisesRegex(ValueError, "contain one another"):
                initialize_sandbox_athletes(
                    overlapping_client,
                    output_csv=Path(tmp) / "export",
                    output_json=Path(tmp) / "export" / "metadata.json",
                )

        self.assertEqual(production_client.calls, [])
        self.assertEqual(sandbox_client.calls, [])
        self.assertEqual(overlapping_client.calls, [])


class InitializerCliTests(unittest.TestCase):
    def test_parser_has_no_password_argument_and_supports_boolean_options(self):
        parser = build_parser()
        option_strings = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        self.assertNotIn("--password", option_strings)
        args = parser.parse_args(
            [
                "--env-file",
                "custom.env",
                "--group-name",
                "Athletes",
                "--include-all-cols",
                "--list-groups",
                "--include-group",
                "--no-discover-endpoints",
            ]
        )
        self.assertEqual(args.env_file, Path("custom.env"))
        self.assertEqual(args.group_name, "Athletes")
        self.assertTrue(args.include_all_cols)
        self.assertTrue(args.include_group)
        self.assertTrue(args.list_groups)
        self.assertFalse(args.discover_endpoints)

    def test_cli_group_selector_uses_configured_value_precedence(self):
        args = build_parser().parse_args(["--user-key", "group"])

        selector = _resolve_cli_selector(
            args,
            {"SMARTABASE_ATHLETE_GROUP": "Process Athletes"},
            {"SMARTABASE_USER_VALUE": "File Athletes"},
        )

        self.assertEqual(
            selector,
            {
                "group_name": None,
                "current_group": False,
                "user_key": "group",
                "user_value": "File Athletes",
            },
        )

    def test_cli_rejects_orphan_explicit_user_value(self):
        args = build_parser().parse_args(["--user-value", "Explicit Value"])

        with self.assertRaisesRegex(ValueError, "--user-value requires"):
            _resolve_cli_selector(
                args,
                {"SMARTABASE_ATHLETE_GROUP": "Environment Athletes"},
                {},
            )

    def test_cli_preserves_explicit_blank_group_for_fail_closed_validation(self):
        args = build_parser().parse_args(["--group-name", ""])

        selector = _resolve_cli_selector(
            args,
            {"SMARTABASE_ATHLETE_GROUP": "Configured Athletes"},
            {},
        )

        self.assertEqual(selector["group_name"], "")
        client = StubInitializerClient([user(1, "Ada", "Lovelace")])
        with self.assertRaisesRegex(ValueError, "must not be blank"):
            initialize_sandbox_athletes(client, **selector)
        self.assertEqual(client.calls, [])

    def test_main_returns_zero_with_concise_non_secret_output(self):
        result = AthleteInitializationResult(
            output_csv=Path("sandbox_state/athletes.csv"),
            output_json=Path("sandbox_state/athletes_metadata.json"),
            row_count=2,
            columns=("user_id", "about", "first_name", "last_name", "username", "email"),
            selector={"user_key": "group", "user_value": "Athletes"},
            url="https://example.smartabase.test/sandbox",
            created_at="2026-07-29T12:00:00+00:00",
            endpoint_discovery="discovered",
            groups_csv=None,
            group_row_count=None,
        )
        credentials = SmartabaseCredentials(
            "https://example.smartabase.test/sandbox",
            "example-user",
            "super-secret",
        )
        with (
            patch("ams_smartabase.initializer.load_dotenv", return_value={}),
            patch("ams_smartabase.initializer._resolve_cli_credentials", return_value=credentials),
            patch("ams_smartabase.initializer.initialize_sandbox_athletes", return_value=result),
            patch("sys.stdout") as stdout,
        ):
            exit_code = main(["--group-name", "Athletes"])

        self.assertEqual(exit_code, 0)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertIn("2", output)
        self.assertIn(str(Path("sandbox_state") / "athletes.csv"), output)
        self.assertNotIn("super-secret", output)
        self.assertNotIn("example-user", output)

    def test_main_returns_nonzero_and_reports_concise_error(self):
        with (
            patch("ams_smartabase.initializer.load_dotenv", return_value={}),
            patch(
                "ams_smartabase.initializer._resolve_cli_credentials",
                side_effect=ValueError("configuration unavailable"),
            ),
            patch("sys.stderr") as stderr,
        ):
            exit_code = main([])

        self.assertEqual(exit_code, 1)
        output = "".join(call.args[0] for call in stderr.write.call_args_list if call.args)
        self.assertIn("configuration unavailable", output)

    def test_main_recommends_group_for_empty_login_username(self):
        client = StubInitializerClient([])
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {}, clear=True),
            patch("ams_smartabase.initializer.load_dotenv", return_value={}),
            patch(
                "ams_smartabase.initializer._resolve_cli_credentials",
                return_value=client.credentials,
            ),
            patch(
                "ams_smartabase.initializer.SmartabaseClient",
                return_value=client,
            ),
            patch("sys.stderr") as stderr,
        ):
            exit_code = main(
                [
                    "--user-key",
                    "username",
                    "--user-value",
                    "private-login",
                    "--output-csv",
                    str(Path(tmp) / "athletes.csv"),
                    "--output-json",
                    str(Path(tmp) / "metadata.json"),
                ]
            )

        self.assertEqual(exit_code, 1)
        output = "".join(
            call.args[0]
            for call in stderr.write.call_args_list
            if call.args
        )
        self.assertIn("Athlete initialization failed:", output)
        self.assertIn(
            '--group-name "Exact Authorized Sandbox Athlete Group"',
            output,
        )
        self.assertIn("SMARTABASE_ATHLETE_GROUP", output)
        self.assertNotIn("private-login", output)
        self.assertNotIn("super-secret", output)

    def test_main_redacts_password_from_runtime_errors(self):
        credentials = SmartabaseCredentials(
            "https://example.smartabase.test/sandbox",
            "example-user",
            "super-secret",
        )
        with (
            patch("ams_smartabase.initializer.load_dotenv", return_value={}),
            patch(
                "ams_smartabase.initializer._resolve_cli_credentials",
                return_value=credentials,
            ),
            patch(
                "ams_smartabase.initializer.initialize_sandbox_athletes",
                side_effect=RuntimeError("transport exposed super-secret"),
            ),
            patch("sys.stderr") as stderr,
        ):
            exit_code = main(["--group-name", "Athletes"])

        self.assertEqual(exit_code, 1)
        output = "".join(
            call.args[0]
            for call in stderr.write.call_args_list
            if call.args
        )
        self.assertIn("transport exposed ***", output)
        self.assertNotIn("super-secret", output)

    def test_public_package_exports_and_console_script_are_declared(self):
        self.assertIs(
            ams_smartabase.initialize_sandbox_athletes,
            initialize_sandbox_athletes,
        )
        self.assertIs(
            ams_smartabase.AthleteInitializationResult,
            AthleteInitializationResult,
        )
        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'ams-initialize-sandbox-athletes = "ams_smartabase.initializer:main"',
            pyproject,
        )


class _null_context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


if __name__ == "__main__":
    unittest.main()
