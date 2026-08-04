"""Orchestrates source adapters and area assessment."""

from __future__ import annotations

from dataclasses import dataclass, field

from school_capture.analysis.assessor import assess_captures, dedupe_captures
from school_capture.learned_terms import update_learned_terms
from school_capture.models import (
    ENGINE_VERSION,
    QualitativeCaptureRecord,
    SchoolInput,
    today_iso,
)
from school_capture.sources.base import RawCapture, SourceAdapter
from school_capture.sources import default_adapters
from school_capture.sources.documents import SchoolDocumentsAdapter


@dataclass
class CaptureEngine:
    adapters: list[SourceAdapter] = field(default_factory=default_adapters)
    max_urls_per_adapter: int = 18
    learned_terms: dict[str, int] | None = None

    def capture_school(self, school: SchoolInput) -> QualitativeCaptureRecord:
        notes: list[str] = []
        captures: list[RawCapture] = []
        source_types: set[str] = set()
        document_inventory: list[dict[str, str]] = []
        seen_doc_urls: set[str] = set()

        for adapter in self.adapters:
            urls = adapter.discover(school)[: self.max_urls_per_adapter]
            if not urls and adapter.source_type != "school-document":
                notes.append(f"No URLs discovered for {adapter.source_type}.")
                continue
            got = 0
            for url in urls:
                raw = adapter.capture(school, url)
                if raw:
                    captures.append(raw)
                    source_types.add(adapter.source_type)
                    got += 1
            if isinstance(adapter, SchoolDocumentsAdapter):
                for row in adapter.last_inventory:
                    u = row.get("url", "")
                    if u and u not in seen_doc_urls:
                        seen_doc_urls.add(u)
                        document_inventory.append(row)
            elif got == 0 and urls:
                notes.append(
                    f"Fetched {len(urls)} {adapter.source_type} URL(s) but no usable text."
                )

        captures = dedupe_captures(captures)
        areas = assess_captures(captures)
        if self.learned_terms is not None:
            for area in areas:
                signal_count = len(area.signals)
                if signal_count <= 0:
                    continue
                for signal in area.signals:
                    if signal.sourceType != "school-website":
                        continue
                    update_learned_terms(
                        self.learned_terms,
                        url=signal.sourceUrl,
                        area=area.area,
                        signal_count=signal_count,
                    )
        docs_extracted = sum(1 for d in document_inventory if d.get("status") == "extracted")

        return QualitativeCaptureRecord(
            urn=school.urn,
            name=school.name,
            assessedAt=today_iso(),
            engineVersion=ENGINE_VERSION,
            sourcesScanned=len(captures),
            sourceTypes=sorted(source_types),
            areas=areas,
            captureNotes=notes,
            documentsDiscovered=len(document_inventory),
            documentsExtracted=docs_extracted,
            documentInventory=document_inventory,
        )
