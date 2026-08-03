"""Orchestrates source adapters and area assessment."""

from __future__ import annotations

from dataclasses import dataclass, field

from school_capture.analysis.assessor import assess_captures, dedupe_captures
from school_capture.models import (
    ENGINE_VERSION,
    QualitativeCaptureRecord,
    SchoolInput,
    today_iso,
)
from school_capture.sources.base import RawCapture, SourceAdapter
from school_capture.sources import default_adapters


@dataclass
class CaptureEngine:
    adapters: list[SourceAdapter] = field(default_factory=default_adapters)
    max_urls_per_adapter: int = 8

    def capture_school(self, school: SchoolInput) -> QualitativeCaptureRecord:
        notes: list[str] = []
        captures: list[RawCapture] = []
        source_types: set[str] = set()

        for adapter in self.adapters:
            urls = adapter.discover(school)[: self.max_urls_per_adapter]
            if not urls:
                notes.append(f"No URLs discovered for {adapter.source_type}.")
                continue
            got = 0
            for url in urls:
                raw = adapter.capture(school, url)
                if raw:
                    captures.append(raw)
                    source_types.add(adapter.source_type)
                    got += 1
            if got == 0:
                notes.append(f"Fetched {len(urls)} {adapter.source_type} URL(s) but no usable text.")

        captures = dedupe_captures(captures)
        areas = assess_captures(captures)

        return QualitativeCaptureRecord(
            urn=school.urn,
            name=school.name,
            assessedAt=today_iso(),
            engineVersion=ENGINE_VERSION,
            sourcesScanned=len(captures),
            sourceTypes=sorted(source_types),
            areas=areas,
            captureNotes=notes,
        )
