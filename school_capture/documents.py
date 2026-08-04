"""Discover and extract school-hosted documents (PDF, etc.)."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from school_capture.html_sections import clean_list_item, infer_section_from_heading
from school_capture.http_utils import link_matches, normalize_url
from school_capture.list_filters import is_plausible_list_offering
from school_capture.section_patterns import PRIORITY_URL_TERMS, SECTION_PATTERNS

DOCUMENT_EXTENSIONS: tuple[str, ...] = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
)

# Formats we attempt to extract text from in v0.5.
EXTRACTABLE_EXTENSIONS: frozenset[str] = frozenset({".pdf"})

MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 15
MAX_DOCUMENTS_PER_SCHOOL = 8

DOCUMENT_PRIORITY_TERMS: tuple[str, ...] = (
    "club",
    "clubs",
    "extra-curricular",
    "extracurricular",
    "enrichment",
    "curriculum",
    "prospectus",
    "handbook",
    "send",
    "sen",
    "senco",
    "inclusion",
    "wraparound",
    "wrap-around",
    "breakfast",
    "childcare",
    "after-school",
    "afterschool",
    "menu",
    "timetable",
    "subject",
    "options",
    "activities",
    "sport",
    "music",
    "ethos",
    "values",
    "welcome",
    "guide",
)

BLOCKED_DOCUMENT_TERMS: tuple[str, ...] = (
    "privacy",
    "cookie",
    "gdpr",
    "complaints",
    "freedom-of-information",
    "foi",
    "data-protection",
    "accessibility",
    "safeguarding-policy",
    "single-central",
    "financial",
    "accounts",
    "audit",
    "governance",
    "minutes",
    "risk-assessment",
)

BULLET_LINE = re.compile(r"^[\s•·\-\*\u2022◦]+")
NUMBERED_LINE = re.compile(r"^\s*\d+[\.\):\-]\s+")


def document_extension(url: str) -> str:
    path = unquote(urlparse(url.lower()).path)
    for ext in DOCUMENT_EXTENSIONS:
        if path.endswith(ext):
            return ext
    return ""


def is_document_url(url: str) -> bool:
    return bool(document_extension(url))


def is_extractable_document(url: str) -> bool:
    return document_extension(url) in EXTRACTABLE_EXTENSIONS


def score_document_url(url: str, anchor: str = "") -> int:
    if not is_document_url(url):
        return 0
    blob = f"{url} {anchor}".lower()
    if any(term in blob for term in BLOCKED_DOCUMENT_TERMS):
        return 0
    score = 1
    for term in DOCUMENT_PRIORITY_TERMS:
        if term in blob:
            score += 3
    for patterns in SECTION_PATTERNS.values():
        if link_matches(anchor, url, patterns):
            score += 2
    for priorities in PRIORITY_URL_TERMS.values():
        for term in priorities:
            if term in blob:
                score += 1
    # Deprioritise generic admission policy PDFs unless also thematic.
    if "admission" in blob and score < 5:
        return 0
    return score


def infer_section_from_document(url: str, anchor: str = "") -> str:
    label = anchor or unquote(urlparse(url).path.split("/")[-1])
    return infer_section_from_heading(label.replace("-", " ").replace("_", " "))


def document_label(url: str, anchor: str = "") -> str:
    if anchor and anchor.strip():
        return anchor.strip()
    name = unquote(urlparse(url).path.split("/")[-1])
    return re.sub(r"\.[a-z0-9]+$", "", name, flags=re.I).replace("-", " ").replace("_", " ")


def extract_pdf_text(data: bytes, *, max_pages: int = MAX_PDF_PAGES) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pypdf is required for document extraction. "
            "Install with: pip install -r requirements.txt"
        ) from exc
    import io

    reader = PdfReader(io.BytesIO(data))
    pages = min(len(reader.pages), max_pages)
    parts: list[str] = []
    for idx in range(pages):
        parts.append(reader.pages[idx].extract_text() or "")
    return "\n".join(parts).strip(), pages


def extract_list_lines_from_document_text(text: str) -> list[str]:
    """Pull bullet/numbered lines and short labels typical of club lists in PDFs."""
    items: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        candidate = line
        if BULLET_LINE.match(line):
            candidate = BULLET_LINE.sub("", line).strip()
        elif NUMBERED_LINE.match(line):
            candidate = NUMBERED_LINE.sub("", line).strip()
        elif not (3 <= len(candidate.split()) <= 8):
            continue
        item = clean_list_item(candidate)
        if not item or not is_plausible_list_offering(item):
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            items.append(item)
    return items[:40]
