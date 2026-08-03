"""Tests for specificity detection and offering extraction."""

from __future__ import annotations

from school_capture.analysis.specificity import (
    extract_offerings,
    is_vague_claim,
    passes_specificity_gate,
)
from school_capture.models import SubjectArea


def test_vague_inclusive_claim_rejected():
    sentence = "We are an inclusive school where every child can thrive."
    assert is_vague_claim(sentence)
    assert not passes_specificity_gate(sentence, SubjectArea.ETHOS)


def test_concrete_clubs_extracted():
    sentence = (
        "After-school clubs include football, rugby, netball, choir, orchestra and drama club."
    )
    offerings = extract_offerings(sentence, SubjectArea.ENRICHMENT)
    assert "football" in offerings
    assert "choir" in offerings
    assert passes_specificity_gate(sentence, SubjectArea.ENRICHMENT)


def test_wraparound_care_detected():
    sentence = "We offer breakfast club and wraparound care until 5:30pm on weekdays."
    offerings = extract_offerings(sentence, SubjectArea.ENRICHMENT)
    assert any("breakfast" in o for o in offerings)
    assert any("wraparound" in o or "wrap-around" in o for o in offerings)


def test_curriculum_subjects_extracted():
    sentence = "GCSE options include art, drama, geography, history, French and computer science."
    offerings = extract_offerings(sentence, SubjectArea.CURRICULUM)
    assert "french" in offerings or "geography" in offerings
