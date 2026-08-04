"""Data models for school contact capture sidecars."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CONTACT_ENGINE_VERSION = "0.1.0"

CONTACT_ROLES = (
    "headteacher",
    "senco",
    "office",
    "admissions",
    "safeguarding",
    "governor",
    "other",
)

CONTACT_SOURCE_TYPES = (
    "gias",
    "dfe-index",
    "school-website",
    "school-document",
    "other",
)


@dataclass
class ContactEntry:
    """One contact field or person with provenance."""

    role: str
    sourceType: str
    sourceUrl: str
    capturedAt: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    town: str | None = None
    postcode: str | None = None
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ContactCaptureRecord:
    """Per-school contact sidecar (keyed by URN)."""

    urn: str
    name: str
    assessedAt: str
    engineVersion: str = CONTACT_ENGINE_VERSION
    contacts: list[ContactEntry] = field(default_factory=list)
    captureNotes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "urn": self.urn,
            "name": self.name,
            "assessedAt": self.assessedAt,
            "engineVersion": self.engineVersion,
            "contacts": [c.to_dict() for c in self.contacts],
            "captureNotes": self.captureNotes,
        }


@dataclass
class ContactCaptureIndex:
    """Batch output written to output/contact-capture.json."""

    generatedAt: str
    engineVersion: str = CONTACT_ENGINE_VERSION
    schoolCount: int = 0
    records: list[ContactCaptureRecord] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generatedAt": self.generatedAt,
            "engineVersion": self.engineVersion,
            "schoolCount": self.schoolCount,
            "records": [r.to_dict() for r in self.records],
            "stats": self.stats,
        }
