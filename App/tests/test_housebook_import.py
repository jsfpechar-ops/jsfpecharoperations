"""Importing a spreadsheet must not be a way around the police field rules.

The house-book import exists so a host can bring years of history across from
whatever they used before, so rows that are already filed have to survive even
when they would not pass today's rules - they are the legal record. But a row
the app will later send to UbyPort has to obey appendix 3, or the host finds out
at submission time with the deadline already running.
"""
from __future__ import annotations

import pytest

from app import db, housebook, validation

HEADER = (
    "Surname;Given name(s);Date of birth;Nationality;Travel document no.;"
    "Permanent residence abroad;Stay from;Stay to;Purpose of stay;Reported to police"
)


@pytest.fixture()
def apartment_id() -> int:
    db.init_db()
    now = db.utcnow()
    _purge()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Import Test", "seat": "Praha", "ico": "12345678", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Flat",
            "city_en": "Prague",
            "permalink_token": "imptok1",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    yield apartment_id
    _purge()


def _purge():
    for row in db.query("SELECT id FROM apartment WHERE permalink_token LIKE 'imptok%'"):
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM legal_entity WHERE name = 'Import Test'")


def _import(apartment_id: int, *lines: str):
    body = "\n".join((HEADER,) + lines).encode("utf-8")
    return housebook.import_csv(body, apartment_id)


def _guests(apartment_id: int):
    return db.query(
        "SELECT g.* FROM guest g JOIN reservation r ON r.id = g.reservation_id"
        " WHERE r.apartment_id = ?",
        (apartment_id,),
    )


def test_a_pipe_never_reaches_the_database(apartment_id):
    """A pipe is the UbyPort field separator; one in a name corrupts the batch."""
    _import(
        apartment_id,
        "Smith|Jones;John;01.01.1990;GBR;P1234567;Street 1, London, GBR;"
        "01.01.2025;05.01.2025;10;yes",
    )

    for guest in _guests(apartment_id):
        for field in ("surname", "first_name", "res_street", "res_city", "note"):
            assert "|" not in (guest[field] or ""), f"{field} kept a pipe"


def test_an_over_length_name_is_cut_to_what_ubyport_accepts(apartment_id):
    """The import used to allow 35 characters where the police allow 24."""
    long_name = "Bartholomewmaximilianconstantine"
    assert len(long_name) > validation.MAX_FIRST_NAME

    _import(
        apartment_id,
        f"Smith;{long_name};01.01.1990;GBR;P1234567;Street 1, London, GBR;"
        "01.01.2025;05.01.2025;10;yes",
    )

    for guest in _guests(apartment_id):
        assert len(guest["first_name"]) <= validation.MAX_FIRST_NAME
        assert len(guest["surname"]) <= validation.MAX_SURNAME


def test_history_that_is_already_filed_is_kept_even_if_it_looks_wrong(apartment_id):
    """These rows are the six-year legal record; refusing them loses history."""
    result = _import(
        apartment_id,
        "Novak;;;;;;01.01.2020;05.01.2020;;yes",
    )

    assert _guests(apartment_id), f"a filed record was dropped: {result}"


def test_a_row_we_will_have_to_send_is_refused_while_it_can_still_be_fixed(apartment_id):
    """Better a line number now than a police rejection against the deadline."""
    result = _import(
        apartment_id,
        "Nguyen;Van;01.01.1990;GBR;short;Street 1, London, GBR;"
        "01.01.2199;05.01.2199;10;no",
    )

    assert not _guests(apartment_id), "an unsendable row was queued for UbyPort"
    assert result["skipped"] >= 1
    assert any("2" in str(message) for message in result["errors"]), result


def test_a_good_pending_row_still_imports(apartment_id):
    result = _import(
        apartment_id,
        "Nguyen;Van;01.01.1990;VNM;P1234567;Street 1, Hanoi, VNM;"
        "01.01.2199;05.01.2199;10;no",
    )

    assert _guests(apartment_id), f"a valid row was refused: {result}"


def test_a_name_outside_cp1250_is_folded_not_hollowed_out(apartment_id):
    """Same rule as the guest form: fold to the passport's Latin spelling."""
    _import(
        apartment_id,
        "Nguy\u1ec5n;Van;01.01.1990;VNM;P1234567;Street 1, Hanoi, VNM;"
        "01.01.2025;05.01.2025;10;yes",
    )

    surnames = [guest["surname"] for guest in _guests(apartment_id)]
    assert "NGUYEN" in surnames, surnames
