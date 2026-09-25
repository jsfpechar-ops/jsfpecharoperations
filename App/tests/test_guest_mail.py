"""Every message a guest receives is branded, and none of them looks like spam.

The guest messages are the ones an outsider sees, so they carry the most risk of
looking like bulk mail and the most risk of leaking a magic link. These tests
cover both: the markup rules ``docs/LOGO.md`` sets, the anti-spam properties a
mail client scores, the rule that a guest is pointed at their host and never at
UbyHost support, and the secret handling that must survive the new HTML part.
"""
from __future__ import annotations

import html
import json
import re
from datetime import timedelta

import pytest

from app import claim, config, db, host_i18n, i18n, mail, mail_notify

TOKEN = "guestmailtok"
HOST_EMAIL = "host@guestmail.test"
HOST_PHONE = "+420999888777"

# The filled coral box ``_button`` paints. Kept in one place so a colour change
# is a one-line edit here rather than a hunt through the assertions.
BUTTON_MARKER = f"background:{mail_notify.BRAND_ACTION};border-radius:8px;"

GUEST_KINDS = ("claim", "completion", "reminder_guest")
HOST_KINDS = ("reminder_host",)

# Keys this change introduced. Kept explicit so a key that is added to one
# language and forgotten in the other fails here by name rather than as a
# generic parity mismatch somewhere else.
NEW_GUEST_KEYS = (
    "mail_claim_subject",
    "mail_claim_resend_subject",
    "mail_claim_preheader",
    "mail_claim_resend_preheader",
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
    "mail_completion_subject_fee",
    "mail_completion_preheader",
    "mail_completion_heading",
    "mail_completion_intro",
    "mail_completion_intro_fee",
    "mail_completion_action",
    "mail_completion_note",
    "mail_reminder_guest_subject",
    "mail_reminder_guest_subject_no_count",
    "mail_reminder_guest_preheader",
    "mail_reminder_guest_heading",
    "mail_reminder_guest_intro",
    "mail_reminder_guest_intro_no_count",
    "mail_reminder_guest_action",
    "mail_reminder_guest_note_label",
    "mail_reminder_guest_note",
    "mail_reminder_guest_device",
    "mail_guest_footer_why",
    "mail_guest_footer_host_label",
    "mail_guest_footer_help",
)

NEW_HOST_KEYS = (
    "mail.reminder_host.subject",
    "mail.reminder_host.subject_unclaimed",
    "mail.reminder_host.preheader",
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


def _reminder_guest_content(lang: str = "en", *, filled: int = 0, expected=None):
    return mail_notify.build_reminder_guest(
        lang=lang,
        property_name="Guest Mail Flat",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1",
        host=_host(),
        filled=filled,
        expected=expected,
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
        "reminder_guest": _reminder_guest_content(filled=1, expected=3),
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


# E-9: the identity coral. It fails AA both as a button fill (white on it is
# 4.17:1) and as link text on white (4.17:1), so no mail may paint it.
IDENTITY_CORAL = "#c85a52"


def test_the_identity_coral_never_reaches_a_mail_client():
    for kind, content in _all_content().items():
        assert IDENTITY_CORAL not in content["html"], kind
        assert IDENTITY_CORAL not in content["text"], kind


def test_the_primary_button_uses_the_action_colour_and_a_48px_target():
    """E-9: 15px/1 with 11px padding in the identity coral gave a 37px target.

    The padding lives on the cell rather than the anchor, because Outlook drops
    padding on an inline element; the anchor fills the padded cell so the whole
    box is clickable in every client. 14px + 20px line + 14px = 48px.
    """
    for kind, content in _all_content().items():
        html = content["html"]
        if BUTTON_MARKER not in html:
            # Only the completion mail can be buttonless: it grows one when a
            # stay fee is still owed and has nothing to press otherwise.
            assert kind == "completion", kind
            continue
        assert (
            f"background:{mail_notify.BRAND_ACTION};border-radius:8px;"
            "padding:14px 24px;"
        ) in html, kind
        assert 'style="display:block;padding:0;font:600 16px/20px' in html, kind
    # And the fee button, which the money slot adds, is the same control.
    fee_html = _fee_completion()["html"]
    assert BUTTON_MARKER in fee_html
    assert "padding:14px 24px;" in fee_html
    assert "display:inline-block" not in fee_html


def test_the_coral_links_use_the_action_colour_too():
    """E-9: the fallback URL and the stay links were the identity coral."""
    marker = f"color:{mail_notify.BRAND_ACTION};text-decoration:underline;"
    for kind, content in _all_content().items():
        html = content["html"]
        assert marker in html, kind
        assert f"color:{IDENTITY_CORAL}" not in html, kind


def test_the_note_label_uses_the_brand_ink_colour():
    """E-9: 13px uppercase in the identity coral on the tint was only 3.54:1.

    E-12 [UX-78] took the tinted box off the guest reminder, so the label E-9
    repainted now lives only in the host problem notice, where
    ``test_submission_mail.py`` covers it. What is left to prove here is that
    nothing on the reminder fell back to the identity coral on the way out.
    """
    for lang in ("en", "cs"):
        html = _reminder_guest_content(lang, filled=1, expected=3)["html"]
        assert f"background:{mail_notify.BRAND_SOFT}" not in html, lang
        assert f"color:{IDENTITY_CORAL}" not in html, lang
        assert f"color:{mail_notify.INK_MUTED};" in html, lang


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
    # The address is readable, not just a button target: a guest whose client
    # mangles the markup can still copy it out of the message.
    assert f">{stay}</a>" in content["html"]


def test_the_completion_mail_closes_with_nothing_left_to_do():
    """E-7: the receipt used to read like a report that was still in flight."""
    for lang, heading, subject, intro, note, action in (
        (
            "en",
            "You're all set",
            "You're registered for Guest Mail Flat \u2014 nothing else to do",
            "Everyone for Guest Mail Flat (2026-01-05 \u2013 2026-01-08) is registered.",
            "Your host takes care of the official registration with the authorities.",
            "See your stay page",
        ),
        (
            "cs",
            "Hotovo",
            "Registrace hotov\u00e1 \u2013 Guest Mail Flat. Nic dal\u0161\u00edho nemus\u00edte d\u011blat",
            "V\u0161ichni host\u00e9 pro Guest Mail Flat (2026-01-05 \u2013 2026-01-08) "
            "jsou zaregistrovan\u00ed.",
            "\u00da\u0159edn\u00ed hl\u00e1\u0161en\u00ed vy\u0159izuje v\u00e1\u0161 hostitel.",
            "Zobrazit str\u00e1nku pobytu",
        ),
    ):
        content = _completion_content(lang)
        # The HTML part is escaped, so an apostrophe arrives as ``&#39;``.
        html_part = html.unescape(content["html"])
        assert content["subject"] == subject, lang
        assert heading in html_part, lang
        assert intro in html_part, lang
        assert note in html_part, lang
        assert note in content["text"], lang
        assert action in html_part, lang
        assert action in content["text"], lang
        # The closing line is a muted paragraph, not a coral callout box.
        assert f"background:{mail_notify.BRAND_SOFT}" not in html_part, lang
        # And the receipt no longer carries a coral button: nothing here is an
        # action the guest still owes the host.
        assert f"background:{mail_notify.BRAND_ACTION};" not in html_part, lang


def test_the_completion_mail_stops_blaming_ubyport():
    """E-7: 'sent to UbyPort automatically' answered a question nobody asked."""
    for lang in ("cs", "en"):
        content = _completion_content(lang)
        assert "UbyPort" not in content["html"], lang
        assert "UbyPort" not in content["text"], lang


# --- E-22 [UX-73]: the money slot -------------------------------------------


def _fee_money(**overrides):
    """What PLAN_POPLATEK will hand the money slot, so the layout is proven now."""
    money = {
        "amount": "400",
        "title": "Local stay fee",
        "rows": [
            ("Total", "400 K\u010d"),
            ("IBAN", "CZ6508000000192000145399", True),
            ("Variable symbol", "1201001", True),
        ],
        "action": (f"{config.PUBLIC_BASE_URL}/pay/fee-token", "Pay 400 K\u010d online"),
        "note": "You can also pay in cash on arrival.",
    }
    money.update(overrides)
    return money


def _fee_completion(lang: str = "en", **overrides):
    return mail_notify.build_completion(
        lang=lang,
        property_name="Guest Mail Flat",
        dates="2026-01-05 \u2013 2026-01-08",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1",
        host=_host(),
        money=_fee_money(**overrides),
    )


def test_the_money_slot_prints_one_panel_in_the_guest_order():
    """The fee must not scatter four uppercase facts through the receipt."""
    html_part = html.unescape(_fee_completion()["html"])
    # One bordered sub-card, not four loose facts: the panel is the only thing
    # on the canvas colour inside a 12px rounded, bordered box.
    panel = (
        f"background:{mail_notify.CANVAS};border:1px solid {mail_notify.LINE};"
        "border-radius:12px;padding:18px 20px;"
    )
    assert html_part.count(panel) == 1
    assert "text-transform:uppercase" not in html_part
    # Title, then the rows in the order they were handed over.
    positions = [
        html_part.index("Local stay fee"),
        html_part.index("Total"),
        html_part.index("CZ6508000000192000145399"),
        html_part.index("1201001"),
    ]
    assert positions == sorted(positions)
    # The values a guest copies by hand are monospace.
    assert mail_notify._MONO_FONT in html_part


def test_the_money_slot_keeps_the_stay_link_and_the_closing_note_after_it():
    """Slots run status, money, secondary links, closing note, footer."""
    html_part = html.unescape(_fee_completion()["html"])
    stay = f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1"
    closing = i18n.STRINGS["en"]["mail_completion_note"]
    assert html_part.index("Local stay fee") < html_part.index(stay)
    assert html_part.index(stay) < html_part.index(closing)


def test_the_money_slot_renders_exactly_one_coral_button():
    """Two primaries means no primary: slot 2 owns the button, slot 1 has none."""
    marker = BUTTON_MARKER
    with_money = html.unescape(_fee_completion()["html"])
    assert with_money.count(marker) == 1
    # The money button, not the stay link, is the one that got it.
    assert "Pay 400 K\u010d online" in with_money
    # Without money there is nothing to press and nothing coral at all.
    plain = html.unescape(_completion_content()["html"])
    assert plain.count(marker) == 0
    # Nor when the host takes cash only and leaves the payment link empty.
    cash_only = html.unescape(_fee_completion(action=None)["html"])
    assert cash_only.count(marker) == 0
    assert "You can also pay in cash on arrival." in cash_only


def test_the_secondary_note_sits_next_to_the_stay_link():
    """Slot 3: the QR line the fee plan needs, quiet and never a button."""
    content = mail_notify.build_completion(
        lang="en",
        property_name="Guest Mail Flat",
        dates="2026-01-05 \u2013 2026-01-08",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1",
        host=_host(),
        secondary_note="The QR code for your banking app is on your stay page.",
    )
    html_part = html.unescape(content["html"])
    stay = f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1"
    assert content["subject"] == "You're registered for Guest Mail Flat \u2014 nothing else to do"
    assert html_part.index(stay) < html_part.index("The QR code for your banking app")
    assert "The QR code for your banking app is on your stay page." in content["text"]
    # No money slot, so still nothing coral.
    assert BUTTON_MARKER not in html_part


def test_the_completion_subject_names_the_fee_that_is_still_owed():
    """E-22: with a fee due, the subject must not read as 'all done'."""
    for lang, expected in (
        (
            "en",
            "Registered \u2014 stay fee 400 K\u010d to pay for Guest Mail Flat",
        ),
        (
            "cs",
            "Registrace hotov\u00e1 \u2013 zapla\u0165te poplatek z pobytu 400 K\u010d "
            "(Guest Mail Flat)",
        ),
    ):
        content = _fee_completion(lang)
        assert content["subject"] == expected, lang
        # The no-fee wording is the fallback, not the fee wording.
        assert content["subject"] != _completion_content(lang)["subject"], lang


def test_the_fee_intro_stops_saying_there_is_nothing_left_to_do():
    """E-22: the second sentence has to match what the guest still owes."""
    for lang, expected in (
        (
            "en",
            "Everyone for Guest Mail Flat (2026-01-05 \u2013 2026-01-08) is "
            "registered. Your host collects the municipal stay fee: 400 K\u010d "
            "for your group.",
        ),
        (
            "cs",
            "V\u0161ichni host\u00e9 pro Guest Mail Flat (2026-01-05 \u2013 "
            "2026-01-08) jsou zaregistrovan\u00ed. V\u00e1\u0161 hostitel vyb\u00edr\u00e1 "
            "poplatek z pobytu: 400 K\u010d za va\u0161i skupinu.",
        ),
    ):
        content = _fee_completion(lang)
        html_part = html.unescape(content["html"])
        assert expected in html_part, lang
        assert "nothing else you need to do" not in html_part, lang
        assert "Nic dal\u0161\u00edho d\u011blat nemus\u00edte" not in html_part, lang
        # The inbox preview is the intro too, so it cannot promise closure the
        # body no longer promises.
        assert "nothing else you need to do" not in content["text"], lang
    # With no fee the closure sentence is still there.
    assert "There is nothing else you need to do." in html.unescape(
        _completion_content()["html"]
    )


def test_the_completion_text_part_mirrors_the_slot_order():
    """A client that drops the HTML still reads the receipt in one piece."""
    content = _fee_completion()
    text = content["text"]
    stay = f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1"
    closing = i18n.STRINGS["en"]["mail_completion_note"]
    assert text.index("Local stay fee") < text.index("Total")
    assert text.index("Total") < text.index("IBAN: CZ6508000000192000145399")
    assert text.index("IBAN: CZ6508000000192000145399") < text.index(
        f"Pay 400 K\u010d online: {config.PUBLIC_BASE_URL}/pay/fee-token"
    )
    assert text.index("Local stay fee") < text.index(stay)
    assert text.index(stay) < text.index(closing)
    # The signature block still closes the message.
    assert text.index("\n--\n") > text.index(closing)


def test_the_money_slot_escapes_whatever_the_host_typed():
    """An IBAN is host data; it goes through the same escape as everything else."""
    money = _fee_money(
        title="<script>alert(1)</script>",
        rows=[("Total", "<b>400</b>")],
        note="<img src=x>",
    )
    content = mail_notify.build_completion(
        lang="en",
        property_name="Guest Mail Flat",
        dates="2026-01-05 \u2013 2026-01-08",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1",
        host=_host(),
        money=money,
    )
    assert "<script>" not in content["html"]
    assert "&lt;script&gt;" in content["html"]
    assert "<b>400</b>" not in content["html"]
    assert "<img src=x>" not in content["html"]


def test_the_money_slot_survives_a_panel_with_nothing_in_it():
    """A stay fee the host has not finished configuring must not break the mail."""
    content = _fee_completion(title="", rows=[], action=None, note=None)
    html_part = html.unescape(content["html"])
    assert f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1" in html_part
    assert content["text"].strip()


def test_the_guest_language_is_honoured():
    for lang in ("cs", "en"):
        expected = i18n.STRINGS[lang]["mail_claim_subject"] % {
            "property": "Guest Mail Flat"
        }
        assert _claim_content(lang)["subject"] == expected
    assert _claim_content("cs")["subject"] != _claim_content("en")["subject"]
    czech = _completion_content("cs")["html"]
    assert "Hotovo" in czech
    assert "You're all set" not in czech


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
    assert match.group(1) == (
        i18n.STRINGS["en"]["mail_claim_preheader"] + mail_notify.PREHEADER_SPACER
    )
    assert "Guest Mail Flat" not in match.group(1)


def _preheader(content):
    """The hidden inbox-snippet line, with the spacer stripped off."""
    match = re.search(r"mso-hide:all;\">([^<]*)</div>", content["html"])
    assert match, content["html"][:400]
    captured = match.group(1)
    assert captured.endswith(mail_notify.PREHEADER_SPACER), repr(captured[-60:])
    assert mail_notify.PREHEADER_SPACER.strip("\u2007\ufeff\u034f") == ""
    return html.unescape(captured[: -len(mail_notify.PREHEADER_SPACER)])


def test_every_kind_has_its_own_preheader_and_the_invisible_spacer():
    """Each kind says something the intro does not, so the snippet is useful.

    Before this, every builder passed ``preheader=intro``, so the inbox showed
    the first body line twice and then ran on into the logo and the heading.
    """
    catalogue = {
        "claim": i18n.STRINGS["en"]["mail_claim_preheader"],
        "claim_resend": i18n.STRINGS["en"]["mail_claim_resend_preheader"],
        "completion": i18n.STRINGS["en"]["mail_completion_preheader"],
        "reminder_guest": i18n.STRINGS["en"]["mail_reminder_guest_preheader"],
        "reminder_host": host_i18n.STRINGS["en"]["mail.reminder_host.preheader"],
    }
    seen = {}
    for kind, content in _all_content().items():
        preheader = _preheader(content)
        assert preheader == catalogue[kind], kind
        assert preheader.strip(), kind
        # The bug this replaces: a preheader that repeats the first body line.
        assert preheader not in content["text"], kind
        seen[kind] = preheader
    assert len(set(seen.values())) == len(seen), seen


def test_the_preheader_spacer_is_invisible_to_every_client():
    """A figure space, a BOM and a combining joiner — none of them visible."""
    assert mail_notify.PREHEADER_SPACER == "\u2007\ufeff\u034f" * 40
    assert all(ord(char) > 0x7F for char in mail_notify.PREHEADER_SPACER)


def test_the_resend_mail_says_the_old_link_stopped_working():
    fresh = _claim_content(resend=False)
    resent = _claim_content(resend=True)
    assert fresh["text"] != resent["text"]
    assert i18n.STRINGS["en"]["mail_claim_expiry_resend"] in resent["text"]
    assert i18n.STRINGS["en"]["mail_claim_expiry_resend"] not in fresh["text"]


def test_the_expiry_sits_under_the_button_and_reads_as_reassurance():
    """E-11: the one time-critical fact used to be the last muted line."""
    for resend in (False, True):
        content = _claim_content(resend=resend)
        expiry = i18n.STRINGS["en"][
            "mail_claim_expiry_resend" if resend else "mail_claim_expiry"
        ]
        page = html.unescape(content["html"])
        button_at = page.index(BUTTON_MARKER)
        expiry_at = page.index(expiry)
        fallback_at = page.index(i18n.STRINGS["en"]["mail_link_fallback"])
        next_at = page.index(i18n.STRINGS["en"]["mail_claim_next_label"])
        assert button_at < expiry_at < fallback_at < next_at, resend
        # Normal 15px body text, not the muted 14px footnote it used to be.
        above = page[expiry_at - 200 : expiry_at]
        assert "font:400 15px/1.6" in above, resend
        assert "font:400 14px/1.6" not in above, resend
        assert expiry in content["text"], resend


def test_the_claim_expiry_no_longer_reads_as_a_threat():
    """The device remembers the guest, so "stops working" was the wrong picture."""
    for key in ("mail_claim_expiry", "mail_claim_expiry_resend"):
        for lang in ("en", "cs"):
            text = i18n.STRINGS[lang][key]
            assert "30" in text, (lang, key)
    assert "remembers your stay" in i18n.STRINGS["en"]["mail_claim_expiry"]
    assert "zapamatuje" in i18n.STRINGS["cs"]["mail_claim_expiry"]


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


# --- E-12 [UX-78]: the reminder says how much of the party is missing ---------


def test_the_reminder_guest_leads_with_the_count_the_guest_needs():
    """E-12: the sweep knew how far along the stay was and the mail never said.

    Without the count the guest has to open the page to find out whether the
    missing form is theirs or their partner's.
    """
    for lang in ("en", "cs"):
        content = _reminder_guest_content(lang, filled=1, expected=3)
        assert content["subject"] == i18n.STRINGS[lang][
            "mail_reminder_guest_subject"
        ] % {"property": "Guest Mail Flat", "filled": 1, "expected": 3}, lang
        intro = i18n.STRINGS[lang]["mail_reminder_guest_intro"] % {"missing": 2}
        assert intro in html.unescape(content["html"]), lang
        assert intro in content["text"], lang
        # The button label is the one piece of E-12 copy the audit kept.
        action = i18n.STRINGS[lang]["mail_reminder_guest_action"]
        assert f">{action}</a>" in content["html"], lang
        assert f"{action}: " in content["text"], lang


def test_the_reminder_guest_subject_names_the_stay_and_tomorrow():
    """E-12: 'Please finish your guest registration' read like every other nag."""
    for lang in ("en", "cs"):
        subject = _reminder_guest_content(lang, filled=1, expected=3)["subject"]
        assert "Guest Mail Flat" in subject, lang
        assert subject.startswith("Tomorrow at " if lang == "en" else "Zítra"), lang


def test_the_reminder_guest_still_reads_without_a_declared_party():
    """No party size means no count to quote, and never a raw placeholder."""
    for lang in ("en", "cs"):
        content = _reminder_guest_content(lang)
        assert content["subject"] == i18n.STRINGS[lang][
            "mail_reminder_guest_subject_no_count"
        ] % {"property": "Guest Mail Flat"}, lang
        assert i18n.STRINGS[lang]["mail_reminder_guest_intro_no_count"] % {
            "property": "Guest Mail Flat"
        } in html.unescape(content["html"]), lang
        for part in ("subject", "text", "html"):
            assert "%(" not in content[part], (lang, part)


def test_the_reminder_guest_tells_the_guest_which_device_opens_the_link():
    """E-12: the PIN, the assigned page and the resend used to arrive unannounced.

    The stay page only opens without friction on the device that claimed it.
    """
    for lang in ("en", "cs"):
        device = i18n.STRINGS[lang]["mail_reminder_guest_device"]
        content = _reminder_guest_content(lang, filled=1, expected=3)
        assert device in html.unescape(content["html"]), lang
        assert device in content["text"], lang
        assert "PIN" in device, lang


def test_the_one_reminder_fact_is_muted_and_the_help_line_is_gone():
    """E-12: the coral box shouted a policy; 'you can ignore this' was false."""
    for lang in ("en", "cs"):
        content = _reminder_guest_content(lang, filled=1, expected=3)
        html_part = html.unescape(content["html"])
        assert f"background:{mail_notify.BRAND_SOFT}" not in html_part, lang
        one_reminder = (
            f"{i18n.STRINGS[lang]['mail_reminder_guest_note_label']} \u2014 "
            f"{i18n.STRINGS[lang]['mail_reminder_guest_note']}"
        )
        assert one_reminder in html_part, lang
        assert one_reminder in content["text"], lang
        # The reminder is only sent while the stay is incomplete, so the line
        # that invited the guest to ignore it is deleted from both catalogues.
        assert "mail_reminder_guest_help" not in i18n.STRINGS[lang], lang


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
