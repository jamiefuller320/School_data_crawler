"""Tests for quality filters."""

from __future__ import annotations

from school_capture.filters import (
    PageType,
    classify_page_type,
    has_school_context,
    is_blocked_sentence,
    is_blocked_url,
)


def test_blocked_urls():
    assert is_blocked_url("https://school.example/privacy-policy")
    assert is_blocked_url("https://school.example/cookie-policy")
    assert is_blocked_url("https://school.example/accessibility-statement")
    assert not is_blocked_url("https://school.example/curriculum")


def test_blocked_sentences():
    assert is_blocked_sentence(
        "We use cookies to improve your experience on our website."
    )
    assert is_blocked_sentence(
        "Form auto complete: adding validation to forms enables our forms."
    )
    assert not is_blocked_sentence(
        "We offer a broad curriculum that helps pupils achieve well."
    )


def test_school_context():
    assert has_school_context("Our pupils enjoy a wide range of clubs.")
    assert not has_school_context("Responsive design works on various devices.")


def test_page_type_classification():
    assert (
        classify_page_type("https://school.example/accessibility-statement")
        == PageType.ACCESSIBILITY
    )
    assert classify_page_type("https://school.example/curriculum") == PageType.SUBSTANTIVE
