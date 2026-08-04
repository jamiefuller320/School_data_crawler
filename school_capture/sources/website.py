"""Crawl school websites for curriculum, enrichment, and ethos pages."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from school_capture.filters import classify_page_type, is_blocked_url
from school_capture.html_sections import parse_structured_page
from school_capture.http_utils import (
    link_matches,
    normalize_url,
    same_site,
    safe_fetch,
)
from school_capture.models import SchoolInput
from school_capture.section_patterns import PRIORITY_URL_TERMS, SECTION_PATTERNS
from school_capture.sources.base import RawCapture, StructuredSection

MAX_PAGES = 10
MAX_LINKS_SCAN = 150


class SchoolWebsiteAdapter:
    source_type = "school-website"

    def discover(self, school: SchoolInput) -> list[str]:
        root = normalize_url(school.schoolWebsite or "")
        if not root:
            return []
        final, html = safe_fetch(root)
        if not final or not html:
            return [root]

        parsed = parse_structured_page(html)
        candidates: list[tuple[int, str]] = []
        seen: set[str] = {final}

        for href, anchor in parsed.links[:MAX_LINKS_SCAN]:
            abs_url = normalize_url(href, final)
            if not abs_url or abs_url in seen:
                continue
            if not same_site(abs_url, final):
                continue
            if is_blocked_url(abs_url):
                continue
            seen.add(abs_url)
            score = self._url_score(abs_url, anchor)
            if score:
                candidates.append((score, abs_url))

        candidates.sort(key=lambda x: (-x[0], x[1]))
        urls = [final] if not is_blocked_url(final) else []
        for _, url in candidates[: MAX_PAGES - len(urls)]:
            if url not in urls:
                urls.append(url)
        return urls or [final]

    def _url_score(self, url: str, anchor: str) -> int:
        score = 0
        blob = f"{url} {anchor}".lower()
        for sec, patterns in SECTION_PATTERNS.items():
            if link_matches(anchor, url, patterns):
                score += 3
            for priority in PRIORITY_URL_TERMS.get(sec, ()):
                if priority in blob:
                    score += 2
        return score

    def capture(self, school: SchoolInput, url: str) -> RawCapture | None:
        if is_blocked_url(url):
            return None
        final, html = safe_fetch(url)
        if not final or not html:
            return None
        if is_blocked_url(final):
            return None

        parsed = parse_structured_page(html)
        text = parsed.flat_text
        if len(text) < 40:
            return None

        title = parsed.title or school.name
        page_type = classify_page_type(final, title)
        section = self._infer_section(final, title)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) > 14000:
            text = text[:14000]

        structured = [
            StructuredSection(
                heading=sec.heading,
                inferred_section=sec.inferred_section,
                paragraphs=sec.paragraphs,
                list_items=sec.list_items,
            )
            for sec in parsed.sections
            if sec.paragraphs or sec.list_items
        ]
        all_list_items: list[str] = []
        for sec in parsed.sections:
            all_list_items.extend(sec.list_items)
        all_list_items.extend(parsed.orphan_list_items)

        return RawCapture(
            url=final,
            source_type=self.source_type,
            text=text,
            page_title=title,
            section=section,
            meta={
                "pageType": page_type.value,
                "sectionCount": str(len(structured)),
                "listItemCount": str(len(all_list_items)),
            },
            structured_sections=structured,
            list_items=all_list_items,
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
