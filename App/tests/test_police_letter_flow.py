"""1085: the police letter paste, check and confirm flow, and the automatic test.

Filing HIGH RISK: a wrong value means filings under the wrong account. Nothing
saves without the tick, the pasted text is never kept, and the connection test
never files. All values here are the fake ``SAMPLE_*`` ones.
"""
from __future__ import annotations

import html
import inspect
import logging
import re
import threading
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n, police_letter, reporting
from app.main import app
from app.police_letter import FieldResult, LetterResult
from app.routes import admin
from app.ubyport import soap
from app.ubyport.client import UbyportAuthError, UbyportClient, UbyportTransportError
from app.ubyport_sample_pdf import (
    SAMPLE_FACILITY_LINE1,
    SAMPLE_IDUB,
    SAMPLE_WS_PASSWORD,
    SAMPLE_WS_USER,
    SAMPLE_ZKRATKA,
)
from tests.conftest import login_as, mark_security_prompt_seen

USERNAME = "police-letter-host"
OTHER = "police-letter-other"
MARKER = "MARKER-7f3a-only-in-the-paste"
LETTER = (
    "Přihlašovací údaje pro robotické vkládání Ubyport Webová služba\n"
    f"{MARKER}\n"
    f"Přihlašovací jméno: {SAMPLE_WS_USER}\n"
    f"Přístupové heslo: {SAMPLE_WS_PASSWORD}\n"
    f"IDUB: {SAMPLE_IDUB}\n"
)
SAVED_IDUB = "123456789012"
SAVED_LOGIN = "UBY-WSform"
SAVED_MARK = "ABC"
READ_ONLY = {"TestDostupnosti", "MaximalniDelkaSeznamu", "DejMiCiselnik"}


def _en(key: str, **params) -> str:
    text = host_i18n.translate("en", key, **params)
    assert text and text != key, key
    return str(text)


def _user_ids(username):
    return [r["id"] for r in db.query("SELECT id FROM user_account WHERE username = ?", (username,))]


def _cleanup():
    for username in (USERNAME, OTHER):
        for user_id in _user_ids(username):
            for apartment in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,)):
                db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))
                db.execute(
                    "DELETE FROM guest WHERE reservation_id IN"
                    " (SELECT id FROM reservation WHERE apartment_id = ?)",
                    (apartment["id"],),
                )
                db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
            db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _apartments(username=USERNAME):
    return db.query(
        "SELECT * FROM apartment WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?) ORDER BY id",
        (username,),
    )


def _apartment(username=USERNAME):
    return _apartments(username)[0]


def _operator_id(username=USERNAME) -> str:
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    row = db.query_one(
        "SELECT id FROM legal_entity WHERE owner_user_id = ? ORDER BY id LIMIT 1", (owner["id"],)
    )
    if row:
        return str(row["id"])
    return str(
        db.insert(
            "legal_entity",
            {"name": "Letter Operator", "owner_user_id": owner["id"], "created_at": db.utcnow()},
        )
    )


def _payload(username=USERNAME, **overrides):
    data = {
        "internal_name": "Letter Flat",
        "addr_city": "Praha",
        "addr_obec": "Praha",
        "addr_street": "Synthetic",
        "addr_house_no": "12",
        "addr_zip": "120 00",
        "uby_idub": SAVED_IDUB,
        "uby_mark": SAVED_MARK,
        "uby_name": "Penzion Letter",
        "uby_contact": "host@letter.test",
        "uby_ws_user": SAVED_LOGIN,
        "permalink_window_days": "2",
        "permalink_reachback_days": "30",
        "legal_entity_id": _operator_id(username),
    }
    data.update(overrides)
    return data


def _letter_payload(**overrides):
    """A save of the three letter values (1100: no tick)."""
    data = _payload(
        uby_idub=SAMPLE_IDUB,
        uby_ws_user=SAMPLE_WS_USER,
        uby_mark=SAMPLE_ZKRATKA,
        letter_fields="uby_idub,uby_ws_user,uby_mark",
        letter_line_uby_idub="5",
        letter_line_uby_ws_user="3",
        letter_line_uby_mark="3",
    )
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


def _login(username) -> TestClient:
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    mark_security_prompt_seen(
        auth.create_account(f"{USERNAME}@example.test", "Letter Host", username=USERNAME)
    )
    client = _login(USERNAME)
    created = client.post("/apartments", data=_payload(), follow_redirects=False)
    assert created.status_code == 303, created.text
    try:
        yield client
    finally:
        _cleanup()


class _FakeClient:
    endpoint = "https://fake.invalid/ws"

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def test_availability(self):
        self.calls.append("TestDostupnosti")
        if self.error:
            raise self.error
        return True

    def max_batch_size(self):
        self.calls.append("MaximalniDelkaSeznamu")
        return 32

    def code_list(self, kind):
        self.calls.append("DejMiCiselnik")
        return []


@pytest.fixture
def fake_client(monkeypatch):
    """Install a fake police client; ``made`` lists every client that was built."""
    state = {"error": None, "made": []}

    def client_for(apartment, env=None):
        client = _FakeClient(state["error"])
        state["made"].append(client)
        return client

    monkeypatch.setattr(reporting, "client_for", client_for)
    return state


@pytest.fixture
def no_client(monkeypatch):
    """Any attempt to build a police client fails the test."""
    calls = []

    def client_for(apartment, env=None):
        calls.append(apartment["id"])
        raise AssertionError("the police client must not be built here")

    monkeypatch.setattr(reporting, "client_for", client_for)
    return calls


def _paste(client, apartment_id, text=LETTER, **extra):
    return client.post(
        f"/apartments/{apartment_id}/police-letter",
        data={"letter_text": text, **extra},
        follow_redirects=False,
    )


def _input_value(page: str, name: str) -> str:
    match = re.search(rf'<input type="text" id="{name}" name="{name}" value="([^"]*)"', page)
    assert match, f"no text input {name}"
    return html.unescape(match.group(1))


def _password_input(page: str) -> str:
    return re.search(r'<input type="text" id="uby_ws_password"[^>]*>', page).group(0)


def _status_line(page: str) -> str:
    match = re.search(r'<p class="police-letter-status[^"]*"[^>]*>(.*?)</p>', page, re.S)
    assert match, "no status line"
    return html.unescape(match.group(1))


def _label(name: str) -> str:
    return dict(admin._LETTER_BOX_LABELS)[name]


def _flash(response) -> str:
    assert response.status_code == 303, response.text[:300]
    return unquote(response.headers["location"])


def _audit_text(username=USERNAME) -> str:
    rows = db.query(
        "SELECT * FROM audit WHERE owner_user_id IN"
        " (SELECT id FROM user_account WHERE username = ?)",
        (username,),
    )
    return "\n".join(" ".join(str(value) for value in dict(row).values()) for row in rows)


# --- a. the paste: check answers, nothing saved, nothing kept ---------------


def test_paste_fills_the_five_boxes_and_saves_nothing(host, no_client):
    """1100: the no-JS read fills every box; no check block, no tick."""
    before = dict(_apartment())
    text = LETTER + f"Ubytovací zařízení:\n{SAMPLE_FACILITY_LINE1}\n"
    response = _paste(host, before["id"], text)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    page = response.text

    assert _input_value(page, "uby_idub") == SAMPLE_IDUB
    assert _input_value(page, "uby_ws_user") == SAMPLE_WS_USER
    assert _input_value(page, "uby_mark") == SAMPLE_ZKRATKA
    assert _input_value(page, "uby_name") == SAMPLE_FACILITY_LINE1
    assert f'value="{SAMPLE_WS_PASSWORD}"' in _password_input(page)
    assert 'autocomplete="off" autocapitalize="off" spellcheck="false"' in _password_input(page)
    assert 'name="letter_fields" value="uby_idub,uby_ws_user,uby_mark"' in page
    assert "police-letter-check" not in page
    assert "letter_ok" not in page
    assert "<code>" not in page[page.index('id="sec-police"') : page.index('id="automation"')]
    status = _status_line(page)
    assert status.startswith(_en("police_letter.filled", names="").split(":")[0])
    for name in ("uby_idub", "uby_ws_user", "uby_ws_password", "uby_mark", "uby_name"):
        assert _en(_label(name)) in status
    assert _en("police_letter.saved_now", value=SAVED_IDUB) in page
    settings_form = re.search(r'<form[^>]*id="property-settings-form"[^>]*>', page).group(0)
    assert 'data-dirty-start="1"' in settings_form
    assert re.search(r'<details class="prop-sec" id="sec-police"[^>]* open', page)

    textarea = re.search(r'<textarea id="letter_text"[^>]*>(.*?)</textarea>', page, re.S)
    assert textarea.group(1) == ""
    assert MARKER not in page

    assert dict(_apartment()) == before
    audit = _audit_text()
    for secret in (SAMPLE_IDUB, SAMPLE_WS_USER, SAMPLE_WS_PASSWORD, SAMPLE_FACILITY_LINE1, MARKER):
        assert secret not in audit
    assert "police_letter_read" in audit
    assert no_client == []


def test_paste_as_json_answers_the_five_values(host, no_client):
    """1100 (D-d): the same route answers JSON for the paste script."""
    before = dict(_apartment())
    text = LETTER + f"Ubytovací zařízení: {SAMPLE_FACILITY_LINE1}\n"
    response = host.post(
        f"/apartments/{before['id']}/police-letter",
        data={"letter_text": text},
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["status"] == "ok"
    assert {name: item["value"] for name, item in body["fields"].items()} == {
        "uby_idub": SAMPLE_IDUB,
        "uby_ws_user": SAMPLE_WS_USER,
        "uby_ws_password": SAMPLE_WS_PASSWORD,
        "uby_mark": SAMPLE_ZKRATKA,
        "uby_name": SAMPLE_FACILITY_LINE1,
    }
    assert body["missing"] == []
    assert set(body["filled"]) == set(body["fields"])
    assert MARKER not in response.text and "Přihlašovací jméno" not in response.text
    assert _en("police_letter.filled", names="").split(":")[0] in body["message"]
    assert dict(_apartment()) == before
    audit = _audit_text()
    for secret in (SAMPLE_IDUB, SAMPLE_WS_USER, SAMPLE_WS_PASSWORD, SAMPLE_FACILITY_LINE1, MARKER):
        assert secret not in audit

    empty = host.post(
        f"/apartments/{before['id']}/police-letter",
        data={"letter_text": "  "},
        headers={"Accept": "application/json"},
    ).json()
    assert empty["status"] == "empty" and empty["message"] == _en("police_letter.empty")
    assert all(not item["value"] for item in empty["fields"].values())

    stranger = TestClient(app)
    logged_out = stranger.post(
        f"/apartments/{before['id']}/police-letter",
        data={"letter_text": text},
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )
    assert not logged_out.headers.get("content-type", "").startswith("application/json")
    assert SAMPLE_WS_PASSWORD not in logged_out.text and SAMPLE_IDUB not in logged_out.text


def test_the_password_box_has_no_value_on_a_get_or_a_refused_save(host, no_client):
    """1100 (D-c): only the answer to a paste carries the read password."""
    apartment = _apartment()
    host.post(f"/apartments/{apartment['id']}", data=_payload(uby_ws_password="Stored-Pass-1"), follow_redirects=False)
    get = host.get(f"/apartments/{apartment['id']}?view=settings&section=reporting").text
    assert "value=" not in _password_input(get)
    assert "Stored-Pass-1" not in get
    refused = host.post(
        f"/apartments/{apartment['id']}",
        data=_payload(uby_ws_password="Typed-Pass-2", legal_entity_id=""),
        follow_redirects=False,
    )
    assert refused.status_code == 400
    assert "value=" not in _password_input(refused.text)
    assert "Typed-Pass-2" not in refused.text and "Stored-Pass-1" not in refused.text


def test_a_value_with_markup_comes_back_escaped(host, monkeypatch):
    """The parser never yields markup; the template must not trust that."""
    found = FieldResult(
        state="found", value="<b>" + SAMPLE_IDUB, line=2, label="IDUB", lines=(2,),
        source=("IDUB: <b>" + SAMPLE_IDUB,),
    )
    monkeypatch.setattr(
        police_letter,
        "parse_letter",
        lambda text: LetterResult(status="ok", fields={"uby_idub": found}),
    )
    response = _paste(host, _apartment()["id"])
    assert response.status_code == 422
    assert "<b>" + SAMPLE_IDUB not in response.text
    assert f'value="&lt;b&gt;{SAMPLE_IDUB}"' in response.text
    assert "IDUB: &lt;b&gt;" not in response.text


# --- b. values that are not taken ------------------------------------------


@pytest.mark.parametrize(
    "text, field, state",
    [
        (f"Přihlašovací jméno heslo: {SAMPLE_WS_USER}\nIDUB: {SAMPLE_IDUB}\n", "uby_ws_user", None),
        (
            f"Přihlašovací jméno: {SAMPLE_WS_USER}\nIDUB: {SAMPLE_IDUB}\nIDUB: 209988776656\n",
            "uby_idub",
            "unreadable",
        ),
        (
            f"Přihlašovací jméno: {SAMPLE_WS_USER}\nZkratka ubytovacího zařízení: OTHER\n"
            f"IDUB: {SAMPLE_IDUB}\n",
            "uby_ws_user",
            "conflict",
        ),
    ],
)
def test_a_value_that_is_not_safe_keeps_the_saved_one(host, text, field, state):
    apartment = _apartment()
    parsed = police_letter.parse_letter(text).fields[field].state
    assert parsed in ("ambiguous", "unreadable", "conflict")
    if state:
        assert parsed == state
    response = _paste(host, apartment["id"], text)
    assert response.status_code == 422
    page = response.text
    assert _input_value(page, field) == apartment[field]
    assert _en(_label(field)) in _status_line(page).split(":", 2)[-1]
    assert "letter_ok" not in page
    assert dict(_apartment()) == dict(apartment)


def test_an_ambiguous_state_shows_its_plain_line(host, monkeypatch):
    apartment = _apartment()
    monkeypatch.setattr(
        police_letter,
        "parse_letter",
        lambda text: LetterResult(
            status="ok",
            fields={"uby_ws_user": FieldResult(state="ambiguous", value="LEAK", line=1)},
        ),
    )
    page = _paste(host, apartment["id"]).text
    assert _input_value(page, "uby_ws_user") == SAVED_LOGIN
    assert "LEAK" not in page
    assert "letter_ok" not in page


@pytest.mark.parametrize(
    "text, key",
    [("   \n", "police_letter.empty"), ("x" * 20001, "police_letter.too_long")],
)
def test_empty_and_too_long_say_so(host, text, key):
    apartment = _apartment()
    response = _paste(host, apartment["id"], text)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert _en(key) in response.text
    assert 'id="police-letter-paste" open' in response.text
    assert re.search(r'<textarea id="letter_text"[^>]* autofocus', response.text)
    assert "police-letter-check" not in response.text
    assert 'data-dirty-start="1"' not in response.text
    assert dict(_apartment()) == dict(apartment)


# --- c. a parser crash never prints the text -------------------------------


def test_a_parser_crash_is_failed_and_never_logged(host, monkeypatch, caplog):
    def boom(text):
        raise ValueError(MARKER)

    monkeypatch.setattr(police_letter, "parse_letter", boom)
    with caplog.at_level(logging.DEBUG):
        response = _paste(host, _apartment()["id"])
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert _en("police_letter.failed") in response.text
    assert MARKER not in response.text
    assert MARKER not in caplog.text
    for record in caplog.records:
        assert MARKER not in str(record.exc_text or "") and not record.exc_info
    audit = _audit_text()
    assert MARKER not in audit
    assert "police_letter_failed" in audit and "error=ValueError" in audit


# --- d. who may post -------------------------------------------------------


@pytest.fixture
def spy_parser(monkeypatch):
    calls = []
    real = police_letter.parse_letter

    def spy(text):
        calls.append(1)
        return real(text)

    monkeypatch.setattr(police_letter, "parse_letter", spy)
    return calls


def test_no_csrf_token_is_refused_and_not_parsed(host, spy_parser):
    apartment = _apartment()
    other_post = host.post(
        f"/apartments/{apartment['id']}", data=_payload(_csrf=""), follow_redirects=False
    )
    response = _paste(host, apartment["id"], _csrf="")
    assert response.status_code == other_post.status_code
    assert response.status_code != 422
    assert "police-letter-check" not in response.text
    assert spy_parser == []
    assert SAMPLE_IDUB not in response.text


def test_logged_out_goes_to_the_login(host, spy_parser):
    apartment = _apartment()
    stranger = TestClient(app)
    response = _paste(stranger, apartment["id"])
    assert spy_parser == []
    assert SAMPLE_IDUB not in response.text
    if response.status_code == 303:
        assert "/login" in response.headers["location"]
    else:
        assert response.status_code in (400, 401, 403)


def test_another_hosts_property_is_not_parsed(host, spy_parser):
    apartment = _apartment()
    mark_security_prompt_seen(
        auth.create_account(f"{OTHER}@example.test", "Other Host", username=OTHER)
    )
    other = _login(OTHER)
    response = _paste(other, apartment["id"])
    assert response.status_code == 303
    assert response.headers["location"].startswith("/apartments?")
    assert spy_parser == []
    assert SAMPLE_IDUB not in response.text
    assert dict(_apartment()) == dict(apartment)


# --- e. nothing saves without each tick ------------------------------------


@pytest.mark.parametrize("path", ["", "/test-connection"])
def test_letter_values_save_without_a_tick_on_both_paths(host, fake_client, path):
    """1100: no tick; a letter save with a password is tested once on either path."""
    before = dict(_apartment())
    response = host.post(
        f"/apartments/{before['id']}{path}",
        data=_payload(
            uby_idub=SAMPLE_IDUB,
            uby_ws_user=SAMPLE_WS_USER,
            uby_mark=SAMPLE_ZKRATKA,
            uby_ws_password="typed-password",
            letter_fields="uby_idub,uby_ws_user,uby_mark",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:300]
    saved = _apartment()
    assert saved["uby_idub"] == SAMPLE_IDUB and saved["uby_ws_user"] == SAMPLE_WS_USER
    assert len(fake_client["made"]) == 1
    assert "typed-password" not in _audit_text()


@pytest.mark.parametrize("line", ["abc", "99999999999", "-1", "0", "5\n"])
def test_a_forged_line_number_never_crashes(host, no_client, line):
    before = dict(_apartment())
    response = host.post(
        f"/apartments/{before['id']}",
        data=_payload(
            uby_idub=SAMPLE_IDUB,
            letter_fields="uby_idub",
            letter_line_uby_idub=line,
            letter_src_uby_idub_1="FORGED-SOURCE-TEXT",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:300]
    assert "FORGED-SOURCE-TEXT" not in response.text
    page = host.get(f"/apartments/{before['id']}?view=settings&section=reporting").text
    assert "FORGED-SOURCE-TEXT" not in page
    assert _apartment()["uby_idub"] == SAMPLE_IDUB


# --- f. the automatic test -------------------------------------------------


def _save(client, apartment_id, path="", **overrides):
    return client.post(
        f"/apartments/{apartment_id}{path}", data=_letter_payload(**overrides), follow_redirects=False
    )


def test_a_confirmed_save_with_a_password_is_tested_once(host, fake_client):
    apartment = _apartment()
    location = _flash(_save(host, apartment["id"], uby_ws_password="typed-password"))
    assert _en("flash.apartments.letter_test_ok") in location
    assert "err=" not in location
    assert location.endswith("#ubyport")
    assert len(fake_client["made"]) == 1
    assert set(fake_client["made"][0].calls) <= READ_ONLY
    saved = _apartment()
    assert (saved["uby_idub"], saved["uby_ws_user"], saved["uby_mark"]) == (
        SAMPLE_IDUB, SAMPLE_WS_USER, SAMPLE_ZKRATKA,
    )
    assert db.decrypt_secret(saved["uby_ws_password_enc"]) == "typed-password"
    assert "typed-password" not in _audit_text()


@pytest.mark.parametrize(
    "error, key",
    [
        (UbyportAuthError("refused"), "flash.error.letter_test_failed"),
        (UbyportTransportError("down"), "flash.error.letter_test_unreachable"),
    ],
)
def test_a_failed_auto_test_says_which_kind(host, fake_client, error, key):
    fake_client["error"] = error
    apartment = _apartment()
    location = _flash(_save(host, apartment["id"], uby_ws_password="typed-password"))
    assert "err=" in location and _en(key) in location
    assert len(fake_client["made"]) == 1, "the automatic test must not retry"
    assert fake_client["made"][0].calls == ["TestDostupnosti"]
    assert _apartment()["uby_idub"] == SAMPLE_IDUB, "the confirmed values stay saved"


def test_no_password_typed_means_no_test(host, no_client):
    apartment = _apartment()
    db.update("apartment", apartment["id"], {"uby_ws_password_enc": db.encrypt_secret("stored")})
    location = _flash(_save(host, apartment["id"]))
    assert _en("flash.apartments.letter_saved_untested") in location
    assert no_client == []
    saved = _apartment()
    assert saved["uby_idub"] == SAMPLE_IDUB
    assert db.decrypt_secret(saved["uby_ws_password_enc"]) == "stored"


def test_a_save_without_letter_values_is_as_before(host, no_client):
    apartment = _apartment()
    location = _flash(
        host.post(
            f"/apartments/{apartment['id']}",
            data=_payload(uby_idub=SAMPLE_IDUB, uby_ws_password="typed-password"),
            follow_redirects=False,
        )
    )
    assert no_client == []
    assert "letter" not in location.lower()
    assert "police" not in location.lower() or "msg=" in location
    for key in (
        "flash.apartments.letter_test_ok",
        "flash.apartments.letter_saved_untested",
        "flash.apartments.letter_new_login_no_password",
    ):
        assert _en(key) not in location
    assert "saved=1" in location and "#ubyport" not in location
    assert _apartment()["uby_idub"] == SAMPLE_IDUB


@pytest.mark.parametrize(
    "error, kind, key",
    [
        (None, "msg=", "flash.apartments.connection_ok"),
        (UbyportAuthError("refused"), "err=", "flash.error.connection_failed"),
        (UbyportTransportError("down"), "err=", "flash.error.connection_failed"),
    ],
)
@pytest.mark.parametrize("with_letter", [False, True])
def test_the_test_button_flashes_are_unchanged(host, fake_client, error, kind, key, with_letter):
    fake_client["error"] = error
    apartment = _apartment()
    data = (
        _letter_payload(uby_ws_password="typed-password")
        if with_letter
        else _payload(uby_ws_password="typed-password")
    )
    location = _flash(
        host.post(f"/apartments/{apartment['id']}/test-connection", data=data, follow_redirects=False)
    )
    assert kind in location and _en(key) in location
    assert len(fake_client["made"]) == 1


# --- g. the read-only proof ------------------------------------------------


def _seed_waiting_guest(apartment_id: int) -> int:
    now = db.utcnow()
    today = date.today()
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "stay-police-letter-flow",
            "date_from": (today - timedelta(days=2)).isoformat(),
            "date_to": (today + timedelta(days=2)).isoformat(),
            "summary": "Letter Stay",
            "status": "active",
            "expected_guests_override": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    return db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Sample",
            "first_name": "Guest",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": "P0000000",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "host",
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )


def test_the_connection_test_is_read_only(host, monkeypatch):
    apartment = _apartment()
    guest_id = _seed_waiting_guest(apartment["id"])
    guest_before = dict(db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,)))
    submissions_before = db.query_one("SELECT COUNT(*) AS n FROM submission")["n"]

    def never(*args, **kwargs):
        raise AssertionError("the connection test must never file")

    monkeypatch.setattr(UbyportClient, "submit", never)
    monkeypatch.setattr(reporting, "submit_for_apartment", never)
    monkeypatch.setattr(reporting, "submit_batch", never)
    monkeypatch.setattr(reporting, "submit_stay_if_complete", never)
    methods = []

    def record(self, method, envelope):
        methods.append(method)
        return ""

    monkeypatch.setattr(UbyportClient, "_post", record)
    monkeypatch.setattr(soap, "parse_scalar_response", lambda *args, **kwargs: "true")
    monkeypatch.setattr(soap, "parse_ciselnik_response", lambda *args, **kwargs: [])

    first = _flash(
        host.post(
            f"/apartments/{apartment['id']}/test-connection",
            data=_payload(uby_ws_password="typed-password"),
            follow_redirects=False,
        )
    )
    assert _en("flash.apartments.connection_ok") in first
    assert methods and set(methods) <= READ_ONLY
    button_methods = list(methods)

    second = _flash(_save(host, apartment["id"], uby_ws_password="typed-password"))
    assert _en("flash.apartments.letter_test_ok") in second
    assert methods[len(button_methods):] == button_methods, "the auto test sends the same calls"
    assert set(methods) <= READ_ONLY

    assert dict(db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))) == guest_before
    assert db.query_one("SELECT COUNT(*) AS n FROM submission")["n"] == submissions_before

    for function in (admin._run_connection_test, admin.test_connection):
        source = inspect.getsource(function)
        assert "submit" not in source
        assert "ZapisUbytovane" not in source


# --- h. final exit only, and the lockout guard -----------------------------


def test_the_wizard_step_runs_no_test(host, no_client):
    apartment = _apartment()
    response = _save(host, apartment["id"], uby_ws_password="typed-password", setup_step="police")
    assert response.status_code < 500
    assert no_client == []
    if response.status_code == 303:
        location = unquote(response.headers["location"])
        assert _en("flash.apartments.letter_test_ok") not in location
        assert _en("flash.apartments.letter_saved_untested") not in location


def test_a_fee_return_runs_no_test(host, no_client):
    apartment = _apartment()
    location = _flash(
        _save(host, apartment["id"], uby_ws_password="typed-password", fee_return_to="/stay-fees")
    )
    assert location.startswith("/stay-fees"), location
    assert no_client == []
    assert _apartment()["uby_idub"] == SAMPLE_IDUB


def test_the_test_button_skips_a_new_login_without_a_password(host, no_client):
    apartment = _apartment()
    db.update("apartment", apartment["id"], {"uby_ws_password_enc": db.encrypt_secret("stored")})
    location = _flash(
        host.post(
            f"/apartments/{apartment['id']}/test-connection",
            data=_payload(
                uby_ws_user=SAMPLE_WS_USER,
                letter_fields="uby_ws_user",
                letter_ok="1",
            ),
            follow_redirects=False,
        )
    )
    assert _en("flash.apartments.letter_new_login_no_password") in location
    assert "err=" not in location
    assert no_client == []
    saved = _apartment()
    assert saved["uby_ws_user"] == SAMPLE_WS_USER
    assert db.decrypt_secret(saved["uby_ws_password_enc"]) == "stored"


def test_the_test_button_tests_a_new_login_with_a_password(host, fake_client):
    apartment = _apartment()
    location = _flash(
        host.post(
            f"/apartments/{apartment['id']}/test-connection",
            data=_payload(
                uby_ws_user=SAMPLE_WS_USER,
                uby_ws_password="typed-password",
                letter_fields="uby_ws_user",
                letter_ok="1",
            ),
            follow_redirects=False,
        )
    )
    assert _en("flash.apartments.connection_ok") in location
    assert len(fake_client["made"]) == 1


def test_the_test_button_still_tests_the_same_login_without_a_password(host, fake_client):
    """The guard is only for a new login: the same one, in any case, is tested."""
    apartment = _apartment()
    location = _flash(
        host.post(
            f"/apartments/{apartment['id']}/test-connection",
            data=_payload(
                uby_ws_user=f"  {SAVED_LOGIN.lower()} ",
                letter_fields="uby_ws_user",
                letter_ok="1",
            ),
            follow_redirects=False,
        )
    )
    assert _en("flash.apartments.connection_ok") in location
    assert len(fake_client["made"]) == 1


# --- i. idempotency and concurrency ----------------------------------------


def test_the_same_confirmed_save_twice_changes_nothing_more(host, fake_client):
    apartment = _apartment()
    _flash(_save(host, apartment["id"], uby_ws_password="typed-password"))
    first = dict(_apartment())
    _flash(_save(host, apartment["id"], uby_ws_password="typed-password"))
    rows = _apartments()
    assert len(rows) == 1
    second = dict(rows[0])
    for field in ("uby_idub", "uby_ws_user", "uby_mark", "uby_name", "internal_name"):
        assert second[field] == first[field]
    assert db.decrypt_secret(second["uby_ws_password_enc"]) == "typed-password"


def test_two_properties_saved_at_once_keep_their_own_idub(host, fake_client):
    created = host.post(
        "/apartments", data=_payload(internal_name="Second Letter Flat"), follow_redirects=False
    )
    assert created.status_code == 303, created.text
    first, second = _apartments()
    values = {first["id"]: "000011112222", second["id"]: SAMPLE_IDUB}
    clients = {first["id"]: host, second["id"]: _login(USERNAME)}
    payloads = {
        apartment_id: _letter_payload(uby_idub=idub, uby_ws_password="typed-password")
        for apartment_id, idub in values.items()
    }
    barrier = threading.Barrier(2)
    results = {}

    def run(apartment_id):
        barrier.wait(timeout=10)
        results[apartment_id] = clients[apartment_id].post(
            f"/apartments/{apartment_id}", data=payloads[apartment_id], follow_redirects=False
        ).status_code

    threads = [threading.Thread(target=run, args=(apartment_id,)) for apartment_id in values]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert results == {first["id"]: 303, second["id"]: 303}
    saved = {row["id"]: row["uby_idub"] for row in _apartments()}
    assert saved == values


# --- j. the discard warning (source pin; 1086 proves it in the browser) -----


def test_the_discard_warning_is_wired(host):
    script = (Path(admin.__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    start = script.index("function initPoliceLetterForm()")
    body = script[start : script.index("\n  }\n", start)]
    assert 'getElementById("police-letter-form")' in body
    assert 'addEventListener("submit"' in body
    assert "window.confirm(letterForm.dataset.discardWarning)" in body
    assert "event.preventDefault()" in body
    assert "_ubySubmitting = true" in body
    assert "uby_ws_password" in body
    assert "\n    initPoliceLetterForm();\n" in script

    apartment = _apartment()
    plain = host.get(f"/apartments/{apartment['id']}?view=settings&section=reporting").text
    settings_form = re.search(r'<form[^>]*id="property-settings-form"[^>]*>', plain).group(0)
    assert "data-dirty-start" not in settings_form
    letter_form = re.search(r'<form id="police-letter-form"[^>]*>', plain).group(0)
    assert f'action="/apartments/{apartment["id"]}/police-letter"' in letter_form
    assert _en("police_letter.discard_warning") in html.unescape(letter_form)
    assert 'name="letter_text" form="police-letter-form"' in plain
    assert 'id="police-sample-link"' in plain
    assert 'name="letter_fields" value=""' in plain
    assert re.search(r'<button[^>]*data-letter-read', plain)

    page = _paste(host, apartment["id"]).text
    settings_form = re.search(r'<form[^>]*id="property-settings-form"[^>]*>', page).group(0)
    assert 'data-dirty-start="1"' in settings_form
    assert "data-discard-warning=" in re.search(r'<form id="police-letter-form"[^>]*>', page).group(0)
    # The letter form sits after the big form: forms cannot nest.
    assert page.index('id="police-letter-form"') > page.index('id="police-letter-status"')


def test_the_figure_uses_real_labels_and_fake_values(host):
    apartment = _apartment()
    page = host.get(f"/apartments/{apartment['id']}?view=settings&section=reporting").text
    start = page.index('<figure class="police-letter-figure">')
    figure = page[start : page.index("</figure>", start)]
    for text in ("Přihlašovací jméno:", "Přístupové heslo:", "IDUB:", "UBY-WS_ABCDE", "000000000000"):
        assert text in figure
    assert 'role="img" aria-labelledby="pl-fig-t"' in figure
    assert "style=" not in figure and "<style" not in figure and "#" not in figure
    assert SAMPLE_WS_PASSWORD not in figure


def test_no_tick_is_needed_and_no_tick_renders(host, no_client):
    """1100: a letter save with no letter_ok saves; nothing on the page asks for a tick."""
    before = dict(_apartment())
    for fields in ("uby_idub,uby_mark", "uby_idub,uby_ws_user,uby_mark"):
        response = host.post(
            f"/apartments/{before['id']}",
            data=_letter_payload(letter_fields=fields),
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text[:300]
    assert _apartment()["uby_idub"] == SAMPLE_IDUB
    page = host.get(f"/apartments/{before['id']}?view=settings&section=reporting").text
    assert "letter_ok" not in page











def test_each_box_renders_once(host, no_client):
    apartment = _apartment()
    page = _paste(host, apartment["id"]).text
    for name in ("uby_idub", "uby_ws_user", "uby_ws_password", "uby_mark", "uby_name", "letter_fields"):
        assert page.count(f'name="{name}"') == 1, name


def test_edit_value_is_saved_with_the_tick(host, no_client):
    apartment = _apartment()
    assert _paste(host, apartment["id"]).status_code == 422
    new_idub = "987654321098"
    assert new_idub not in (SAMPLE_IDUB, SAVED_IDUB)
    response = _save(host, apartment["id"], uby_idub=new_idub)
    assert response.status_code == 303, response.text[:300]
    saved = _apartment()
    assert saved["uby_idub"] == new_idub
    assert saved["uby_ws_user"] == SAMPLE_WS_USER
    assert saved["uby_mark"] == SAMPLE_ZKRATKA


def test_an_unfound_value_keeps_its_own_field(host, no_client):
    apartment = _apartment()
    text = "\n".join(line for line in LETTER.splitlines() if "IDUB" not in line)
    page = _paste(host, apartment["id"], text).text
    assert page.count('name="uby_idub"') == 1
    assert _input_value(page, "uby_idub") == apartment["uby_idub"]
    assert 'name="letter_fields" value="uby_ws_user,uby_mark"' in page
    assert _en(_label("uby_idub")) in _status_line(page)


def test_an_untouched_save_keeps_all_three_values(host, no_client):
    apartment = _apartment()
    page = _paste(host, apartment["id"]).text
    form_html = page[page.index('id="property-settings-form"') : page.index("</form>", page.index('id="property-settings-form"'))]
    data = {}
    for tag in re.findall(r"<input\b[^>]*>", form_html):
        name = re.search(r'name="([^"]+)"', tag)
        if not name or re.search(r'type="(checkbox|radio|file|submit|password)"', tag):
            continue
        if name.group(1) == "uby_ws_password":
            continue  # a typed password would run the connection test
        value = re.search(r'value="([^"]*)"', tag)
        data.setdefault(name.group(1), html.unescape(value.group(1)) if value else "")
    for name in ("uby_idub", "uby_ws_user", "uby_mark"):
        assert len(re.findall(rf'<input\b[^>]*name="{name}"', form_html)) == 1, name
    payload = _payload(**{k: v for k, v in data.items() if k.startswith(("uby_", "letter_"))})
    response = host.post(f"/apartments/{apartment['id']}", data=payload, follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
    saved = _apartment()
    assert saved["uby_idub"] == SAMPLE_IDUB
    assert saved["uby_ws_user"] == SAMPLE_WS_USER
    assert saved["uby_mark"] == SAMPLE_ZKRATKA


# --- browser: the v2 stylesheet really styles the helper (1085 attempt 2) ---


def test_the_letter_helper_is_styled_in_the_browser(host, no_client):
    """The property editor is a v2 page: the rules must live in app2.css.

    Set UBYHOST_SHOT_DIR to also write the 390/768/1280 review screenshots.
    """
    import os
    import socket
    import time

    import uvicorn

    if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
        import playwright.sync_api as sync_api
    else:
        sync_api = pytest.importorskip("playwright.sync_api")
    from tests.browser_support import chromium_launch_kwargs, settle_motion

    apartment = _apartment()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "the test server did not start"
    base = f"http://127.0.0.1:{port}"
    shot_dir = os.environ.get("UBYHOST_SHOT_DIR")
    url = f"{base}/apartments/{apartment['id']}?view=settings&section=reporting#ubyport"

    def shot(page, name, width):
        if shot_dir:
            page.wait_for_timeout(700)
            Path(shot_dir).mkdir(parents=True, exist_ok=True)
            page.locator("#ubyport").screenshot(path=str(Path(shot_dir) / f"{name}-{width}.png"))

    def fits(page):
        return page.evaluate(
            "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )

    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            for width in (390, 768, 1280):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies(
                    [{"name": auth.SESSION_COOKIE, "value": host.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}]
                )
                page = context.new_page()
                page.goto(url)
                # 1099: on a first-setup property both disclosures already start open.
                # 1099: both start open in first setup; close and reopen "Where do I find these?" with real clicks.
                page.locator("details.police-letter-find > summary").click()
                assert page.locator("details.police-letter-find").evaluate("d => d.open") is False
                page.locator("details.police-letter-find > summary").click()
                page.evaluate(
                    "document.querySelectorAll('details.police-letter-find, details.police-letter-paste')"
                    ".forEach((d) => { d.open = true; })"
                )
                page.wait_for_timeout(400)
                settle_motion(page)
                style = page.evaluate(
                    """() => {
                      const css = (sel) => getComputedStyle(document.querySelector(sel));
                      const box = (sel) => document.querySelector(sel).getBoundingClientRect();
                      const find = css('details.police-letter-find');
                      return {
                        fill: css('.pl-sheet').fill,
                        svgWidth: box('.police-letter-svg').width,
                        findBorderLeft: find.borderLeftWidth,
                        findRadius: find.borderTopLeftRadius,
                        summaryHeight: box('details.police-letter-find > summary').height,
                        summaryLeft: box('details.police-letter-paste > summary').left,
                        textareaLeft: box('#letter_text').left,
                        buttonBottom: box('details.police-letter-paste .actions button').bottom,
                        idubTop: box('#uby_idub').top,
                      };
                    }"""
                )
                assert style["fill"] != "rgb(0, 0, 0)", "the figure is unstyled (dead CSS)"
                assert 100 < style["svgWidth"] <= 360.5
                assert style["findBorderLeft"] == "0px" and style["findRadius"] == "0px"
                assert style["summaryHeight"] >= 44
                assert abs(style["summaryLeft"] - style["textareaLeft"]) < 1
                assert style["idubTop"] - style["buttonBottom"] >= 12
                assert fits(page)
                shot(page, "helpers-open", width)

                page.fill("#letter_text", LETTER)
                page.locator("#letter_text").dispatch_event("paste")
                page.wait_for_function(
                    "v => document.querySelector('#uby_idub').value === v", arg=SAMPLE_IDUB, timeout=5000
                )
                check = page.evaluate(
                    """() => ({
                      status: document.querySelector('#police-letter-status').textContent,
                      password: document.querySelector('#uby_ws_password').value,
                      passwordType: document.querySelector('#uby_ws_password').type,
                      readHidden: document.querySelector('[data-letter-read]').hidden,
                    })"""
                )
                assert check["password"] == SAMPLE_WS_PASSWORD and check["passwordType"] == "text"
                assert check["readHidden"] is True
                assert _en(_label("uby_idub")) in check["status"]
                assert fits(page)
                shot(page, "after-paste", width)

                # N1: an empty read with the button lands on its error, too.
                page.on("dialog", lambda dialog: dialog.accept())
                page.goto(url)
                page.locator("details.police-letter-paste").evaluate("d => { d.open = true; }")  # 1099: may start open
                with page.expect_response(lambda r: r.url.endswith("/police-letter")) as empty:
                    page.evaluate("() => { document.querySelector('#letter_text').value = ''; document.querySelector('[data-letter-read]').hidden = false; }")
                    page.locator("details.police-letter-paste .actions button").click()
                assert empty.value.status == 422
                page.wait_for_selector("#letter_text-error")
                page.wait_for_timeout(300)
                error_top = page.evaluate(
                    "() => [document.querySelector('#letter_text-error').getBoundingClientRect().top,"
                    " document.querySelector('#letter_text-error').getBoundingClientRect().bottom, window.innerHeight]"
                )
                assert 0 <= error_top[0] and error_top[1] <= error_top[2], error_top
                if shot_dir:
                    page.screenshot(path=str(Path(shot_dir) / f"landing-error-{width}.png"))
                context.close()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    assert no_client == []
    assert _apartment()["uby_idub"] == SAVED_IDUB
