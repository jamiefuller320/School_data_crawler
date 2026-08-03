"""Value judgement engine over captured source text."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from school_capture.analysis.lexicons import AREA_LEXICONS, SECTION_TO_AREA
from school_capture.filters import (
    PageType,
    classify_page_type,
    has_school_context,
    is_blocked_sentence,
    page_type_confidence_multiplier,
)
from school_capture.http_utils import extract_sentences, keyword_hits
from school_capture.models import (
    QualitativeSignal,
    SubjectArea,
    SubjectAreaAssessment,
    today_iso,
)
from school_capture.sources.base import RawCapture

MAX_SIGNALS_PER_AREA = 5
MIN_KEYWORD_HITS = 2
MIN_QUALITY_SIGNALS_FOR_SCORE = 2
HIGH_QUALITY_RELEVANCE = 4.0


@dataclass
class _Candidate:
    cap: RawCapture
    sentence: str
    relevance: float
    breadth_hits: list[str]
    quality_hits: list[str]
    page_type: PageType


def assess_captures(captures: list[RawCapture]) -> list[SubjectAreaAssessment]:
    by_area: dict[SubjectArea, list[_Candidate]] = defaultdict(list)

    for cap in captures:
        page_type = _page_type_for_capture(cap)
        primary = SECTION_TO_AREA.get(cap.section or "", SubjectArea.ETHOS)
        for sentence in extract_sentences(cap.text):
            if is_blocked_sentence(sentence):
                continue
            if not has_school_context(sentence):
                continue
            areas = _areas_for_sentence(sentence, primary)
            for area in areas:
                candidate = _score_sentence(cap, sentence, area, page_type)
                if candidate and candidate.relevance >= 2.0:
                    by_area[area].append(candidate)

    assessments: list[SubjectAreaAssessment] = []
    for area in SubjectArea:
        assessments.append(_assess_area(area, by_area.get(area, [])))
    return assessments


def _page_type_for_capture(cap: RawCapture) -> PageType:
    raw = (cap.meta or {}).get("pageType")
    if raw:
        try:
            return PageType(raw)
        except ValueError:
            pass
    return classify_page_type(cap.url, cap.page_title or "")


def _areas_for_sentence(sentence: str, primary: SubjectArea) -> set[SubjectArea]:
    lower = sentence.lower()
    hits: set[SubjectArea] = set()
    for area, groups in AREA_LEXICONS.items():
        all_kw = groups.get("breadth", ()) + groups.get("quality", ())
        matched = keyword_hits(lower, all_kw)
        if len(matched) >= MIN_KEYWORD_HITS:
            hits.add(area)
    if not hits and primary:
        # Only assign to primary section when sentence has some topical hint.
        primary_kw = AREA_LEXICONS[primary].get("breadth", ()) + AREA_LEXICONS[
            primary
        ].get("quality", ())
        if len(keyword_hits(lower, primary_kw)) >= 1:
            hits.add(primary)
    return hits


def _score_sentence(
    cap: RawCapture,
    sentence: str,
    area: SubjectArea,
    page_type: PageType,
) -> _Candidate | None:
    lex = AREA_LEXICONS[area]
    lower = sentence.lower()
    breadth = keyword_hits(lower, lex.get("breadth", ()))
    quality = keyword_hits(lower, lex.get("quality", ()))
    if len(breadth) + len(quality) < MIN_KEYWORD_HITS:
        return None

    relevance = 0.0
    relevance += len(breadth) * 1.5
    relevance += len(quality) * 2.0
    if cap.section and SECTION_TO_AREA.get(cap.section) == area:
        relevance += 2.0
    if has_school_context(sentence):
        relevance += 1.0
    relevance *= page_type_confidence_multiplier(page_type, area.value)

    if relevance < 2.0:
        return None

    return _Candidate(
        cap=cap,
        sentence=sentence,
        relevance=relevance,
        breadth_hits=breadth,
        quality_hits=quality,
        page_type=page_type,
    )


def _assess_area(area: SubjectArea, candidates: list[_Candidate]) -> SubjectAreaAssessment:
    captured_at = today_iso()
    ranked = sorted(candidates, key=lambda c: (-c.relevance, c.sentence))
    high_quality = [c for c in ranked if c.relevance >= HIGH_QUALITY_RELEVANCE]

    breadth_hits: set[str] = set()
    quality_hits: set[str] = set()
    source_types: set[str] = set()
    source_urls: set[str] = set()
    signals: list[QualitativeSignal] = []

    pool = high_quality if len(high_quality) >= MIN_QUALITY_SIGNALS_FOR_SCORE else ranked

    for cand in pool:
        breadth_hits.update(cand.breadth_hits)
        quality_hits.update(cand.quality_hits)
        source_types.add(cand.cap.source_type)
        source_urls.add(cand.cap.url)
        if len(signals) < MAX_SIGNALS_PER_AREA:
            signals.append(
                QualitativeSignal(
                    text=cand.sentence,
                    sourceUrl=cand.cap.url,
                    sourceType=cand.cap.source_type,
                    capturedAt=captured_at,
                    pageTitle=cand.cap.page_title,
                    section=cand.cap.section,
                )
            )

    themes = sorted(breadth_hits | quality_hits)[:12]
    score = _compute_score(
        breadth_hits,
        quality_hits,
        high_quality,
        len(source_urls),
    )
    confidence = _compute_confidence(
        signals,
        high_quality,
        source_types,
        source_urls,
    )
    summary = _summarise(area, score, themes, len(signals), len(high_quality))

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
    high_quality: list[_Candidate],
    distinct_urls: int,
) -> int:
    if len(high_quality) < MIN_QUALITY_SIGNALS_FOR_SCORE:
        # Cap low when evidence is thin or weak.
        if not high_quality:
            return 0
        return min(25, int(round(max(c.relevance for c in high_quality) * 4)))

    raw = 0.0
    raw += min(len(breadth) * 5, 30)
    raw += min(len(quality) * 7, 28)
    raw += min(len(high_quality) * 8, 24)
    raw += min(distinct_urls * 4, 12)
    avg_rel = sum(c.relevance for c in high_quality) / len(high_quality)
    raw += min(avg_rel * 2, 10)
    return max(0, min(100, int(round(raw))))


def _compute_confidence(
    signals: list[QualitativeSignal],
    high_quality: list[_Candidate],
    source_types: set[str],
    source_urls: set[str],
) -> float:
    if not signals:
        return 0.05
    if len(high_quality) < MIN_QUALITY_SIGNALS_FOR_SCORE:
        return round(min(0.35, 0.1 + len(signals) * 0.05), 3)

    base = 0.3
    base += min(len(high_quality), 5) * 0.08
    base += min(len(source_types), 3) * 0.06
    base += 0.08 if len(source_urls) >= 2 else 0.0
    return round(min(0.92, base), 3)


def _summarise(
    area: SubjectArea,
    score: int,
    themes: list[str],
    signal_count: int,
    high_quality_count: int,
) -> str:
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
    if high_quality_count < MIN_QUALITY_SIGNALS_FOR_SCORE:
        return (
            f"Limited public evidence for {label} "
            f"({signal_count} excerpt{'s' if signal_count != 1 else ''}; "
            "insufficient for a confident assessment)."
        )

    strength = "limited"
    if score >= 65:
        strength = "strong"
    elif score >= 40:
        strength = "moderate"
    theme_clause = ""
    if themes:
        shown = ", ".join(themes[:4])
        theme_clause = f" Themes include {shown}."
    return (
        f"{strength.capitalize()} publicly visible evidence for {label} "
        f"({high_quality_count} high-quality excerpt"
        f"{'s' if high_quality_count != 1 else ''}).{theme_clause}"
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
