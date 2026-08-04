"""Tests for hub-and-spoke URL discovery and learned terms."""

from __future__ import annotations

from school_capture.learned_terms import is_useful_term, update_learned_terms
from school_capture.url_discovery import is_hub_page, score_url


def test_subject_url_scores_higher():
    hub = score_url(
        "https://school.example/page/?title=Subject+Curriculum+Overviews&pid=58",
        "Subject Curriculum Overviews",
    )
    subject = score_url(
        "https://school.example/page/?title=Maths&pid=95",
        "Maths",
    )
    assert subject >= hub
    assert subject >= 4


def test_learned_terms_boost():
    learned = {"maths": 3, "clubs": 2}
    base = score_url("https://school.example/clubs", "Clubs")
    boosted = score_url("https://school.example/clubs", "Clubs", learned_terms=learned)
    assert boosted > base


def test_is_hub_page():
    assert is_hub_page("/page/?title=Curriculum&pid=9", "Curriculum")
    assert not is_hub_page("/page/?title=Maths&pid=95", "Maths")


def test_update_learned_terms():
    store: dict[str, int] = {}
    update_learned_terms(
        store,
        url="https://school.example/page/?title=Maths&pid=95",
        anchor="Maths curriculum",
        area="curriculum",
        signal_count=3,
    )
    assert is_useful_term("maths")
    assert store.get("maths", 0) >= 1
