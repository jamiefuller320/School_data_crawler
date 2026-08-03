"""Crawl school websites for curriculum, enrichment, and ethos pages."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from school_capture.http_utils import (
    link_matches,
    normalize_url,
    parse_html,
    same_site,
    safe_fetch,
)
from school_capture.models import SchoolInput
from school_capture.sources.base import RawCapture

# Link href / anchor text patterns per thematic section.
SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "curriculum": (
        "curriculum",
        "subjects",
        "learning",
        "academic",
        "key-stage",
        "keystage",
        "gcse",
        "a-level",
        "alevel",
        "options",
        "timetable",
        "reading",
        "maths",
        "science",
    ),
    "enrichment": (
        "enrichment",
        "extra-curricular",
        "extracurricular",
        "clubs",
        "activities",
        "sport",
        "music",
        "drama",
        "trips",
        "visits",
        "after-school",
        "afterschool",
    ),
    "ethos": (
        "ethos",
        "values",
        "vision",
        "mission",
        "aims",
        "about",
        "welcome",
        "character",
        "spiritual",
        "moral",
        "british-values",
        "inclusion",
    ),
    "behaviour": (
        "behaviour",
        "behavior",
        "pastoral",
        "wellbeing",
        "well-being",
        "safeguarding",
        "anti-bullying",
        "discipline",
    ),
    "send": (
        "send",
        "sen",
        "special-needs",
        "special educational",
        "inclusion",
        "accessibility",
        "ehcp",
    ),
    "community": (
        "community",
        "parents",
        "governors",
        "pta",
        "friends of",
        "local",
        "partnership",
        "charity",
    ),
}

MAX_PAGES = 8
MAX_LINKS_SCAN = 120


class SchoolWebsiteAdapter:
    source_type = "school-website"

    def discover(self, school: SchoolInput) -> list[str]:
        root = normalize_url(school.schoolWebsite or "")
        if not root:
            return []
        final, html = safe_fetch(root)
        if not final or not html:
            return [root]

        parser = parse_html(html)
        candidates: list[tuple[int, str, str]] = []
        seen: set[str] = {final}

        for href, _ in parser.links[:MAX_LINKS_SCAN]:
            abs_url = normalize_url(href, final)
            if not abs_url or abs_url in seen:
                continue
            if not same_site(abs_url, final):
                continue
            seen.add(abs_url)
            score = 0
            section = "general"
            for sec, patterns in SECTION_PATTERNS.items():
                if link_matches("", abs_url, patterns):
                    score += 3
                    section = sec
            if score:
                candidates.append((score, abs_url, section))

        # Always include homepage; prioritise themed pages.
        candidates.sort(key=lambda x: (-x[0], x[1]))
        urls = [final]
        for _, url, _ in candidates[: MAX_PAGES - 1]:
            if url not in urls:
                urls.append(url)
        return urls

    def capture(self, school: SchoolInput, url: str) -> RawCapture | None:
        final, html = safe_fetch(url)
        if not final or not html:
            return None
        parser = parse_html(html)
        text = parser.text
        if len(text) < 80:
            return None

        section = self._infer_section(final, parser.title)
        # Trim boilerplate nav noise: keep substantive paragraphs.
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) > 12000:
            text = text[:12000]

        return RawCapture(
            url=final,
            source_type=self.source_type,
            text=text,
            page_title=parser.title.strip() or school.name,
            section=section,
        )

    def _infer_section(self, url: str, title: str) -> str:
        blob = f"{url} {title}".lower()
        best = "general"
        best_score = 0
        for section, patterns in SECTION_PATTERNS.items():
            score = sum(1 for p in patterns if p in blob)
            if score > best_score:
                best_score = score
                best = section
        path = urlparse(url).path.lower()
        if path in ("", "/"):
            return "homepage"
        return best
