"""Merge contact sidecars into Comparison-tool schools-index.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def merge_into_schools_index(
    schools_index_path: Path,
    capture_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    schools_payload = json.loads(schools_index_path.read_text(encoding="utf-8"))
    capture_payload = json.loads(capture_path.read_text(encoding="utf-8"))
    by_urn = {str(r["urn"]): r for r in capture_payload.get("records") or []}

    merged = 0
    for school in schools_payload.get("schools") or []:
        urn = str(school.get("urn") or "").strip()
        record = by_urn.get(urn)
        if not record:
            continue
        school["contactCapture"] = record
        school["contactCaptureEnrichedAt"] = record.get("assessedAt")
        merged += 1

        office_phone = next(
            (
                c.get("phone")
                for c in record.get("contacts") or []
                if c.get("role") == "office" and c.get("phone")
            ),
            None,
        )
        if office_phone and not school.get("telephone"):
            school["telephone"] = office_phone

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
        description="Merge contact-capture.json into a Comparison-tool schools-index."
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument(
        "--capture",
        type=Path,
        default=Path("output/contact-capture.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    stats = merge_into_schools_index(args.index, args.capture, dry_run=args.dry_run)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
