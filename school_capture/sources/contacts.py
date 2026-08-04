"""Crawl school websites for contact and staff pages."""

from __future__ import annotations

from school_capture.contacts import parse_contact_html
from school_capture.contact_models import ContactEntry
from school_capture.filters import is_blocked_url
from school_capture.http_utils import link_matches, normalize_url, same_site, safe_fetch
from school_capture.models import SchoolInput, today_iso

CONTACT_URL_TERMS: tuple[str, ...] = (
    "contact",
    "contact-us",
    "contact-details",
    "get-in-touch",
    "staff",
    "our-staff",
    "staff-list",
    "meet-the-team",
    "leadership",
    "senior-leadership",
    "governors",
    "about-us",
    "about",
    "send",
    "senco",
    "inclusion",
    "office",
)

MAX_CONTACT_PAGES = 6


class SchoolContactsAdapter:
    source_type = "school-website"

    def discover(self, school: SchoolInput) -> list[str]:
        root = normalize_url(school.schoolWebsite or "")
        if not root:
            return []

        final, html = safe_fetch(root)
        if not final or not html:
            return [root]

        from school_capture.html_sections import parse_structured_page

        parsed = parse_structured_page(html)
        candidates: list[tuple[int, str]] = []
        seen: set[str] = {final}

        for href, anchor in parsed.links[:120]:
            abs_url = normalize_url(href, final)
            if not abs_url or abs_url in seen:
                continue
            if not same_site(abs_url, root):
                continue
            if is_blocked_url(abs_url):
                continue
            seen.add(abs_url)
            score = self._url_score(abs_url, anchor)
            if score:
                candidates.append((score, abs_url))

        candidates.sort(key=lambda x: (-x[0], x[1]))
        urls = [final]
        for _, url in candidates:
            if url not in urls:
                urls.append(url)
            if len(urls) >= MAX_CONTACT_PAGES:
                break
        return urls

    def _url_score(self, url: str, anchor: str) -> int:
        blob = f"{url} {anchor}".lower()
        score = 0
        for term in CONTACT_URL_TERMS:
            if term in blob:
                score += 3
        if "staff" in blob and "contact" in blob:
            score += 2
        return score

    def capture_page(self, school: SchoolInput, url: str) -> list[ContactEntry]:
        if is_blocked_url(url):
            return []
        final, html = safe_fetch(url)
        if not final or not html or is_blocked_url(final):
            return []
        return parse_contact_html(
            html,
            source_url=final,
            source_type=self.source_type,
            captured_at=today_iso(),
        )
