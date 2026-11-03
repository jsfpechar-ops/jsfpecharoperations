"""0884 follow-up: the Try it rehearsal stays reachable after setup, with Skip and Leave."""
from __future__ import annotations

from urllib.parse import urlparse

from app import db, demo, host_i18n, property_setup
from tests.test_onboarding_wizard_survival import _full_apartment, host  # noqa: F401


def _path(response) -> str:
    return urlparse(response.headers["location"]).path


def _page(host, lang="en", *, register=False, mode=None):  # noqa: F811
    flat = _full_apartment(host)
    apt_id = flat["id"]
    client = host["client"]
    property_setup.finish(apt_id)
    client.post(f"/apartments/{apt_id}/setup", data={"step": "try_it", "action": "demo"}, follow_redirects=False)
    if mode is not None:
        db.execute("UPDATE apartment SET automation_mode = ?, submit_after_hours = ? WHERE id = ?", (mode, 12, apt_id))
    if register:
        stay = demo.demo_stay_for(apt_id)
        demo._guest(
            stay["id"], True, surname="Smith", first_name="John Paul", birth_date="01011990",
            nationality="GBR", doc_number="P1234567", res_street="Baker Street 221B",
            res_city="London", res_country="GBR", purpose="10",
        )
    response = client.get(f"/apartments/{apt_id}/setup/try_it?lang={lang}")
    assert response.status_code == 200
    return apt_id, response.text


def test_the_done_page_links_to_the_rehearsal(host):  # noqa: F811
    flat = _full_apartment(host)
    property_setup.finish(flat["id"])
    page = host["client"].get(f"/apartments/{flat['id']}/setup/done?lang=en").text
    assert f'href="/apartments/{flat["id"]}/setup/try_it"' in page


def test_every_state_offers_skip_and_leave_and_no_exit(host):  # noqa: F811
    flat = _full_apartment(host)
    property_setup.finish(flat["id"])
    client = host["client"]
    base = f"/apartments/{flat['id']}/setup"
    for lang in ("en", "cs", "vi"):
        leave = host_i18n.translate(lang, "wizard.try_it.leave")
        assert leave != "wizard.try_it.leave"
        none_yet = client.get(f"{base}/try_it?lang={lang}").text
        assert f'href="{base}/done"' in none_yet and leave in none_yet
        assert "setup-wizard-exit" not in none_yet
        assert 'value="skip"' in none_yet
    client.post(base, data={"step": "try_it", "action": "demo"}, follow_redirects=False)
    open_state = client.get(f"{base}/try_it?lang=en").text
    assert 'value="skip"' in open_state and f'href="{base}/done"' in open_state
    demo._guest(
        demo.demo_stay_for(flat["id"])["id"], True, surname="Smith", first_name="J", birth_date="01011990",
        nationality="GBR", doc_number="P1234567", res_street="Baker Street 221B", res_city="London",
        res_country="GBR", purpose="10",
    )
    registered = client.get(f"{base}/try_it?lang=en").text
    assert 'value="skip"' in registered and 'value="keep_demo"' in registered
    assert f'href="{base}/done"' in registered


def test_walkthrough_after_demo_registration(host):  # noqa: F811
    for lang in ("en", "cs", "vi"):
        _, text = _page(host, lang, register=True)
        assert "data-rehearsal" in text
        assert text.count("data-rehearsal-step=") == 5
        assert 'data-rehearsal-step="paste"' in text
        assert text.index("data-rehearsal") < text.index('id="demo-property-heading"')
        assert host_i18n.translate(lang, "wizard.try_it.instructions") not in text
        assert host_i18n.translate(lang, "wizard.rehearsal.never_police") in text


def test_police_line_follows_mode(host):  # noqa: F811
    _, scheduled = _page(host, "en", register=True, mode="scheduled")
    assert "12 hours" in scheduled
    _, manual = _page(host, "en", register=True, mode="manual")
    assert host_i18n.translate("en", "wizard.rehearsal.police_manual") in manual


def test_no_walkthrough_before_registration(host):  # noqa: F811
    _, text = _page(host, "en", register=False)
    assert "data-rehearsal" not in text


def test_skip_deletes_the_demo_stay_and_goes_to_done(host):  # noqa: F811
    apt_id, _ = _page(host, "en", register=True)
    client = host["client"]
    assert demo.demo_stay_for(apt_id)
    response = client.post(f"/apartments/{apt_id}/setup", data={"step": "try_it", "action": "skip"}, follow_redirects=False)
    assert response.status_code == 303 and _path(response) == f"/apartments/{apt_id}/setup/done"
    assert demo.demo_stay_for(apt_id) is None
    assert "try_it" not in property_setup.load(apt_id)["steps"]
    again = client.post(f"/apartments/{apt_id}/setup", data={"step": "try_it", "action": "skip"}, follow_redirects=False)
    assert _path(again) == f"/apartments/{apt_id}/setup/done"


def test_keep_and_leave_keep_the_demo_stay(host):  # noqa: F811
    apt_id, _ = _page(host, "en", register=True)
    client = host["client"]
    kept = client.post(f"/apartments/{apt_id}/setup", data={"step": "try_it", "action": "keep_demo"}, follow_redirects=False)
    assert _path(kept) == f"/apartments/{apt_id}/setup/done"
    assert demo.demo_stay_for(apt_id)
    left = client.get(f"/apartments/{apt_id}/setup/try_it?lang=en")
    assert left.status_code == 200 and demo.demo_stay_for(apt_id)


def test_another_hosts_property_is_refused(host):  # noqa: F811
    response = host["client"].get("/apartments/999999/setup/try_it", follow_redirects=False)
    assert response.status_code == 303 and _path(response) == "/apartments"
