"""1101: a new property walks the setup wizard to the ready card (server side, no JavaScript)."""
from __future__ import annotations

import html
import re

from app import db, host_i18n, property_setup
from app.ubyport.client import UbyportAuthError
from app.ubyport_sample_pdf import SAMPLE_IDUB, SAMPLE_WS_PASSWORD, SAMPLE_WS_USER, SAMPLE_ZKRATKA
from tests.test_onboarding_wizard_survival import host  # noqa: F401
from tests.test_police_letter_flow import fake_client  # noqa: F401

LETTER = (
    "Přihlašovací údaje pro robotické vkládání Ubyport Webová služba\n"
    f"Přihlašovací jméno: {SAMPLE_WS_USER}\n"
    f"Přístupové heslo: {SAMPLE_WS_PASSWORD}\n"
    f"IDUB: {SAMPLE_IDUB}\n"
)


def _path(response) -> str:
    return response.headers["location"].split("?")[0]


def _skip_calendar(host, apartment_id) -> None:
    response = host["client"].post(
        f"/apartments/{apartment_id}/setup", data={"action": "skip", "step": "calendar"}, follow_redirects=False
    )
    assert response.status_code == 303


def _post_create(host, complete=True, name="Wizard Flat"):
    data = {
        "internal_name": name,
        "legal_entity_id": str(host["entity"]),
        "city_en": "Praha",
    }
    if complete:
        data.update(
            addr_obec="Praha", addr_street="Synthetic", addr_house_no="12", addr_zip="120 00",
            checkin_hour="14", checkout_hour="10",
        )
    return host["client"].post("/apartments", data=data, follow_redirects=False)


def _guest_done(host, apartment_id) -> None:
    response = host["client"].post(
        f"/apartments/{apartment_id}/setup", data={"step": "guest_link", "action": "done"}, follow_redirects=False
    )
    assert response.status_code == 303 and _path(response).endswith("/setup/done"), response.headers


def _create(host, complete=True, skip=True) -> int:
    response = _post_create(host, complete)
    assert response.status_code == 303, response.text
    apartment_id = int(re.search(r"/apartments/(\d+)", response.headers["location"]).group(1))
    if complete:
        _skip_calendar(host, apartment_id) if skip else None
    return apartment_id


def _boxes(**over):
    data = {
        "setup_step": "police", "step": "police", "automation_mode": "manual",
        "uby_idub": SAMPLE_IDUB, "uby_ws_user": SAMPLE_WS_USER, "uby_ws_password": SAMPLE_WS_PASSWORD,
        "uby_mark": SAMPLE_ZKRATKA, "uby_name": "Penzion Wizard", "uby_contact": "",
        "internal_name": "Wizard Flat", "default_purpose": "10",
    }
    data.update(over)
    return data


def _test(host, apartment_id, **over):
    data = _boxes(**over)
    data.setdefault("legal_entity_id", str(host["entity"]))
    data["return_to"] = f"/apartments/{apartment_id}/setup/police"
    return host["client"].post(f"/apartments/{apartment_id}/test-connection", data=data, follow_redirects=False)


def _page(host, apartment_id, step) -> str:
    response = host["client"].get(f"/apartments/{apartment_id}/setup/{step}?lang=en", follow_redirects=False)
    assert response.status_code == 200, (step, response.status_code, response.headers.get("location"))
    return response.text


def _visible(page: str) -> str:
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S)
    page = re.sub(r"<[^>]+>", " ", page)
    return page.lower()


def test_create_lands_in_the_wizard(host):  # noqa: F811
    apartment_id = _create(host, skip=False)
    response = _post_create(host, name="Second Flat")
    assert _path(response).endswith("/setup/calendar")
    assert property_setup.load(apartment_id) is not None
    from tests.test_wizard_old_look_0953 import _open_apartment

    incomplete = _open_apartment(host)["id"]
    landed = host["client"].get(f"/apartments/{incomplete}/setup/calendar", follow_redirects=False)
    assert landed.status_code == 303 and landed.headers["location"].endswith("/setup/property")


def test_steps_show_count_and_back(host):  # noqa: F811
    apartment_id = _create(host, skip=False)
    assert "wiz-count" in _page(host, apartment_id, "calendar")
    assert "setup-wizard-back" not in _page(host, apartment_id, "calendar")
    _skip_calendar(host, apartment_id)
    for step in ("police",):
        assert "wiz-count" in _page(host, apartment_id, step), step
    host["client"].post(f"/apartments/{apartment_id}/setup", data={"action": "wait", "step": "police"}, follow_redirects=False)
    assert "wiz-count" in _page(host, apartment_id, "guest_link")
    assert "setup-wizard-back" in _page(host, apartment_id, "police")
    assert "setup-wizard-back" in _page(host, apartment_id, "guest_link")


def test_police_step_uses_the_shared_partial(host):  # noqa: F811
    apartment_id = _create(host)
    page = _page(host, apartment_id, "police")
    for hook in ("data-letter-paste", "data-letter-read", "data-letter-status", "data-letter-fields"):
        assert hook in page, hook
    assert page.count('id="police-letter-form"') == 1
    form = re.search(r'<form[^>]*id="police-form".*?</form>', page, re.S).group(0)
    assert 'id="police-letter-form"' not in form
    assert re.search(r'id="uby_ws_password"[^>]*type="text"|type="text"[^>]*id="uby_ws_password"', form)
    assert "letter_ok" not in page
    assert "Save and test connection" not in form
    assert re.search(r'formaction="/apartments/\d+/test-connection"', page)
    letter = re.search(r'<form[^>]*id="police-letter-form".*?</form>', page, re.S).group(0)
    assert 'name="setup_step" value="police"' in letter


def test_calendar_skip_goes_to_police(host):  # noqa: F811
    apartment_id = _create(host, skip=False)
    response = host["client"].post(f"/apartments/{apartment_id}/setup", data={"action": "skip", "step": "calendar"},
                                   follow_redirects=False)
    assert response.status_code == 303
    assert _path(response).endswith("/setup/police")


def test_passing_test_advances_and_marks(host, fake_client):  # noqa: F811
    apartment_id = _create(host)
    response = _test(host, apartment_id)
    assert response.status_code == 303, response.text
    assert _path(response).endswith("/setup/guest_link")
    state = property_setup.load(apartment_id)
    assert state["tested"] is True
    assert state["steps"]["police"] == "done" and state["steps"]["automation"] == "done"


def test_failed_test_stays_on_police(host, fake_client):  # noqa: F811
    apartment_id = _create(host)
    fake_client["error"] = UbyportAuthError("refused")
    response = _test(host, apartment_id)
    assert response.status_code == 303
    assert _path(response).endswith("/setup/police")
    shown = host["client"].get(response.headers["location"], follow_redirects=False)
    assert shown.status_code == 200
    assert html.escape(host_i18n.translate("en", "flash.error.connection_failed"), quote=False) in html.unescape(shown.text) \
        or host_i18n.translate("en", "flash.error.connection_failed") in html.unescape(shown.text)
    state = property_setup.load(apartment_id)
    assert not state.get("tested") and state["steps"].get("police") != "done"


def test_missing_box_stays_on_police(host, fake_client):  # noqa: F811
    apartment_id = _create(host)
    response = _test(host, apartment_id, uby_name="")
    assert response.status_code in (200, 400)
    assert 'data-setup-step="police"' in response.text
    assert property_setup.load(apartment_id)["steps"].get("police") != "done"


def test_invalid_idub_keeps_typed_login_and_no_password_value(host, fake_client):  # noqa: F811
    apartment_id = _create(host)
    response = _test(host, apartment_id, uby_idub="12")
    assert response.status_code == 400
    assert 'data-setup-step="police"' in response.text
    assert SAMPLE_WS_USER in response.text
    assert SAMPLE_WS_PASSWORD not in response.text


def test_wait_goes_on_and_done_says_almost(host):  # noqa: F811
    apartment_id = _create(host)
    response = host["client"].post(f"/apartments/{apartment_id}/setup", data={"action": "wait", "step": "police"}, follow_redirects=False)
    assert response.status_code == 303
    assert _path(response).endswith("/setup/guest_link")
    assert not property_setup.load(apartment_id).get("tested")
    _guest_done(host, apartment_id)
    page = _page(host, apartment_id, "done")
    assert "data-ready-card" not in page
    assert 'data-setup-celebrate="partial"' in page
    assert f"/apartments/{apartment_id}/setup/police" in page


def test_done_shows_the_ready_card_after_a_test_and_on_reload(host, fake_client):  # noqa: F811
    apartment_id = _create(host)
    assert _test(host, apartment_id).status_code == 303
    _guest_done(host, apartment_id)
    pin = db.query("SELECT permalink_pin FROM apartment WHERE id = ?", (apartment_id,))[0]["permalink_pin"]
    for _ in range(2):
        page = _page(host, apartment_id, "done")
        assert "data-ready-card" in page
        assert '<img class="ready-card-qr" src="data:image/png;base64,' in page
        assert pin in page and "/l/" in page
        assert "setup-wizard-celebrate" not in page


def test_wait_finish_then_test_reaches_the_card(host, fake_client):  # noqa: F811
    apartment_id = _create(host)
    host["client"].post(f"/apartments/{apartment_id}/setup", data={"action": "wait", "step": "police"}, follow_redirects=False)
    _guest_done(host, apartment_id)
    property_setup.finish(apartment_id)
    response = _test(host, apartment_id)
    assert response.status_code == 303 and _path(response).endswith("/setup/done")
    assert property_setup.load(apartment_id)["tested"] is True
    assert "data-ready-card" in _page(host, apartment_id, "done")


def test_no_js_letter_read_renders_the_wizard(host):  # noqa: F811
    apartment_id = _create(host)
    response = host["client"].post(
        f"/apartments/{apartment_id}/police-letter", data={"letter_text": LETTER, "setup_step": "police"},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert 'data-setup-step="police"' in response.text
    assert SAMPLE_IDUB in response.text
    assert response.headers["cache-control"] == "no-store"
    plain = host["client"].post(f"/apartments/{apartment_id}/police-letter", data={"letter_text": LETTER},
                                follow_redirects=False)
    assert plain.status_code == 422 and 'data-setup-step="police"' not in plain.text


def test_no_archive_on_setup_pages_or_first_setup_editor(host):  # noqa: F811
    apartment_id = _create(host)
    assert f"/apartments/{apartment_id}/archive" not in _page(host, apartment_id, "police")
    host["client"].post(f"/apartments/{apartment_id}/setup", data={"action": "wait", "step": "police"}, follow_redirects=False)
    assert f"/apartments/{apartment_id}/archive" not in _page(host, apartment_id, "guest_link")
    assert f"/apartments/{apartment_id}/archive" not in _page(host, apartment_id, "done")
    editor = host["client"].get(f"/apartments/{apartment_id}?view=settings&lang=en").text
    assert 'id="sec-archive"' not in editor
    db.execute("UPDATE apartment SET archived_at = ? WHERE id = ?", (db.utcnow(), apartment_id))
    archived = host["client"].get(f"/apartments/{apartment_id}?view=settings&lang=en").text
    assert 'id="sec-archive"' in archived and "/unarchive" in archived


def test_finished_property_editor_keeps_archive_and_test_button(host, fake_client):  # noqa: F811
    apartment_id = _create(host)
    property_setup.finish(apartment_id)
    editor = host["client"].get(f"/apartments/{apartment_id}?view=settings&lang=en").text
    assert 'id="sec-archive"' in editor
    assert re.search(r'<button[^>]*formaction="/apartments/\d+/test-connection"', editor)
    assert "Save and test connection" in editor


def test_no_visible_apartment_word_on_setup_pages(host, fake_client):  # noqa: F811
    apartment_id = _create(host, skip=False)
    assert "apartment" not in _visible(_page(host, apartment_id, "calendar"))
    _skip_calendar(host, apartment_id)
    assert "apartment" not in _visible(_page(host, apartment_id, "police"))
    _test(host, apartment_id)
    assert "apartment" not in _visible(_page(host, apartment_id, "guest_link"))
    _guest_done(host, apartment_id)
    assert "apartment" not in _visible(_page(host, apartment_id, "done"))
    page = _page(host, apartment_id, "guest_link")
    assert "Find your property" in page


def test_new_login_without_password_is_not_tested_and_stays_on_police(host, fake_client):  # noqa: F811
    apartment_id = _create(host)
    assert _test(host, apartment_id).status_code == 303
    made = len(fake_client["made"])
    response = _test(
        host, apartment_id, uby_ws_user="UBY-WS_OTHER1", uby_ws_password="", letter_fields="uby_ws_user",
    )
    assert response.status_code == 303 and _path(response).endswith("/setup/police")
    assert len(fake_client["made"]) == made
    shown = host["client"].get(response.headers["location"], follow_redirects=False)
    assert host_i18n.translate("en", "flash.apartments.letter_new_login_no_password") in html.unescape(shown.text)
