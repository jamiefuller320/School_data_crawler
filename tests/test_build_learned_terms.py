"""Tests for learned terms rebuild from capture index."""

from __future__ import annotations

import json
from pathlib import Path

from school_capture.learned_terms import build_from_capture_file


def test_build_learned_terms_from_capture_fixture(tmp_path: Path):
    capture = tmp_path / "capture.json"
    capture.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "areas": [
                            {
                                "area": "curriculum",
                                "signals": [
                                    {
                                        "sourceUrl": "https://school.example/page/?title=Maths&pid=1",
                                        "pageTitle": "Maths curriculum",
                                        "text": "Maths overview",
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    terms = build_from_capture_file(capture)
    assert "maths" in terms or any("math" in k for k in terms)
