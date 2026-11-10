"""1079 (S15): the child box is hidden for adults by the script alone; filing is as before.

The guest form hides the "child travelling on a parent's passport" box when the
birth date says 18 or over. That is display only: the script never unticks the
box and never changes a value, and the server reads the form exactly as before.
These tests pin the script's limits at source and the stored guest row.
"""
from __future__ import annotations

import threading
from pathlib import Path

from fastapi.testclient import TestClient

from app import db, validation
from app.main import app
from tests.conftest import complete_guest_claim
from tests.test_guest_child_document import TOKEN, _cleanup, _payload, _seed

APP = Path(__file__).resolve().parents[1] / "app"
KEPT = ("doc_number", "note", "visa_number", "submit_state")


def _client(reservation_id: int) -> TestClient:
    client = TestClient(app)
    complete_guest_claim(client, TOKEN, reservation_id, party_size=2)
    return client


def _save(client: TestClient, reservation_id: int, **overrides):
    response = client.post(f"/l/{TOKEN}/{reservation_id}/save?lang=en", data=_payload(**overrides))
    assert response.status_code < 400, response.text[:400]
    return response


def _guests(reservation_id: int):
    return db.query("SELECT * FROM guest WHERE reservation_id = ? ORDER BY id", (reservation_id,))


def _child(**overrides):
    data = {
        "first_name": "Amy",
        "birth_date": "1.1.2020",
        "doc_number": "",
        "child_in_passport": "1",
        "parent_doc_number": "PARENT79",
    }
    data.update(overrides)
    return data


# --- source pins: what the script may and may not do --------------------------


def test_the_script_only_ever_shows_or_hides_the_wrapper():
    script = (APP / "static" / "signature.js").read_text(encoding="utf-8")
    toggle = script.split("function initChildToggle()", 1)[1].split("\n  }", 1)[0]
    assert "toggle.checked =" not in toggle, "the script must never tick or untick the box"
    assert ".value =" not in toggle, "the script must never write a value"
    assert toggle.count(".required =") == 2
    assert "docInput.required = !toggle.checked" in toggle
    assert "parentInput.required = toggle.checked" in toggle
    assert "childWrap.style.display" in toggle
    assert 'window.addEventListener("pageshow"' in toggle
    # A ticked box is shown before anything else is asked.
    show = toggle.split("function showBox(mayHide) {", 1)[1].split("\n    }", 1)[0]
    lines = [line.strip() for line in show.strip().splitlines()]
    assert lines[1] == 'if (toggle.checked) { childWrap.style.display = ""; return; }', lines
    # The box's own change may reveal the wrapper, never hide it.
    apply = toggle.split("function apply() {", 1)[1].split("\n    }", 1)[0]
    assert apply.rstrip().endswith("showBox(false);")
    assert "showBox(true)" not in apply


def test_the_template_marks_the_wrapper_and_does_not_hide_it():
    form = (APP / "templates" / "guest" / "form.html").read_text(encoding="utf-8")
    lines = [line for line in form.splitlines() if 'id="child-wrap"' in line]
    assert len(lines) == 1 and form.count('id="child-wrap"') == 1
    assert lines[0].strip() == '<div class="g-field" id="child-wrap">'
    assert "style=" not in lines[0], "without JavaScript the box must stay visible"
    after = form.split('id="child-wrap"', 1)[1]
    assert after.lstrip(">").lstrip().startswith('<label class="checkline" for="child_in_passport">')


# --- filing pins: the stored row is what main stores ---------------------------


def test_a_save_without_the_box_stores_the_typed_document_number():
    reservation_id = _seed()
    try:
        _save(_client(reservation_id), reservation_id, visa_number="VISA79")
        rows = _guests(reservation_id)
        assert len(rows) == 1
        assert rows[0]["doc_number"] == "P1234567"
        assert rows[0]["doc_number"] != validation.INPASS
        assert rows[0]["visa_number"] == "VISA79"
        assert validation.INPASS_NOTE_PREFIX not in (rows[0]["note"] or "")
    finally:
        _cleanup()


def test_a_save_with_the_box_and_a_parent_number_stores_inpass_and_the_note():
    reservation_id = _seed()
    try:
        _save(_client(reservation_id), reservation_id, **_child())
        rows = _guests(reservation_id)
        assert len(rows) == 1
        assert rows[0]["doc_number"] == validation.INPASS
        assert rows[0]["note"] == validation.INPASS_NOTE_PREFIX + "PARENT79"
    finally:
        _cleanup()


def test_a_ticked_box_is_honoured_whatever_the_birth_date_says():
    """The server does not look at the age: a box the script would have hidden
    for an adult still files as INPASS if it arrives ticked, as on main."""
    reservation_id = _seed()
    try:
        _save(_client(reservation_id), reservation_id, **_child(birth_date="1.1.1990"))
        rows = _guests(reservation_id)
        assert len(rows) == 1 and rows[0]["doc_number"] == validation.INPASS
    finally:
        _cleanup()


# --- idempotency ---------------------------------------------------------------


def test_the_same_edit_posted_twice_leaves_one_unchanged_row():
    reservation_id = _seed()
    try:
        client = _client(reservation_id)
        _save(client, reservation_id, **_child())
        guest_id = _guests(reservation_id)[0]["id"]
        seen = []
        for _ in range(2):
            _save(client, reservation_id, guest_id=str(guest_id), **_child(parent_doc_number="PARENT80"))
            rows = _guests(reservation_id)
            assert len(rows) == 1 and rows[0]["id"] == guest_id
            seen.append({key: rows[0][key] for key in KEPT})
        assert seen[0] == seen[1], seen
        assert seen[0]["doc_number"] == validation.INPASS
        assert seen[0]["note"] == validation.INPASS_NOTE_PREFIX + "PARENT80"
    finally:
        _cleanup()


# --- concurrency ---------------------------------------------------------------


def test_an_adult_and_a_child_saved_at_the_same_moment_keep_their_own_values():
    reservation_id = _seed()
    try:
        adult_client = _client(reservation_id)
        _save(adult_client, reservation_id, visa_number="VISA79")
        adult_id = _guests(reservation_id)[0]["id"]
        _save(adult_client, reservation_id, **_child())
        # A second browser of the same group: its own client, the same claim.
        # (Claiming again from a new client would end the first one's claim.)
        child_client = TestClient(app)
        for cookie in adult_client.cookies.jar:
            child_client.cookies.set(cookie.name, cookie.value)
        ids = [row["id"] for row in _guests(reservation_id)]
        assert len(ids) == 2
        child_id = [i for i in ids if i != adult_id][0]

        gate = threading.Barrier(2)
        results = {}

        def post(name, client, data):
            try:
                gate.wait(timeout=10)
                response = client.post(f"/l/{TOKEN}/{reservation_id}/save?lang=en", data=_payload(**data))
                results[name] = response.status_code
            except Exception as error:  # reported by the assert below
                results[name] = repr(error)

        threads = [
            threading.Thread(target=post, args=("adult", adult_client, {
                "guest_id": str(adult_id), "doc_number": "P7654321", "visa_number": "VISA80",
            })),
            threading.Thread(target=post, args=("child", child_client, _child(
                guest_id=str(child_id), parent_doc_number="PARENT81",
            ))),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert all(isinstance(code, int) and code < 400 for code in results.values()), results
        assert set(results) == {"adult", "child"}

        rows = {row["id"]: row for row in _guests(reservation_id)}
        assert set(rows) == {adult_id, child_id}, "the guest count changed"
        adult, child = rows[adult_id], rows[child_id]
        assert adult["doc_number"] == "P7654321" and adult["visa_number"] == "VISA80"
        assert adult["first_name"].upper() == "JOHN PAUL"
        assert validation.INPASS_NOTE_PREFIX not in (adult["note"] or "")
        assert child["doc_number"] == validation.INPASS
        assert child["note"] == validation.INPASS_NOTE_PREFIX + "PARENT81"
        assert child["first_name"].upper() == "AMY"
        assert not child["visa_number"]
    finally:
        _cleanup()
