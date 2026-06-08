"""Local manifest and operation artifact helpers."""

from __future__ import annotations

import csv
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Iterable, Mapping

from .config import redact_secrets


def create_operation_folder(
    operation: str,
    *,
    base_dir: str | Path = "smartabase_runs",
    timestamp: datetime | None = None,
) -> Path:
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    path = Path(base_dir) / f"{stamp}_{safe_slug(operation)}"
    for child in ("raw_json", "payloads", "attachments"):
        (path / child).mkdir(parents=True, exist_ok=True)
    return path


def write_operation_config(path: str | Path, config: Mapping[str, object]) -> Path:
    output = Path(path) / "operation_config.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(redact_secrets(dict(config)), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def write_manifest_csv(path: str | Path, rows: Iterable[Mapping[str, object]]) -> Path:
    output = Path(path) / "operation_manifest.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    materialized = [dict(row) for row in rows]
    fieldnames = _fieldnames(materialized)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)
    return output


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug.lower() or "operation"


def _fieldnames(rows: list[dict[str, object]]) -> list[str]:
    preferred = ["operation", "endpoint", "form", "output_path", "row_count", "status", "error"]
    seen = set()
    fields = []
    for key in preferred:
        if any(key in row for row in rows):
            fields.append(key)
            seen.add(key)
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    return fields or preferred
