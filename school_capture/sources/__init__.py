"""Source adapters for qualitative capture."""

from __future__ import annotations

from school_capture.sources.base import SourceAdapter
from school_capture.sources.documents import SchoolDocumentsAdapter
from school_capture.sources.news import LocalNewsAdapter
from school_capture.sources.social import SocialMediaAdapter
from school_capture.sources.website import SchoolWebsiteAdapter

__all__ = [
    "SourceAdapter",
    "SchoolWebsiteAdapter",
    "SchoolDocumentsAdapter",
    "LocalNewsAdapter",
    "SocialMediaAdapter",
    "default_adapters",
]


def default_adapters(*, include_documents: bool = True) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = [SchoolWebsiteAdapter()]
    if include_documents:
        adapters.append(SchoolDocumentsAdapter())
    adapters.extend([LocalNewsAdapter(), SocialMediaAdapter()])
    return adapters
