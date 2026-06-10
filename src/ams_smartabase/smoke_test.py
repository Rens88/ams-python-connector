"""Read-only Smartabase smoke test helpers."""

from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
import sys
from typing import Any, Callable, Mapping, Sequence

from .client import SmartabaseClient
from .config import SmartabaseCredentials, load_dotenv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a read-only Smartabase smoke test against a live AMS site.",
    )
    parser.add_argument("--url", help="Smartabase base URL. Falls back to SMARTABASE_URL or SB_URL.")
    parser.add_argument("--username", help="Smartabase username. Falls back to SMARTABASE_USERNAME or SB_USER.")
    parser.add_argument(
        "--password",
        help="Smartabase password. If omitted, falls back to SMARTABASE_PASSWORD or SB_PASS, then prompts.",
    )
    parser.add_argument(
        "--discover-endpoints",
        action="store_true",
        help="Call the endpoint-discovery API after login.",
    )
    parser.add_argument(
        "--list-groups",
        action="store_true",
        help="List groups accessible to the supplied account after login.",
    )
    parser.add_argument(
        "--group-name",
        help="If supplied, fetch members of this Smartabase group after login.",
    )
    return parser


def resolve_credentials(
    args: argparse.Namespace,
    *,
    env: Mapping[str, str] | None = None,
    password_prompt: Callable[[str], str] = getpass,
) -> SmartabaseCredentials:
    source = dict(load_dotenv())
    source.update(dict(os.environ if env is None else env))
    url = args.url or source.get("SMARTABASE_URL") or source.get("SB_URL") or ""
    username = args.username or source.get("SMARTABASE_USERNAME") or source.get("SB_USER") or ""
    password = args.password or source.get("SMARTABASE_PASSWORD") or source.get("SB_PASS") or ""
    if not password:
        password = password_prompt("Smartabase password: ")
    return SmartabaseCredentials(url=url, username=username, password=password)


def run_smoke_test(
    credentials: SmartabaseCredentials,
    *,
    discover_endpoints: bool = False,
    list_groups: bool = False,
    group_name: str | None = None,
    client: SmartabaseClient | None = None,
) -> dict[str, Any]:
    active_client = client or SmartabaseClient(credentials)
    results: dict[str, Any] = {
        "login": active_client.login(),
    }

    if discover_endpoints:
        endpoint_map = active_client.discover_endpoints()
        results["endpoints"] = dict(endpoint_map.aliases)

    if list_groups:
        results["groups"] = active_client.get_group()

    if group_name:
        results["group_users"] = active_client.get_user(user_key="group", user_value=group_name)

    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        credentials = resolve_credentials(args, env=os.environ)
        results = run_smoke_test(
            credentials,
            discover_endpoints=args.discover_endpoints,
            list_groups=args.list_groups,
            group_name=args.group_name,
        )
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1

    print("Smoke test succeeded.")
    print(json.dumps(_json_safe(results), indent=2, sort_keys=True))
    return 0


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value
