"""Value judgement engine over captured source text."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from school_capture.analysis.lexicons import AREA_LEXICONS, SECTION_TO_AREA
from school_capture.analysis.specificity import (
    extract_offerings,
    is_meaningful_offering,
    passes_specificity_gate,
    specificity_score,
)
from school_capture.filters import (
    PageType,
    classify_page_type,
    has_school_context,
    is_blocked_sentence,
    page_type_confidence_multiplier,
)
from school_capture.list_filters import (
    filter_offerings,
    is_nav_or_junk_list_item,
    is_plausible_list_offering,
    is_thematic_heading,
)
from school_capture.html_sections import clean_list_item, infer_section_from_heading
from school_capture.http_utils import extract_sentences, keyword_hits
from school_capture.models import (
    QualitativeSignal,
    SubjectArea,
    SubjectAreaAssessment,
    today_iso,
)
from school_capture.sources.base import RawCapture, StructuredSection

MAX_SIGNALS_PER_AREA = 5
MIN_KEYWORD_HITS = 2
MIN_QUALITY_SIGNALS_FOR_SCORE = 2
HIGH_QUALITY_RELEVANCE = 5.0
MIN_SPECIFICITY_FOR_SIGNAL = 1.0
LIST_ITEM_RELEVANCE = 7.5


@dataclass
class _Candidate:
    cap: RawCapture
    sentence: str
    relevance: float
    specificity: float
    breadth_hits: list[str]
    quality_hits: list[str]
    offerings: list[str] = field(default_factory=list)
    page_type: PageType = PageType.SUBSTANTIVE
    from_list_item: bool = False


def assess_captures(captures: list[RawCapture]) -> list[SubjectAreaAssessment]:
    by_area: dict[SubjectArea, list[_Candidate]] = defaultdict(list)

    for cap in captures:
        page_type = _page_type_for_capture(cap)
        by_area = _ingest_structured_sections(cap, page_type, by_area)
        primary = SECTION_TO_AREA.get(cap.section or "", SubjectArea.ETHOS)
        for sentence in extract_sentences(cap.text):
            if is_blocked_sentence(sentence):
                continue
            if not has_school_context(sentence):
                continue
            areas = _areas_for_sentence(sentence, primary)
            for area in areas:
                if not passes_specificity_gate(sentence, area):
                    continue
                candidate = _score_sentence(cap, sentence, area, page_type)
                if candidate and candidate.relevance >= 2.5:
                    by_area[area].append(candidate)

    assessments: list[SubjectAreaAssessment] = []
    for area in SubjectArea:
        assessments.append(_assess_area(area, by_area.get(area, [])))
    return assessments


def _ingest_structured_sections(
    cap: RawCapture,
    page_type: PageType,
    by_area: dict[SubjectArea, list[_Candidate]],
) -> dict[SubjectArea, list[_Candidate]]:
    sections = cap.structured_sections or []
    for sec in sections:
        if sec.inferred_section == "general" and not is_thematic_heading(sec.heading):
            continue
        area = SECTION_TO_AREA.get(sec.inferred_section)
        if not area and is_thematic_heading(sec.heading):
            area = SECTION_TO_AREA.get(infer_section_from_heading(sec.heading))
        if not area:
            continue
        for item in sec.list_items:
            cand = _candidate_from_list_item(cap, sec, item, area, page_type)
            if cand:
                by_area[area].append(cand)
    # Page-level orphan list items: only on clearly thematic pages.
    page_area = SECTION_TO_AREA.get(cap.section or "")
    if page_area and cap.section not in ("general", "homepage"):
        for item in cap.list_items or []:
            if any(item in s.list_items for s in sections):
                continue
            cand = _candidate_from_list_item(
                cap,
                StructuredSection(heading="", inferred_section=cap.section or "general"),
                item,
                page_area,
                page_type,
            )
            if cand:
                by_area[page_area].append(cand)
    return by_area


def _candidate_from_list_item(
    cap: RawCapture,
    sec: StructuredSection,
    raw_item: str,
    area: SubjectArea,
    page_type: PageType,
) -> _Candidate | None:
    item = clean_list_item(raw_item)
    if not item or not is_plausible_list_offering(item):
        return None

    offerings = extract_offerings(item, area)
    if not offerings:
        offerings = [item]

    sentence = f"{sec.heading}: {item}" if sec.heading else item
    spec = specificity_score(item, area) + 2.0
    lex = AREA_LEXICONS[area]
    breadth = keyword_hits(item.lower(), lex.get("breadth", ()))
    quality = keyword_hits(item.lower(), lex.get("quality", ()))

    relevance = LIST_ITEM_RELEVANCE + min(len(offerings) * 1.5, 4.0)
    if sec.inferred_section and SECTION_TO_AREA.get(sec.inferred_section) == area:
        relevance += 2.0
    relevance *= page_type_confidence_multiplier(page_type, area.value)
    if relevance < 3.0:
        return None

    return _Candidate(
        cap=cap,
        sentence=sentence,
        relevance=relevance,
        specificity=spec,
        breadth_hits=breadth,
        quality_hits=quality,
        offerings=offerings,
        page_type=page_type,
        from_list_item=True,
    )


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

    offerings = extract_offerings(sentence, area)
    spec = specificity_score(sentence, area)

    relevance = 0.0
    relevance += len(breadth) * 1.2
    relevance += len(quality) * 1.5
    relevance += spec * 1.8
    relevance += min(len(offerings) * 1.5, 4.5)
    if cap.section and SECTION_TO_AREA.get(cap.section) == area:
        relevance += 2.0
    if has_school_context(sentence):
        relevance += 0.5
    relevance *= page_type_confidence_multiplier(page_type, area.value)

    if relevance < 2.5:
        return None
    if not offerings and spec < MIN_SPECIFICITY_FOR_SIGNAL and area in (
        SubjectArea.ETHOS,
        SubjectArea.SEND,
        SubjectArea.COMMUNITY,
    ):
        return None

    return _Candidate(
        cap=cap,
        sentence=sentence,
        relevance=relevance,
        specificity=spec,
        breadth_hits=breadth,
        quality_hits=quality,
        offerings=offerings,
        page_type=page_type,
    )


def _assess_area(area: SubjectArea, candidates: list[_Candidate]) -> SubjectAreaAssessment:
    captured_at = today_iso()
    ranked = sorted(
        candidates,
        key=lambda c: (
            -int(c.from_list_item),
            -(c.relevance + c.specificity),
            -len(c.offerings),
            c.sentence,
        ),
    )
    high_quality = [
        c
        for c in ranked
        if c.from_list_item
        or (c.relevance >= HIGH_QUALITY_RELEVANCE and c.specificity >= MIN_SPECIFICITY_FOR_SIGNAL)
    ]

    breadth_hits: set[str] = set()
    quality_hits: set[str] = set()
    offerings: list[str] = []
    offering_urls: dict[str, set[str]] = defaultdict(set)
    source_types: set[str] = set()
    source_urls: set[str] = set()
    signals: list[QualitativeSignal] = []

    pool = high_quality if len(high_quality) >= MIN_QUALITY_SIGNALS_FOR_SCORE else ranked

    for cand in pool:
        breadth_hits.update(cand.breadth_hits)
        quality_hits.update(cand.quality_hits)
        for item in cand.offerings:
            key = item.lower()
            if item not in offerings:
                offerings.append(item)
            offering_urls[key].add(cand.cap.url)
        source_types.add(cand.cap.source_type)
        source_urls.add(cand.cap.url)
        if len(signals) < MAX_SIGNALS_PER_AREA and (
            cand.from_list_item
            or cand.offerings
            or cand.specificity >= MIN_SPECIFICITY_FOR_SIGNAL
        ):
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

    offerings = filter_offerings(offerings)[:20]
    corroborated = sum(1 for o in offerings if len(offering_urls.get(o.lower(), set())) >= 2)
    themes = sorted(set(breadth_hits | quality_hits))[:12]
    score = _compute_score(
        breadth_hits,
        quality_hits,
        high_quality,
        offerings,
        len(source_urls),
        corroborated,
    )
    confidence = _compute_confidence(
        signals,
        high_quality,
        offerings,
        source_types,
        source_urls,
        corroborated,
    )
    summary = _summarise(
        area, score, themes, offerings, len(signals), len(high_quality), corroborated
    )

    return SubjectAreaAssessment(
        area=area.value,
        score=score,
        confidence=confidence,
        summary=summary,
        themes=themes,
        offerings=offerings,
        signals=signals,
    )


def _compute_score(
    breadth: set[str],
    quality: set[str],
    high_quality: list[_Candidate],
    offerings: list[str],
    distinct_urls: int,
    corroborated: int,
) -> int:
    list_items = sum(1 for c in high_quality if c.from_list_item)
    if len(high_quality) < MIN_QUALITY_SIGNALS_FOR_SCORE:
        if not high_quality and not offerings:
            return 0
        if offerings:
            raw = 25 + min(len(offerings) * 5, 45) + min(list_items * 4, 12)
            raw += min(corroborated * 5, 15)
            return min(82, int(round(raw)))
        return min(20, int(round(max((c.relevance for c in high_quality), default=0) * 3)))

    raw = 0.0
    raw += min(len(breadth) * 4, 22)
    raw += min(len(quality) * 5, 18)
    raw += min(len(high_quality) * 6, 18)
    raw += min(len(offerings) * 4, 22)
    raw += min(list_items * 3, 12)
    raw += min(distinct_urls * 3, 9)
    raw += min(corroborated * 4, 12)
    if high_quality:
        avg_spec = sum(c.specificity for c in high_quality) / len(high_quality)
        raw += min(avg_spec * 2, 8)
    return max(0, min(100, int(round(raw))))


def _compute_confidence(
    signals: list[QualitativeSignal],
    high_quality: list[_Candidate],
    offerings: list[str],
    source_types: set[str],
    source_urls: set[str],
    corroborated: int,
) -> float:
    if not signals and not offerings:
        return 0.05
    if len(high_quality) < MIN_QUALITY_SIGNALS_FOR_SCORE:
        base = 0.1 + min(len(offerings), 8) * 0.04 + min(len(signals), 4) * 0.03
        base += min(corroborated, 3) * 0.05
        return round(min(0.48, base), 3)

    base = 0.28
    base += min(len(high_quality), 5) * 0.06
    base += min(len(offerings), 10) * 0.035
    base += min(len(source_types), 3) * 0.05
    base += 0.08 if len(source_urls) >= 2 else 0.0
    base += min(corroborated, 4) * 0.04
    return round(min(0.94, base), 3)


def _summarise(
    area: SubjectArea,
    score: int,
    themes: list[str],
    offerings: list[str],
    signal_count: int,
    high_quality_count: int,
    corroborated: int,
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
    if signal_count == 0 and not offerings:
        return f"Little public evidence found about {label} from scanned sources."

    offering_clause = ""
    if offerings:
        shown = ", ".join(offerings[:8])
        suffix = "…" if len(offerings) > 8 else ""
        offering_clause = f" Listed provision includes {shown}{suffix}."
    corroboration_clause = ""
    if corroborated:
        corroboration_clause = f" {corroborated} item{'s' if corroborated != 1 else ''} corroborated across multiple pages."

    if high_quality_count < MIN_QUALITY_SIGNALS_FOR_SCORE:
        if offerings:
            return (
                f"Concrete {label} details found on the school website."
                f"{offering_clause}{corroboration_clause}"
            ).strip()
        return (
            f"Limited public evidence for {label} "
            f"({signal_count} excerpt{'s' if signal_count != 1 else ''}; "
            "mostly general statements rather than specific provision)."
        )

    strength = "limited"
    if score >= 65:
        strength = "strong"
    elif score >= 40:
        strength = "moderate"
    theme_clause = ""
    if themes and not offerings:
        shown = ", ".join(themes[:4])
        theme_clause = f" Themes include {shown}."
    return (
        f"{strength.capitalize()} publicly visible evidence for {label} "
        f"({high_quality_count} specific item"
        f"{'s' if high_quality_count != 1 else ''})."
        f"{offering_clause}{corroboration_clause}{theme_clause}"
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
