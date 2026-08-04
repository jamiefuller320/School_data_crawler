"""Cross-school learned URL/anchor terms from successful captures."""

from __future__ import annotations

import json
import re
from pathlib import Path

from school_capture.url_discovery import path_terms

DEFAULT_PATH = Path("output/learned-url-terms.json")
MIN_TERM_LEN = 3
MAX_TERMS = 500

BLOCKED_TERMS = frozenset(
    {
        "page",
        "title",
        "pid",
        "html",
        "index",
        "home",
        "www",
        "http",
        "https",
        "school",
        "primary",
        "secondary",
        "junior",
        "infant",
        "academy",
        "sch",
        "uk",
        "org",
        "com",
        "net",
        "pdf",
        "wp",
        "content",
        "uploads",
    }
)


def normalize_term(term: str) -> str:
    return re.sub(r"\s+", " ", term.lower().strip())


def is_useful_term(term: str) -> bool:
    t = normalize_term(term)
    if len(t) < MIN_TERM_LEN or t in BLOCKED_TERMS:
        return False
    if t.isdigit():
        return False
    if re.fullmatch(r"pid\d+", t):
        return False
    return True


def load_learned_terms(path: Path | None = None) -> dict[str, int]:
    p = path or DEFAULT_PATH
    if not p.is_file():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    terms = payload.get("terms") or {}
    return {str(k): int(v) for k, v in terms.items() if is_useful_term(str(k))}


def save_learned_terms(terms: dict[str, int], path: Path | None = None) -> None:
    p = path or DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    ranked = sorted(terms.items(), key=lambda x: (-x[1], x[0]))[:MAX_TERMS]
    payload = {
        "terms": dict(ranked),
        "termCount": len(ranked),
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def terms_from_anchor(anchor: str) -> list[str]:
    out: list[str] = []
    for part in re.split(r"[/&|:\-–]+", anchor.lower()):
        part = normalize_term(part)
        if is_useful_term(part):
            out.append(part)
    return out


def update_learned_terms(
    store: dict[str, int],
    *,
    url: str,
    anchor: str = "",
    area: str,
    signal_count: int = 1,
) -> None:
    """Boost terms from URLs that yielded useful evidence."""
    if signal_count <= 0:
        return
    boost = 1 + min(signal_count, 5)
    if area in ("curriculum", "enrichment", "send"):
        boost += 1
    for term in path_terms(url) + terms_from_anchor(anchor):
        if not is_useful_term(term):
            continue
        store[term] = store.get(term, 0) + boost


def merge_learned_terms(base: dict[str, int], incoming: dict[str, int]) -> dict[str, int]:
    merged = dict(base)
    for term, count in incoming.items():
        if is_useful_term(term):
            merged[term] = merged.get(term, 0) + count
    return merged


def build_from_capture_file(capture_path: Path) -> dict[str, int]:
    """Rebuild learned terms from an existing qualitative-capture index."""
    import json

    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    store: dict[str, int] = {}
    for record in payload.get("records") or []:
        for area in record.get("areas") or []:
            signal_count = len(area.get("signals") or [])
            if signal_count <= 0:
                continue
            for signal in area.get("signals") or []:
                update_learned_terms(
                    store,
                    url=signal.get("sourceUrl") or "",
                    anchor=signal.get("pageTitle") or signal.get("text") or "",
                    area=area.get("area") or "general",
                    signal_count=signal_count,
                )
    return store
