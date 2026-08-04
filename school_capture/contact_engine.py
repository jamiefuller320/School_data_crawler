"""Orchestrate contact capture from index, GIAS, and school websites."""

from __future__ import annotations

from dataclasses import dataclass, field

from school_capture.contact_models import (
    CONTACT_ENGINE_VERSION,
    ContactCaptureRecord,
    ContactEntry,
)
from school_capture.contacts import dedupe_contacts
from school_capture.gias_edubase import load_gias_contacts_by_urn
from school_capture.models import SchoolInput, today_iso
from school_capture.sources.contacts import SchoolContactsAdapter


@dataclass
class ContactCaptureEngine:
    scrape_website: bool = True
    use_gias: bool = True
    gias_cache: str | None = None
    _gias_by_urn: dict[str, list[ContactEntry]] | None = None
    _adapter: SchoolContactsAdapter = field(default_factory=SchoolContactsAdapter)

    def _gias_lookup(self, urn: str) -> list[ContactEntry]:
        if not self.use_gias:
            return []
        if self._gias_by_urn is None:
            from pathlib import Path

            cache = Path(self.gias_cache) if self.gias_cache else Path(".cache/edubase/edubasealldata.csv")
            self._gias_by_urn = load_gias_contacts_by_urn({urn}, cache_path=cache)
        return list(self._gias_by_urn.get(urn, []))

    def preload_gias(self, urns: set[str]) -> None:
        if not self.use_gias:
            self._gias_by_urn = {}
            return
        from pathlib import Path

        cache = Path(self.gias_cache) if self.gias_cache else Path(".cache/edubase/edubasealldata.csv")
        self._gias_by_urn = load_gias_contacts_by_urn(urns, cache_path=cache)

    def _index_baseline(self, school: SchoolInput) -> list[ContactEntry]:
        captured = today_iso()
        source = school.giasUrl or f"urn:{school.urn}"
        entries: list[ContactEntry] = []
        if school.address or school.postcode:
            entries.append(
                ContactEntry(
                    role="office",
                    label="Postal address",
                    address=school.address,
                    town=school.town,
                    postcode=school.postcode,
                    sourceType="dfe-index",
                    sourceUrl=source,
                    capturedAt=captured,
                )
            )
        if school.telephone:
            entries.append(
                ContactEntry(
                    role="office",
                    label="Telephone",
                    phone=school.telephone,
                    sourceType="dfe-index",
                    sourceUrl=source,
                    capturedAt=captured,
                )
            )
        return entries

    def capture_school(self, school: SchoolInput) -> ContactCaptureRecord:
        notes: list[str] = []
        entries: list[ContactEntry] = []

        entries.extend(self._index_baseline(school))
        entries.extend(self._gias_lookup(school.urn))

        if self.scrape_website and school.schoolWebsite:
            urls = self._adapter.discover(school)
            if not urls:
                notes.append("No contact pages discovered on school website.")
            got = 0
            for url in urls:
                page_entries = self._adapter.capture_page(school, url)
                if page_entries:
                    entries.extend(page_entries)
                    got += 1
            if urls and got == 0:
                notes.append("Fetched contact page(s) but no structured contacts parsed.")
        elif not school.schoolWebsite:
            notes.append("No school website — index and GIAS only.")

        entries = dedupe_contacts(entries)

        return ContactCaptureRecord(
            urn=school.urn,
            name=school.name,
            assessedAt=today_iso(),
            engineVersion=CONTACT_ENGINE_VERSION,
            contacts=entries,
            captureNotes=notes,
        )
