"""Tests for navigation/junk list item filters."""

from __future__ import annotations

from school_capture.list_filters import (
    is_nav_or_junk_list_item,
    is_plausible_list_offering,
)


def test_rejects_nav_and_files():
    assert is_nav_or_junk_list_item("Home")
    assert is_nav_or_junk_list_item("PICA0191.jpg")
    assert is_nav_or_junk_list_item("Admission Policy 2026 27")
    assert is_nav_or_junk_list_item("https://clubspark.lta.org.uk")
    assert not is_nav_or_junk_list_item("Football (Years 3–6)")


def test_plausible_offerings():
    assert not is_plausible_list_offering("Curriculum, useful information & SEND")
    assert not is_plausible_list_offering("website can only tell part of our story")
    assert is_plausible_list_offering("Football (Years 3–6)")
    assert is_plausible_list_offering("Breakfast club from 7:45am")
    assert is_plausible_list_offering("House Captain")
    assert is_plausible_list_offering("cricket")
