"""Fetch binary document content with size limits."""

from __future__ import annotations

import http.client
import urllib.error
import urllib.request

from school_capture.http_utils import UA, polite_sleep

DEFAULT_MAX_BYTES = 8 * 1024 * 1024


def fetch_bytes(url: str, *, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[str, bytes] | None:
    try:
        polite_sleep()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            final = resp.geturl()
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                return None
            return final, raw
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        http.client.InvalidURL,
    ):
        return None
