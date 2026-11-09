"""Owner decision 2026-11-09: a guest edits or removes the people they added until
the record is filed with UbyPort (guest.submit_state == reporting.SENT). After
that the page is locked and offers a "Message host" button."""
import pytest
from fastapi.testclient import TestClient

from app import db, i18n, reporting
from app.main import app
from app.routes import guest
from tests import test_guest_navigation as nav
from tests.conftest import complete_guest_claim

TOKEN = nav.TOKEN


@pytest.fixture
def stay():
    token, stay_id, _right = nav._make_apartment_with_stays()
    # Other guest tests spend the same link's POST budget; start each test clean.
    db.execute("DELETE FROM rate_limit_event")
    db.execute(
        "UPDATE legal_entity SET contact_email = ? WHERE name = ?",
        ("host@example.test", "Nav Test"),
    )
    try:
        yield token, stay_id
    finally:
        nav._cleanup()


def _guest_on_device(token, stay_id, party_size="2", **overrides):
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(browser, token, stay_id, party_size=int(party_size))
    saved = browser.post(
        f"/l/{token}/{stay_id}/save",
        data=nav._form(party_size=party_size, **overrides),
        files=nav._passport_files(),
        follow_redirects=False,
    )
    assert saved.status_code == 303
    row = db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (stay_id,))
    return browser, row


def _resave(browser, token, stay_id, guest_id, **overrides):
    return browser.post(
        f"/l/{token}/{stay_id}/save",
        data=nav._form(guest_id=str(guest_id), **overrides),
        files=nav._passport_files(),
        follow_redirects=False,
    )


def _surname(guest_id):
    return db.query_one("SELECT surname FROM guest WHERE id = ?", (guest_id,))["surname"].title()


def test_a_complete_signed_form_can_be_reopened_and_changed_before_filing(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    # 2026-11-09: complete + signed no longer locks the form.
    assert reporting.guest_is_complete(row, db.query_one("SELECT * FROM reservation WHERE id = ?", (stay_id,)))
    page = browser.get(f"/l/{token}/{stay_id}/edit/{row['id']}?lang=en")
    assert page.status_code == 200
    changed = _resave(browser, token, stay_id, row["id"], surname="Jones")
    assert changed.status_code == 303
    after = db.query_one("SELECT * FROM guest WHERE id = ?", (row["id"],))
    assert after["surname"].title() == "Jones"
    # The signature and the stored scan survive the edit; the record is sendable again.
    assert after["signature_png"].startswith("data:image/png")
    assert reporting.guest_has_signature(after)
    assert after["submit_state"] == reporting.PENDING
    assert db.query_one("SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay_id,))["n"] == 1


def test_an_edit_still_needs_a_valid_signature_and_the_legal_tick(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    refused = _resave(browser, token, stay_id, row["id"], surname="Jones", legal_ack="")
    assert refused.status_code == 422
    assert _surname(row["id"]) == "Smith"


def test_a_correction_after_a_failed_record_resets_the_attempts(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    db.update("guest", row["id"], {"submit_state": reporting.ERROR, "submit_attempts": 5})
    assert _resave(browser, token, stay_id, row["id"], surname="Jones").status_code == 303
    after = db.query_one("SELECT * FROM guest WHERE id = ?", (row["id"],))
    assert after["submit_state"] == reporting.PENDING
    assert after["submit_attempts"] == 0


def test_a_filed_record_is_locked_with_a_message_host_button(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    db.update("guest", row["id"], {"submit_state": reporting.SENT})
    page = browser.get(f"/l/{token}/{stay_id}/edit/{row['id']}?lang=en")
    assert page.status_code == 403
    assert i18n.STRINGS["en"]["already_filed_title"] in page.text
    assert 'data-message-host' in page.text
    assert "mailto:host@example.test" in page.text
    save = _resave(browser, token, stay_id, row["id"], surname="Jones")
    assert save.status_code == 403
    assert _surname(row["id"]) == "Smith"
    hub = browser.get(f"/l/{token}/{stay_id}?lang=en")
    assert "data-message-host" in hub.text
    assert "data-remove-person" not in hub.text
    assert f"/edit/{row['id']}" not in hub.text


def test_filing_between_page_load_and_save_shows_the_filed_message_and_keeps_the_record(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    assert browser.get(f"/l/{token}/{stay_id}/edit/{row['id']}?lang=en").status_code == 200
    # The automation files the stay while the guest still has the form open.
    db.update("guest", row["id"], {"submit_state": reporting.SENT})
    save = _resave(browser, token, stay_id, row["id"], surname="Jones")
    assert save.status_code == 403
    assert i18n.STRINGS["en"]["already_filed_title"] in save.text
    assert _surname(row["id"]) == "Smith"


def test_filing_in_the_instant_after_the_check_is_caught_by_the_compare_and_set(stay, monkeypatch):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    real = guest._guest_form_raw

    def filed_while_reading(form, apartment):
        # After the route read the row (not yet filed) and before it writes.
        db.update("guest", row["id"], {"submit_state": reporting.SENT})
        return real(form, apartment)

    monkeypatch.setattr(guest, "_guest_form_raw", filed_while_reading)
    save = _resave(browser, token, stay_id, row["id"], surname="Jones")
    assert save.status_code == 403
    assert i18n.STRINGS["en"]["already_filed_title"] in save.text
    assert _surname(row["id"]) == "Smith"


def test_an_edit_made_before_filing_is_what_gets_filed(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    assert _resave(browser, token, stay_id, row["id"], surname="Jones").status_code == 303
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay_id,))
    pending = db.query_one("SELECT * FROM guest WHERE id = ?", (row["id"],))
    assert reporting.guest_dict(pending)["surname"].title() == "Jones"
    assert reporting.guest_is_complete(pending, reservation)
    db.update("guest", row["id"], {"submit_state": reporting.SENT})
    # Once filed, a late edit from the old page cannot change what was filed.
    assert _resave(browser, token, stay_id, row["id"], surname="Late").status_code == 403
    assert _surname(row["id"]) == "Jones"


def test_a_device_cannot_edit_or_remove_a_person_it_did_not_add(stay):
    token, stay_id = stay
    _browser, row = _guest_on_device(token, stay_id)
    other = TestClient(app)
    other.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(other, token, stay_id, party_size=2)
    assert other.get(f"/l/{token}/{stay_id}/edit/{row['id']}").status_code == 403
    assert other.get(f"/l/{token}/{stay_id}/remove/{row['id']}").status_code == 403
    assert other.post(f"/l/{token}/{stay_id}/remove/{row['id']}", follow_redirects=False).status_code == 403
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (row["id"],))


def test_remove_asks_first_then_deletes_the_person_and_updates_the_headcount(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    hub = browser.get(f"/l/{token}/{stay_id}?lang=en")
    assert "data-remove-person" in hub.text
    confirm = browser.get(f"/l/{token}/{stay_id}/remove/{row['id']}?lang=en")
    assert confirm.status_code == 200
    assert 'method="post"' in confirm.text and 'name="_csrf"' in confirm.text
    # A GET never deletes.
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (row["id"],))
    done = browser.post(f"/l/{token}/{stay_id}/remove/{row['id']}?lang=en", follow_redirects=False)
    assert done.status_code == 303
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (row["id"],)) is None
    assert db.query_one(
        "SELECT 1 AS x FROM audit WHERE action = ?", ("guest_removed_by_guest",)
    )
    # With nobody left the hub opens the empty form again.
    assert browser.get(done.headers["location"], follow_redirects=False).status_code == 303
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay_id,))
    progress = reporting.reservation_progress(reservation)
    assert progress["filled"] == 0
    # The removed person's page link is gone with the cookie entry.
    assert browser.get(f"/l/{token}/{stay_id}/edit/{row['id']}").status_code == 403


def test_a_filed_person_cannot_be_removed_even_after_the_confirmation_loaded(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    assert browser.get(f"/l/{token}/{stay_id}/remove/{row['id']}?lang=en").status_code == 200
    db.update("guest", row["id"], {"submit_state": reporting.SENT})
    done = browser.post(f"/l/{token}/{stay_id}/remove/{row['id']}?lang=en", follow_redirects=False)
    assert done.status_code == 403
    assert i18n.STRINGS["en"]["already_filed_title"] in done.text
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (row["id"],))


def test_a_person_being_filed_right_now_is_not_removed(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    import time

    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES (?, ?, ?)",
        (row["id"], "t", time.time()),
    )
    done = browser.post(f"/l/{token}/{stay_id}/remove/{row['id']}?lang=en", follow_redirects=False)
    assert done.status_code == 403
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (row["id"],))


def test_a_restricted_record_stays_read_only(stay):
    token, stay_id = stay
    browser, row = _guest_on_device(token, stay_id)
    db.update("guest", row["id"], {"restricted_at": db.utcnow()})
    assert _resave(browser, token, stay_id, row["id"], surname="Jones").status_code == 303
    assert _surname(row["id"]) == "Smith"
    assert browser.get(f"/l/{token}/{stay_id}/remove/{row['id']}").status_code == 403


def test_the_new_copy_exists_in_every_guest_language():
    keys = ("message_host", "remove_person", "remove_title", "remove_help", "remove_yes",
            "remove_keep", "removed_ok", "filed_short", "already_filed_help", "review_help")
    for lang, table in i18n.STRINGS.items():
        for key in keys:
            assert table.get(key), (lang, key)
        assert "%(name)s" in table["remove_title"], lang


def test_removing_one_of_two_people_keeps_the_other_and_says_so(stay):
    token, stay_id = stay
    browser, first = _guest_on_device(token, stay_id)
    second = browser.post(
        f"/l/{token}/{stay_id}/save",
        data=nav._form(party_size="2", first_name="Anna", doc_number="P7654321"),
        files=nav._passport_files(),
        follow_redirects=False,
    )
    assert second.status_code == 303
    rows = db.query("SELECT id FROM guest WHERE reservation_id = ? ORDER BY id", (stay_id,))
    assert len(rows) == 2
    done = browser.post(f"/l/{token}/{stay_id}/remove/{rows[1]['id']}?lang=en", follow_redirects=False)
    assert done.status_code == 303
    page = browser.get(done.headers["location"])
    assert i18n.STRINGS["en"]["removed_ok"] in page.text
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay_id,))
    progress = reporting.reservation_progress(reservation)
    assert progress["filled"] == 1 and progress["expected"] == 2
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (first["id"],))
