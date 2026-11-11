"""Guest receipt "What you sent" block (task 1122).

Names for everyone; the masked document number only for guests typed in
through the guest form since the claim was confirmed; no birth date or address
for anyone. Rendered at send time, so the outbox row holds the stay id only.
All guest data here is made up.
"""
from __future__ import annotations

import html
import json

from app import claim, db, door_codes, guest_mail_pref, i18n, mail, mail_notify
# _env is the autouse fixture of that file; importing it here applies it here too.
from tests.test_host_guest_details_mail import LEAD, MASK, _env, _rows, _seed  # noqa: F401


NEW_KEYS = (
    "mail_completion_sent_title",
    "mail_completion_sent_doc_label",
    "mail_completion_sent_unnamed",
)


def _complete(monkeypatch, seed):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: False)
    monkeypatch.setattr(
        claim.reporting, "reservation_progress",
        lambda *a, **k: {"expected": 2, "filled": 2, "incomplete": []},
    )
    monkeypatch.setattr(door_codes, "completion_door_code", lambda *a, **k: ("none", None, None))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (seed["apartment"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (seed["stay"],))
    claim.maybe_notify_completion(reservation, apartment)
    (row,) = _rows(seed["stay"], "completion")
    payload = json.loads(row["payload"])
    return row, payload, mail.delivery_body(payload), html.unescape(mail.delivery_html(payload))


def test_guests_typed_in_through_this_claim_show_a_masked_document(monkeypatch):
    seed = _seed()
    _row, _payload, text, page = _complete(monkeypatch, seed)
    for part in (text, page):
        assert "What you sent" in part
        assert f"Jana Testova – Document number: {MASK} 4567" in part
        assert f"Petr Ukazka – Document number: {MASK} 4321" in part
        for absent in ("AB1234567", "XY7654321", "V99887766", "Testgasse", "Musterweg",
                       "1990", "1985"):
            assert absent not in part, absent


def test_a_guest_the_host_entered_is_named_only(monkeypatch):
    seed = _seed()
    db.execute("UPDATE guest SET entered_by = 'host' WHERE id = ?", (seed["guests"][1],))
    _row, _payload, text, page = _complete(monkeypatch, seed)
    for part in (text, page):
        assert "Petr Ukazka" in part
        assert "4321" not in part
        assert f"{MASK} 4567" in part


def test_a_guest_typed_in_before_the_claim_is_named_only(monkeypatch):
    seed = _seed()
    db.execute(
        "UPDATE guest SET created_at = ? WHERE id = ?",
        ("2000-01-01T00:00:00+00:00", seed["guests"][1]),
    )
    _row, _payload, text, page = _complete(monkeypatch, seed)
    for part in (text, page):
        assert "Petr Ukazka" in part
        assert "4321" not in part


def test_the_receipt_row_holds_the_stay_id_and_goes_to_the_claim_address_only(monkeypatch):
    seed = _seed()
    row, payload, _text, _page = _complete(monkeypatch, seed)
    assert row["to_email"] == LEAD
    assert row["cc_email"] is None
    assert payload[mail.RECEIPT_DETAILS_KEY] == seed["stay"]
    assert mail.RECEIPT_DETAILS_MARKER in payload["text"]
    stored = " ".join([row["subject"] or "", row["payload"] or ""])
    for value in ("Jana", "Testova", "Petr", "Ukazka", "4567", "4321", "AB1234567"):
        assert value not in stored, value


def test_the_builder_adds_the_marker_only_when_asked():
    common = dict(lang="en", property_name="Test Flat", dates="1 Mar 2030 – 4 Mar 2030",
                  stay_url="https://example.test/l/x/1")
    assert mail.RECEIPT_DETAILS_MARKER not in mail_notify.build_completion(**common)["text"]
    with_block = mail_notify.build_completion(**common, sent_details=True)
    assert mail.RECEIPT_DETAILS_MARKER in with_block["text"]
    assert mail.RECEIPT_DETAILS_MARKER in with_block["html"]


def test_every_guest_language_has_the_new_keys():
    for lang in i18n.LANGUAGES:
        for key in NEW_KEYS:
            assert key in i18n.STRINGS[lang], (lang, key)
