"""Blocklist and heuristics for navigation / junk list items."""

from __future__ import annotations

import re

from school_capture.offering_terms import (
    ACTIVITY_TERMS,
    CURRICULUM_SUBJECT_TERMS,
    PROVISION_TERMS,
)

NAV_LIST_LABELS: frozenset[str] = frozenset(
    {
        "home",
        "home page",
        "contact",
        "contact us",
        "admissions",
        "about us",
        "about",
        "news",
        "calendar",
        "parents",
        "parents & carers",
        "parents and carers",
        "parents info",
        "policies",
        "governors",
        "staff",
        "vacancies",
        "search",
        "login",
        "menu",
        "clubs",
        "curriculum",
        "send",
        "useful information",
        "absence reporting",
        "attendance information",
        "awards and recognition",
        "british values",
        "home learning",
        "school meals",
        "term dates",
    }
)

JUNK_LIST_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\.(jpg|jpeg|png|gif|pdf|docx?|xlsx?)$",
        r"^https?:",
        r"www\.",
        r"\.org\.uk",
        r"\.sch\.uk",
        r"policy\s+20\d{2}",
        r"admission(s)?\s+policy",
        r"^[a-z]$",
        r"[▼▾▸]",
        r"^both before school$",
        r"^after school$",
        r"^they ",
        r"^with a ",
        r"^of course$",
        r"^of course,",
        r"^website can",
        r"^meet our ",
        r"^see our ",
        r"https?:",
        r"clubspark",
        r"parents info",
        r"useful information",
        r"curriculum,",
        r"will cost £",
        r"£\d",
        r"^& activities",
        r"^run monday",
        r"^speaking$",
        r"^listening skills$",
        r"^staff$",
        r"^imagination$",
        r"^creativity$",
        r"^in years \d+",
    )
)


def is_nav_or_junk_list_item(item: str) -> bool:
    lower = re.sub(r"\s+", " ", item.lower()).strip()
    if not lower:
        return True
    if lower in NAV_LIST_LABELS:
        return True
    if any(p.search(item) for p in JUNK_LIST_PATTERNS):
        return True
    if "http" in lower or "www." in lower:
        return True
    # Menu breadcrumbs
    if " & " in item and any(x in lower for x in ("curriculum", "send", "information")):
        return True
    # Long items are usually sentences, not club labels
    if len(lower.split()) > 7:
        return True
    # Title-case menu labels without verbs (e.g. "Alver Valley Creative Hub" on its own can be ok,
    # but single generic words are not).
    if len(lower.split()) == 1 and lower not in {
        "football",
        "rugby",
        "netball",
        "choir",
        "cricket",
        "tennis",
        "dance",
        "drama",
        "art",
        "music",
        "chess",
        "coding",
    }:
        return len(lower) < 8
    return False


def is_thematic_heading(heading: str) -> bool:
    if not heading:
        return False
    blob = heading.lower()
    thematic = (
        "club",
        "sport",
        "music",
        "curriculum",
        "subject",
        "enrichment",
        "wraparound",
        "breakfast",
        "childcare",
        "after school",
        "send",
        "sen",
        "inclusion",
        "ethos",
        "values",
        "pastoral",
        "wellbeing",
        "community",
        "gcse",
        "option",
    )
    return any(t in blob for t in thematic)


def _term_in_text(term: str, text: str) -> bool:
    if " " in term or "-" in term:
        return term in text
    return bool(re.search(rf"\b{re.escape(term)}\b", text, re.I))


def is_plausible_list_offering(item: str) -> bool:
    """List items should look like club/subject/provision labels, not nav or prose."""
    if is_nav_or_junk_list_item(item):
        return False
    lower = item.lower()
    known = PROVISION_TERMS + ACTIVITY_TERMS + CURRICULUM_SUBJECT_TERMS
    if any(_term_in_text(term, lower) for term in known):
        # Still reject if it's clearly a long sentence despite containing a keyword
        if len(lower.split()) > 6:
            return False
        if any(p in lower for p in (" is called ", " of our ", " of personal ", " either ", " including ")):
            return False
        return True
    words = item.split()
    if not 1 <= len(words) <= 5:
        return False
    prose_markers = (" the ", " our ", " they ", " with ", " only ", " can ", " will ", " each ")
    if any(m in f" {lower} " for m in prose_markers):
        return False
    # Short title-case labels: "House Captain", "Climate Ambassador"
    if 1 <= len(words) <= 5:
        if words[0][:1].isupper() and all(
            w[:1].isupper() or w.lower() in {"and", "of", "&", "for"} for w in words
        ):
            return True
    return False


def filter_offerings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        item = raw.strip()
        if not item or not is_plausible_list_offering(item):
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
