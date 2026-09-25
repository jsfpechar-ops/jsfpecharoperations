"""Every message a guest receives is branded, and none of them looks like spam.

The guest messages are the ones an outsider sees, so they carry the most risk of
looking like bulk mail and the most risk of leaking a magic link. These tests
cover both: the markup rules ``docs/LOGO.md`` sets, the anti-spam properties a
mail client scores, the rule that a guest is pointed at their host and never at
UbyHost support, and the secret handling that must survive the new HTML part.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest

from app import claim, config, db, host_i18n, i18n, mail, mail_notify

TOKEN = "guestmailtok"
HOST_EMAIL = "host@guestmail.test"
HOST_PHONE = "+420999888777"

GUEST_KINDS = ("claim", "completion", "reminder_guest")
HOST_KINDS = ("reminder_host",)

# Keys this change introduced. Kept explicit so a key that is added to one
# language and forgotten in the other fails here by name rather than as a
# generic parity mismatch somewhere else.
NEW_GUEST_KEYS = (
    "mail_claim_subject",
    "mail_claim_resend_subject",
    "mail_claim_preheader",
    "mail_claim_heading",
    "mail_claim_resend_heading",
    "mail_claim_intro",
    "mail_claim_action",
    "mail_link_fallback",
    "mail_claim_expiry",
    "mail_claim_expiry_resend",
    "mail_claim_next_label",
    "mail_claim_next_body",
    "mail_completion_subject",
    "mail_completion_heading",
    "mail_completion_intro",
    "mail_completion_action",
    "mail_completion_note_label",
    "mail_completion_note",
    "mail_reminder_guest_subject",
    "mail_reminder_guest_heading",
    "mail_reminder_guest_intro",
    "mail_reminder_guest_action",
    "mail_reminder_guest_note_label",
    "mail_reminder_guest_note",
    "mail_reminder_guest_help",
    "mail_guest_footer_why",
    "mail_guest_footer_host_label",
    "mail_guest_footer_help",
)

NEW_HOST_KEYS = (
    "mail.reminder_host.subject",
    "mail.reminder_host.subject_unclaimed",
    "mail.reminder_host.heading",
    "mail.reminder_host.intro",
    "mail.reminder_host.assigned_label",
    "mail.reminder_host.assigned_unknown",
    "mail.reminder_host.next_label",
    "mail.reminder_host.next_steps_claimed",
    "mail.reminder_host.next_steps_unclaimed",
    "mail.reminder_host.action_stay",
    "mail.reminder_host.footer",
)


@pytest.fixture(autouse=True)
def _no_leftovers():
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    for row in db.query(
        "SELECT id FROM apartment WHERE permalink_token LIKE 'guestmail%'"
    ):
        apartment_id = row["id"]
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment_id,),
        )
        db.execute(
            "DELETE FROM reservation_claim WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment_id,),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM email_outbox WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute(
        "DELETE FROM legal_entity WHERE name = 'Guest Mail' AND id NOT IN"
        " (SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)"
    )
    db.execute("DELETE FROM email_outbox WHERE kind IN ('claim', 'claim_resend')"
               " AND idempotency_key LIKE 'claim:%'")
    db.execute("DELETE FROM console_mail_log")


def _seed(*, uby_name: str = "Guest Mail Flat", internal_name: str = "Guest flat"):
    db.init_db()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Guest Mail",
            "seat": "Praha",
            "contact_email": HOST_EMAIL,
            "contact_phone": HOST_PHONE,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": internal_name,
            "uby_name": uby_name,
            "permalink_token": TOKEN,
            "permalink_window_days": 2,
            "default_purpose": "10",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": f"guest-mail-{uby_name[:8]}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ?", (reservation_id,)
    )
    return apartment, reservation


def _host():
    return {"name": "Guest Mail", "email": HOST_EMAIL, "phone": HOST_PHONE}


def _claim_content(lang: str = "en", *, resend: bool = False, property_name="Guest Mail Flat"):
    link = (
        f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1/claim#c={mail.CLAIM_SECRET_MARKER}"
    )
    return mail_notify.build_claim_link(
        lang=lang,
        property_name=property_name,
        dates="2026-01-05 \u2013 2026-01-08",
        link=link,
        resend=resend,
        host=_host(),
    )


def _completion_content(lang: str = "en"):
    return mail_notify.build_completion(
        lang=lang,
        property_name="Guest Mail Flat",
        dates="2026-01-05 \u2013 2026-01-08",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1",
        host=_host(),
    )


def _reminder_guest_content(lang: str = "en"):
    return mail_notify.build_reminder_guest(
        lang=lang,
        property_name="Guest Mail Flat",
        dates="2026-01-05 \u2013 2026-01-08",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1",
        host=_host(),
    )


def _host_copy(lang: str, key: str, **kwargs) -> str:
    """The raw host string, interpolated here.

    ``host_i18n.translate`` silently returns the key when a placeholder does not
    match, so a test that wants to prove the real copy reads the catalogue.
    """
    text = host_i18n.STRINGS[lang][key]
    return text % kwargs if kwargs else text


def _reminder_host_content(lang: str = "en", *, claimed: bool = True):
    return mail_notify.build_reminder_host(
        property_name="Guest flat",
        date="2026-01-05",
        assigned="g***@example.test",
        stay_url=f"{config.PUBLIC_BASE_URL}/reservations/1",
        lang=lang,
        claimed=claimed,
        filled=1,
        expected=3,
    )


def _all_content():
    return {
        "claim": _claim_content(),
        "claim_resend": _claim_content(resend=True),
        "completion": _completion_content(),
        "reminder_guest": _reminder_guest_content(),
        "reminder_host": _reminder_host_content(),
    }


def test_every_guest_message_has_a_subject_and_both_parts():
    for kind, content in _all_content().items():
        assert content["subject"].strip(), kind
        assert content["text"].strip(), kind
        assert content["html"].strip(), kind


def test_the_magic_link_is_in_both_parts_and_keeps_its_marker():
    """The marker must survive into the HTML too, or the link arrives dead.

    ``mail.delivery_html`` substitutes the secret by looking for the marker, so
    an HTML part that lost it would deliver a link nobody can open.
    """
    content = _claim_content()
    assert mail.CLAIM_SECRET_MARKER in content["text"]
    assert mail.CLAIM_SECRET_MARKER in content["html"]

    payload = {
        "text": content["text"],
        "html": content["html"],
        "claim_secret_enc": db.encrypt_field("s3cret-value"),
    }
    assert "s3cret-value" in mail.delivery_body(payload)
    assert "s3cret-value" in mail.delivery_html(payload)
    assert mail.CLAIM_SECRET_MARKER not in mail.delivery_body(payload)
    assert mail.CLAIM_SECRET_MARKER not in mail.delivery_html(payload)
    # And at rest neither part is usable.
    assert "s3cret-value" not in mail.stored_body(payload)
    assert "s3cret-value" not in mail.stored_html(payload)


def test_a_real_claim_stores_no_usable_secret_in_either_part(monkeypatch):
    apartment, reservation = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)

    ok, err, secret = claim.start_claim(
        reservation, apartment, email="guest@guestmail.test", party_size=1, lang="en"
    )
    assert ok, err
    assert secret

    row = db.query_one(
        "SELECT * FROM email_outbox WHERE kind = 'claim' ORDER BY id DESC"
    )
    assert row
    payload = json.loads(row["payload"])
    assert "html" in payload, "the claim mail must ship an HTML part"
    assert secret not in payload["text"]
    assert secret not in payload["html"]
    assert mail.CLAIM_SECRET_MARKER in payload["html"]
    # The text part carries the link once; the HTML carries it in the button and
    # in the copyable address below it. The invariant that matters is that every
    # marker became the secret and none survived.
    assert mail.delivery_body(payload).count(secret) == 1
    assert payload["html"].count(mail.CLAIM_SECRET_MARKER) == (
        mail.delivery_html(payload).count(secret)
    )
    assert mail.CLAIM_SECRET_MARKER not in mail.delivery_html(payload)

    logged = db.query_one("SELECT * FROM console_mail_log ORDER BY id DESC")
    assert logged["body_html"], "the console log must keep the HTML part"
    assert secret not in logged["body_html"]
    assert mail.CLAIM_SECRET_MARKER in logged["body_html"]


def test_a_guest_message_carries_the_branded_logo_and_nothing_else_remote():
    for kind, content in _all_content().items():
        html = content["html"]
        assert f'src="{config.PUBLIC_BASE_URL}/static/ubyhost-logo.jpg"' in html, kind
        assert 'width="180"' in html, kind
        assert 'alt="UbyHost"' in html, kind
        for wrong in ("ubyhost-logo.png", "ubyhost-mark.png", "ubyhost-logo-stacked.png"):
            assert wrong not in html, kind
        # The logo is the only remote resource. A second one would be a
        # tracking pixel or a blocked image, and either hurts delivery.
        assert html.count("<img ") == 1, kind


def test_guest_mail_is_light_mode_only():
    for kind, content in _all_content().items():
        html = content["html"]
        assert "prefers-color-scheme" not in html, kind
        assert "@media" not in html, kind
        assert "color-scheme" not in html, kind
        assert "background:#f7f7f5" in html, kind


def test_guest_mail_looks_transactional_not_bulk():
    """The tells a spam filter looks for, and the ones we must not add."""
    for kind, content in _all_content().items():
        html = content["html"]
        text = content["text"]
        # A transactional notice is not a newsletter: no unsubscribe plumbing,
        # which would mark it as bulk to some filters and is meaningless here.
        assert "List-Unsubscribe" not in html, kind
        assert "Precedence" not in html, kind
        assert "unsubscribe" not in html.lower(), kind
        # No link rewriting, no tracking parameters.
        assert "utm_" not in html, kind
        assert "click." not in html, kind
        # The plain-text part stands on its own rather than pointing at HTML.
        assert text.strip(), kind
        assert "view this email in" not in text.lower(), kind
        # Real, absolute links rather than a redirector.
        assert f"{config.PUBLIC_BASE_URL}/" in text, kind


def test_guest_mail_escapes_anything_a_host_can_type():
    content = _claim_content(property_name='<b>bold</b> & <script>alert(1)</script>')
    html = content["html"]
    assert "<script>" not in html
    assert "<b>bold</b>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    # The text part is not markup, so it keeps the characters as typed.
    assert "<b>bold</b>" in content["text"]


def test_the_footer_names_the_host_and_never_ubyhost_support():
    """A guest cannot use a support address; the guest pages make the same call."""
    for kind, content in _all_content().items():
        assert "support@ubyhost.com" not in content["html"], kind
        assert "support@ubyhost.com" not in content["text"], kind
    for kind in GUEST_KINDS:
        content = _all_content()[kind]
        assert HOST_EMAIL in content["html"], kind
        assert HOST_PHONE in content["html"], kind
        assert HOST_EMAIL in content["text"], kind


def test_the_completion_mail_links_to_the_stay():
    content = _completion_content()
    stay = f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1"
    assert stay in content["html"]
    assert stay in content["text"]
    assert content["html"].count(stay) >= 2, "button and copyable address"


def test_the_completion_mail_says_the_receipt_is_not_proof_of_reporting():
    content = _completion_content()
    assert "not proof of police reporting" in content["text"]
    assert "not proof of police reporting" in content["html"]


def test_the_guest_language_is_honoured():
    for lang in ("cs", "en"):
        expected = i18n.STRINGS[lang]["mail_claim_subject"] % {
            "property": "Guest Mail Flat"
        }
        assert _claim_content(lang)["subject"] == expected
    assert _claim_content("cs")["subject"] != _claim_content("en")["subject"]
    czech = _completion_content("cs")["html"]
    assert "Registrace byla přijata" in czech
    assert "Registration received" not in czech


def test_the_claim_subject_names_the_stay_and_not_a_city():
    """Forty unread mails: the inbox line has to identify this stay."""
    for lang in ("en", "cs"):
        subject = _claim_content(lang)["subject"]
        assert "Guest Mail Flat" in subject, lang
        assert "Prague" not in subject, lang
        assert "Praha" not in subject, lang
    assert _claim_content("en")["subject"].startswith("Confirm your stay at ")
    assert _claim_content("cs")["subject"].startswith("Potvrďte svůj pobyt")


def test_the_resend_subject_cannot_be_confused_with_the_link_it_replaces():
    fresh = _claim_content()["subject"]
    resent = _claim_content(resend=True)["subject"]
    assert resent != fresh
    assert "Guest Mail Flat" in resent
    assert resent == i18n.STRINGS["en"]["mail_claim_resend_subject"] % {
        "property": "Guest Mail Flat"
    }


def test_the_resend_mail_says_in_its_heading_that_it_is_the_new_link():
    assert i18n.STRINGS["en"]["mail_claim_resend_heading"] in _claim_content(
        resend=True
    )["html"]
    assert i18n.STRINGS["en"]["mail_claim_resend_heading"] not in _claim_content()["html"]
    assert i18n.STRINGS["en"]["mail_claim_heading"] in _claim_content()["html"]


def test_the_claim_mail_prints_dates_the_way_every_guest_page_does():
    """An e-mail, an alert and a page must never print the same stay differently.

    ``claim._guest_mail_content`` used to hand the composer the raw ISO values
    out of the reservation row.
    """
    content = claim._guest_mail_content(
        "claim",
        {
            "uby_name": "Vinohrady Studio",
            "internal_name": "",
            "legal_entity_id": None,
        },
        {"id": 1, "date_from": "2026-09-25", "date_to": "2026-09-28"},
        lang="en",
        plain_text="fallback",
        link=f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1/claim#c=x",
    )
    for part in ("text", "html"):
        assert "25.09.2026 \u2013 28.09.2026" in content[part], part
        assert "2026-09-25" not in content[part], part
        assert "2026-09-28" not in content[part], part


def test_the_claim_preheader_is_its_own_line_and_not_the_intro():
    """The preheader is what the inbox shows beside the subject."""
    html = _claim_content()["html"]
    match = re.search(r"mso-hide:all;\">([^<]*)</div>", html)
    assert match, html[:400]
    assert match.group(1) == i18n.STRINGS["en"]["mail_claim_preheader"]
    assert "Guest Mail Flat" not in match.group(1)


def test_the_resend_mail_says_the_old_link_stopped_working():
    fresh = _claim_content(resend=False)
    resent = _claim_content(resend=True)
    assert fresh["text"] != resent["text"]
    assert i18n.STRINGS["en"]["mail_claim_expiry_resend"] in resent["text"]
    assert i18n.STRINGS["en"]["mail_claim_expiry_resend"] not in fresh["text"]


def test_the_host_reminder_is_host_facing_and_keeps_its_subject():
    """The subject leads with the count the host needs on check-in morning."""
    content = _reminder_host_content()
    assert content["subject"] == "Check-in today, 1/3 registered: Guest flat"
    assert "Registration link sent to" in content["text"]
    # The host reminder is a host message, so it may name UbyHost support --
    # but it must not borrow the guest footer, which talks to the guest.
    assert "You received this e-mail because your stay" not in content["text"]


def test_the_host_reminder_never_promises_a_link_the_host_cannot_send():
    """The stay page has no "send a fresh link" control (UX-27, E-5).

    The claimed variant points at the stay page; the unclaimed variant tells the
    host to re-send the apartment link and PIN by hand, and drops the fact row
    that would otherwise read "sent to: the guest has not claimed the stay yet".
    """
    for lang in ("en", "cs"):
        claimed = _reminder_host_content(lang)
        unclaimed = _reminder_host_content(lang, claimed=False)
        for content in (claimed, unclaimed):
            assert "fresh link" not in content["text"]
            assert "nový odkaz" not in content["text"]
        assert _host_copy(lang, "mail.reminder_host.next_steps_claimed", filled=1, expected=3) in claimed["text"]
        assert _host_copy(lang, "mail.reminder_host.next_steps_unclaimed") in unclaimed["text"]
        # The unclaimed mail has no fact row in either part.
        assert _host_copy(lang, "mail.reminder_host.assigned_label") not in unclaimed["text"]
        assert _host_copy(lang, "mail.reminder_host.assigned_unknown") not in unclaimed["text"]
        assert _host_copy(lang, "mail.reminder_host.assigned_label") in claimed["text"]


def test_the_host_reminder_subject_falls_back_when_the_party_is_unknown():
    """An unclaimed stay has no declared party, so the count would read None."""
    content = mail_notify.build_reminder_host(
        property_name="Guest flat",
        date="2026-01-05",
        assigned="",
        stay_url=f"{config.PUBLIC_BASE_URL}/reservations/1",
        lang="en",
        claimed=False,
        filled=0,
        expected=None,
    )
    assert content["subject"] == "Incomplete registration: Guest flat"
    assert "None" not in content["subject"]
    assert "None" not in content["text"]
    assert "None" not in content["html"]


def test_a_composer_bug_never_costs_the_guest_their_link(monkeypatch):
    """The plain-text body is the contract; the HTML is an enhancement."""
    apartment, reservation = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)

    def _boom(**_kwargs):
        raise RuntimeError("composer exploded")

    monkeypatch.setattr(mail_notify, "build_claim_link", _boom)

    ok, err, secret = claim.start_claim(
        reservation, apartment, email="guest@guestmail.test", party_size=1, lang="en"
    )
    assert ok, err
    row = db.query_one(
        "SELECT * FROM email_outbox WHERE kind = 'claim' ORDER BY id DESC"
    )
    assert row, "a broken composer must still queue the message"
    payload = json.loads(row["payload"])
    assert "html" not in payload or not payload["html"]
    assert mail.CLAIM_SECRET_MARKER in payload["text"]
    assert secret in mail.delivery_body(payload)


def test_a_guest_message_survives_an_apartment_without_a_name():
    apartment, _reservation = _seed(uby_name="", internal_name="")
    label = mail_notify.property_label(apartment, "en")
    assert label.strip()
    content = mail_notify.build_claim_link(
        lang="en", property_name=label, dates="x", link="https://example.test/l", host=None
    )
    assert content["html"].strip()
    assert "your stay at  (" not in content["text"]


def test_every_new_key_exists_in_both_languages():
    for key in NEW_GUEST_KEYS:
        for lang in ("en", "cs"):
            assert key in i18n.STRINGS[lang], f"{lang}:{key}"
            assert i18n.STRINGS[lang][key].strip(), f"{lang}:{key}"
    for key in NEW_HOST_KEYS:
        for lang in ("en", "cs"):
            assert key in host_i18n.STRINGS[lang], f"{lang}:{key}"
            assert host_i18n.STRINGS[lang][key].strip(), f"{lang}:{key}"


def test_the_three_catalogues_stay_at_exact_parity():
    for name, table in (
        ("host_i18n.STRINGS", host_i18n.STRINGS),
        ("host_i18n._INTERFACE_STRINGS", host_i18n._INTERFACE_STRINGS),
        ("i18n.STRINGS", i18n.STRINGS),
    ):
        assert set(table["en"]) == set(table["cs"]), name


def test_every_guest_mail_kind_is_registered():
    for kind in (*GUEST_KINDS, *HOST_KINDS):
        assert kind in mail.KINDS, kind


def test_the_from_line_is_not_a_bare_address():
    assert mail.display_from("noreply@ubyhost.com") == "UbyHost <noreply@ubyhost.com>"
