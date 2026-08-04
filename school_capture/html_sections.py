"""Structured HTML extraction: sections, lists, and tables."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from school_capture.list_filters import is_nav_or_junk_list_item
from school_capture.section_patterns import SECTION_PATTERNS

SKIP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "iframe",
    }
)

HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4"})
BLOCK_TAGS = frozenset({"p", "li", "td", "th", "dt", "dd"})


@dataclass
class PageSection:
    heading: str
    level: int
    paragraphs: list[str] = field(default_factory=list)
    list_items: list[str] = field(default_factory=list)
    inferred_section: str = "general"

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs + self.list_items)


@dataclass
class ParsedPage:
    title: str = ""
    links: list[tuple[str, str]] = field(default_factory=list)
    sections: list[PageSection] = field(default_factory=list)
    orphan_list_items: list[str] = field(default_factory=list)

    @property
    def flat_text(self) -> str:
        chunks: list[str] = []
        for sec in self.sections:
            if sec.heading:
                chunks.append(sec.heading)
            chunks.extend(sec.paragraphs)
            chunks.extend(sec.list_items)
        chunks.extend(self.orphan_list_items)
        return re.sub(r"\n{2,}", "\n", "\n".join(chunks)).strip()


def infer_section_from_heading(heading: str) -> str:
    blob = heading.lower()
    best = "general"
    best_score = 0
    for section, patterns in SECTION_PATTERNS.items():
        score = sum(1 for p in patterns if p in blob)
        if score > best_score:
            best_score = score
            best = section
    return best


class _SectionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.links: list[tuple[str, str]] = []
        self.sections: list[PageSection] = []
        self.orphan_list_items: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._current: PageSection | None = None
        self._capture_tag: str | None = None
        self._capture_parts: list[str] = []
        self._pending_href: str | None = None
        self._link_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = next((v or "" for k, v in attrs if k == "href"), "")
            self._pending_href = href or None
            self._link_text_parts = []
        if tag in HEADING_TAGS:
            self._flush_capture()
            self._capture_tag = tag
            self._capture_parts = []
        elif tag in BLOCK_TAGS:
            self._flush_capture()
            self._capture_tag = tag
            self._capture_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag == "a":
            if self._pending_href:
                text = re.sub(r"\s+", " ", "".join(self._link_text_parts)).strip()
                self.links.append((self._pending_href, text))
            self._pending_href = None
            self._link_text_parts = []
        if tag in HEADING_TAGS or tag in BLOCK_TAGS:
            self._flush_capture()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        if self._capture_tag:
            self._capture_parts.append(data)
        if self._pending_href is not None:
            self._link_text_parts.append(data)

    def _flush_capture(self) -> None:
        if not self._capture_tag:
            return
        text = re.sub(r"\s+", " ", "".join(self._capture_parts)).strip()
        tag = self._capture_tag
        self._capture_tag = None
        self._capture_parts = []
        if not text or len(text) < 2:
            return

        if tag in HEADING_TAGS:
            level = int(tag[1])
            self._current = PageSection(
                heading=text,
                level=level,
                inferred_section=infer_section_from_heading(text),
            )
            self.sections.append(self._current)
        elif tag == "li":
            item = clean_list_item(text)
            if item:
                if self._current:
                    self._current.list_items.append(item)
                else:
                    self.orphan_list_items.append(item)
        elif tag in ("p", "td", "th", "dt", "dd") and len(text) >= 20:
            if self._current:
                self._current.paragraphs.append(text)
            else:
                self.sections.append(PageSection(heading="", level=0, paragraphs=[text]))


def clean_list_item(text: str) -> str:
    item = re.sub(r"\s+", " ", text).strip(" •·-\t")
    item = re.sub(
        r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s*[:\-–]\s*",
        "",
        item,
        flags=re.I,
    )
    if len(item) < 2 or len(item) > 80:
        return ""
    if is_nav_or_junk_list_item(item):
        return ""
    blocked = ("click here", "read more", "download", "login", "cookie")
    lower = item.lower()
    if any(b in lower for b in blocked):
        return ""
    return item


def parse_structured_page(html: str) -> ParsedPage:
    parser = _SectionParser()
    parser.feed(html)
    parser._flush_capture()
    return ParsedPage(
        title=parser.title.strip(),
        links=parser.links,
        sections=parser.sections,
        orphan_list_items=parser.orphan_list_items,
    )
