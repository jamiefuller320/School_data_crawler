"""Extract text from documents hosted on school websites."""

from __future__ import annotations

import re

from school_capture.binary_fetch import fetch_bytes
from school_capture.documents import (
    MAX_DOCUMENTS_PER_SCHOOL,
    document_label,
    extract_list_lines_from_document_text,
    extract_pdf_text,
    infer_section_from_document,
    is_document_url,
    is_extractable_document,
    score_document_url,
)
from school_capture.filters import classify_page_type
from school_capture.html_sections import parse_structured_page
from school_capture.http_utils import fetch_text, normalize_url, polite_sleep, same_site
from school_capture.models import SchoolInput
from school_capture.sources.base import RawCapture, StructuredSection
from school_capture.sources.website import SchoolWebsiteAdapter


class SchoolDocumentsAdapter:
    source_type = "school-document"

    def __init__(self, website_adapter: SchoolWebsiteAdapter | None = None) -> None:
        self._website = website_adapter or SchoolWebsiteAdapter()
        self._last_inventory: list[dict[str, str]] = []

    @property
    def last_inventory(self) -> list[dict[str, str]]:
        return list(self._last_inventory)

    def discover(self, school: SchoolInput) -> list[str]:
        self._last_inventory = []
        root = normalize_url(school.schoolWebsite or "")
        if not root:
            return []

        page_urls = self._website.discover(school)
        candidates: dict[str, tuple[int, str]] = {}

        def scan_page(page_url: str, html: str, base: str) -> None:
            parsed = parse_structured_page(html)
            for href, anchor in parsed.links:
                abs_url = normalize_url(href, base)
                if not abs_url or not same_site(abs_url, root):
                    continue
                if not is_document_url(abs_url):
                    continue
                score = score_document_url(abs_url, anchor)
                if score <= 0:
                    continue
                label = document_label(abs_url, anchor)
                ext = abs_url.rsplit(".", 1)[-1].lower()
                status = "discovered" if is_extractable_document(abs_url) else "unsupported_format"
                prev = candidates.get(abs_url)
                if not prev or score > prev[0]:
                    candidates[abs_url] = (score, label)
                self._record_inventory(abs_url, label, ext, status, page_url)

        for page_url in page_urls:
            try:
                polite_sleep()
                final, html = fetch_text(page_url)
                scan_page(page_url, html, final)
            except Exception:  # noqa: BLE001
                continue

        if root not in page_urls:
            try:
                polite_sleep()
                final, html = fetch_text(root)
                scan_page(root, html, final)
            except Exception:  # noqa: BLE001
                pass

        ranked = sorted(
            ((score, url) for url, (score, _) in candidates.items()),
            key=lambda x: (-x[0], x[1]),
        )
        extractable = [url for _, url in ranked if is_extractable_document(url)]
        return extractable[:MAX_DOCUMENTS_PER_SCHOOL]

    def capture(self, school: SchoolInput, url: str) -> RawCapture | None:
        if not is_extractable_document(url):
            return None
        fetched = fetch_bytes(url)
        if not fetched:
            self._update_inventory_status(url, "failed")
            return None
        final, raw = fetched
        try:
            text, page_count = extract_pdf_text(raw)
        except Exception:  # noqa: BLE001
            self._update_inventory_status(url, "extract_failed")
            return None
        if len(text) < 80:
            self._update_inventory_status(url, "empty")
            return None

        label = document_label(final)
        section = infer_section_from_document(final, label)
        list_items = extract_list_lines_from_document_text(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) > 16000:
            text = text[:16000]

        structured: list[StructuredSection] = []
        if list_items:
            structured.append(
                StructuredSection(
                    heading=label,
                    inferred_section=section,
                    paragraphs=[],
                    list_items=list_items,
                )
            )

        self._update_inventory_status(
            url,
            "extracted",
            extra={
                "pageCount": str(page_count),
                "charCount": str(len(text)),
                "listItems": str(len(list_items)),
            },
        )

        return RawCapture(
            url=final,
            source_type=self.source_type,
            text=text,
            page_title=label or school.name,
            section=section,
            meta={
                "pageType": classify_page_type(final, label).value,
                "documentFormat": "pdf",
                "pageCount": str(page_count),
                "listItemCount": str(len(list_items)),
            },
            structured_sections=structured,
            list_items=list_items,
        )

    def _record_inventory(
        self,
        url: str,
        label: str,
        ext: str,
        status: str,
        found_on: str,
    ) -> None:
        for row in self._last_inventory:
            if row.get("url") == url:
                return
        self._last_inventory.append(
            {
                "url": url,
                "label": label,
                "format": ext,
                "status": status,
                "foundOn": found_on,
            }
        )

    def _update_inventory_status(
        self, url: str, status: str, extra: dict[str, str] | None = None
    ) -> None:
        for row in self._last_inventory:
            if row.get("url") == url:
                row["status"] = status
                if extra:
                    row.update(extra)
                return
        entry: dict[str, str] = {
            "url": url,
            "label": document_label(url),
            "format": "pdf",
            "status": status,
        }
        if extra:
            entry.update(extra)
        self._last_inventory.append(entry)
