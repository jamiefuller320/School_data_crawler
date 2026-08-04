"""Tests for structured HTML section extraction."""

from __future__ import annotations

from pathlib import Path

from school_capture.analysis.assessor import assess_captures
from school_capture.html_sections import parse_structured_page
from school_capture.sources.base import RawCapture, StructuredSection

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pages"


def test_parse_club_lists_under_headings():
    html = (FIXTURES / "clubs-list.html").read_text(encoding="utf-8")
    page = parse_structured_page(html)
    assert page.sections
    club_section = next(s for s in page.sections if "after-school" in s.heading.lower())
    assert "Football (Years 3–6)" in club_section.list_items or any(
        "football" in i.lower() for i in club_section.list_items
    )
    wrap_section = next(s for s in page.sections if "wraparound" in s.heading.lower())
    assert any("breakfast" in i.lower() for i in wrap_section.list_items)


def test_assessor_uses_list_items_as_offerings():
    html = (FIXTURES / "clubs-list.html").read_text(encoding="utf-8")
    page = parse_structured_page(html)
    cap = RawCapture(
        url="https://example.testvalley.sch.uk/clubs",
        source_type="school-website",
        text=page.flat_text,
        page_title="Clubs",
        section="enrichment",
        meta={"pageType": "substantive"},
        structured_sections=[
            StructuredSection(
                heading=sec.heading,
                inferred_section=sec.inferred_section,
                paragraphs=sec.paragraphs,
                list_items=sec.list_items,
            )
            for sec in page.sections
        ],
        list_items=[i for s in page.sections for i in s.list_items],
    )
    areas = {a.area: a for a in assess_captures([cap])}
    enrich = areas["enrichment"]
    assert enrich.offerings
    assert any("football" in o for o in enrich.offerings)
    assert any("breakfast" in o or "after-school" in o for o in enrich.offerings)
    assert enrich.score >= 40
