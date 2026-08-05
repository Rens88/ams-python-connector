"""Sandbox-safe athlete registry initialization.

The initializer performs read-only AMS/Smartabase calls, validates the returned
roster, and replaces local registry artifacts only after every requested
artifact has been staged successfully.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence
import warnings

from .client import SmartabaseClient
from .config import (
    ConfigurationError,
    SmartabaseCredentials,
    load_credentials,
    load_dotenv,
    redact_secrets,
)
from .filters import USER_KEYS
from .roster import (
    fetch_roster,
    normalize_group_response,
    roster_to_rows,
)


DEFAULT_OUTPUT_CSV = Path("sandbox_state/athletes.csv")
DEFAULT_OUTPUT_JSON = Path("sandbox_state/athletes_metadata.json")
_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AthleteInitializationResult:
    """Summary of a completed local athlete-registry refresh."""

    output_csv: Path
    output_json: Path
    row_count: int
    columns: tuple[str, ...]
    selector: Mapping[str, object]
    url: str
    created_at: str
    endpoint_discovery: str
    groups_csv: Path | None = None
    group_row_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selector",
            MappingProxyType(dict(self.selector)),
        )


def initialize_sandbox_athletes(
    client: SmartabaseClient,
    *,
    output_csv: str | Path = DEFAULT_OUTPUT_CSV,
    output_json: str | Path = DEFAULT_OUTPUT_JSON,
    group_name: str | None = None,
    current_group: bool = False,
    user_key: str | None = None,
    user_value: object | None = None,
    include_all_cols: bool = False,
    list_groups: bool = False,
    groups_csv: str | Path | None = None,
    discover_endpoints: bool = True,
) -> AthleteInitializationResult:
    """Fetch a sandbox roster, stage every artifact, and replace validated files.

    The remote operation is read-only. Locally, the function writes or replaces
    the requested CSV and JSON files. The files may contain personal data and
    should remain in an ignored, access-controlled directory.
    """

    athlete_path = Path(output_csv)
    metadata_path = Path(output_json)
    group_path = (
        Path(groups_csv)
        if groups_csv is not None
        else athlete_path.parent / "groups.csv"
    )
    active_targets = [athlete_path, metadata_path]
    if list_groups:
        active_targets.append(group_path)
    _validate_output_targets(active_targets)

    resolved_key, resolved_value = _resolve_selector(
        group_name=group_name,
        current_group=current_group,
        user_key=user_key,
        user_value=user_value,
    )
    _require_sandbox_url(client.credentials.url)

    client.login()
    endpoint_status = "defaults"
    if discover_endpoints:
        try:
            discovered_endpoints = client.discover_endpoints()
        except Exception:
            warnings.warn(
                "Smartabase endpoint discovery failed; using the connector's "
                "known default endpoints.",
                RuntimeWarning,
                stacklevel=2,
            )
        else:
            endpoint_status = _endpoint_discovery_status(
                discovered_endpoints,
                required_aliases=_required_endpoint_aliases(
                    resolved_key,
                    list_groups=list_groups,
                ),
            )
            if endpoint_status != "discovered":
                warnings.warn(
                    "Smartabase endpoint discovery did not return every "
                    "required alias; using known default endpoints for the "
                    "missing aliases.",
                    RuntimeWarning,
                    stacklevel=2,
                )

    if resolved_key is None:
        warnings.warn(
            "No athlete selector was supplied; all users accessible to this "
            "Smartabase account will be exported.",
            UserWarning,
            stacklevel=2,
        )
    if include_all_cols:
        warnings.warn(
            "Extended user columns can contain sensitive profile information "
            "and have tenant-specific response shapes.",
            UserWarning,
            stacklevel=2,
        )

    roster = fetch_roster(
        client,
        group_name=str(resolved_value) if resolved_key == "group" else None,
        current_group=resolved_key == "current_group",
        user_key=resolved_key if resolved_key not in {"group", "current_group"} else None,
        user_value=resolved_value if resolved_key not in {"group", "current_group"} else None,
    )
    columns, athlete_rows = roster_to_rows(
        roster,
        include_all_cols=include_all_cols,
    )
    if not athlete_rows and resolved_key == "username":
        raise ValueError(
            "Smartabase returned no athlete rows for the username selector. "
            "The login account may not represent an athlete record. Recommended "
            "follow-up: rerun with --group-name \"Exact Authorized Sandbox "
            "Athlete Group\", or set SMARTABASE_ATHLETE_GROUP in .env. No registry "
            "files were changed."
        )
    athlete_rows = _validate_and_sort_athlete_rows(athlete_rows)

    group_rows: list[dict[str, str]] | None = None
    if list_groups:
        group_rows = normalize_group_response(client.get_group())

    created_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    selector_data = {
        "user_key": resolved_key,
        "user_value": _json_safe(resolved_value),
    }
    metadata: dict[str, object] = {
        "source": "ams-python-connector",
        "operation": "initialize_sandbox_athletes",
        "url": client.credentials.url,
        "created_at": created_at,
        "output_csv": str(athlete_path),
        "row_count": len(athlete_rows),
        "columns": columns,
        "selector": selector_data,
        "include_all_cols": bool(include_all_cols),
        "endpoint_discovery": endpoint_status,
    }
    if group_rows is not None:
        metadata["groups_csv"] = str(group_path)
        metadata["group_row_count"] = len(group_rows)

    staged: dict[Path, Path] = {}
    try:
        staged[athlete_path] = _stage_csv(athlete_path, columns, athlete_rows)
        metadata["output_csv_sha256"] = _sha256_file(staged[athlete_path])
        if group_rows is not None:
            staged[group_path] = _stage_csv(group_path, ["group"], group_rows)
            metadata["groups_csv_sha256"] = _sha256_file(staged[group_path])
        metadata = redact_secrets(metadata)
        staged[metadata_path] = _stage_json(metadata_path, metadata)

        # Replace the primary registry last. Multi-file replacement cannot be
        # perfectly transactional, but a failed optional/metadata replacement
        # cannot replace a previously valid athlete registry.
        replacement_order = []
        if group_rows is not None:
            replacement_order.append(group_path)
        replacement_order.extend((metadata_path, athlete_path))
        for target in replacement_order:
            staged[target].replace(target)
            staged.pop(target, None)
    finally:
        for temporary_path in staged.values():
            temporary_path.unlink(missing_ok=True)

    return AthleteInitializationResult(
        output_csv=athlete_path,
        output_json=metadata_path,
        row_count=len(athlete_rows),
        columns=tuple(columns),
        selector=MappingProxyType(dict(selector_data)),
        url=client.credentials.url,
        created_at=created_at,
        endpoint_discovery=endpoint_status,
        groups_csv=group_path if group_rows is not None else None,
        group_row_count=len(group_rows) if group_rows is not None else None,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the packaged sandbox-initializer command parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Fetch users from a Smartabase sandbox and write a validated local "
            "athlete registry. Remote calls are read-only; local files may be replaced."
        ),
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--group-name")
    parser.add_argument("--current-group", action="store_true")
    parser.add_argument("--user-key", choices=sorted(USER_KEYS))
    parser.add_argument("--user-value")
    parser.add_argument(
        "--include-all-cols",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Include deterministic passthrough columns from the raw user response. "
            "These can contain additional personal data."
        ),
    )
    parser.add_argument("--list-groups", action="store_true")
    parser.add_argument(
        "--groups-csv",
        type=Path,
        help="Groups output path. Defaults to groups.csv beside --output-csv.",
    )
    parser.add_argument(
        "--discover-endpoints",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--url", help="Non-secret Smartabase URL override.")
    parser.add_argument("--username", help="Non-secret Smartabase username override.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the packaged command-line initializer."""

    parser = build_parser()
    args = parser.parse_args(argv)
    file_values: Mapping[str, str] = {}
    process_values = dict(os.environ)
    credentials: SmartabaseCredentials | None = None
    try:
        file_values = load_dotenv(args.env_file)
        credentials = _resolve_cli_credentials(
            args,
            env=process_values,
            password_prompt=getpass,
        )
        selector_options = _resolve_cli_selector(args, process_values, file_values)
        include_all_cols = (
            args.include_all_cols
            if args.include_all_cols is not None
            else _configured_bool(
                process_values,
                file_values,
                "SMARTABASE_INCLUDE_ALL_COLS",
                "SB_INCLUDE_ALL_COLS",
            )
        )
        result = initialize_sandbox_athletes(
            SmartabaseClient(credentials),
            output_csv=args.output_csv,
            output_json=args.output_json,
            include_all_cols=include_all_cols,
            list_groups=args.list_groups,
            groups_csv=args.groups_csv,
            discover_endpoints=args.discover_endpoints,
            **selector_options,
        )
    except Exception as exc:
        secret_values = [
            process_values.get("SMARTABASE_PASSWORD", ""),
            process_values.get("SB_PASS", ""),
            file_values.get("SMARTABASE_PASSWORD", ""),
            file_values.get("SB_PASS", ""),
            credentials.password if credentials is not None else "",
        ]
        message = _redact_error_message(exc, secret_values)
        print(f"Athlete initialization failed: {message}", file=sys.stderr)
        return 1

    print(f"Wrote {result.row_count} athletes to {result.output_csv}")
    print(f"Wrote non-secret metadata to {result.output_json}")
    if result.groups_csv is not None:
        print(f"Wrote {result.group_row_count} groups to {result.groups_csv}")
    selector_key = result.selector.get("user_key")
    if selector_key is None:
        print("Selector: all accessible users")
    elif selector_key in {"group", "current_group"}:
        selector_value = result.selector.get("user_value")
        suffix = f" ({selector_value})" if selector_value not in (None, "") else ""
        print(f"Selector: {selector_key}{suffix}")
    else:
        print(f"Selector: {selector_key} (value omitted from output)")
    print(f"Endpoint discovery: {result.endpoint_discovery}")
    return 0


def _resolve_cli_credentials(
    args: argparse.Namespace,
    *,
    env: Mapping[str, str] | None = None,
    password_prompt: Callable[[str], str] = getpass,
) -> SmartabaseCredentials:
    source = dict(os.environ if env is None else env)
    if args.url:
        source["SMARTABASE_URL"] = args.url
    if args.username:
        source["SMARTABASE_USERNAME"] = args.username
    try:
        return load_credentials(source, args.env_file)
    except ConfigurationError as exc:
        if "password is required" not in str(exc).lower():
            raise
    password = password_prompt("Smartabase password: ")
    if not password:
        raise ConfigurationError("Smartabase password is required.")
    source["SMARTABASE_PASSWORD"] = password
    return load_credentials(source, args.env_file)


def _resolve_cli_selector(
    args: argparse.Namespace,
    process_values: Mapping[str, str],
    file_values: Mapping[str, str],
) -> dict[str, object]:
    explicit_selector = (
        args.group_name is not None
        or args.current_group
        or args.user_key is not None
    )
    if explicit_selector:
        configured_value = args.user_value
        if args.user_key and configured_value in (None, ""):
            configured_value = _configured_value(
                process_values,
                file_values,
                "SMARTABASE_USER_VALUE",
                "SB_USER_VALUE",
            )
        if args.user_key == "group" and configured_value in (None, ""):
            configured_value = _configured_value(
                process_values,
                file_values,
                "SMARTABASE_ATHLETE_GROUP",
            )
        return {
            "group_name": args.group_name,
            "current_group": args.current_group,
            "user_key": args.user_key,
            "user_value": configured_value,
        }

    configured_key = _configured_value(
        process_values,
        file_values,
        "SMARTABASE_USER_KEY",
        "SB_USER_KEY",
    )
    configured_value = args.user_value or _configured_value(
        process_values,
        file_values,
        "SMARTABASE_USER_VALUE",
        "SB_USER_VALUE",
    )
    athlete_group = _configured_value(
        process_values,
        file_values,
        "SMARTABASE_ATHLETE_GROUP",
    )
    if args.user_value is not None and not configured_key:
        raise ValueError(
            "--user-value requires --user-key or SMARTABASE_USER_KEY."
        )
    if configured_key:
        if configured_key == "group" and not configured_value:
            configured_value = athlete_group
        return {
            "group_name": None,
            "current_group": False,
            "user_key": configured_key,
            "user_value": configured_value,
        }
    if athlete_group:
        return {
            "group_name": athlete_group,
            "current_group": False,
            "user_key": None,
            "user_value": None,
        }
    return {
        "group_name": None,
        "current_group": False,
        "user_key": None,
        "user_value": args.user_value,
    }


def _resolve_selector(
    *,
    group_name: str | None,
    current_group: bool,
    user_key: str | None,
    user_value: object | None,
) -> tuple[str | None, object | None]:
    if group_name is not None:
        group_name = group_name.strip()
        if not group_name:
            raise ValueError("group_name must not be blank.")
    user_key = user_key.strip() if user_key else None
    selected = sum((group_name is not None, bool(current_group), user_key is not None))
    if selected > 1:
        raise ValueError(
            "Choose only one roster selector: group_name, current_group, "
            "or user_key/user_value."
        )
    if user_key is not None and user_key not in USER_KEYS:
        raise ValueError(f"Unsupported user_key: {user_key!r}.")
    if group_name is not None:
        return "group", group_name
    if current_group or user_key == "current_group":
        return "current_group", None
    if user_key is None:
        if not _selector_value_is_missing(user_value):
            raise ValueError("user_key is required when user_value is supplied.")
        return None, None
    if _selector_value_is_missing(user_value):
        raise ValueError(f"user_value is required when user_key={user_key!r}.")
    if user_key == "group":
        return "group", str(user_value).strip()
    return user_key, user_value


def _require_sandbox_url(url: str) -> None:
    if "sandbox" not in url.lower():
        raise PermissionError(
            "The athlete initializer is restricted to Smartabase sandbox URLs."
        )


def _validate_output_targets(paths: Sequence[Path]) -> None:
    resolved = [path.expanduser().resolve(strict=False) for path in paths]
    if len(resolved) != len(set(resolved)):
        raise ValueError("Initializer output paths must be distinct.")
    for index, first in enumerate(resolved):
        for second in resolved[index + 1 :]:
            if first in second.parents or second in first.parents:
                raise ValueError(
                    "Initializer output paths must not contain one another."
                )
    for path in paths:
        if path.exists() and not path.is_file():
            raise ValueError(f"Initializer output path is not a file: {path}")


def _validate_and_sort_athlete_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, str]]:
    if not rows:
        raise ValueError("Smartabase returned no athlete rows.")

    normalized: list[dict[str, str]] = []
    errors: list[str] = []
    seen_user_ids: dict[str, int] = {}
    seen_names: dict[tuple[str, str], tuple[int, str]] = {}
    for index, source_row in enumerate(rows, start=2):
        row = {
            str(key): "" if value is None else str(value)
            for key, value in source_row.items()
        }
        for field in ("first_name", "last_name"):
            row[field] = row.get(field, "").strip()
            if not row[field]:
                errors.append(f"athlete row {index}: missing {field}")
        user_id = row.get("user_id", "")
        stripped_user_id = user_id.strip()
        if not stripped_user_id:
            errors.append(f"athlete row {index}: missing user_id")
        elif stripped_user_id != user_id:
            errors.append(
                f"athlete row {index}: user_id contains surrounding whitespace"
            )
        if user_id:
            if user_id in seen_user_ids:
                errors.append(
                    f"athlete row {index}: duplicate user_id {user_id!r} "
                    f"(first seen on row {seen_user_ids[user_id]})"
                )
            else:
                seen_user_ids[user_id] = index
        name = (row.get("first_name", ""), row.get("last_name", ""))
        if all(name):
            if name in seen_names:
                first_row, first_user_id = seen_names[name]
                errors.append(
                    "athlete row "
                    f"{index}: duplicate first_name/last_name combination "
                    f"(first seen on row {first_row}; user_ids "
                    f"{first_user_id!r} and {user_id!r})"
                )
            else:
                seen_names[name] = (index, user_id)
        normalized.append(row)

    if errors:
        raise ValueError(
            "Athlete roster validation failed:\n" + "\n".join(errors[:20])
        )
    return sorted(normalized, key=lambda row: _user_id_sort_key(row["user_id"]))


def _user_id_sort_key(value: str) -> tuple[object, ...]:
    if re.fullmatch(r"[+-]?\d+", value):
        return (0, int(value), value)
    return (1, value.casefold(), value)


def _stage_csv(
    target: Path,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        delete=False,
    )
    temporary_path = Path(handle.name)
    try:
        with handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(columns),
                extrasaction="raise",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def _stage_json(target: Path, payload: Mapping[str, object]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        delete=False,
    )
    temporary_path = Path(handle.name)
    try:
        with handle:
            json.dump(
                redact_secrets(dict(payload)),
                handle,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
                sort_keys=True,
            )
            handle.write("\n")
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def _configured_value(
    process_values: Mapping[str, str],
    file_values: Mapping[str, str],
    preferred_name: str,
    legacy_name: str | None = None,
) -> str:
    preferred_process = process_values.get(preferred_name, "").strip()
    if preferred_process:
        return preferred_process
    preferred_file = file_values.get(preferred_name, "").strip()
    if preferred_file:
        return preferred_file
    if legacy_name is None:
        return ""
    return (
        process_values.get(legacy_name, "").strip()
        or file_values.get(legacy_name, "").strip()
    )


def _configured_bool(
    process_values: Mapping[str, str],
    file_values: Mapping[str, str],
    preferred_name: str,
    legacy_name: str | None = None,
) -> bool:
    return (
        _configured_value(
            process_values,
            file_values,
            preferred_name,
            legacy_name,
        ).casefold()
        in _TRUE_VALUES
    )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, set):
        return [
            _json_safe(item)
            for item in sorted(
                value,
                key=lambda item: (type(item).__name__, str(item)),
            )
        ]
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _selector_value_is_missing(value: object | None) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return not value
    return False


def _required_endpoint_aliases(
    resolved_key: str | None,
    *,
    list_groups: bool,
) -> set[str]:
    selector_endpoint = {
        "group": "groupmembers",
        "current_group": "currentgroup",
    }.get(resolved_key, "usersearch")
    required = {selector_endpoint}
    if list_groups:
        required.add("listgroups")
    return required


def _endpoint_discovery_status(
    endpoint_map: object,
    *,
    required_aliases: set[str],
) -> str:
    discovered = getattr(endpoint_map, "discovered_aliases", None)
    if discovered is None:
        # An injected client without provenance cannot prove discovery.
        return "defaults"
    discovered_set = set(discovered)
    if required_aliases.issubset(discovered_set):
        return "discovered"
    if discovered_set:
        return "partial"
    return "defaults"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redact_error_message(
    error: BaseException,
    secret_values: Sequence[str],
) -> str:
    message = str(error)
    for secret in secret_values:
        if secret:
            message = message.replace(secret, "***")
    return message


if __name__ == "__main__":
    raise SystemExit(main())
