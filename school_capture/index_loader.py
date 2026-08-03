"""Load schools from Comparison-tool indexes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from school_capture.models import SchoolInput

SEED_LOCAL_AUTHORITY = "Hampshire"


def normalize_la_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip())


def load_schools_index(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("schools") or [])


def filter_schools(
    schools: list[dict[str, Any]],
    *,
    la: str | None = None,
    urn: str | None = None,
    require_website: bool = False,
) -> list[SchoolInput]:
    la_norm = normalize_la_name(la) if la else ""
    out: list[SchoolInput] = []
    for row in schools:
        if urn and str(row.get("urn") or "").strip() != urn:
            continue
        if la_norm and normalize_la_name(row.get("localAuthority")) != la_norm:
            continue
        if require_website and not (row.get("schoolWebsite") or "").strip():
            continue
        if row.get("closed"):
            continue
        school = SchoolInput.from_dict(row)
        if school.urn and school.name:
            out.append(school)
    return out


def resolve_comparison_tool_index(
    comparison_tool_root: Path,
    *,
    la_slug: str | None = None,
) -> Path:
    if la_slug:
        pack = comparison_tool_root / "public" / "data" / "packs" / la_slug / "schools-index.json"
        if pack.is_file():
            return pack
        raise FileNotFoundError(f"No pack index at {pack}")
    root = comparison_tool_root / "public" / "data" / "schools-index.json"
    if root.is_file():
        return root
    raise FileNotFoundError(f"No schools index at {root}")
