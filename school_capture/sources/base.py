"""Protocol for qualitative source adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from school_capture.models import SchoolInput


@dataclass
class StructuredSection:
    heading: str
    inferred_section: str
    paragraphs: list[str] = field(default_factory=list)
    list_items: list[str] = field(default_factory=list)


@dataclass
class RawCapture:
    """Unstructured text pulled from one URL before area assessment."""

    url: str
    source_type: str
    text: str
    page_title: str | None = None
    section: str | None = None
    meta: dict[str, str] = field(default_factory=dict)
    structured_sections: list[StructuredSection] = field(default_factory=list)
    list_items: list[str] = field(default_factory=list)


class SourceAdapter(Protocol):
    source_type: str

    def discover(self, school: SchoolInput) -> list[str]:
        """Return candidate URLs to fetch for this school."""
        ...

    def capture(self, school: SchoolInput, url: str) -> RawCapture | None:
        """Fetch and normalise one URL into capture text."""
        ...
