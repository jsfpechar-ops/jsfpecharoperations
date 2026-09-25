"""What a rejected report tells the host to do next, and the words it uses.

A refused report used to end at the detail page: the outcome said rejected, the
only file offered was the error report, and nothing said where the guest data
lives. The page now offers the stay itself, and the header problems point at the
property settings they come from instead of leaving the host to find them.

The fallback text for a code the live code book does not explain used to send
the host to a Doručenka, which a rejected report does not have -- the register
only issues one for a report it accepted. It now names the code lists instead.
"""
from __future__ import annotations

import re

from app import db, host_i18n, reporting
from app.ubyport import errors as uby_errors
from tests.test_submission_retry_cap import (  # noqa: F401
    AcceptingClient,
    DuplicateClient,
    RefusingClient,
    _cleanup,
    _seed,
    host as host,
)

FIX_STAY = "Open the stay to fix"
FIX_STAY_CS = "Otevřít pobyt a opravit"
OPEN_PROPERTY = "Open property reporting details"
OPEN_PROPERTY_CS = "Otevřít údaje pro hlášení"

# A host who logs in without touching the language switch lands in Czech -- the
# signed-out default the login page itself used -- so every English assertion
# has to ask for English by URL.
EN = "?lang=en"
CS = "?lang=cs"

# The English the audit specifies for a code the code book does not cover.
FALLBACK_EN = (
    "UbyPort error %(code)s — refresh code lists on the property page to see "
    "the explanation."
)
FALLBACK_CS = (
    "Chyba UbyPortu %(code)s — vysvětlení uvidíte po obnovení číselníků na "
    "stránce ubytování."
)


def _send(apartment, monkeypatch, client):
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client())
    pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
    return reporting.submit_batch(apartment, pairs, mode="manual")


def _erase(apartment_id: int) -> None:
    """Leave the shared database as it was found: the account stays, the rest goes.

    The suite shares one database and the empty-install canary counts
    properties, stays and guests, so a seeded property must not outlive its test.
    """
    entity = db.query_one(
        "SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,)
    )
    _cleanup(apartment_id)
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment_id,),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    if entity:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity["legal_entity_id"],))


def _actions(page: str) -> str:
    match = re.search(r'<div class="actions">(.*?)</div>', page, re.S)
    return match.group(1) if match else ""


def _header_help(page: str) -> str:
    """The paragraph that offers the property's reporting details, if it is there.

    Found by the link it carries rather than by its heading, so the same helper
    reads the English and the Czech page.
    """
    end = page.find('#ubyport"')
    if end == -1:
        return ""
    return page[page.rfind("<p", 0, end) : page.find("</p>", end) + 4]


def test_a_rejected_report_offers_the_stay_that_needs_fixing(host, monkeypatch):
    apartment, reservation, _guest = _seed("ux96-rejected")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        page = host.get(f"/submissions/{sent['submission_id']}{EN}").text
        actions = _actions(page)
        assert FIX_STAY in actions, "a rejected report must say where to fix it"
        assert f'href="/reservations/{reservation["id"]}#guests"' in actions
    finally:
        _erase(apartment["id"])


def test_the_next_step_is_the_coral_primary_and_the_only_button(host, monkeypatch):
    """Nothing was accepted, so there is no receipt to compete with it."""
    apartment, reservation, _guest = _seed("ux96-coral")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        page = host.get(f"/submissions/{sent['submission_id']}{EN}").text
        actions = _actions(page)
        assert (
            f'<a class="btn primary" href="/reservations/{reservation["id"]}#guests">'
            in actions
        )
        assert actions.count("<a class=\"btn") == 1
    finally:
        _erase(apartment["id"])


def test_an_accepted_report_offers_nothing_to_fix(host, monkeypatch):
    apartment, _reservation, _guest = _seed("ux96-accepted")
    try:
        sent = _send(apartment, monkeypatch, AcceptingClient)
        page = host.get(f"/submissions/{sent['submission_id']}{EN}").text
        assert FIX_STAY not in page
    finally:
        _erase(apartment["id"])


def test_a_duplicate_report_offers_nothing_to_fix(host, monkeypatch):
    """150 means the register already holds the record: there is nothing to fix."""
    apartment, _reservation, _guest = _seed("ux96-duplicate")
    try:
        sent = _send(apartment, monkeypatch, DuplicateClient)
        page = host.get(f"/submissions/{sent['submission_id']}{EN}").text
        assert FIX_STAY not in page
    finally:
        _erase(apartment["id"])


def test_the_czech_page_offers_the_same_next_step(host, monkeypatch):
    apartment, reservation, _guest = _seed("ux96-czech")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        page = host.get(f"/submissions/{sent['submission_id']}{CS}").text
        assert FIX_STAY_CS in page
        assert f'href="/reservations/{reservation["id"]}#guests"' in page
    finally:
        _erase(apartment["id"])


def test_the_header_help_points_at_the_property_that_owns_the_report(
    host, monkeypatch
):
    apartment, _reservation, _guest = _seed("ux96-header")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        db.update("submission", sent["submission_id"], {"header_errors": ";12;"})
        page = host.get(f"/submissions/{sent['submission_id']}{EN}").text
        block = _header_help(page)
        assert OPEN_PROPERTY in block
        assert f'href="/apartments/{apartment["id"]}#ubyport"' in block
    finally:
        _erase(apartment["id"])


def test_the_czech_header_help_says_the_same(host, monkeypatch):
    apartment, _reservation, _guest = _seed("ux96-header-cs")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        db.update("submission", sent["submission_id"], {"header_errors": ";12;"})
        page = host.get(f"/submissions/{sent['submission_id']}{CS}").text
        assert OPEN_PROPERTY_CS in page
        assert f'href="/apartments/{apartment["id"]}#ubyport"' in page
    finally:
        _erase(apartment["id"])


def test_the_header_help_is_not_shown_when_there_are_no_header_problems(
    host, monkeypatch
):
    apartment, _reservation, _guest = _seed("ux96-noheader")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        page = host.get(f"/submissions/{sent['submission_id']}{EN}").text
        assert OPEN_PROPERTY not in page
    finally:
        _erase(apartment["id"])


def test_the_audited_next_step_copy_is_in_both_dictionaries():
    for key, en, cs in (
        ("reports.detail.fix_stay", FIX_STAY, FIX_STAY_CS),
        ("reports.detail.header_help_link", OPEN_PROPERTY, OPEN_PROPERTY_CS),
    ):
        assert host_i18n.STRINGS["en"][key] == en
        assert host_i18n.STRINGS["cs"][key] == cs


def test_the_fallback_names_the_code_lists_in_english():
    assert uby_errors.describe("12", {}) == FALLBACK_EN % {"code": "12"}


def test_the_fallback_names_the_code_lists_in_czech():
    assert uby_errors.describe("12", {}, "cs") == FALLBACK_CS % {"code": "12"}


def test_the_fallback_no_longer_sends_the_host_to_a_receipt():
    for lang in ("en", "cs"):
        text = uby_errors.describe("12", {}, lang)
        assert "Doručen" not in text, "a rejected report has no Doručenka"
        assert "receipt" not in text.lower()


def test_the_fallback_cannot_be_read_as_a_reason_not_to_resend():
    """The markers decide whether a report is worth resending.

    They are substring matches against the message, so wording that happens to
    contain one would silently park the record as unfixable.
    """
    for lang in ("en", "cs"):
        text = uby_errors.describe("12", {}, lang)
        assert not uby_errors.is_non_correctable(text), text
        assert not uby_errors.is_duplicate(text), text


def test_a_known_code_and_a_known_code_book_stay_english():
    """Only the fallback is ours to word; anything the register explains is its own."""
    assert uby_errors.describe("150", {}, "cs") == uby_errors.KNOWN_CODES["150"]
    assert uby_errors.describe("12", {"12": "Z kódu"}, "cs") == "Z kódu"


def test_the_language_never_changes_the_outcome():
    """``lang`` may only reword the message, never the state the app acts on."""
    codebook = {"12": "Z kódu"}
    for header, record in (
        (";12;", ""),
        ("", ";112;"),
        ("", ";150;"),
        (";12;", ";150;"),
        ("", ""),
    ):
        en = uby_errors.classify(header, record, codebook)
        cs = uby_errors.classify(header, record, codebook, "cs")
        assert en[0] == cs[0], (header, record)
        assert len(en[1]) == len(cs[1])


def test_a_localized_message_cannot_look_like_a_duplicate():
    """The route runs is_duplicate over the shown text, so the translation must not lie."""
    _state, messages = uby_errors.classify("", ";12;", {}, "cs")
    assert not any(uby_errors.is_duplicate(message) for message in messages)
