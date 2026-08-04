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

    with patch("school_capture.url_discovery.safe_fetch") as mock_fetch:
        mock_fetch.return_value = ("https://example.testvalley.sch.uk/", homepage)
        urls = adapter.discover(school)

    assert any(u.rstrip("/") == "https://example.testvalley.sch.uk" for u in urls)


def test_assessor_rejects_vague_ethos():
    captures = [
        RawCapture(
            url="https://school.example/",
            source_type="school-website",
            text=(
                "We are immensely proud of our school and hope that you and your child "
                "will enjoy being part of our caring community."
            ),
            page_title="Welcome",
            section="ethos",
            meta={"pageType": "substantive"},
        ),
        RawCapture(
            url="https://school.example/clubs",
            source_type="school-website",
            text=(
                "After-school clubs include football, rugby, choir and homework club. "
                "Breakfast club runs from 7:45am and wraparound care is available until 5:30pm."
            ),
            page_title="Clubs",
            section="enrichment",
            meta={"pageType": "substantive"},
        ),
    ]
    areas = {a.area: a for a in assess_captures(captures)}
    assert areas["ethos"].score <= 15
    assert not areas["ethos"].signals
    assert "football" in areas["enrichment"].offerings or any(
        "football" in s.text.lower() for s in areas["enrichment"].signals
    )


def test_assessor_rejects_boilerplate():
    captures = [
        RawCapture(
            url="https://school.example/accessibility-statement",
            source_type="school-website",
            text=(
                "Responsive Design: Our website is designed to work on various devices. "
                "Form auto complete: adding validation to forms enables our forms. "
                "The Equality and Human Rights Commission is responsible for enforcement."
            ),
            page_title="Accessibility",
            section="send",
            meta={"pageType": "accessibility"},
        ),
        RawCapture(
            url="https://school.example/curriculum",
            source_type="school-website",
            text=(
                "We provide a broad and balanced curriculum that is ambitious for all pupils. "
                "Pupils study reading, writing, mathematics and science across the school. "
                "Our curriculum is carefully sequenced so knowledge builds over time."
            ),
            page_title="Curriculum",
            section="curriculum",
            meta={"pageType": "substantive"},
        ),
    ]
    areas = {a.area: a for a in assess_captures(captures)}
    assert areas["send"].score <= 25
    assert areas["curriculum"].score >= 25
    for signal in areas["curriculum"].signals:
        assert "cookie" not in signal.text.lower()


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
    assert areas["curriculum"].confidence >= 0.2
    assert any("curriculum" in t or "gcse" in t for t in areas["curriculum"].themes) or areas["curriculum"].offerings
    assert areas["enrichment"].score >= 35
    assert areas["enrichment"].offerings or areas["enrichment"].signals
    # Ethos requires concrete practices — vague values-only homepage should not score highly.
    assert areas["ethos"].score <= 25


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
