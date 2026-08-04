"""Parse contact information from school website HTML."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import unquote

from school_capture.contact_models import ContactEntry, CONTACT_SOURCE_TYPES

UK_PHONE = re.compile(
    r"(?:\+44\s?|0)(?:\d[\s\-().]?){9,12}\d"
)
EMAIL = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

ROLE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("headteacher", ("headteacher", "head teacher", "executive head", "principal", "head of school")),
    ("senco", ("senco", "sen co", "send co", "special educational needs co", "inclusion lead")),
    ("office", ("school office", "main office", "reception", "admin office", "enquiries", "contact us")),
    ("admissions", ("admissions", "admission")),
    ("safeguarding", ("safeguarding", "designated safeguarding", "dsl")),
    ("governor", ("chair of governors", "governor", "governing body")),
)

BLOCKED_EMAIL_DOMAINS = frozenset(
    {
        "example.com",
        "sentry.io",
        "w3.org",
        "schema.org",
        "google.com",
        "facebook.com",
    }
)

LABEL_SPLIT = re.compile(r"\s*[:\-–|]\s*")

BLOCKED_CONTACT_LABELS = frozenset(
    {
        "website menu",
        "school history",
        "click here",
        "read more",
        "home",
        "menu",
    }
)


def is_junk_contact_text(text: str) -> bool:
    lower = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not lower or lower in BLOCKED_CONTACT_LABELS:
        return True
    if re.search(r"[a-z][A-Z]", text or "") and " " not in text:
        return True
    return False


@dataclass
class ParsedContacts:
    entries: list[ContactEntry] = field(default_factory=list)


def infer_role(text: str) -> str:
    blob = re.sub(r"\s+", " ", (text or "").lower()).strip()
    for role, patterns in ROLE_PATTERNS:
        if any(p in blob for p in patterns):
            return role
    return "other"


def infer_role_from_email(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    if any(t in local for t in ("senco", "send", "sen.", "sen-")):
        return "senco"
    if any(t in local for t in ("admission", "admissions")):
        return "admissions"
    if any(t in local for t in ("office", "admin", "reception", "enquir")):
        return "office"
    if any(t in local for t in ("head", "principal")):
        return "headteacher"
    if "safeguard" in local:
        return "safeguarding"
    return "other"


def normalize_phone(raw: str) -> str | None:
    value = re.sub(r"[^\d+]", "", (raw or "").strip())
    if not value:
        return None
    if value.startswith("44") and not value.startswith("+"):
        value = "+" + value
    digits = re.sub(r"\D", "", value)
    if len(digits) < 10 or len(digits) > 15:
        return None
    return raw.strip()


def normalize_email(raw: str) -> str | None:
    email = (raw or "").strip().lower()
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[-1]
    if domain in BLOCKED_EMAIL_DOMAINS:
        return None
    if email.endswith((".png", ".jpg", ".gif", ".svg")):
        return None
    return email


def _person_name_from_label(label: str) -> str | None:
    cleaned = LABEL_SPLIT.split(label, maxsplit=1)[-1].strip()
    if not cleaned or "@" in cleaned or re.search(r"\d{5,}", cleaned):
        return None
    words = cleaned.split()
    if not 2 <= len(words) <= 5:
        return None
    if not all(w[:1].isupper() for w in words if w.lower() not in {"de", "van", "von", "mc"}):
        return None
    if infer_role(cleaned) != "other" and len(words) <= 3:
        return None
    return cleaned


class _ContactHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entries: list[dict[str, str]] = []
        self._pending_dt: str | None = None
        self._cell_label: str | None = None
        self._in_script = False
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self._in_script = True
            return
        if tag == "a":
            href = next((v or "" for k, v in attrs if k == "href"), "")
            if href.startswith("mailto:"):
                email = normalize_email(unquote(href[7:].split("?")[0]))
                if email:
                    self.entries.append({"email": email, "label": ""})
            elif href.startswith("tel:"):
                phone = normalize_phone(unquote(href[4:].split("?")[0]))
                if phone:
                    self.entries.append({"phone": phone, "label": ""})
        if tag in ("td", "th"):
            self._cell_label = None

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False
        if tag == "dt":
            self._pending_dt = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
            self._text_parts = []
        elif tag == "dd" and self._pending_dt:
            value = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
            self._text_parts = []
            if value:
                self.entries.append({"label": self._pending_dt, "value": value})
            self._pending_dt = None
        elif tag in ("p", "li", "td", "div", "span"):
            text = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
            self._text_parts = []
            if text and len(text) <= 240:
                self.entries.append({"text": text, "label": self._cell_label or ""})
            self._cell_label = None

    def handle_data(self, data: str) -> None:
        if self._in_script:
            chunk = data.strip()
            if chunk.startswith("{") and "schema.org" in chunk:
                self._parse_json_ld(chunk)
            return
        if data.strip():
            self._text_parts.append(data)

    def _parse_json_ld(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            self._walk_json_ld(node)

    def _walk_json_ld(self, node: dict) -> None:
        if node.get("@type") in ("School", "Organization", "EducationalOrganization"):
            phone = node.get("telephone")
            email = node.get("email")
            if phone:
                self.entries.append({"phone": str(phone), "label": "schema.org"})
            if email:
                self.entries.append({"email": str(email), "label": "schema.org"})
        for cp in node.get("contactPoint") or []:
            if isinstance(cp, dict):
                self._walk_json_ld(cp)
        if node.get("@type") == "ContactPoint":
            phone = node.get("telephone")
            email = node.get("email")
            label = str(node.get("contactType") or node.get("name") or "")
            if phone:
                self.entries.append({"phone": str(phone), "label": label})
            if email:
                self.entries.append({"email": str(email), "label": label})


def parse_contact_html(
    html: str,
    *,
    source_url: str,
    source_type: str,
    captured_at: str,
) -> list[ContactEntry]:
    if source_type not in CONTACT_SOURCE_TYPES:
        source_type = "school-website"

    parser = _ContactHTMLParser()
    parser.feed(html)
    out: list[ContactEntry] = []
    seen: set[tuple[str, str, str]] = set()

    def add(
        *,
        role: str,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        label: str | None = None,
    ) -> None:
        email_n = normalize_email(email) if email else None
        phone_n = normalize_phone(phone) if phone else None
        if not any((name, email_n, phone_n)):
            return
        if name and is_junk_contact_text(name):
            name = None
        if label and is_junk_contact_text(label):
            label = None
        if not any((name, email_n, phone_n)):
            return
        key = (role, email_n or "", phone_n or "")
        if key in seen:
            return
        seen.add(key)
        out.append(
            ContactEntry(
                role=role,
                name=name,
                email=email_n,
                phone=phone_n,
                label=label,
                sourceType=source_type,
                sourceUrl=source_url,
                capturedAt=captured_at,
            )
        )

    for raw in parser.entries:
        if "email" in raw:
            label = raw.get("label") or ""
            email = raw["email"]
            role = infer_role(label)
            if role == "other":
                role = infer_role_from_email(email)
            add(role=role, email=email, label=label or None)
        elif "phone" in raw:
            label = raw.get("label") or ""
            add(role=infer_role(label), phone=raw["phone"], label=label or None)
        elif "label" in raw and "value" in raw:
            label = raw["label"]
            value = raw["value"]
            role = infer_role(label)
            email_m = EMAIL.search(value)
            phone_m = UK_PHONE.search(value)
            name = _person_name_from_label(value) if role != "other" else None
            if not name and role == "other":
                name = _person_name_from_label(label)
            add(
                role=role,
                name=name,
                email=email_m.group(0) if email_m else None,
                phone=phone_m.group(0) if phone_m else None,
                label=label,
            )
        elif "text" in raw:
            text = raw["text"]
            label = raw.get("label") or ""
            role = infer_role(f"{label} {text}")
            if ":" in text and len(text) < 120:
                left, right = LABEL_SPLIT.split(text, maxsplit=1)
                role = infer_role(left) if infer_role(left) != "other" else role
                text = right
            email_m = EMAIL.search(text)
            phone_m = UK_PHONE.search(text)
            name = _person_name_from_label(text)
            if email_m or phone_m or name:
                add(
                    role=role,
                    name=name,
                    email=email_m.group(0) if email_m else None,
                    phone=phone_m.group(0) if phone_m else None,
                    label=label or None,
                )

    return out


def dedupe_contacts(entries: list[ContactEntry]) -> list[ContactEntry]:
    """Prefer earlier (higher-trust) entries; merge name onto email/phone rows."""
    by_key: dict[tuple[str, str, str], ContactEntry] = {}
    order: list[tuple[str, str, str]] = []
    for entry in entries:
        key = (
            entry.role,
            (entry.email or "").lower(),
            re.sub(r"\D", "", entry.phone or ""),
        )
        if key not in by_key:
            by_key[key] = entry
            order.append(key)
            continue
        prev = by_key[key]
        if not prev.name and entry.name:
            prev.name = entry.name
        if not prev.label and entry.label:
            prev.label = entry.label
    return [by_key[k] for k in order]
