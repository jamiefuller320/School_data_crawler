"""Tests for the qualitative capture engine (offline fixtures)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from school_capture.analysis.assessor import assess_captures
from school_capture.engine import CaptureEngine
from school_capture.models import SchoolInput
from school_capture.sources.base import RawCapture
from school_capture.sources.website import SchoolWebsiteAdapter

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAGES = FIXTURES / "pages"


def _page(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


def test_website_adapter_discovers_themed_pages():
    school = SchoolInput(
        urn="116338",
        name="Test Valley School",
        schoolWebsite="https://example.testvalley.sch.uk",
    )
    adapter = SchoolWebsiteAdapter()
    homepage = _page("homepage.html")

    with patch("school_capture.sources.website.safe_fetch") as mock_fetch:
        mock_fetch.return_value = ("https://example.testvalley.sch.uk/", homepage)
        urls = adapter.discover(school)

    assert "https://example.testvalley.sch.uk/" in urls


def test_assessor_scores_curriculum_and_enrichment():
    captures = [
        RawCapture(
            url="https://example.testvalley.sch.uk/curriculum",
            source_type="school-website",
            text=_page("curriculum.html"),
            page_title="Curriculum",
            section="curriculum",
        ),
        RawCapture(
            url="https://example.testvalley.sch.uk/clubs",
            source_type="school-website",
            text=_page("enrichment.html"),
            page_title="Clubs",
            section="enrichment",
        ),
        RawCapture(
            url="https://example.testvalley.sch.uk/",
            source_type="school-website",
            text=_page("homepage.html"),
            page_title="Welcome",
            section="ethos",
        ),
    ]
    areas = {a.area: a for a in assess_captures(captures)}

    assert areas["curriculum"].score >= 40
    assert areas["curriculum"].confidence > 0.2
    assert any("curriculum" in t or "gcse" in t for t in areas["curriculum"].themes)
    assert areas["enrichment"].score >= 35
    assert areas["ethos"].score >= 30
    assert all(a.signals for a in areas.values() if a.score >= 30)


def test_engine_offline_with_mocked_fetch():
    school = SchoolInput(
        urn="116338",
        name="Test Valley School",
        schoolWebsite="https://example.testvalley.sch.uk",
    )

    def fake_fetch(url: str):
        if "curriculum" in url:
            return url, _page("curriculum.html")
        if "clubs" in url:
            return url, _page("enrichment.html")
        return "https://example.testvalley.sch.uk/", _page("homepage.html")

    engine = CaptureEngine(adapters=[SchoolWebsiteAdapter()])

    with patch("school_capture.sources.website.safe_fetch", side_effect=fake_fetch):
        record = engine.capture_school(school)

    assert record.urn == "116338"
    assert record.sourcesScanned >= 1
    by_area = {a.area: a for a in record.areas}
    assert by_area["curriculum"].summary
    assert record.to_dict()["engineVersion"]


def test_sample_fixture_loads():
    rows = json.loads((FIXTURES / "sample-schools.json").read_text(encoding="utf-8"))
    school = SchoolInput.from_dict(rows[0])
    assert school.urn == "116338"
    assert school.schoolWebsite
