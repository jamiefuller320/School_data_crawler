#!/usr/bin/env python3
"""CLI for school contact capture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from school_capture.contact_engine import ContactCaptureEngine  # noqa: E402
from school_capture.contact_models import ContactCaptureIndex  # noqa: E402
from school_capture.index_loader import (  # noqa: E402
    SEED_LOCAL_AUTHORITY,
    filter_schools,
    load_schools_index,
    resolve_comparison_tool_index,
)
from school_capture.models import SchoolInput, today_iso  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Capture school contact information — headteacher, SENCO, "
            "address, email and telephone — from GIAS and school websites."
        )
    )
    p.add_argument("--comparison-tool", type=Path, help="Comparison-tool repo root")
    p.add_argument("--index", type=Path, help="Path to schools-index.json")
    p.add_argument("--la", default=SEED_LOCAL_AUTHORITY, help="Filter to local authority")
    p.add_argument("--urn", help="Capture a single school by URN")
    p.add_argument("--limit", type=int, default=5, help="Max schools to process")
    p.add_argument("--require-website", action="store_true")
    p.add_argument(
        "--output",
        type=Path,
        default=Path("output/contact-capture.json"),
        help="Output sidecar index path",
    )
    p.add_argument("--fixture", type=Path, help="JSON fixture of school records")
    p.add_argument(
        "--no-website",
        action="store_true",
        help="Skip website scrape (GIAS + index baseline only)",
    )
    p.add_argument(
        "--no-gias",
        action="store_true",
        help="Skip GIAS Edubase download/lookup",
    )
    p.add_argument(
        "--gias-cache",
        type=Path,
        help="Path to cached Edubase CSV (default: .cache/edubase/edubasealldata.csv)",
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    schools = load_schools(args)
    if not schools:
        print("No schools matched filters.", file=sys.stderr)
        return 1

    engine = ContactCaptureEngine(
        scrape_website=not args.no_website,
        use_gias=not args.no_gias,
        gias_cache=str(args.gias_cache) if args.gias_cache else None,
    )
    if not args.no_gias:
        engine.preload_gias({s.urn for s in schools})

    records = []
    for school in schools:
        print(f"Capturing contacts {school.urn} {school.name}...", file=sys.stderr)
        records.append(engine.capture_school(school))

    with_phone = sum(1 for r in records if any(c.phone for c in r.contacts))
    with_email = sum(1 for r in records if any(c.email for c in r.contacts))
    with_head = sum(1 for r in records if any(c.role == "headteacher" and c.name for c in r.contacts))
    with_senco = sum(1 for r in records if any(c.role == "senco" for c in r.contacts))

    index = ContactCaptureIndex(
        generatedAt=today_iso(),
        schoolCount=len(records),
        records=records,
        stats={
            "la": args.la,
            "withPhone": with_phone,
            "withEmail": with_email,
            "withHeadteacher": with_head,
            "withSenco": with_senco,
            "scrapeWebsite": not args.no_website,
            "useGias": not args.no_gias,
        },
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(index.to_dict(), indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} record(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
