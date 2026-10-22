"""0230: the five-step story, the guest-link window and the paste check."""

from __future__ import annotations

from datetime import date

from app import db, workflow
from app.main import app  # noqa: F401  (creates the test database schema)

TODAY = date(2026, 11, 10)


def test_steps_follow_the_police_option_and_name_who_acts():
    manual = workflow.steps({"automation_mode": "manual", "lock_provider": None})
    assert [s["n"] for s in manual] == [1, 2, 3, 4, 5]
    assert manual[0]["who"] == "you_once"
    assert manual[3] == {"n": 4, "key": "police_manual", "who": "you"}
    assert workflow.steps({"automation_mode": "scheduled"})[3]["who"] == "auto"
    assert workflow.steps(None)[3]["key"] == "police"
    assert workflow.steps(None)[4]["key"] == "finish"


def test_status_maps_to_one_step():
    assert workflow.step_number("awaiting_guest") == 2
    assert workflow.step_number("incomplete") == 2
    assert workflow.step_number("ready") == 4
    assert workflow.step_number("failed") == 4
    assert workflow.step_number("reported") == 5
    assert workflow.step_number("not_required") is None


def _stay(date_from, **extra):
    row = {"status": "active", "archived_at": None, "source": "airbnb",
           "date_from": date_from, "permalink_window_days": 2}
    row.update(extra)
    return row


def test_link_window_matches_the_guest_picker_rule():
    assert workflow.link_window(_stay("2026-11-12"), TODAY) == {"state": "now", "opens": TODAY}
    later = workflow.link_window(_stay("2026-11-20"), TODAY)
    assert later == {"state": "from", "opens": date(2026, 11, 18)}
    assert workflow.link_window(_stay("2026-11-09"), TODAY) is None
    assert workflow.link_window(_stay("2026-11-20", source="demo"), TODAY) is None
    assert workflow.link_window(_stay("2026-11-20", status="cancelled"), TODAY) is None


def _apartment(token):
    entity = db.insert("legal_entity", {"name": "Workflow 0230 s.r.o.", "created_at": db.utcnow()})
    return db.insert("apartment", {
        "legal_entity_id": entity, "internal_name": "Workflow flat", "permalink_token": token,
        "active": 1, "permalink_window_days": 2, "created_at": "2026-11-01T08:00:00",
    })


def _reservation(apartment_id, date_from, uid):
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": uid, "date_from": date_from, "date_to": "2026-11-30",
        "status": "active", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_paste_check_shows_until_a_guest_claims_a_stay():
    db.init_db()
    apartment_id = _apartment("workflow0230token")
    try:
        row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        assert workflow.link_unused([row], TODAY) == []  # no stay reached the link yet
        reservation_id = _reservation(apartment_id, "2026-11-11", "wf0230-a")
        assert [r["id"] for r in workflow.link_unused([row], TODAY)] == [apartment_id]
        db.insert("reservation_claim", {
            "reservation_id": reservation_id, "state": "claimed", "token_version": 0,
            "claimed_at": db.utcnow(), "created_at": db.utcnow(), "updated_at": db.utcnow(),
        })
        assert workflow.guest_used_link(apartment_id) is True
        assert workflow.link_unused([row], TODAY) == []
    finally:
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))


def test_strings_exist_in_every_host_language():
    from app import host_i18n

    for lang in ("en", "cs", "vi"):
        for key in ("workflow.title", "workflow.link.from", "workflow.paste.title",
                    "wizard.door_lock.question", "wizard.summary.status.not_needed"):
            assert host_i18n.STRINGS[lang].get(key), (lang, key)
