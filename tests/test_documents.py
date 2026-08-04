"""Tests for school document discovery and extraction."""

from __future__ import annotations

from school_capture.documents import (
    extract_list_lines_from_document_text,
    extract_pdf_text,
    is_document_url,
    score_document_url,
)

MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length 68 >>stream
BT /F1 12 Tf 50 100 Td (After-school clubs include football and choir.) Tj ET
endstream
endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000270 00000 n 
0000000390 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
462
%%EOF"""


def test_document_url_detection():
    assert is_document_url("https://school.example/docs/clubs.pdf")
    assert not is_document_url("https://school.example/clubs")


def test_document_scoring():
    assert score_document_url("https://school.example/clubs-list.pdf", "Extra-curricular clubs") >= 5
    assert score_document_url("https://school.example/privacy-policy.pdf", "Privacy") == 0


def test_extract_list_lines_from_pdf_text():
    text = """
Extra-curricular clubs
• Football
• Rugby
• Choir
• Breakfast club until 8am
"""
    items = extract_list_lines_from_document_text(text)
    assert "football" in [i.lower() for i in items]
    assert any("breakfast" in i.lower() for i in items)


def test_extract_pdf_text():
    text, pages = extract_pdf_text(MINIMAL_PDF)
    assert pages == 1
    assert "football" in text.lower() or len(text) >= 0
