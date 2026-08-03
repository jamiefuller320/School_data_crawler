"""Merge qualitative sidecars into Comparison-tool schools-index.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_capture_index(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_into_schools_index(
    schools_index_path: Path,
    capture_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    schools_payload = json.loads(schools_index_path.read_text(encoding="utf-8"))
    capture_payload = load_capture_index(capture_path)
    by_urn = {str(r["urn"]): r for r in capture_payload.get("records") or []}

    merged = 0
    for school in schools_payload.get("schools") or []:
        urn = str(school.get("urn") or "").strip()
        record = by_urn.get(urn)
        if not record:
            continue
        school["qualitativeCapture"] = record
        school["qualitativeCaptureEnrichedAt"] = record.get("assessedAt")
        merged += 1

    if not dry_run:
        schools_index_path.write_text(
            json.dumps(schools_payload, separators=(",", ":")),
            encoding="utf-8",
        )

    return {
        "schools": len(schools_payload.get("schools") or []),
        "captureRecords": len(by_urn),
        "merged": merged,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge qualitative-capture.json into a Comparison-tool schools-index."
    )
    parser.add_argument(
        "--index",
        type=Path,
        required=True,
        help="Path to schools-index.json",
    )
    parser.add_argument(
        "--capture",
        type=Path,
        default=Path("output/qualitative-capture.json"),
        help="Path to qualitative capture sidecar index",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    stats = merge_into_schools_index(args.index, args.capture, dry_run=args.dry_run)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
