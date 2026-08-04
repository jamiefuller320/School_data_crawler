"""Detect vague marketing claims vs concrete, listable school offerings."""

from __future__ import annotations

import re

from school_capture.list_filters import is_nav_or_junk_list_item
from school_capture.models import SubjectArea

# Unevidenced marketing language — low evidential merit on its own.
VAGUE_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bwe are (an? )?inclusive\b",
        r"\bwe are (a |an )?(caring|happy|proud|welcoming)\b",
        r"\b(inclusive|welcoming) school\b",
        r"\b(immensely|very) proud\b",
        r"\bvalues?[- ]driven\b",
        r"\bhope that you and your child\b",
        r"\bhappy place to (learn|be)\b",
        r"\bspecial place to\b",
        r"\bbig heart\b",
        r"\bevery child can (thrive|achieve|succeed|flourish)\b",
        r"\bstrive (to be|for) (the )?best\b",
        r"\bthe very best they can be\b",
        r"\bnurturing (environment|community)\b",
        r"\bcaring community\b",
        r"\bwide opportunities\b",
        r"\bhigh quality.{0,30}education\b",
        r"\bcelebrating achievement\b",
        r"\bbuilding the future\b",
    )
)

# Concrete provision parents can verify or ask about.
PROVISION_TERMS: tuple[str, ...] = (
    "breakfast club",
    "after-school club",
    "after school club",
    "wraparound care",
    "wrap-around care",
    "wrap around care",
    "after-school care",
    "after school care",
    "holiday club",
    "holiday provision",
    "extended day",
    "early birds",
    "late stay",
    "childcare",
    "homework club",
    "study support",
)

ACTIVITY_TERMS: tuple[str, ...] = (
    "football",
    "rugby",
    "netball",
    "hockey",
    "cricket",
    "athletics",
    "swimming",
    "gymnastics",
    "dance",
    "ballet",
    "choir",
    "orchestra",
    "band",
    "music",
    "drama",
    "theatre",
    "art club",
    "chess",
    "coding",
    "robotics",
    "debate",
    "gardening",
    "cooking",
    "science club",
    "languages club",
    "french club",
    "spanish club",
    "stem club",
    "library club",
    "running club",
    "cross country",
    "tennis",
    "badminton",
    "basketball",
    "volleyball",
    "table tennis",
    "karate",
    "judo",
    "fencing",
    "archery",
    "sailing",
    "rowing",
    "cadets",
    "duke of edinburgh",
    "young leaders",
    "school council",
    "eco club",
    "photography",
)

CURRICULUM_SUBJECT_TERMS: tuple[str, ...] = (
    "english",
    "mathematics",
    "maths",
    "science",
    "biology",
    "chemistry",
    "physics",
    "history",
    "geography",
    "french",
    "spanish",
    "german",
    "latin",
    "computer science",
    "computing",
    "design technology",
    "food technology",
    "religious education",
    "pshe",
    "citizenship",
    "art",
    "music",
    "drama",
    "pe",
    "physical education",
)

LIST_SPLIT = re.compile(r",|;|/|\band\b|\bor\b|•|·", re.I)
TIME_PATTERN = re.compile(
    r"\b\d{1,2}(:\d{2})?\s?(am|pm)\b|\buntil\s+\d|\bfrom\s+\d{1,2}",
    re.I,
)
DAY_PATTERN = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekday|daily)\b",
    re.I,
)

AREA_OFFERING_TERMS: dict[SubjectArea, tuple[str, ...]] = {
    SubjectArea.ENRICHMENT: PROVISION_TERMS + ACTIVITY_TERMS,
    SubjectArea.CURRICULUM: CURRICULUM_SUBJECT_TERMS
    + ("gcse", "a-level", "a level", "options", "btec"),
    SubjectArea.COMMUNITY: (
        "pta",
        "friends of",
        "parent forum",
        "open day",
        "parents evening",
        "workshop",
        "coffee morning",
    ),
    SubjectArea.SEND: (
        "senco",
        "ehcp",
        "speech and language",
        "occupational therapy",
        "nurture group",
        "sensory room",
        "1:1 support",
        "one to one support",
    ),
    SubjectArea.BEHAVIOUR: (
        "pastoral team",
        "school counsellor",
        "mentoring",
        "buddy system",
        "house system",
    ),
    SubjectArea.ETHOS: (
        "worship",
        "assembly",
        "house system",
        "charity",
        "fundraising",
        "volunteering",
    ),
}

# Areas where generic value statements are especially unhelpful.
STRICT_SPECIFICITY_AREAS = frozenset(
    {SubjectArea.ETHOS, SubjectArea.SEND, SubjectArea.COMMUNITY}
)


def is_vague_claim(sentence: str) -> bool:
    return any(p.search(sentence) for p in VAGUE_CLAIM_PATTERNS)


def has_concrete_detail(sentence: str, area: SubjectArea | None = None) -> bool:
    offerings = [o for o in extract_offerings(sentence, area) if _is_meaningful_offering(o)]
    if offerings:
        return True
    if TIME_PATTERN.search(sentence) or DAY_PATTERN.search(sentence):
        return True
    if sentence.count(",") >= 2 and _has_list_like_content(sentence):
        return True
    if re.search(r"\b(including|such as|for example|e\.g\.)\b", sentence, re.I):
        return True
    return False


def extract_offerings(sentence: str, area: SubjectArea | None = None) -> list[str]:
    lower = sentence.lower()
    found: list[str] = []

    terms = list(PROVISION_TERMS + ACTIVITY_TERMS + CURRICULUM_SUBJECT_TERMS)
    if area and area in AREA_OFFERING_TERMS:
        terms = list(AREA_OFFERING_TERMS[area]) + terms

    for term in sorted(set(terms), key=len, reverse=True):
        if _term_in_text(term, lower) and term not in found:
            found.append(term)

    # Parse simple inline lists: "clubs include football, rugby and netball"
    list_intro = re.search(
        r"\b(clubs?|activities|subjects?|options?|provision|include[sd]?|offer(?:s|ed)?)"
        r"\s*[:\-]?\s*(.+)$",
        sentence,
        re.I,
    )
    if list_intro:
        tail = list_intro.group(2)
        for part in LIST_SPLIT.split(tail):
            item = _clean_offering(part)
            if item and len(item) >= 3 and item not in found:
                found.append(item)

    # Comma-separated runs of short noun phrases (e.g. "art, drama, music and sport")
    if sentence.count(",") >= 2:
        for part in LIST_SPLIT.split(sentence):
            item = _clean_offering(part)
            if item and 3 <= len(item) <= 40 and _looks_like_offering(item):
                if item not in found:
                    found.append(item)

    return _dedupe_offerings([o for o in found if _is_meaningful_offering(o)])[:12]


def _term_in_text(term: str, text: str) -> bool:
    if " " in term or "-" in term:
        return term in text
    return bool(re.search(rf"\b{re.escape(term)}\b", text, re.I))


def _has_list_like_content(sentence: str) -> bool:
    parts = [_clean_offering(p) for p in LIST_SPLIT.split(sentence)]
    valid = [p for p in parts if _is_meaningful_offering(p)]
    return len(valid) >= 2


def is_meaningful_offering(item: str) -> bool:
    if is_nav_or_junk_list_item(item):
        return False
    return _is_meaningful_offering(item)


def _is_meaningful_offering(item: str) -> bool:
    if not item or len(item) < 3 or len(item) > 45:
        return False
    blocked_fragments = (
        "across the",
        "where every",
        "our school",
        "all pupils",
        "the school",
        "we ",
        "your child",
        "enjoy being",
        "between ",
        "including an",
        "including a",
        "operates between",
        "at maple",
        "pm at",
    )
    lower = item.lower()
    if re.match(r"^\d", lower):
        return False
    if any(b in lower for b in blocked_fragments):
        return False
    return _looks_like_offering(lower)


def specificity_score(sentence: str, area: SubjectArea) -> float:
    offerings = extract_offerings(sentence, area)
    score = 0.0
    score += min(len(offerings) * 1.5, 6.0)
    if TIME_PATTERN.search(sentence) or DAY_PATTERN.search(sentence):
        score += 1.5
    if sentence.count(",") >= 2:
        score += 1.0
    if re.search(r"\b(including|such as|for example)\b", sentence, re.I):
        score += 1.0

    if is_vague_claim(sentence):
        score -= 3.0
    if area in STRICT_SPECIFICITY_AREAS and not offerings:
        score -= 1.5

    return score


def passes_specificity_gate(sentence: str, area: SubjectArea) -> bool:
    spec = specificity_score(sentence, area)
    if is_vague_claim(sentence) and not has_concrete_detail(sentence, area):
        return False
    if area in STRICT_SPECIFICITY_AREAS:
        return spec >= 1.0 or bool(extract_offerings(sentence, area))
    # Enrichment/curriculum: allow moderate specificity if not purely vague
    if area in (SubjectArea.ENRICHMENT, SubjectArea.CURRICULUM):
        return spec >= 0.5 or not is_vague_claim(sentence)
    return spec >= 0.0 or not is_vague_claim(sentence)


def _clean_offering(value: str) -> str:
    item = re.sub(r"^[\s\-–•·]+", "", value.strip())
    item = re.sub(r"[\s\.]+$", "", item)
    item = re.sub(r"^(our|the|a|an)\s+", "", item, flags=re.I)
    return item.lower()


def _looks_like_offering(item: str) -> bool:
    if not item or len(item) < 3:
        return False
    blocked = (
        "we ",
        "our ",
        "pupils",
        "children",
        "school",
        "learning",
        "opportunities",
        "experience",
        "welcome",
    )
    return not any(item.startswith(b) for b in blocked)


def _dedupe_offerings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out
