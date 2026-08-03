"""Experimental social-media discovery (public pages only)."""

from __future__ import annotations

import re

from school_capture.http_utils import normalize_url, parse_html, safe_fetch, slug_words
from school_capture.models import SchoolInput
from school_capture.sources.base import RawCapture

SOCIAL_HOSTS = ("facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com")
MAX_POSTS = 3


class SocialMediaAdapter:
    source_type = "social-media"

    def discover(self, school: SchoolInput) -> list[str]:
        root = normalize_url(school.schoolWebsite or "")
        if not root:
            return []
        final, html = safe_fetch(root)
        if not final or not html:
            return []
        parser = parse_html(html)
        urls: list[str] = []
        for href, _ in parser.links:
            abs_url = normalize_url(href, final)
            if not abs_url:
                continue
            host = abs_url.lower()
            if any(h in host for h in SOCIAL_HOSTS):
                if abs_url not in urls:
                    urls.append(abs_url)
        return urls[:2]

    def capture(self, school: SchoolInput, url: str) -> RawCapture | None:
        final, html = safe_fetch(url)
        if not final or not html:
            return None
        parser = parse_html(html)
        text = parser.text
        if not self._likely_official(text, school):
            return None
        # Social pages are noisy — extract short substantive lines.
        lines = [ln.strip() for ln in text.splitlines() if 30 <= len(ln.strip()) <= 280]
        if not lines:
            return None
        excerpt = "\n".join(lines[:8])
        return RawCapture(
            url=final,
            source_type=self.source_type,
            text=excerpt,
            page_title=parser.title.strip() or school.name,
            section="social",
            meta={"platform": self._platform(final)},
        )

    def _platform(self, url: str) -> str:
        lower = url.lower()
        for host in SOCIAL_HOSTS:
            if host in lower:
                return host.split(".")[0]
        return "unknown"

    def _likely_official(self, text: str, school: SchoolInput) -> bool:
        lower = text.lower()
        if school.name.lower() in lower:
            return True
        tokens = slug_words(school.name)
        core = tokens - {"school", "primary", "secondary", "academy", "the"}
        return len(core & slug_words(lower)) >= min(2, len(core))
