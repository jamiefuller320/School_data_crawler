"""URL discovery with hub-and-spoke crawling and learned cross-school terms."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from school_capture.filters import is_blocked_url
from school_capture.html_sections import parse_structured_page
from school_capture.http_utils import link_matches, normalize_url, same_site, safe_fetch
from school_capture.offering_terms import CURRICULUM_SUBJECT_TERMS
from school_capture.section_patterns import PRIORITY_URL_TERMS, SECTION_PATTERNS

MAX_PAGES = 18
MAX_LINKS_SCAN = 180
MAX_HUB_PAGES = 3
MAX_CHILD_LINKS_PER_HUB = 12

HUB_BLOB_TERMS: tuple[str, ...] = (
    "curriculum",
    "subjects",
    "subject curriculum",
    "year group curriculum",
    "our curriculum",
    "learning",
    "extra-curricular",
    "clubs",
    "send",
    "staff",
    "contact",
)

SUBJECT_URL_TERMS: tuple[str, ...] = tuple(
    dict.fromkeys(
        list(CURRICULUM_SUBJECT_TERMS)
        + ["dt", "re", "rs", "mfl", "languages", "stem", "humanities"]
    )
)


def score_url(url: str, anchor: str, *, learned_terms: dict[str, int] | None = None) -> int:
    blob = _url_blob(url, anchor)
    score = 0
    for sec, patterns in SECTION_PATTERNS.items():
        if link_matches(anchor, url, patterns):
            score += 3
        for priority in PRIORITY_URL_TERMS.get(sec, ()):
            if priority in blob:
                score += 2
    for term in SUBJECT_URL_TERMS:
        if term in blob:
            score += 4
    if learned_terms:
        for term, boost in learned_terms.items():
            if term in blob:
                score += boost
    return score


def _url_blob(url: str, anchor: str) -> str:
    return unquote(f"{url} {anchor}").replace("+", " ").lower()


def is_hub_page(url: str, anchor: str) -> bool:
    blob = _url_blob(url, anchor)
    return any(term in blob for term in HUB_BLOB_TERMS)


def is_curriculum_hub(url: str, anchor: str) -> bool:
    blob = _url_blob(url, anchor)
    return any(
        term in blob
        for term in (
            "subject curriculum",
            "curriculum overview",
            "year group curriculum",
            "whole school curriculum",
            "our curriculum",
            "subjects",
        )
    )


def discover_site_pages(
    root: str,
    *,
    learned_terms: dict[str, int] | None = None,
    hub_spoke: bool = True,
    max_pages: int = MAX_PAGES,
) -> list[str]:
    """Discover thematic pages on a school site, optionally following hub links."""
    final, html = safe_fetch(root)
    if not final or not html:
        return [root]

    site_root = final
    parsed = parse_structured_page(html)
    candidates: list[tuple[int, str, str]] = []
    seen: set[str] = {final}

    def consider(href: str, anchor: str, base: str, *, bonus: int = 0) -> None:
        abs_url = normalize_url(href, base)
        if not abs_url or abs_url in seen:
            return
        if not same_site(abs_url, site_root):
            return
        if is_blocked_url(abs_url):
            return
        seen.add(abs_url)
        score = score_url(abs_url, anchor, learned_terms=learned_terms) + bonus
        if score:
            candidates.append((score, abs_url, anchor))

    for href, anchor in parsed.links[:MAX_LINKS_SCAN]:
        consider(href, anchor, final)

    if hub_spoke:
        candidates.sort(key=lambda x: (-x[0], x[1]))
        curriculum_hubs = [
            (score, url, anchor)
            for score, url, anchor in candidates
            if is_curriculum_hub(url, anchor)
        ][:2]
        other_hubs = [
            (score, url, anchor)
            for score, url, anchor in candidates
            if (is_hub_page(url, anchor) or score >= 5)
            and not is_curriculum_hub(url, anchor)
        ][: max(0, MAX_HUB_PAGES - len(curriculum_hubs))]
        hubs = curriculum_hubs + other_hubs
        for _, hub_url, _ in hubs:
            hub_final, hub_html = safe_fetch(hub_url)
            if not hub_final or not hub_html:
                continue
            hub_bonus = 8 if is_curriculum_hub(hub_url, "") else 0
            hub_parsed = parse_structured_page(hub_html)
            child_count = 0
            for href, anchor in hub_parsed.links:
                if child_count >= MAX_CHILD_LINKS_PER_HUB:
                    break
                before = len(seen)
                consider(href, anchor, hub_final, bonus=hub_bonus)
                if len(seen) > before:
                    child_count += 1

    candidates.sort(key=lambda x: (-x[0], x[1]))
    urls = [final] if not is_blocked_url(final) else []
    for _, url, _ in candidates:
        if url not in urls:
            urls.append(url)
        if len(urls) >= max_pages:
            break
    return urls or [final]


def path_terms(url: str) -> list[str]:
    """Extract searchable terms from a URL path and query."""
    parsed = urlparse(unquote(url))
    blob = f"{parsed.path} {parsed.query}".lower()
    terms: list[str] = []
    for chunk in re_split_terms(blob):
        if 3 <= len(chunk) <= 40:
            terms.append(chunk)
    return terms


def re_split_terms(blob: str) -> list[str]:
    parts = re.split(r"[/&?=_.+\-]+", blob)
    return [p.strip() for p in parts if p.strip()]
