"""Tests for HTML parsing improvements."""

from __future__ import annotations

from school_capture.http_utils import normalize_url, parse_html


def test_parse_html_prefers_main_content():
    html = """
    <html><body>
    <nav>Home Admissions Letters Arbor management information system</nav>
    <main>
      <h1>Our curriculum</h1>
      <p>We provide a broad and balanced curriculum that is ambitious for all pupils.</p>
      <p>Pupils study reading, writing, maths and science across the school.</p>
    </main>
    <footer>We use cookies to improve your experience. Accept all cookies.</footer>
    </body></html>
  """
    parser = parse_html(html)
    text = parser.text.lower()
    assert "broad and balanced curriculum" in text
    assert "cookies" not in text
    assert "arbor management" not in text


def test_normalize_url_encodes_spaces_in_path():
    url = normalize_url(
        "/docs/Parents-Complete-Guide to the National Curriculum.pdf",
        "https://school.example",
    )
    assert url == (
        "https://school.example/docs/Parents-Complete-Guide%20to%20the%20National%20Curriculum.pdf"
    )
