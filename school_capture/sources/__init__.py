"""Source adapters for qualitative capture."""

from __future__ import annotations

from school_capture.sources.base import SourceAdapter
from school_capture.sources.news import LocalNewsAdapter
from school_capture.sources.social import SocialMediaAdapter
from school_capture.sources.website import SchoolWebsiteAdapter

__all__ = [
    "SourceAdapter",
    "SchoolWebsiteAdapter",
    "LocalNewsAdapter",
    "SocialMediaAdapter",
    "default_adapters",
]


def default_adapters() -> list[SourceAdapter]:
    return [
        SchoolWebsiteAdapter(),
        LocalNewsAdapter(),
        SocialMediaAdapter(),
    ]
