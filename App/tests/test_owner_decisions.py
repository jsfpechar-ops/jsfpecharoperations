"""The product owner's decisions on the flagged audit items.

Each test pins one answer the owner gave for a ⚑ item that was left open by the
UX-145→162 backlog: the independence line (D-12), the locked tagline (D-13), one
public guest-book term (D-18), the guest privacy copy (A-30), the logo sizes
(B-21), and the legal review/staging copy (D-30).
"""
from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from app import db, host_i18n, i18n
from app.dpa_i18n import DPA_STRINGS
from app.landing_i18n import LANDING_STRINGS
from app.main import app
from app.privacy_policy_i18n import PRIVACY_STRINGS
from app.subprocessors_i18n import SUBPROCESSOR_STRINGS
from app.terms_i18n import TERMS_STRINGS

LOGO = (Path(__file__).resolve().parents[2] / "docs" / "LOGO.md").read_text(
    encoding="utf-8"
)


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _get(path: str, lang: str = "en") -> str:
    joiner = "&" if "?" in path else "?"
    response = _client().get(f"{path}{joiner}lang={lang}")
    assert response.status_code == 200, f"{path} answered {response.status_code}"
    return response.text


# --- D-12: the independence line replaces the old trust line ----------------


def test_the_landing_carries_the_independence_line():
    for lang in ("en", "cs"):
        line = LANDING_STRINGS[lang]["landing.independent"]
        assert line in _get("/", lang), lang
    assert "landing.trust" not in LANDING_STRINGS["en"]
    assert "landing.trust" not in LANDING_STRINGS["cs"]


# --- D-13: the locked tagline is the final CTA title ------------------------


def test_the_locked_tagline_is_the_final_cta():
    assert LANDING_STRINGS["en"]["landing.final.title"] == "Guest reporting, handled for you."
    assert LANDING_STRINGS["cs"]["landing.final.title"] == "Hlášení hostů vyřídíme za vás."
    assert host_i18n.STRINGS["en"]["login.hero_title"] == "Guest reporting, handled for you."
    assert host_i18n.STRINGS["cs"]["login.hero_title"] == "Hlášení hostů vyřídíme za vás."
    assert "autopilot" not in _get("/").lower()
    assert "autopilota" not in _get("/", "cs").lower()


# --- D-18: one public term for the guest book ------------------------------


def test_one_public_guest_book_term():
    assert LANDING_STRINGS["en"]["landing.feature.book.title"] == "Online guest book"
    assert LANDING_STRINGS["cs"]["landing.feature.book.title"] == "Online ubytovací kniha"
    assert LANDING_STRINGS["en"]["pricing.includes.3"] == "Online guest book"
    assert LANDING_STRINGS["cs"]["pricing.includes.3"] == "Online ubytovací kniha"
    assert "Online house book" not in _get("/jak-to-funguje")
    assert "Online domovní kniha" not in _get("/jak-to-funguje", "cs")


# --- A-30: guest privacy drops support@ and the jargon ----------------------


def test_guest_privacy_copy_drops_support_and_jargon():
    for lang in ("en", "cs"):
        strings = i18n.STRINGS[lang]
        assert "%(email)s" not in strings["privacy_processor_body"], lang
        assert "support@" not in strings["privacy_processor_body"], lang
        assert "Bot Fight" not in strings["privacy_bot_protection_body"], lang
        assert "staging" not in strings["privacy_retention_body"].lower(), lang
        assert "stagingu" not in strings["privacy_retention_body"].lower(), lang


# --- B-21: the doc follows the shipped login sizes --------------------------


def test_the_logo_doc_matches_the_login_css():
    assert "**178 px** wide" in LOGO
    assert "**170 px** wide" in LOGO
    assert "**220 px** wide" not in LOGO
    assert "**300 px** wide" not in LOGO


# --- D-30: reworded review panels, no staging notes -------------------------


def test_the_review_panels_are_reworded():
    assert TERMS_STRINGS["en"]["terms.review_title"] == "About these terms"
    assert TERMS_STRINGS["cs"]["terms.review_title"] == "K těmto podmínkám"
    assert PRIVACY_STRINGS["en"]["privacy.review_title"] == "About this policy"
    assert PRIVACY_STRINGS["cs"]["privacy.review_title"] == "K těmto zásadám"
    assert DPA_STRINGS["en"]["dpa.review_title"] == "About this DPA"
    assert DPA_STRINGS["cs"]["dpa.review_title"] == "K tomuto DPA"

    for strings, key in (
        (TERMS_STRINGS, "terms.review_body"),
        (PRIVACY_STRINGS, "privacy.review_body"),
        (DPA_STRINGS, "dpa.review_body"),
    ):
        for lang in ("en", "cs"):
            body = strings[lang][key].lower()
            assert "lawyer" not in body, (key, lang)
            assert "counsel" not in body, (key, lang)
            assert "advokát" not in body, (key, lang)


def test_the_staging_notes_are_not_public():
    for strings in (PRIVACY_STRINGS, DPA_STRINGS, SUBPROCESSOR_STRINGS):
        for lang in ("en", "cs"):
            for key, value in strings[lang].items():
                if isinstance(value, str):
                    assert "staging" not in value.lower(), (key, lang)
    assert "staging" not in _get("/subprocessors").lower()
    assert "staging" not in _get("/subprocessors", "cs").lower()


# --- C-21/UX-86: the no-report pill says what it is exempt from -------------


def test_the_no_report_pill_is_clear_and_localized():
    assert host_i18n.STRINGS["en"]["status.not_required"] == "Exempt from reporting"
    assert host_i18n.STRINGS["cs"]["status.not_required"] == "Nehlásí se"
    assert host_i18n.STRINGS["en"]["stay.detail.guests.exempt"] == "Exempt from reporting"
    assert host_i18n.STRINGS["cs"]["stay.detail.guests.exempt"] == "Nehlásí se"
