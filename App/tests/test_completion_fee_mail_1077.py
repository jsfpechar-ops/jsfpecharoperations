"""The completion mail is the bill (task 1077, F1).

A fee mail names the fee in its subject, lists only the pay ways that work
with every detail inline, carries the QR as an inline ``cid:`` image for a
Czech or Slovak guest, and ends with "Already paid?". The door-code mail
repeats the block once the completion mail has gone.
"""
from __future__ import annotations

import hashlib
import html
import json
import re

import pytest

from app import claim, config, db, door_codes, i18n, mail, mail_notify, stay_fee, ttlock
# _env is the autouse fixture of that file; importing it here applies it here too.
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401

PIN = "4821937"
IBAN = "CZ6508000000192000145399"
SPAYD = "SPD*1.0*ACC:CZ6508000000192000145399*AM:600.00*CC:CZK*X-VS:1234*MSG:Stay fee 1234"
LANGS = ("en", "cs", "de", "es", "fr", "uk")
NEW_KEYS = (
    "mail_completion_subject_fee",
    "mail_completion_preheader_fee",
    "mail_completion_heading_fee",
    "mail_completion_intro_fee",
    "mail_completion_fee_once",
    "mail_completion_fee_already",
)
PAID_PHRASES = ("fee is paid", "was paid", "has been paid", "payment received", "settled")


def _fee(ways, total=600):
    return {
        "total": total,
        "lines": [(2, total)],
        "rate": total // 2,
        "rails": [way["key"] for way in ways],
        "ways": ways,
        "vs": "1234",
    }


def _bank(spayd=SPAYD, payee="Host s.r.o."):
    return {"key": "iban", "payee": payee, "account": "CZ65 0800 0000 1920 0014 5399",
            "spayd": spayd}


def _all_ways():
    return [_bank(), {"key": "revolut", "link": "https://revolut.me/host"},
            {"key": "cash", "note": "At the reception desk."}]


def _completion(fee, lang="en"):
    return mail_notify.build_completion(
        lang=lang,
        property_name="Fee Flat",
        dates="2026-01-05 – 2026-01-08",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/feetok/1",
        host={"name": "Host s.r.o.", "email": "host@example.test", "phone": ""},
        checkin="5 Jan 2026, from 15:00",
        checkout="8 Jan 2026, by 10:00",
        host_url=f"{config.PUBLIC_BASE_URL}/reservations/1",
        fee=fee,
    )


def _door(fee=None, lang="en", **kwargs):
    if "fee" in kwargs or fee is not None:
        kwargs["fee"] = fee
    return mail_notify.build_door_code(
        lang=lang,
        property_name="Fee Flat",
        checkin="5 Jan 2026, 15:00",
        checkout="8 Jan 2026, 10:00",
        first_use_by="5 Jan 2026, 15:00",
        host={"name": "Host s.r.o.", "email": "host@example.test", "phone": ""},
        **kwargs,
    )


def _t(lang, key, **kw):
    return i18n.translator(lang)(key, **kw)


# a. bank way with a QR


def test_a_bank_way_with_qr_is_a_full_bill():
    content = _completion(_fee([_bank()]))
    text, page = content["text"], html.unescape(content["html"])
    assert "600" in content["subject"]
    assert content["subject"] == _t("en", "mail_completion_subject_fee", property="Fee Flat", total=600)
    assert "Recipient: Host s.r.o." in text
    assert "Account (IBAN): CZ65 0800 0000 1920 0014 5399" in text
    assert "Amount: 600 CZK" in text
    assert "Variable symbol: 1234" in text
    assert f'src="cid:{mail.QR_CONTENT_ID}"' in content["html"]
    assert 'src="cid:stayfeeqr"' in content["html"]
    assert content["qr_spayd"] == SPAYD
    for part in (content["subject"], text, page):
        assert "nothing else" not in part.lower()
    fee_part = text.split("--")[0]
    assert "Choose one way to pay:" in fee_part
    already = _t("en", "mail_completion_fee_already")
    assert already in fee_part
    # The "Already paid?" line closes the fee block: after it only the receipt's own note.
    assert fee_part.index(already) > fee_part.index("Variable symbol: 1234")
    assert fee_part.index(already) < fee_part.index(_t("en", "mail_completion_note"))


# b. bank way without a QR


def test_a_bank_way_without_qr_has_rows_and_no_image():
    content = _completion(_fee([_bank(spayd="")]))
    assert "Variable symbol: 1234" in content["text"]
    assert "<img" not in _without_logo(content["html"])
    assert "qr_spayd" not in content


# c. no remote or data: image in any case


def _without_logo(page):
    """The shell's brand logo is the one image every mail had before 1077."""
    logo = re.search(r'<img src="[^"]*/static/ubyhost-logo\.[a-z]+"', page)
    return page.replace(logo.group(0), "") if logo else page


@pytest.mark.parametrize("ways", [[_bank()], [_bank(spayd="")], [], _all_ways()])
def test_no_mail_has_a_remote_or_data_image(ways):
    for content in (_completion(_fee(ways)), _door(_fee(ways)), _completion(None), _door()):
        page = _without_logo(content["html"])
        assert 'src="http' not in page
        assert 'src="data:' not in page
        assert re.findall(r'<img src="([^"]*)"', page) in ([], [f"cid:{mail.QR_CONTENT_ID}"])


# d. guest_pay_ways and qr_offered_for_reservation


def _apartment(**fields):
    base = {
        "legal_entity_id": None,
        "stay_fee_guest_rails": "",
        "stay_fee_guest_default_rail": "",
        "stay_fee_guest_revolut_link": "",
        "stay_fee_guest_cash_note": "",
    }
    base.update(fields)
    return base


CHARGE = {"total_czk": 600}
RESERVATION = {"id": 1234}


@pytest.fixture
def entity():
    now = db.utcnow()
    with_iban = db.insert("legal_entity", {"name": "Fee Ways 1077", "iban": IBAN, "created_at": now})
    without = db.insert("legal_entity", {"name": "Fee Ways 1077", "created_at": now})
    yield {"iban": with_iban, "none": without}
    db.execute("DELETE FROM legal_entity WHERE id IN (?, ?)", (with_iban, without))


def test_a_malformed_bank_account_drops_the_bank_way_only():
    now = db.utcnow()
    bad = db.insert("legal_entity", {"name": "Fee Ways 1077", "bank_account": "12-ab/0800",
                                     "created_at": now})
    try:
        ways = stay_fee.guest_pay_ways(
            _apartment(legal_entity_id=bad, stay_fee_guest_rails="iban,revolut,cash",
                       stay_fee_guest_revolut_link="https://revolut.me/host"),
            RESERVATION, CHARGE, True,
        )
        assert [way["key"] for way in ways] == ["revolut", "cash"]
    finally:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (bad,))


def test_bank_without_an_account_is_left_out(entity):
    ways = stay_fee.guest_pay_ways(
        _apartment(legal_entity_id=entity["none"], stay_fee_guest_rails="iban,cash"),
        RESERVATION, CHARGE, True,
    )
    assert [way["key"] for way in ways] == ["cash"]


def test_bank_with_an_account_carries_the_spayd_only_when_qr_is_offered(entity):
    apartment = _apartment(legal_entity_id=entity["iban"], stay_fee_guest_rails="qr")
    with_qr = stay_fee.guest_pay_ways(apartment, RESERVATION, CHARGE, True)
    assert with_qr[0]["key"] == "iban"
    assert with_qr[0]["payee"] == "Fee Ways 1077"
    assert with_qr[0]["account"] == "CZ65 0800 0000 1920 0014 5399"
    assert "1234" in with_qr[0]["spayd"] and "600" in with_qr[0]["spayd"]
    assert stay_fee.guest_pay_ways(apartment, RESERVATION, CHARGE, False)[0]["spayd"] == ""


def test_revolut_without_a_link_is_left_out():
    ways = stay_fee.guest_pay_ways(_apartment(stay_fee_guest_rails="revolut,cash"),
                                   RESERVATION, CHARGE, True)
    assert [way["key"] for way in ways] == ["cash"]


def test_cash_without_a_note_shows_the_default_text():
    ways = stay_fee.guest_pay_ways(_apartment(stay_fee_guest_rails="cash"), RESERVATION, CHARGE, True)
    assert ways == [{"key": "cash", "note": ""}]
    text = _completion(_fee(ways))["text"]
    assert f"Cash: {_t('en', 'fee_cash_default')}" in text


def test_the_default_rail_comes_first(entity):
    apartment = _apartment(
        legal_entity_id=entity["iban"],
        stay_fee_guest_rails="iban,revolut,cash",
        stay_fee_guest_default_rail="cash",
        stay_fee_guest_revolut_link="https://revolut.me/host",
    )
    keys = [way["key"] for way in stay_fee.guest_pay_ways(apartment, RESERVATION, CHARGE, True)]
    assert keys == ["cash", "iban", "revolut"]
    apartment["stay_fee_guest_default_rail"] = "qr"
    keys = [way["key"] for way in stay_fee.guest_pay_ways(apartment, RESERVATION, CHARGE, True)]
    assert keys == ["iban", "revolut", "cash"]


def _guest(stay, nationality, archived=False):
    now = db.utcnow()
    db.insert("guest", {
        "reservation_id": stay,
        "first_name": "Test",
        "surname": "Guest",
        "nationality": nationality,
        "archived_at": now if archived else None,
        "created_at": now,
        "updated_at": now,
    })


def _drop_guests(stay):
    db.execute("DELETE FROM guest WHERE reservation_id = ?", (stay,))


def test_qr_is_offered_for_a_slovak_guest_only():
    _, _, stay = _stay(registered_minutes_ago=1)
    try:
        _guest(stay, "DEU")
        assert stay_fee.qr_offered_for_reservation({"id": stay}) is False
        _guest(stay, "CZE", archived=True)
        assert stay_fee.qr_offered_for_reservation({"id": stay}) is False
        _guest(stay, "svk")
        assert stay_fee.qr_offered_for_reservation({"id": stay}) is True
    finally:
        _drop_guests(stay)


# e. no working way


def test_no_working_way_still_states_the_total():
    content = _completion(_fee([]))
    text = content["text"]
    assert "600 CZK" in text
    assert _t("en", "fee_no_rails") in text
    assert "Choose one way" not in text
    assert _t("en", "mail_completion_fee_already") in text
    assert "qr_spayd" not in content


# f. escaping


def test_a_cash_note_arrives_escaped():
    content = _completion(_fee([{"key": "cash", "note": "<b>x</b>"}]))
    assert "<b>x</b>" not in content["html"]
    assert "&lt;b&gt;x&lt;/b&gt;" in content["html"]
    assert "&amp;lt;" not in content["html"]


def test_the_revolut_button_label_and_link_are_inline():
    content = _completion(_fee([{"key": "revolut", "link": "https://revolut.me/host"}]))
    assert "Pay 600 CZK with Revolut: https://revolut.me/host" in content["text"]
    assert 'href="https://revolut.me/host"' in content["html"]


# g. the switch off leaves both mails as today


def test_completion_fee_is_none_with_the_flag_or_collect_off(monkeypatch):
    called = []
    monkeypatch.setattr(stay_fee, "charge_for_reservation", lambda *a: called.append(1) or {
        "total_czk": 600, "rate_czk": 300, "lines": []})
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    assert claim._completion_fee({"stay_fee_collect": 1}, {"id": 1}) is None
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    assert claim._completion_fee({"stay_fee_collect": 0}, {"id": 1}) is None
    assert called == []


# sha256 of subject, text and HTML of each no-fee mail, as built by the builders
# on the base commit 14ba49ce (before 1077), with the base URLs pinned below.
PINNED_NO_FEE = {
    "completion": "e08f9311d7e4676a86f9bf78f3f58ec5da84bf07e284a667537278b37282e2a6",
    "door_code": "56000ed4c6a8b0f6bb60f8f83c3c89f81f18dabcd4de87ec6cf5b2ed8b2ae2e6",
}


def _digest(content):
    raw = "\x00".join([content["subject"], content["text"], content["html"]])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_without_a_fee_both_mails_are_byte_for_byte_as_before(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://pin.example.test")
    monkeypatch.setattr(config, "APP_BASE_URL", "https://pin.example.test")
    assert _digest(_completion(None)) == PINNED_NO_FEE["completion"]
    assert _digest(_door()) == PINNED_NO_FEE["door_code"]


def test_without_a_fee_both_mails_are_unchanged():
    content = _completion(None)
    assert content["subject"] == _t("en", "mail_completion_subject", property="Fee Flat")
    assert "qr_spayd" not in content
    assert _door() == _door(fee=None)
    door = _door()
    assert _t("en", "mail_completion_fee_heading") not in door["text"]
    assert "qr_spayd" not in door


# h. all six languages


@pytest.mark.parametrize("lang", LANGS)
def test_every_language_renders_the_full_bill(lang):
    fee = _fee(_all_ways())
    for content in (_completion(fee, lang), _door(fee, lang)):
        for part in (content["subject"], content["text"], content["html"]):
            assert "%(" not in part, lang
        assert _t(lang, "mail_completion_fee_already") in content["text"]
        assert content["qr_spayd"] == SPAYD


@pytest.mark.parametrize("lang", [lang for lang in LANGS if lang != "en"])
def test_the_new_keys_are_translated(lang):
    for key in NEW_KEYS:
        assert _t(lang, key, property="P", total=1) != _t("en", key, property="P", total=1), (lang, key)


def test_the_two_old_keys_are_gone():
    for lang in LANGS:
        for key in ("mail_completion_fee_ways", "mail_completion_fee_vs"):
            assert _t(lang, key) == key, (lang, key)


# k. never "paid"


def test_no_sentence_states_the_fee_as_paid():
    fee = _fee(_all_ways())
    for content in (_completion(fee), _door(fee)):
        for part in (content["subject"], content["text"], html.unescape(content["html"])):
            lowered = part.lower()
            for phrase in PAID_PHRASES:
                assert phrase not in lowered, phrase


# i and j: the flows


def _works(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: (PIN, "99"))


@pytest.fixture
def fee_stay(monkeypatch):
    """A lock stay on a property that collects the fee by bank, with a Czech guest."""
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(
        stay_fee, "charge_for_reservation",
        lambda apartment, reservation: {
            "total_czk": 600, "rate_czk": 300, "liable_nights": 2,
            "lines": [{"liable_nights": 2, "amount_czk": 600}],
        },
    )
    monkeypatch.setattr(
        claim.reporting, "reservation_progress",
        lambda _r: {"expected": 1, "filled": 1, "incomplete": False, "status": "complete"},
    )
    _, apartment, stay = _stay(registered_minutes_ago=1)
    entity = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment,))
    db.execute("UPDATE legal_entity SET iban = ? WHERE id = ?", (IBAN, entity["legal_entity_id"]))
    db.execute(
        "UPDATE apartment SET stay_fee_collect = 1, stay_fee_guest_rails = 'iban,cash', "
        "stay_fee_guest_default_rail = 'iban' WHERE id = ?",
        (apartment,),
    )
    _guest(stay, "CZE")
    yield apartment, stay
    db.execute("DELETE FROM reservation_claim WHERE reservation_id = ?", (stay,))
    _drop_guests(stay)


def _claim(stay, completion_sent=False):
    now = db.utcnow()
    db.execute(
        "INSERT INTO reservation_claim (reservation_id, state, email, lang, completion_notified_at, "
        "created_at, updated_at) VALUES (?, 'claimed', 'guest@example.test', 'en', ?, ?, ?)",
        (stay, now if completion_sent else None, now, now),
    )


def _rows(stay, kind):
    return db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND kind = ? ORDER BY id", (stay, kind)
    )


def _rows_of(stay):
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
    return reservation, apartment


def test_the_completion_mail_is_queued_once_with_the_qr(fee_stay, monkeypatch):
    _works(monkeypatch)
    _, stay = fee_stay
    _claim(stay)
    door_codes.on_registration_complete(stay)
    reservation, apartment = _rows_of(stay)
    claim.maybe_notify_completion(reservation, apartment)
    claim.maybe_notify_completion(*_rows_of(stay))
    rows = _rows(stay, "completion")
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload"])
    assert payload[mail.QR_SPAYD_KEY].startswith("SPD*1.0*ACC:" + IBAN)
    assert "X-VS:" + str(stay) in payload[mail.QR_SPAYD_KEY]
    assert "600" in rows[0]["subject"]


def test_the_door_code_mail_repeats_the_bill_after_the_completion_mail(fee_stay, monkeypatch):
    _works(monkeypatch)
    _, stay = fee_stay
    _claim(stay, completion_sent=True)
    door_codes.reconcile()
    rows = _rows(stay, "door_code")
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload"])
    assert mail.DOOR_CODE_MARKER in rows[0]["payload"]
    assert PIN not in rows[0]["payload"]
    assert mail.QR_SPAYD_KEY in payload
    text = mail.delivery_body(payload)
    assert _t("en", "mail_completion_fee_heading") in text
    assert _t("en", "mail_completion_fee_already") in text
    assert f"{PIN}#" in text


def test_the_door_code_mail_has_no_bill_before_the_completion_mail(fee_stay, monkeypatch):
    """A partial group: the completion mail (the bill) has not gone, so the code goes alone."""
    _works(monkeypatch)
    monkeypatch.setattr(
        claim.reporting, "reservation_progress",
        lambda _r: {"expected": 2, "filled": 1, "incomplete": True, "status": "partial"},
    )
    _, stay = fee_stay
    _claim(stay)
    door_codes.reconcile()
    rows = _rows(stay, "door_code")
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload"])
    assert PIN not in rows[0]["payload"]
    assert mail.QR_SPAYD_KEY not in payload
    text = mail.delivery_body(payload)
    assert _t("en", "mail_completion_fee_heading") not in text
    assert _t("en", "mail_completion_fee_already") not in text
    assert _rows(stay, "completion") == []


def test_a_failing_fee_block_never_holds_the_code_mail(fee_stay, monkeypatch):
    _works(monkeypatch)

    def broken(*args, **kwargs):
        raise RuntimeError("fee block broke")

    monkeypatch.setattr(mail_notify, "_fee_block", broken)
    _, stay = fee_stay
    _claim(stay, completion_sent=True)
    door_codes.reconcile()
    rows = _rows(stay, "door_code")
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload"])
    assert mail.QR_SPAYD_KEY not in payload
    text = mail.delivery_body(payload)
    assert f"{PIN}#" in text
    assert _t("en", "mail_completion_fee_heading") not in text


def test_a_group_that_became_partial_gets_no_bill_on_a_reissued_code(fee_stay, monkeypatch):
    """The completion mail went for the whole group; then a guest dropped out and the code is reissued."""
    _works(monkeypatch)
    _, stay = fee_stay
    _claim(stay, completion_sent=True)
    door_codes.reconcile()
    first = _rows(stay, "door_code")
    assert len(first) == 1
    assert _t("en", "mail_completion_fee_heading") in mail.delivery_body(json.loads(first[0]["payload"]))
    monkeypatch.setattr(
        claim.reporting, "reservation_progress",
        lambda _r: {"expected": 2, "filled": 1, "incomplete": True, "status": "partial"},
    )
    # A reissued code: a new provider code on the row, not mailed yet.
    db.execute("UPDATE door_code SET notified_at = NULL, provider_code_id = '100' "
               "WHERE reservation_id = ?", (stay,))
    code = db.query_one("SELECT id FROM door_code WHERE reservation_id = ?", (stay,))
    door_codes._send_code_mail(int(code["id"]))
    rows = _rows(stay, "door_code")
    assert len(rows) == 2
    payload = json.loads(rows[-1]["payload"])
    assert mail.QR_SPAYD_KEY not in payload
    text = mail.delivery_body(payload)
    assert _t("en", "mail_completion_fee_heading") not in text
    assert _t("en", "mail_completion_fee_already") not in text


def test_with_the_flag_off_the_outbox_has_the_old_completion_mail(fee_stay, monkeypatch):
    _works(monkeypatch)
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    apartment, stay = fee_stay
    _claim(stay)
    door_codes.on_registration_complete(stay)
    claim.maybe_notify_completion(*_rows_of(stay))
    rows = _rows(stay, "completion")
    assert len(rows) == 1
    name = db.query_one("SELECT internal_name FROM apartment WHERE id = ?", (apartment,))["internal_name"]
    assert rows[0]["subject"] == _t("en", "mail_completion_subject", property=name)
    payload = json.loads(rows[0]["payload"])
    assert mail.QR_SPAYD_KEY not in payload
    assert _t("en", "mail_completion_fee_heading") not in mail.delivery_body(payload)
