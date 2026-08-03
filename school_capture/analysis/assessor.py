"""Value judgement engine over captured source text."""

from __future__ import annotations

import re
from collections import defaultdict

from school_capture.analysis.lexicons import AREA_LEXICONS, SECTION_TO_AREA
from school_capture.http_utils import extract_sentences, keyword_hits
from school_capture.models import (
    QualitativeSignal,
    SubjectArea,
    SubjectAreaAssessment,
    today_iso,
)
from school_capture.sources.base import RawCapture

MAX_SIGNALS_PER_AREA = 5


def assess_captures(captures: list[RawCapture]) -> list[SubjectAreaAssessment]:
    by_area: dict[SubjectArea, list[tuple[RawCapture, str]]] = defaultdict(list)

    for cap in captures:
        primary = SECTION_TO_AREA.get(cap.section or "", SubjectArea.ETHOS)
        for sentence in extract_sentences(cap.text):
            areas = _areas_for_sentence(sentence, primary)
            for area in areas:
                by_area[area].append((cap, sentence))

    assessments: list[SubjectAreaAssessment] = []
    for area in SubjectArea:
        pairs = by_area.get(area, [])
        assessments.append(_assess_area(area, pairs))
    return assessments


def _areas_for_sentence(sentence: str, primary: SubjectArea) -> set[SubjectArea]:
    lower = sentence.lower()
    hits: set[SubjectArea] = set()
    for area, groups in AREA_LEXICONS.items():
        all_kw = groups.get("breadth", ()) + groups.get("quality", ())
        if keyword_hits(lower, all_kw):
            hits.add(area)
    if not hits:
        hits.add(primary)
    return hits


def _assess_area(
    area: SubjectArea,
    pairs: list[tuple[RawCapture, str]],
) -> SubjectAreaAssessment:
    lex = AREA_LEXICONS[area]
    breadth_hits: set[str] = set()
    quality_hits: set[str] = set()
    source_types: set[str] = set()
    signals: list[QualitativeSignal] = []
    captured_at = today_iso()

    for cap, sentence in pairs:
        lower = sentence.lower()
        b = keyword_hits(lower, lex.get("breadth", ()))
        q = keyword_hits(lower, lex.get("quality", ()))
        if not b and not q:
            continue
        breadth_hits.update(b)
        quality_hits.update(q)
        source_types.add(cap.source_type)
        if len(signals) < MAX_SIGNALS_PER_AREA:
            signals.append(
                QualitativeSignal(
                    text=sentence,
                    sourceUrl=cap.url,
                    sourceType=cap.source_type,
                    capturedAt=captured_at,
                    pageTitle=cap.page_title,
                    section=cap.section,
                )
            )

    themes = sorted(breadth_hits | quality_hits)[:12]
    score = _compute_score(breadth_hits, quality_hits, len(pairs), len(source_types))
    confidence = _compute_confidence(len(signals), len(source_types), len(pairs))
    summary = _summarise(area, score, themes, len(signals))

    return SubjectAreaAssessment(
        area=area.value,
        score=score,
        confidence=confidence,
        summary=summary,
        themes=themes,
        signals=signals,
    )


def _compute_score(
    breadth: set[str],
    quality: set[str],
    sentence_count: int,
    source_diversity: int,
) -> int:
    raw = 0.0
    raw += min(len(breadth) * 6, 36)
    raw += min(len(quality) * 8, 32)
    raw += min(sentence_count * 2, 20)
    raw += min(source_diversity * 5, 12)
    return max(0, min(100, int(round(raw))))


def _compute_confidence(signals: int, source_types: int, candidates: int) -> float:
    if signals == 0:
        return 0.05
    base = 0.25 + min(signals, 5) * 0.1 + min(source_types, 3) * 0.08
    if candidates > 8:
        base += 0.05
    return round(min(0.95, base), 3)


def _summarise(area: SubjectArea, score: int, themes: list[str], signal_count: int) -> str:
    labels = {
        SubjectArea.CURRICULUM: "curriculum",
        SubjectArea.ENRICHMENT: "enrichment and extra-curricular activity",
        SubjectArea.ETHOS: "ethos and values",
        SubjectArea.BEHAVIOUR: "behaviour and pastoral care",
        SubjectArea.SEND: "SEND and inclusion",
        SubjectArea.COMMUNITY: "community and parental engagement",
    }
    label = labels[area]
    if signal_count == 0:
        return f"Little public evidence found about {label} from scanned sources."
    strength = "limited"
    if score >= 70:
        strength = "strong"
    elif score >= 45:
        strength = "moderate"
    theme_clause = ""
    if themes:
        shown = ", ".join(themes[:4])
        theme_clause = f" Themes include {shown}."
    return (
        f"{strength.capitalize()} publicly visible evidence for {label} "
        f"({signal_count} excerpt{'s' if signal_count != 1 else ''}).{theme_clause}"
    ).strip()


def dedupe_captures(captures: list[RawCapture]) -> list[RawCapture]:
    seen: set[str] = set()
    out: list[RawCapture] = []
    for cap in captures:
        key = re.sub(r"\s+", " ", cap.text[:200].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(cap)
    return out
