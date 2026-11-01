"""0703: the Overview header shows the date in words (cs, en, vi)."""
from __future__ import annotations

from app.templating import date_long


def test_date_long_czech_uses_genitive_month_and_lowercase_weekday():
    assert date_long("2026-11-01", "cs") == "neděle 1. listopadu"


def test_date_long_english():
    assert date_long("2026-11-01", "en") == "Sunday 1 November"


def test_date_long_vietnamese_uses_numeric_month():
    assert date_long("2026-11-01", "vi") == "Chủ nhật, 1 tháng 11"


def test_date_long_unknown_language_falls_back_to_english():
    assert date_long("2026-11-01", "de") == "Sunday 1 November"


def test_date_long_empty_value_is_blank():
    assert date_long(None, "cs") == ""
