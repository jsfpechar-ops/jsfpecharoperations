"""0088: a property always has an operator; there is no activity switch."""
from __future__ import annotations

import re
import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from app.routes import guest as guest_routes
from tests.conftest import login_as

PREFIX = "op-defaults-"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        owner_id = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute(
            "DELETE FROM apartment_slug WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _host(entities: int = 1):
    username = f"{PREFIX}{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Operator Host", role="host", username=username)
    ids = [_entity(owner_id, f"Operator {chr(65 + index)} s.r.o.") for index in range(entities)]
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    return {"client": client, "owner": owner_id, "entities": ids}


def _entity(owner_id: int, name: str, **extra) -> int:
    row = {
        "name": name,
        "seat": "Praha",
        "ico": "12345678",
        "contact_email": f"{secrets.token_hex(3)}@operator.test",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    }
    row.update(extra)
    return db.insert("legal_entity", row)


def _apartment(owner_id: int, entity_id, **extra) -> int:
    row = {
        "internal_name": f"Stored flat {secrets.token_hex(3)}",
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "permalink_token": f"opdef{secrets.token_hex(5)}",
        "permalink_pin": "123456",
        "automation_mode": "scheduled",
        "submit_after_hours": 12,
        "default_purpose": "10",
        "uby_ws_password_enc": db.encrypt_secret("stored-secret"),
        "active": 1,
        "created_at": db.utcnow(),
    }
    row.update(extra)
    return db.insert("apartment", row)


def _row(apartment_id: int):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


def _count(owner_id: int) -> int:
    return db.query_one("SELECT COUNT(*) AS n FROM apartment WHERE owner_user_id = ?", (owner_id,))["n"]


@pytest.fixture(autouse=True)
def _clean():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _operator_select(html: str) -> str:
    start = html.index('id="legal_entity_id"')
    return html[start : html.index("</select>", start)]


# --- the control -----------------------------------------------------------


def test_zero_operators_block_the_form_and_offer_business_details():
    host = _host(entities=0)
    for lang, message, action in (
        ("en", "Add an operator to continue.", "Add business details"),
        ("cs", "Nejprve přidejte provozovatele.", "Přidat firemní údaje"),
    ):
        page = host["client"].get(f"/apartments/new?lang={lang}").text
        assert page.count('name="legal_entity_id"') == 1
        select = _operator_select(page)
        assert "required" in page[page.index('<select id="legal_entity_id"') : page.index(">", page.index('<select id="legal_entity_id"'))]
        assert '<option value="" disabled selected>' in select
        assert message in page
        assert action in page
        assert 'href="/entities" target="_blank"' in page
        assert 'name="operator_refresh"' in page


def test_one_operator_is_chosen_for_the_host():
    host = _host(entities=1)
    page = host["client"].get("/apartments/new?lang=en").text
    assert page.count('name="legal_entity_id"') == 1
    select = _operator_select(page)
    assert f'<option value="{host["entities"][0]}" selected>' in select
    assert "disabled" not in select
    assert "(none)" not in page and "(žádná)" not in page


def test_several_operators_need_a_deliberate_choice():
    host = _host(entities=3)
    page = host["client"].get("/apartments/new?lang=en").text
    assert page.count('name="legal_entity_id"') == 1
    select = _operator_select(page)
    assert '<option value="" disabled selected>Choose operator</option>' in select
    assert " selected>Operator" not in select
    assert "(none)" not in page
    cs = host["client"].get("/apartments/new?lang=cs").text
    assert "Vyberte provozovatele</option>" in _operator_select(cs)


def test_a_preselected_or_copied_operator_is_kept():
    host = _host(entities=3)
    chosen = host["entities"][1]
    page = host["client"].get(f"/apartments/new?legal_entity_id={chosen}").text
    assert f'<option value="{chosen}" selected>' in _operator_select(page)
    source = _apartment(host["owner"], host["entities"][2])
    copied = host["client"].get(f"/apartments/new?copy_from={source}").text
    assert f'<option value="{host["entities"][2]}" selected>' in _operator_select(copied)


def test_no_active_switch_or_controller_checkbox_on_either_form():
    host = _host(entities=2)
    apartment_id = _apartment(host["owner"], host["entities"][0])
    for path in ("/apartments/new?lang=en", f"/apartments/{apartment_id}?lang=en"):
        page = host["client"].get(path).text
        assert 'name="active"' not in page
        assert 'id="controller_is_operator"' not in page
        assert "Recommended default" not in page
        assert "legal_entity_id_select" not in page
    edit = host["client"].get(f"/apartments/{apartment_id}?lang=en").text
    controller = edit[edit.index('id="data_controller_entity_id"') :]
    controller = controller[: controller.index("</select>")]
    assert '<option value="">Same as operator</option>' in controller
    # Visible: not inside the folded "More options" block.
    before = edit[: edit.index('id="data_controller_entity_id"')]
    last_fold = before.rfind('<details class="more-options"')
    assert last_fold == -1 or "</details>" in before[last_fold:]
    assert 'id="property-more-options"' not in edit


# --- create ----------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["", "abc", "0", "999999999"],
    ids=["missing", "malformed", "zero", "unknown"],
)
def test_create_refuses_a_missing_or_malformed_operator_without_writing(value):
    host = _host(entities=2)
    response = host["client"].post(
        "/apartments",
        data={
            "internal_name": "Refused flat",
            "city_en": "Brno",
            "legal_entity_id": value,
            "uby_ws_password": "typed-secret",
            "uby_contact": "contact@example.test",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Choose the operator for this property." in response.text
    assert 'value="Refused flat"' in response.text
    assert 'value="Brno"' in response.text
    assert "typed-secret" not in response.text
    assert _count(host["owner"]) == 0


def test_create_refuses_a_foreign_or_archived_operator():
    host = _host(entities=2)
    other = _host(entities=1)
    archived = _entity(host["owner"], "Archived s.r.o.", archived_at=db.utcnow())
    for entity_id in (other["entities"][0], archived):
        response = host["client"].post(
            "/apartments",
            data={"internal_name": "Refused flat", "legal_entity_id": str(entity_id)},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Operator A s.r.o." in response.text  # the host's own list, not the foreign one
        assert f'<option value="{entity_id}"' not in response.text
    assert _count(host["owner"]) == 0
    assert _count(other["owner"]) == 0


def test_create_with_zero_operators_refuses_and_check_again_keeps_the_draft():
    host = _host(entities=0)
    refused = host["client"].post(
        "/apartments",
        data={"internal_name": "Draft flat", "addr_street": "Draft Street"},
        follow_redirects=False,
    )
    assert refused.status_code == 400
    assert "Add an operator to continue." in refused.text
    assert _count(host["owner"]) == 0
    _entity(host["owner"], "Added Later s.r.o.")
    again = host["client"].post(
        "/apartments",
        data={"internal_name": "Draft flat", "addr_street": "Draft Street", "operator_refresh": "1"},
        follow_redirects=False,
    )
    assert again.status_code == 200
    assert 'value="Draft flat"' in again.text
    assert 'value="Draft Street"' in again.text
    assert re.search(r'<option value="\d+" selected>Added Later s\.r\.o\.</option>', again.text)
    assert _count(host["owner"]) == 0


def test_create_forces_active_and_defaults_the_controller_to_the_operator():
    host = _host(entities=2)
    operator = host["entities"][1]
    response = host["client"].post(
        "/apartments",
        data={"internal_name": "Forged flat", "legal_entity_id": str(operator), "active": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.query_one("SELECT * FROM apartment WHERE owner_user_id = ?", (host["owner"],))
    assert row["active"] == 1
    assert row["legal_entity_id"] == operator
    assert row["data_controller_entity_id"] is None
    assert row["automation_mode"] == "manual"
    operator_name = db.query_one("SELECT name FROM legal_entity WHERE id = ?", (operator,))["name"]
    assert guest_routes._controller(row)["name"] == operator_name
    assert guest_routes._host_contact(row)["name"] == operator_name


def test_create_rejects_a_foreign_controller():
    host = _host(entities=2)
    other = _host(entities=1)
    response = host["client"].post(
        "/apartments",
        data={
            "internal_name": "Controller flat",
            "legal_entity_id": str(host["entities"][0]),
            "data_controller_entity_id": str(other["entities"][0]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "That data controller no longer exists." in response.text
    assert _count(host["owner"]) == 0


# --- full save ----------------------------------------------------------------


def _save(host, apartment_id, **data):
    return host["client"].post(f"/apartments/{apartment_id}", data=data, follow_redirects=False)


def test_full_save_without_a_valid_operator_changes_nothing():
    host = _host(entities=2)
    other = _host(entities=1)
    apartment_id = _apartment(host["owner"], host["entities"][0], internal_name="Keep me")
    before = _row(apartment_id)
    archived = _entity(host["owner"], "Archived s.r.o.", archived_at=db.utcnow())
    for value in ("", "abc", str(other["entities"][0]), str(archived)):
        response = _save(
            host,
            apartment_id,
            internal_name="Renamed",
            legal_entity_id=value,
            uby_ws_password="new-secret",
        )
        assert response.status_code == 400
        assert 'value="Renamed"' in response.text
        assert "new-secret" not in response.text
        after = _row(apartment_id)
        assert after["internal_name"] == "Keep me"
        assert after["uby_ws_password_enc"] == before["uby_ws_password_enc"]
        assert after["legal_entity_id"] == host["entities"][0]


def test_test_connection_uses_the_same_operator_rule():
    host = _host(entities=2)
    apartment_id = _apartment(host["owner"], host["entities"][0])
    before = _row(apartment_id)
    response = host["client"].post(
        f"/apartments/{apartment_id}/test-connection",
        data={"internal_name": "X", "uby_ws_user": "UBY-WSnew", "uby_ws_password": "typed", "legal_entity_id": ""},
        follow_redirects=False,
    )
    assert response.status_code == 400
    after = _row(apartment_id)
    assert after["uby_ws_user"] == before["uby_ws_user"]
    assert after["uby_ws_password_enc"] == before["uby_ws_password_enc"]


def test_legacy_property_without_operator_stays_readable_but_must_choose():
    host = _host(entities=2)
    apartment_id = _apartment(host["owner"], None, internal_name="Legacy flat")
    page = host["client"].get(f"/apartments/{apartment_id}?lang=en")
    assert page.status_code == 200
    assert '<option value="" disabled selected>Choose operator</option>' in _operator_select(page.text)
    assert _save(host, apartment_id, internal_name="Legacy flat").status_code == 400
    saved = _save(host, apartment_id, internal_name="Legacy flat", legal_entity_id=str(host["entities"][1]))
    assert saved.status_code == 303
    assert _row(apartment_id)["legal_entity_id"] == host["entities"][1]


@pytest.mark.parametrize("forged", [None, "0", "false", ""], ids=["omitted", "zero", "false", "blank"])
def test_ordinary_save_keeps_a_property_active(forged):
    host = _host(entities=1)
    apartment_id = _apartment(host["owner"], host["entities"][0], active=0)
    data = {"internal_name": "Active flat", "legal_entity_id": str(host["entities"][0])}
    if forged is not None:
        data["active"] = forged
    assert _save(host, apartment_id, **data).status_code == 303
    row = _row(apartment_id)
    assert row["active"] == 1
    # The reporting mode is not touched by a form without the timing fields.
    assert row["automation_mode"] == "scheduled"
    assert row["submit_after_hours"] == 12


def test_saving_an_archived_property_keeps_it_inactive_and_archive_restore_work():
    host = _host(entities=1)
    operator = str(host["entities"][0])
    apartment_id = _apartment(host["owner"], host["entities"][0])
    assert host["client"].post(f"/apartments/{apartment_id}/archive", follow_redirects=False).status_code == 303
    assert _row(apartment_id)["active"] == 0
    assert _save(host, apartment_id, internal_name="Archived flat", legal_entity_id=operator, active="1").status_code == 303
    row = _row(apartment_id)
    assert row["active"] == 0 and row["archived_at"]
    assert host["client"].post(f"/apartments/{apartment_id}/unarchive", follow_redirects=False).status_code == 303
    row = _row(apartment_id)
    assert row["active"] == 1 and row["archived_at"] is None


def test_explicit_mode_change_still_saves():
    host = _host(entities=1)
    apartment_id = _apartment(host["owner"], host["entities"][0])
    _save(
        host,
        apartment_id,
        internal_name="Mode flat",
        legal_entity_id=str(host["entities"][0]),
        automation_mode="immediate",
        submit_after_hours="0",
        default_purpose="10",
    )
    assert _row(apartment_id)["automation_mode"] == "immediate"


# --- controller override -----------------------------------------------------


def test_controller_override_survives_a_save_without_the_selector():
    host = _host(entities=2)
    operator, controller = host["entities"]
    apartment_id = _apartment(host["owner"], operator, data_controller_entity_id=controller)
    assert _save(host, apartment_id, internal_name="Override flat", legal_entity_id=str(operator)).status_code == 303
    assert _row(apartment_id)["data_controller_entity_id"] == controller
    page = host["client"].get(f"/apartments/{apartment_id}?lang=en").text
    select = page[page.index('id="data_controller_entity_id"') :]
    assert f'<option value="{controller}" selected>' in select[: select.index("</select>")]


def test_controller_override_kept_when_resubmitted_and_cleared_only_explicitly():
    host = _host(entities=2)
    operator, controller = host["entities"]
    apartment_id = _apartment(host["owner"], operator, data_controller_entity_id=controller)
    base = {"internal_name": "Override flat", "legal_entity_id": str(operator)}
    assert _save(host, apartment_id, **base, data_controller_entity_id=str(controller)).status_code == 303
    assert _row(apartment_id)["data_controller_entity_id"] == controller
    assert _save(host, apartment_id, **base, data_controller_entity_id=str(operator)).status_code == 303
    assert _row(apartment_id)["data_controller_entity_id"] is None
    _save(host, apartment_id, **base, data_controller_entity_id=str(controller))
    assert _save(host, apartment_id, **base, data_controller_entity_id="").status_code == 303
    assert _row(apartment_id)["data_controller_entity_id"] is None


def test_controller_override_must_be_the_hosts_own_active_operator():
    host = _host(entities=2)
    other = _host(entities=1)
    operator, controller = host["entities"]
    archived = _entity(host["owner"], "Archived controller", archived_at=db.utcnow())
    apartment_id = _apartment(host["owner"], operator, data_controller_entity_id=controller)
    for value in (str(other["entities"][0]), str(archived), "abc"):
        response = _save(
            host,
            apartment_id,
            internal_name="Override flat",
            legal_entity_id=str(operator),
            data_controller_entity_id=value,
        )
        assert response.status_code == 400
        assert "That data controller no longer exists." in response.text
        assert _row(apartment_id)["data_controller_entity_id"] == controller


def test_copy_from_keeps_an_explicit_controller_override():
    host = _host(entities=2)
    operator, controller = host["entities"]
    source = _apartment(host["owner"], operator, data_controller_entity_id=controller)
    page = host["client"].get(f"/apartments/new?copy_from={source}&lang=en").text
    select = page[page.index('id="data_controller_entity_id"') :]
    assert f'<option value="{controller}" selected>' in select[: select.index("</select>")]
    plain = host["client"].get("/apartments/new?lang=en").text
    assert 'id="data_controller_entity_id"' not in plain
