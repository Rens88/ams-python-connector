"""Run a live, read-only Smartabase smoke test from the repository checkout."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.smoke_test import main


if __name__ == "__main__":
    raise SystemExit(main())
