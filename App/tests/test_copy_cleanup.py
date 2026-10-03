"""WP17 (review 3.E): guest and host copy cleanup.

Two rules, also in AGENTS.md: one explanation lives in one place, and no
sentence repeats what the button label already says. This file pins the
structural half of the cleanup (deleted keys stay deleted, duplicated blocks
render once, the milestone notice does not block the page). The exact new
wording is pinned next to each screen's existing tests.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, db, host_i18n, i18n
from app.main import app
from tests.test_celebrations import _add_sent_guests, _clean, _owner, _reservation

APP_DIR = Path(__file__).resolve().parents[1] / "app"
TEMPLATES = APP_DIR / "templates"

DELETED_GUEST_KEYS = (
    "arrival_welcome",
    "arrival_help",
    "why_more",
    "why_point_report",
    "why_point_book",
    "why_point_czech",
    "why_point_passport",
    "why_point_sign",
    "why_point_nothing_else",
    "claim_confirm_help",
    "assigned_private_link",
    "assigned_resend_help",
    "tw_done_keep",
    "legal_notice_intro",
    "legal_notice_disclaimer",
)

DELETED_HOST_KEYS = (
    "housebook.legal_intro_title",
    "housebook.legal_intro_ack",
    "housebook.legal_intro_skip",
    "apartment.form.guest_link.lede",
    "dashboard.reporting_modes_body",
    "dashboard.minutes_saved",
    "apartment.form.ubyport.map_summary",
    "apartment.form.ubyport.map.idub",
    "apartment.form.ubyport.map.login",
    "apartment.form.ubyport.map.password",
    "apartment.form.ubyport.map.mark",
    "apartment.form.ubyport.map.mark_label",
    "apartment.form.ubyport.map.name",
    "apartment.form.ubyport.map.contact",
    "apartment.form.ubyport.map.contact_label",
    "onboarding.welcome_lede",
    "onboarding.safe_title",
    "onboarding.safe_body",
    "celebration.title",
    "apartments.lede",
    "apartment.form.lede",
    "stays.lede",
    "automation.lede",
)

# Legal text that must survive any copy pass (review 3.E "Keep" list).
KEPT_GUEST_KEYS = (
    "legal_notice_retention_title",
    "legal_notice_retention_body",
    "legal_notice_refusal_body",
    "legal_notice_accuracy_body",
    "legal_notice_passport_body",
    "legal_ack_label",
    "privacy_intro",
    "privacy_controller_body",
    "pin_recovery",
    "party_help",
    "doc_number_help",
    "child_help",
    "visa_help",
    "signature_help",
    "review_help",
    "claim_cookie_help",
)


def _all_templates() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(TEMPLATES.rglob("*.html"))
    )


def test_deleted_keys_are_gone_from_both_languages():
    for lang in ("en", "cs"):
        for key in DELETED_GUEST_KEYS:
            assert key not in i18n.STRINGS[lang], (lang, key)
        for key in DELETED_HOST_KEYS:
            assert key not in host_i18n.STRINGS[lang], (lang, key)


def test_no_template_still_asks_for_a_deleted_key():
    source = _all_templates()
    for key in DELETED_GUEST_KEYS + DELETED_HOST_KEYS:
        assert not re.search(r"t\(\s*'" + re.escape(key) + r"'", source), key


def test_the_legal_keep_list_is_still_there_in_both_languages():
    for lang in ("en", "cs"):
        for key in KEPT_GUEST_KEYS:
            assert i18n.STRINGS[lang].get(key), (lang, key)
    notice = (TEMPLATES / "guest" / "_legal_notice.html").read_text(encoding="utf-8")
    for key in (
        "legal_notice_retention_body",
        "legal_notice_refusal_body",
        "legal_ack_label",
    ):
        assert "t('" + key + "')" in notice, key


def test_the_reporting_section_still_states_the_deadline_and_timing():
    # Owner (legal) decision: the shortened notice keeps one sentence on the
    # three-working-day deadline and on reporting straight away or a little later.
    en = i18n.STRINGS["en"]["legal_notice_reporting_body"]
    cs = i18n.STRINGS["cs"]["legal_notice_reporting_body"]
    assert "Foreign Police within three working days of arrival" in en
    assert "straight away or a little later" in en
    assert "cizinecké policii do tří pracovních dnů od příjezdu" in cs
    assert "hned, nebo o něco později" in cs
    notice = (TEMPLATES / "guest" / "_legal_notice.html").read_text(encoding="utf-8")
    assert "t('legal_notice_reporting_body')" in notice


def test_the_house_book_legal_block_renders_once():
    template = (TEMPLATES / "housebook.html").read_text(encoding="utf-8")
    assert template.count("t('housebook.legal_body')") == 1
    assert template.count("t('housebook.legal_paper')") == 1
    assert template.count("t('housebook.legal_footnote')") == 1
    assert "housebook-legal-intro" not in template
    assert "ubyhost_housebook_legal_v1" not in template


def test_each_property_form_explanation_renders_once():
    template = (TEMPLATES / "apartment_form.html").read_text(encoding="utf-8")
    assert template.count("apartment.form.calendars.lede") == 1
    assert template.count("t('guest_links.lede')") == 1
    assert "guest_links.message_lede" not in template
    guest_links = (TEMPLATES / "guest_links.html").read_text(encoding="utf-8")
    assert guest_links.count("t('guest_links.message_lede')") == 1


def test_one_retention_note_not_three():
    marker = {"en": "permanently delete", "cs": "Trvalé smazání"}
    for lang, needle in marker.items():
        holders = sorted(
            key
            for key in (
                "archive.retention_note",
                "settings.archive_hint_extended",
                "settings.audit.help",
            )
            if needle.lower() in host_i18n.STRINGS[lang][key].lower()
        )
        assert holders == ["archive.retention_note"], (lang, holders)


def test_signature_hint_carries_no_statute_numbers():
    for lang in ("en", "cs"):
        value = host_i18n.STRINGS[lang]["host.signature_help"]
        assert "§" not in value, lang
        assert "326/1999" not in value, lang


def test_the_milestone_is_a_small_notice_not_a_modal():
    template = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    assert "celebration-dialog" not in template
    _clean()
    owner_id = _owner()
    try:
        _add_sent_guests(_reservation(owner_id, "copy-cleanup-milestone"), 10)
        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
        client = TestClient(app)
        client.cookies.set(
            auth.SESSION_COOKIE,
            auth.issue_session(owner_id, account["session_version"]),
        )
        page = client.get("/?lang=en")
        assert page.status_code == 200
        assert 'id="celebration-toast"' in page.text
        toast = page.text[page.text.index('id="celebration-toast"') :]
        toast = toast[: toast.index("</div>")]
        assert "Milestone: 10 guests reported through UbyHost." in toast
        assert 'action="/celebrations/dismiss"' in toast
        assert "<dialog" not in toast
        assert 'class="toast-stack"' in page.text
    finally:
        _clean()
