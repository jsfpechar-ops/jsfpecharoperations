"""0274: the finish moment (confetti once, partial amber, one finish button per branch)."""
from __future__ import annotations

import re
from datetime import date, timedelta

from app import config, db, host_i18n, property_setup
from tests.test_onboarding_wizard_survival import _full_apartment, host  # noqa: F401
from tests.wizard_walk import walk_to

FINISH_KEYS = (
    "wizard.done.fix.police",
    "wizard.done.fix.step",
    "wizard.done.go_stays",
    "wizard.done.go_property",
)
PRIMARY_RE = re.compile(r'<a class="ui-btn ui-btn-primary" href="([^"]+)" data-finish-go="([a-z]+)"')


def _finish(host, monkeypatch, *, wait_police: bool) -> int:
    """Walk the wizard to the done page; blank the police login first when ``wait_police``."""
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    flat = _full_apartment(host)
    apt_id = flat["id"]
    if wait_police:
        db.execute(
            "UPDATE apartment SET uby_idub = '', uby_ws_user = '', uby_mark = '', "
            "uby_name = '', uby_ws_password_enc = NULL WHERE id = ?",
            (apt_id,),
        )
    # Once finished, the wizard entry leaves the wizard, so walk_to reports "".
    assert walk_to(host["client"], apt_id, "done") in ("done", "")
    assert property_setup.load(apt_id)["finished"] is True
    return apt_id


def _primary(text: str) -> tuple[str, str]:
    match = PRIMARY_RE.search(text)
    assert match, "no primary finish button"
    return match.group(1), match.group(2)


def test_confetti_once(host, monkeypatch):
    apt_id = _finish(host, monkeypatch, wait_police=False)
    client = host["client"]
    first = client.get(f"/apartments/{apt_id}/setup/done?lang=en")
    assert first.status_code == 200
    assert "setup-wizard-confetti" in first.text
    assert 'data-setup-celebrate="done"' in first.text
    assert "all set!" in first.text  # Jinja escapes the apostrophe, so match the tail of the copy
    second = client.get(f"/apartments/{apt_id}/setup/done?lang=en")
    assert second.status_code == 200
    assert "setup-wizard-confetti" not in second.text


def test_missing_police_goes_to_police(host, monkeypatch):
    apt_id = _finish(host, monkeypatch, wait_police=True)
    text = host["client"].get(f"/apartments/{apt_id}/setup/done?lang=en").text
    assert 'data-setup-celebrate="partial"' in text
    assert "setup-wizard-confetti" not in text
    assert f'href="/apartments/{apt_id}/setup/police" data-finish-go="fix"' in text


def test_no_stays_goes_to_property(host, monkeypatch):
    apt_id = _finish(host, monkeypatch, wait_police=False)
    text = host["client"].get(f"/apartments/{apt_id}/setup/done?lang=en").text
    href, flag = _primary(text)
    assert flag == "property"
    assert href == f"/apartments/{apt_id}?view=overview"
    assert href != "/"


def test_next_stay_goes_to_stays(host, monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    flat = _full_apartment(host)
    apt_id = flat["id"]
    start = date.today() + timedelta(days=5)
    now = db.utcnow()
    db.insert("reservation", {
        "apartment_id": apt_id, "uid": "fin0274-a",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
        "status": "active", "source": "airbnb", "created_at": now, "updated_at": now,
    })
    assert walk_to(host["client"], apt_id, "done") in ("done", "")
    assert property_setup.load(apt_id)["finished"] is True
    text = host["client"].get(f"/apartments/{apt_id}/setup/done?lang=en").text
    href, flag = _primary(text)
    assert flag == "stays"
    assert href == f"/apartments/{apt_id}?view=bookings"
    assert "data-finish-note" in text


def test_labels_short():
    for lang in ("en", "cs", "vi"):
        for key in FINISH_KEYS:
            label = host_i18n.translate(lang, key)
            assert label and len(label) <= 24, (lang, key, label)
