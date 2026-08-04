"""Tests for contact parsing and capture engine."""

from __future__ import annotations

from pathlib import Path

from school_capture.contact_engine import ContactCaptureEngine
from school_capture.contacts import (
    infer_role,
    infer_role_from_email,
    normalize_email,
    normalize_phone,
    parse_contact_html,
)
from school_capture.models import SchoolInput, today_iso

FIXTURE = Path(__file__).parent / "fixtures" / "pages" / "contact.html"


def test_infer_role():
    assert infer_role("Headteacher") == "headteacher"
    assert infer_role("Special Educational Needs Coordinator") == "senco"
    assert infer_role("School office") == "office"


def test_normalize_phone_and_email():
    assert normalize_phone("01962 123456") == "01962 123456"
    assert normalize_email("Office@School.Hants.SCH.UK") == "office@school.hants.sch.uk"
    assert normalize_email("bad@example.com") is None


def test_parse_contact_html_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    entries = parse_contact_html(
        html,
        source_url="https://school.example/contact",
        source_type="school-website",
        captured_at=today_iso(),
    )
    roles = {e.role for e in entries}
    emails = {e.email for e in entries if e.email}
    phones = {e.phone for e in entries if e.phone}
    assert "headteacher" in roles or any(e.name == "Jane Smith" for e in entries)
    assert "office@example.hants.sch.uk" in emails
    assert "senco@example.hants.sch.uk" in emails
    assert any("123456" in (p or "") for p in phones)


def test_infer_role_from_email():
    assert infer_role_from_email("admin.office@school.hants.sch.uk") == "office"
    assert infer_role_from_email("senco@school.hants.sch.uk") == "senco"


def test_index_baseline_without_network():
    school = SchoolInput(
        urn="116482",
        name="Test School",
        address="1 School Lane",
        town="Southampton",
        postcode="SO40 8EB",
        giasUrl="https://www.get-information-schools.service.gov.uk/Establishments/Establishment/Details/116482",
    )
    engine = ContactCaptureEngine(scrape_website=False, use_gias=False)
    record = engine.capture_school(school)
    assert any(c.address for c in record.contacts)
    assert record.contacts[0].sourceType == "dfe-index"
