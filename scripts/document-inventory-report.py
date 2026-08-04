#!/usr/bin/env python3
"""Summarise site documents discovered across a qualitative capture index."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "index",
        nargs="?",
        type=Path,
        default=Path("output/qualitative-capture.json"),
        help="Path to qualitative-capture.json",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable summary JSON",
    )
    return p


def summarise(payload: dict) -> dict:
    records = payload.get("records") or []
    status_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    label_terms: Counter[str] = Counter()
    schools_with_docs = 0
    schools_with_extracted = 0
    total_docs = 0
    total_extracted = 0

    for record in records:
        inventory = record.get("documentInventory") or []
        if inventory:
            schools_with_docs += 1
        extracted = sum(1 for row in inventory if row.get("status") == "extracted")
        if extracted:
            schools_with_extracted += 1
        total_docs += len(inventory)
        total_extracted += extracted
        for row in inventory:
            status_counts[row.get("status") or "unknown"] += 1
            fmt = (row.get("format") or "unknown").lower()
            format_counts[fmt] += 1
            label = (row.get("label") or "").lower()
            for term in (
                "club",
                "curriculum",
                "prospectus",
                "send",
                "wraparound",
                "breakfast",
                "menu",
                "handbook",
                "enrichment",
            ):
                if term in label:
                    label_terms[term] += 1

    return {
        "schoolCount": len(records),
        "schoolsWithDocuments": schools_with_docs,
        "schoolsWithExtractedPdfs": schools_with_extracted,
        "documentsDiscovered": total_docs,
        "documentsExtracted": total_extracted,
        "statusCounts": dict(status_counts),
        "formatCounts": dict(format_counts),
        "labelTermHits": dict(label_terms.most_common(12)),
        "engineVersion": payload.get("engineVersion"),
        "generatedAt": payload.get("generatedAt"),
    }


def main() -> int:
    args = build_parser().parse_args()
    payload = json.loads(args.index.read_text(encoding="utf-8"))
    summary = summarise(payload)
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print(f"Index: {args.index}")
    print(f"Generated: {summary.get('generatedAt')} · engine {summary.get('engineVersion')}")
    print(f"Schools: {summary['schoolCount']}")
    print(
        f"With site documents: {summary['schoolsWithDocuments']} "
        f"({summary['documentsDiscovered']} files)"
    )
    print(
        f"With extracted PDFs: {summary['schoolsWithExtractedPdfs']} "
        f"({summary['documentsExtracted']} files)"
    )
    if summary["statusCounts"]:
        print("\nStatus breakdown:")
        for status, count in sorted(summary["statusCounts"].items()):
            print(f"  {status}: {count}")
    if summary["formatCounts"]:
        print("\nFormats:")
        for fmt, count in sorted(summary["formatCounts"].items()):
            print(f"  .{fmt}: {count}")
    if summary["labelTermHits"]:
        print("\nCommon document themes (label matches):")
        for term, count in summary["labelTermHits"].items():
            print(f"  {term}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
