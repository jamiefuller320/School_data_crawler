#!/usr/bin/env python3
"""CLI for the experimental qualitative data capture engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from school_capture.engine import CaptureEngine  # noqa: E402
from school_capture.index_loader import (  # noqa: E402
    SEED_LOCAL_AUTHORITY,
    filter_schools,
    load_schools_index,
    resolve_comparison_tool_index,
)
from school_capture.models import QualitativeCaptureIndex, SchoolInput, today_iso  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Experimental qualitative capture for schoolcompass.uk — "
            "curriculum, enrichment, ethos and related areas from "
            "school websites, local news, and social media."
        )
    )
    p.add_argument(
        "--comparison-tool",
        type=Path,
        help="Path to Comparison-tool repo root (for schools-index.json)",
    )
    p.add_argument(
        "--index",
        type=Path,
        help="Direct path to schools-index.json (overrides --comparison-tool)",
    )
    p.add_argument("--la", default=SEED_LOCAL_AUTHORITY, help="Filter to local authority")
    p.add_argument("--urn", help="Capture a single school by URN")
    p.add_argument("--limit", type=int, default=5, help="Max schools to process")
    p.add_argument(
        "--require-website",
        action="store_true",
        help="Skip schools without a schoolWebsite URL",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("output/qualitative-capture.json"),
        help="Output sidecar index path",
    )
    p.add_argument(
        "--fixture",
        type=Path,
        help="Run against a JSON fixture of SchoolInput records (offline dev)",
    )
    p.add_argument(
        "--no-news",
        action="store_true",
        help="Disable local news adapter (faster, website-only)",
    )
    p.add_argument(
        "--no-social",
        action="store_true",
        help="Disable social media adapter",
    )
    return p


def load_schools(args: argparse.Namespace) -> list[SchoolInput]:
    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("schools") or []
        return [SchoolInput.from_dict(r) for r in rows][: args.limit]

    if args.index:
        index_path = args.index
    elif args.comparison_tool:
        index_path = resolve_comparison_tool_index(args.comparison_tool)
    else:
        raise SystemExit("Provide --comparison-tool, --index, or --fixture")

    schools = load_schools_index(index_path)
    filtered = filter_schools(
        schools,
        la=args.la if not args.urn else None,
        urn=args.urn,
        require_website=args.require_website,
    )
    return filtered[: args.limit]


def build_engine(args: argparse.Namespace) -> CaptureEngine:
    from school_capture.sources import (
        LocalNewsAdapter,
        SchoolWebsiteAdapter,
        SocialMediaAdapter,
    )

    adapters = [SchoolWebsiteAdapter()]
    if not args.no_news:
        adapters.append(LocalNewsAdapter())
    if not args.no_social:
        adapters.append(SocialMediaAdapter())
    return CaptureEngine(adapters=adapters)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    schools = load_schools(args)
    if not schools:
        print("No schools matched filters.", file=sys.stderr)
        return 1

    engine = build_engine(args)
    records = []
    for school in schools:
        print(f"Capturing {school.urn} {school.name}...", file=sys.stderr)
        records.append(engine.capture_school(school))

    index = QualitativeCaptureIndex(
        generatedAt=today_iso(),
        schoolCount=len(records),
        records=records,
        stats={
            "la": args.la,
            "withWebsite": sum(1 for s in schools if s.schoolWebsite),
            "adapters": [a.source_type for a in engine.adapters],
        },
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(index.to_dict(), indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} record(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
