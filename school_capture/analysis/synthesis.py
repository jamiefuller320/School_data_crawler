"""Parent-facing narrative synthesis with mandatory source citations."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import replace

from school_capture.models import QualitativeCaptureRecord, SubjectAreaAssessment

CORE_AREA_LABELS = {
    "curriculum": "Curriculum",
    "enrichment": "Enrichment & clubs",
    "ethos": "Ethos & values",
    "behaviour": "Behaviour & pastoral care",
    "send": "SEND & inclusion",
    "community": "Community & parents",
}

_CITATION_RE = re.compile(r"\[(\d+)\]")


def _coverage_id(area: SubjectAreaAssessment) -> str:
    signals = area.signals or []
    offerings = area.offerings or []
    confidence = area.confidence or 0.0
    if not signals and not offerings:
        return "none"
    if len(signals) >= 3 and confidence >= 0.55:
        return "rich"
    if signals or offerings:
        return "some"
    return "thin"


def _count_distinct_urls(signals) -> int:
    return len({s.sourceUrl for s in signals if s.sourceUrl})


def deterministic_parent_paragraph(area: SubjectAreaAssessment) -> str:
    """Build a parent-facing paragraph without an LLM (mirrors evidence prototype)."""
    offerings = area.offerings or []
    signals = area.signals or []
    label = CORE_AREA_LABELS.get(area.area, area.area)
    cov = _coverage_id(area)

    if cov == "none":
        return (
            f"We did not find much about {label.lower()} on the pages and documents "
            "scanned for this school. Worth asking on a visit or checking the school's "
            "website directly."
        )

    if len(offerings) >= 2:
        shown = ", ".join(offerings[:6])
        extra = f" and {len(offerings) - 6} more" if len(offerings) > 6 else ""
        corroboration = ""
        distinct = _count_distinct_urls(signals)
        if distinct >= 2:
            page_word = "page" if distinct == 1 else "pages"
            corroboration = f" Information appears across {distinct} {page_word}."
        return f"The school website lists {shown}{extra}.{corroboration}"

    if len(signals) == 1 and len(signals[0].text) < 120:
        text = signals[0].text
        if not text.lower().startswith("the "):
            text = text[0].lower() + text[1:] if text else text
        return (
            f"The school mentions {text}. See the source link below for the original page."
        )

    best = next((s for s in signals if len(s.text) > 60), signals[0] if signals else None)
    if best:
        return best.text

    if area.summary:
        return area.summary
    return f"Some material related to {label.lower()} was found on the school site."


def _numbered_sources(area: SubjectAreaAssessment) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for signal in area.signals or []:
        key = signal.sourceUrl or signal.text[:80]
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "text": signal.text[:400],
                "sourceUrl": signal.sourceUrl,
                "sourceType": signal.sourceType,
                "pageTitle": signal.pageTitle or "",
            }
        )
        if len(sources) >= 8:
            break
    return sources


def _valid_citations(text: str, source_count: int) -> bool:
    if source_count == 0:
        return "[" not in text
    refs = {int(m) for m in _CITATION_RE.findall(text)}
    if not refs:
        return False
    return all(1 <= n <= source_count for n in refs)


def _openai_chat(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout: int = 45,
) -> str:
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return str(body["choices"][0]["message"]["content"]).strip()


def llm_parent_paragraph(
    area: SubjectAreaAssessment,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
) -> str | None:
    """Return an LLM paragraph with [n] citations, or None on failure."""
    sources = _numbered_sources(area)
    if not sources and not (area.offerings or []):
        return None

    label = CORE_AREA_LABELS.get(area.area, area.area)
    offerings = area.offerings or []
    source_lines = []
    for i, src in enumerate(sources, start=1):
        title = src.get("pageTitle") or src.get("sourceUrl") or "source"
        excerpt = src.get("text", "")[:280]
        source_lines.append(f"[{i}] ({title}) {excerpt}")

    system = (
        "You write short, neutral paragraphs for parents comparing schools. "
        "Use only the supplied offerings and source excerpts — do not invent facts. "
        "Write 2–4 sentences in British English. "
        "Every factual claim must include at least one citation marker like [1] or [2] "
        "referring to the numbered sources. Do not use bullet lists."
    )
    user = (
        f"Focus area: {label}\n"
        f"Offerings: {', '.join(offerings[:12]) or '(none listed)'}\n"
        "Sources:\n"
        + "\n".join(source_lines)
        + "\n\nWrite one parent-facing paragraph."
    )

    try:
        text = _openai_chat(api_key=api_key, model=model, system=system, user=user)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError):
        return None

    if not text or len(text) < 40:
        return None
    if not _valid_citations(text, len(sources)):
        return None
    return text


def synthesize_area(
    area: SubjectAreaAssessment,
    *,
    use_llm: bool = False,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
) -> SubjectAreaAssessment:
    """Attach narrativeSummary and synthesisMethod to one area assessment."""
    narrative: str | None = None
    method: str | None = None

    if use_llm and api_key:
        narrative = llm_parent_paragraph(area, api_key=api_key, model=model)
        if narrative:
            method = "llm"

    if not narrative:
        narrative = deterministic_parent_paragraph(area)
        method = "deterministic"

    return replace(area, narrativeSummary=narrative, synthesisMethod=method)


def synthesize_record(
    record: QualitativeCaptureRecord,
    *,
    use_llm: bool = False,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
) -> QualitativeCaptureRecord:
    """Synthesize parent-facing narratives for all areas on a capture record."""
    key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
    areas = [
        synthesize_area(area, use_llm=use_llm, api_key=key, model=model)
        for area in record.areas
    ]
    return replace(record, areas=areas)
