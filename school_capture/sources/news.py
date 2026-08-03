"""Discover local news articles positively associated with a school."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from school_capture.http_utils import parse_html, safe_fetch, slug_words
from school_capture.models import SchoolInput
from school_capture.sources.base import RawCapture

# Google News RSS — no API key; bounded experimental use.
NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en"

POSITIVE_NEWS_HINTS = (
    "award",
    "achieve",
    "success",
    "celebrate",
    "fundraise",
    "charity",
    "community",
    "sport",
    "music",
    "drama",
    "ofsted",
    "good",
    "outstanding",
    "pupil",
    "student",
    "open day",
    "results",
)

MAX_ARTICLES = 4


class LocalNewsAdapter:
    source_type = "local-news"

    def discover(self, school: SchoolInput) -> list[str]:
        query_parts = [f'"{school.name}"']
        if school.town:
            query_parts.append(school.town)
        if school.localAuthority:
            query_parts.append(school.localAuthority.split()[0])
        query = " ".join(query_parts)
        rss_url = NEWS_RSS.format(query=query.replace(" ", "+"))
        final, body = safe_fetch(rss_url)
        if not final or not body:
            return []
        return self._parse_rss(body, school)[:MAX_ARTICLES]

    def capture(self, school: SchoolInput, url: str) -> RawCapture | None:
        final, html = safe_fetch(url)
        if not final or not html:
            return None
        parser = parse_html(html)
        text = parser.text
        if not self._mentions_school(text, school):
            return None
        if not self._looks_positive(text):
            return None
        if len(text) > 10000:
            text = text[:10000]
        return RawCapture(
            url=final,
            source_type=self.source_type,
            text=text,
            page_title=parser.title.strip() or school.name,
            section="local-news",
            meta={"association": "name-match-positive-tone"},
        )

    def _parse_rss(self, xml_text: str, school: SchoolInput) -> list[str]:
        urls: list[str] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return urls
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if link_el is None or not (link_el.text or "").strip():
                continue
            title = (title_el.text if title_el is not None else "") or ""
            if not self._title_mentions_school(title, school):
                continue
            urls.append(link_el.text.strip())
        return urls

    def _title_mentions_school(self, title: str, school: SchoolInput) -> bool:
        title_words = slug_words(title)
        name_words = slug_words(school.name)
        # Require at least two significant tokens from the school name, or full short name.
        if len(name_words) <= 2:
            return name_words.issubset(title_words) or school.name.lower() in title.lower()
        overlap = name_words & title_words
        return len(overlap) >= min(2, len(name_words) - 1)

    def _mentions_school(self, text: str, school: SchoolInput) -> bool:
        lower = text.lower()
        if school.name.lower() in lower:
            return True
        # Acronym / shortened forms (e.g. "Test Valley School" → "test valley").
        tokens = [w for w in slug_words(school.name) if w not in {"school", "primary", "secondary", "academy", "college"}]
        if len(tokens) >= 2:
            phrase = " ".join(tokens[:2])
            return phrase in lower
        return False

    def _looks_positive(self, text: str) -> bool:
        lower = text.lower()
        hits = sum(1 for hint in POSITIVE_NEWS_HINTS if hint in lower)
        negative = sum(1 for w in ("closure", "investigation", "court", "strike", "protest") if w in lower)
        return hits >= 2 and negative == 0
