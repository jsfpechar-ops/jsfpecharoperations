"""The Czech Terms lede misspelled "kteří" as "kterí" (D-26 / UX-157)."""
from __future__ import annotations

from pathlib import Path

from app.terms_i18n import TERMS_STRINGS

APP = Path(__file__).resolve().parents[1] / "app"


def test_the_czech_terms_lede_spells_kteri_correctly():
    czech = TERMS_STRINGS["cs"]["terms.page_lede"]
    assert "kteří" in czech
    assert "kterí" not in czech


def test_no_catalogue_still_misspells_kteri():
    for path in sorted(APP.glob("*_i18n.py")):
        assert "kterí" not in path.read_text(encoding="utf-8"), path.name
