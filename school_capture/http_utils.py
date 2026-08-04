"""Shared HTTP and HTML utilities (stdlib only)."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Iterable

UA = (
    "SchoolDataCrawler/0.1 (+https://github.com/jamiefuller320/School_data_crawler; "
    "schoolcompass.uk experimental qualitative capture)"
)

DEFAULT_TIMEOUT = 30
RATE_LIMIT_SECONDS = 0.75

SKIP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "iframe",
    }
)

MAIN_LANDMARK_TAGS = frozenset({"main", "article"})
MAIN_CLASS_HINTS = re.compile(
    r"(^|[\s_-])(main|content|page-body|entry-content|post-content|article)([\s_-]|$)",
    re.I,
)


def normalize_url(url: str, base: str | None = None) -> str | None:
    url = (url or "").strip()
    if not url or url.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    if base:
        url = urllib.parse.urljoin(base, url)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc:
        return None
    path = urllib.parse.quote(
        urllib.parse.unquote(parsed.path),
        safe="/%:@!$&'()*+,;=-._~",
    )
    return urllib.parse.urlunparse(parsed._replace(path=path, fragment=""))


def same_site(url: str, root: str) -> bool:
    a = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    b = urllib.parse.urlparse(root).netloc.lower().removeprefix("www.")
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def fetch_text(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str]:
    """Return (final_url, html_or_text)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        final = resp.geturl()
    for enc in ("utf-8", "latin-1"):
        try:
            return final, raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return final, raw.decode("utf-8", errors="replace")


def polite_sleep(seconds: float = RATE_LIMIT_SECONDS) -> None:
    time.sleep(seconds)


class _LinkTextParser(HTMLParser):
    """Extract links and text, skipping chrome and preferring main content."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self.title = ""
        self._all_parts: list[str] = []
        self._main_parts: list[str] = []
        self._skip_depth = 0
        self._main_depth = 0

    def _class_attr(self, attrs: list[tuple[str, str | None]]) -> str:
        return next((v or "" for k, v in attrs if k == "class"), "")

    def _role_attr(self, attrs: list[tuple[str, str | None]]) -> str:
        return next((v or "" for k, v in attrs if k == "role"), "")

    def _opens_main(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        if tag in MAIN_LANDMARK_TAGS:
            return True
        role = self._role_attr(attrs)
        if role in ("main", "article"):
            return True
        classes = self._class_attr(attrs)
        return bool(classes and MAIN_CLASS_HINTS.search(classes))

    def _closes_main(self, tag: str) -> bool:
        return tag in MAIN_LANDMARK_TAGS

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._opens_main(tag, attrs):
            self._main_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = next((v or "" for k, v in attrs if k == "href"), "")
            if href:
                self.links.append((href, ""))
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "td", "th", "div", "span"):
            self._all_parts.append(" ")
            if self._main_depth:
                self._main_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if self._closes_main(tag) and self._main_depth:
            self._main_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "td", "th", "div"):
            self._all_parts.append("\n")
            if self._main_depth:
                self._main_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        self._all_parts.append(data)
        if self._main_depth:
            self._main_parts.append(data)

    def _normalise(self, parts: list[str]) -> str:
        raw = "".join(parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{2,}", "\n", raw)
        return raw.strip()

    @property
    def text(self) -> str:
        main = self._normalise(self._main_parts)
        if len(main) >= 120:
            return main
        return self._normalise(self._all_parts)


def parse_html(html: str) -> _LinkTextParser:
    parser = _LinkTextParser()
    parser.feed(html)
    return parser


def extract_sentences(text: str, min_len: int = 40, max_len: int = 320) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for chunk in chunks:
        s = re.sub(r"\s+", " ", chunk).strip()
        if min_len <= len(s) <= max_len:
            out.append(s)
    return out


def keyword_hits(text: str, keywords: Iterable[str]) -> list[str]:
    lower = text.lower()
    return sorted({kw for kw in keywords if kw in lower})


def slug_words(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", value.lower()) if len(w) > 2}


def link_matches(link_text: str, href: str, patterns: Iterable[str]) -> bool:
    blob = f"{link_text} {href}".lower()
    return any(p in blob for p in patterns)


def safe_fetch(url: str) -> tuple[str | None, str | None]:
    try:
        polite_sleep()
        final, body = fetch_text(url)
        return final, body
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None, None
