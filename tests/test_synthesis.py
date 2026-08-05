"""Tests for parent-facing narrative synthesis."""

from __future__ import annotations

from unittest.mock import patch

from school_capture.analysis.synthesis import (
    deterministic_parent_paragraph,
    llm_parent_paragraph,
    synthesize_area,
    synthesize_record,
)
from school_capture.models import (
    QualitativeCaptureRecord,
    QualitativeSignal,
    SubjectAreaAssessment,
)


def _area(**kwargs) -> SubjectAreaAssessment:
  defaults = dict(
      area="enrichment",
      score=50,
      confidence=0.6,
      summary="Clubs and activities.",
      themes=["clubs"],
      offerings=["football", "choir", "homework club"],
      signals=[
          QualitativeSignal(
              text="After-school clubs include football and choir.",
              sourceUrl="https://school.example/clubs",
              sourceType="school-website",
              capturedAt="2026-08-05",
          ),
          QualitativeSignal(
              text="Breakfast club runs from 7:45am.",
              sourceUrl="https://school.example/wraparound",
              sourceType="school-website",
              capturedAt="2026-08-05",
          ),
      ],
  )
  defaults.update(kwargs)
  return SubjectAreaAssessment(**defaults)


def test_deterministic_lists_offerings():
    text = deterministic_parent_paragraph(_area())
    assert "football" in text
    assert "choir" in text


def test_deterministic_empty_area():
    text = deterministic_parent_paragraph(
        _area(offerings=[], signals=[], confidence=0.0, score=0)
    )
    assert "did not find much" in text.lower()


def test_synthesize_area_without_key_uses_deterministic():
    out = synthesize_area(_area(), use_llm=True, api_key=None)
    assert out.narrativeSummary
    assert out.synthesisMethod == "deterministic"


@patch("school_capture.analysis.synthesis._openai_chat")
def test_synthesize_area_uses_llm_when_valid(mock_chat):
    mock_chat.return_value = (
        "The school offers football and choir after school [1], with breakfast club from 7:45am [2]."
    )
    out = synthesize_area(_area(), use_llm=True, api_key="test-key")
    assert out.synthesisMethod == "llm"
    assert "[1]" in out.narrativeSummary


@patch("school_capture.analysis.synthesis._openai_chat")
def test_llm_rejects_missing_citations(mock_chat):
    mock_chat.return_value = "The school has many clubs and activities."
    assert llm_parent_paragraph(_area(), api_key="test-key") is None


def test_synthesize_record_attaches_all_areas():
    record = QualitativeCaptureRecord(
        urn="116338",
        name="Test School",
        assessedAt="2026-08-05",
        areas=[_area(), _area(area="curriculum", offerings=["maths", "english"])],
    )
    out = synthesize_record(record, use_llm=False)
    assert len(out.areas) == 2
    assert all(a.narrativeSummary for a in out.areas)
    payload = out.to_dict()
    assert payload["areas"][0]["narrativeSummary"]
