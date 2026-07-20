"""Replay one example event form for one athlete in sandbox."""

from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase import SmartabaseClient, load_credentials, run_example_event_replay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Count, delete, recount, upload, and recount one example event form in sandbox.",
    )
    parser.add_argument(
        "--csv-path",
        default="use_case_examples/synthetic_data/csv/training load template 1777445863459.csv",
        help="Example CSV file to replay.",
    )
    parser.add_argument(
        "--base-dir",
        default="smartabase_runs",
        help="Base directory for workflow artifacts.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run live delete and upload calls. Omit for dry run.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required together with --execute to allow mutation requests.",
    )
    parser.add_argument(
        "--discover-endpoints",
        action="store_true",
        help="Refresh endpoint aliases before running the workflow.",
    )
    parser.add_argument(
        "--delete-all-in-range",
        action="store_true",
        help="Sandbox-only override: delete all existing events for the form/user/date range before upload.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    credentials = load_credentials()
    if args.execute and "sandbox" not in credentials.url.lower():
        print("Refusing to execute delete/modify operations because SMARTABASE_URL does not contain 'sandbox'.", file=sys.stderr)
        return 2
    if args.delete_all_in_range and "sandbox" not in credentials.url.lower():
        print("--delete-all-in-range is restricted to sandbox URLs.", file=sys.stderr)
        return 2
    if args.execute and not args.confirm:
        print("--confirm is required together with --execute.", file=sys.stderr)
        return 2

    client = SmartabaseClient(credentials)
    client.login()
    if args.discover_endpoints:
        client.discover_endpoints()

    result = run_example_event_replay(
        client,
        csv_path=args.csv_path,
        base_dir=args.base_dir,
        dry_run=not args.execute,
        confirm=args.confirm,
        delete_all_in_range=args.delete_all_in_range,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
