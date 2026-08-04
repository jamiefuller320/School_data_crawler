#!/usr/bin/env python3
"""Rebuild learned URL terms from an existing qualitative-capture index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from school_capture.learned_terms import (  # noqa: E402
    build_from_capture_file,
    save_learned_terms,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "capture",
        nargs="?",
        type=Path,
        default=Path("docs/data/qualitative-capture.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/learned-url-terms.json"),
    )
    args = parser.parse_args()
    terms = build_from_capture_file(args.capture)
    save_learned_terms(terms, args.output)
    print(f"Wrote {len(terms)} terms to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
