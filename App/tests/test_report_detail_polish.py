"""The report surfaces should stay free of raw register values.

The Reports list already translates the mode, but the detail page still printed
the transport endpoint in its key-value panel, showed a guest's nationality as
the raw ISO code, described a receipt in implementation terms, and rendered an
empty "Guests in this transmission" table with no explanation when nothing
reached UbyPort. This pins the audit's fixes (C-42 / UX-146).
"""
from __future__ import annotations

import re

from app import db, host_i18n, reporting
from tests.test_submission_retry_cap import (  # noqa: F401
    AcceptingClient,
    RefusingClient,
    _cleanup,
    _seed,
    host as host,
)

EN = "?lang=en"
CS = "?lang=cs"

FIRST_KV_RE = re.compile(r'<dl class="kv">(.*?)</dl>', re.DOTALL)
TECHNICAL_RE = re.compile(
    r'<details class="panel technical">(.*?)</details>', re.DOTALL
)

ENDPOINT_EN = host_i18n.STRINGS["en"]["reports.detail.endpoint"]
ENDPOINT_CS = host_i18n.STRINGS["cs"]["reports.detail.endpoint"]
NATION_EN = "United Kingdom"
NATION_CS = "Spojené království"
HINT_EN = "One PDF receipt per accepted report."
HINT_CS = "Jedna PDF doručenka za každé přijaté hlášení."
EMPTY_EN = "Nothing reached UbyPort, so no guest was processed."
EMPTY_CS = "Do UbyPortu nic nedorazilo, žádný host nebyl zpracován."


def _send(apartment, monkeypatch, client):
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client())
    pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
    return reporting.submit_batch(apartment, pairs, mode="manual")


def _erase(apartment_id: int) -> None:
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
        db.execute(
            "DELETE FROM legal_entity WHERE id = ?", (entity["legal_entity_id"],)
        )


def _first_kv(page: str) -> str:
    match = FIRST_KV_RE.search(page)
    assert match, "no key-value panel on the report detail page"
    return match.group(1)


def _technical(page: str) -> str:
    match = TECHNICAL_RE.search(page)
    assert match, "no technical-details disclosure on the report detail page"
    return match.group(1)


def test_the_endpoint_is_moved_into_technical_details(host, monkeypatch):
    apartment, _reservation, _guest = _seed("ux146-endpoint")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        page = host.get(f"/submissions/{sent['submission_id']}{EN}").text

        assert ENDPOINT_EN not in _first_kv(page)
        assert ENDPOINT_EN in _technical(page)
    finally:
        _erase(apartment["id"])


def test_the_czech_endpoint_is_also_technical_only(host, monkeypatch):
    apartment, _reservation, _guest = _seed("ux146-endpoint-cs")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        page = host.get(f"/submissions/{sent['submission_id']}{CS}").text

        assert ENDPOINT_CS not in _first_kv(page)
        assert ENDPOINT_CS in _technical(page)
    finally:
        _erase(apartment["id"])


def test_a_guest_nationality_is_shown_as_a_country_name(host, monkeypatch):
    apartment, _reservation, _guest = _seed("ux146-country")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)

        english = host.get(f"/submissions/{sent['submission_id']}{EN}").text
        assert NATION_EN in english
        assert "GBR" not in english

        czech = host.get(f"/submissions/{sent['submission_id']}{CS}").text
        assert NATION_CS in czech
    finally:
        _erase(apartment["id"])


def test_the_receipts_hint_is_about_the_receipt_not_the_implementation(
    host, monkeypatch,
):
    apartment, _reservation, _guest = _seed("ux146-hint")
    try:
        sent = _send(apartment, monkeypatch, AcceptingClient)
        # The ZIP header, and with it the hint, is offered once a receipt exists.
        db.update("submission", sent["submission_id"], {"receipt_pdf": "JVBERi0="})

        english = host.get(f"/submissions{EN}").text
        assert HINT_EN in english
        assert "built on disk" not in english

        czech = host.get(f"/submissions{CS}").text
        assert HINT_CS in czech
        assert "na disku" not in czech
    finally:
        _erase(apartment["id"])


def test_the_receipts_hint_copy_is_in_both_dictionaries():
    assert host_i18n.STRINGS["en"]["reports.download_receipts_hint"] == HINT_EN
    assert host_i18n.STRINGS["cs"]["reports.download_receipts_hint"] == HINT_CS


def test_an_empty_transmission_explains_itself(host, monkeypatch):
    apartment, _reservation, _guest = _seed("ux146-empty")
    try:
        sent = _send(apartment, monkeypatch, RefusingClient)
        db.update("submission", sent["submission_id"], {"guest_ids": "[]"})

        english = host.get(f"/submissions/{sent['submission_id']}{EN}").text
        assert EMPTY_EN in english

        czech = host.get(f"/submissions/{sent['submission_id']}{CS}").text
        assert EMPTY_CS in czech
    finally:
        _erase(apartment["id"])


def test_the_empty_transmission_copy_is_in_both_dictionaries():
    assert host_i18n.STRINGS["en"]["reports.detail.guests_empty"] == EMPTY_EN
    assert host_i18n.STRINGS["cs"]["reports.detail.guests_empty"] == EMPTY_CS
