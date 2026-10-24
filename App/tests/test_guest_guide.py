"""0291: the guest guide data layer."""
from __future__ import annotations

import pytest

from app import db, guest_guide

PREFIX = "guide-0291-"


def _cleanup() -> None:
    db.execute(
        "DELETE FROM apartment WHERE permalink_token LIKE ?", (PREFIX + "%",)
    )


@pytest.fixture
def apartment():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    apt_id = db.insert(
        "apartment",
        {
            "internal_name": "Guide flat",
            "permalink_token": PREFIX + "tok",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "checkin_info": "Key box left of the door, code from your host.",
            "created_at": now,
        },
    )
    yield db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,))
    _cleanup()


def _by_kind(apt_id):
    return {r["kind"]: r for r in guest_guide.items(apt_id)}


def test_defaults_are_created_once(apartment):
    guest_guide.ensure_defaults(apartment)
    guest_guide.ensure_defaults(apartment)
    kinds = [r["kind"] for r in guest_guide.items(apartment["id"])]
    assert sorted(kinds) == sorted(guest_guide.DEFAULT_KINDS)
    assert len(kinds) == len(set(kinds))


def test_old_checkin_text_becomes_a_draft(apartment):
    guest_guide.ensure_defaults(apartment)
    checkin = _by_kind(apartment["id"])["checkin"]
    assert checkin["state"] == "check"
    assert checkin["source"] == "legacy"
    assert checkin["steps"].startswith("Key box")


def test_items_come_in_guest_order(apartment):
    guest_guide.ensure_defaults(apartment)
    guest_guide.add_kind(apartment["id"], "garage", source="booking")
    topics = [r["topic"] for r in guest_guide.items(apartment["id"])]
    order = [guest_guide.TOPICS.index(t) for t in topics]
    assert order == sorted(order)


def test_save_marks_done_and_validates(apartment):
    guest_guide.ensure_defaults(apartment)
    wifi = _by_kind(apartment["id"])["wifi"]
    saved = guest_guide.save(
        apartment["id"], wifi["id"], {"steps": "Network Vivus, password on the router", "visibility": "booked"}
    )
    assert saved["state"] == "done"
    assert saved["visibility"] == "booked"
    with pytest.raises(guest_guide.GuideError):
        guest_guide.save(apartment["id"], wifi["id"], {"video_url": "http://example.test/v"})
    with pytest.raises(guest_guide.GuideError):
        guest_guide.save(apartment["id"], wifi["id"], {"steps": "x" * 4001})
    with pytest.raises(guest_guide.GuideError):
        guest_guide.save(apartment["id"], wifi["id"], {"visibility": "public"})
    cleared = guest_guide.save(apartment["id"], wifi["id"], {"steps": ""})
    assert cleared["state"] == "missing"


def test_another_property_cannot_edit_the_item(apartment):
    guest_guide.ensure_defaults(apartment)
    wifi = _by_kind(apartment["id"])["wifi"]
    with pytest.raises(guest_guide.GuideError):
        guest_guide.save(apartment["id"] + 100000, wifi["id"], {"steps": "x"})


def test_custom_cards_can_be_added_and_deleted_built_in_cannot(apartment):
    guest_guide.ensure_defaults(apartment)
    item_id = guest_guide.add_custom(apartment["id"], "kitchen", "Induction hob")
    assert guest_guide.get(apartment["id"], item_id)["kind"] == "custom"
    assert guest_guide.delete_custom(apartment["id"], item_id) is True
    wifi = _by_kind(apartment["id"])["wifi"]
    assert guest_guide.delete_custom(apartment["id"], wifi["id"]) is False
    with pytest.raises(guest_guide.GuideError):
        guest_guide.add_custom(apartment["id"], "nowhere", "Hob")


def _finish_must_haves(apt_id):
    for kind in guest_guide.MUST_HAVE:
        item = _by_kind(apt_id)[kind]
        guest_guide.save(apt_id, item["id"], {"steps": f"How to {kind}"})


def test_guests_see_nothing_until_the_five_are_done(apartment):
    guest_guide.ensure_defaults(apartment)
    apt = apartment["id"]
    assert guest_guide.progress(apt)["live"] is False
    assert guest_guide.for_guest(apt, "everyone") == []
    _finish_must_haves(apt)
    assert guest_guide.progress(apt)["live"] is True
    assert guest_guide.for_guest(apt, "everyone")


def test_visibility_levels(apartment):
    guest_guide.ensure_defaults(apartment)
    apt = apartment["id"]
    _finish_must_haves(apt)
    items = _by_kind(apt)
    guest_guide.save(apt, items["wifi"]["id"], {"visibility": "booked"})
    guest_guide.save(apt, items["keys"]["id"], {"steps": "Spare key with cleaner", "visibility": "host"})
    public = {r["kind"] for r in guest_guide.for_guest(apt, "everyone")}
    booked = {r["kind"] for r in guest_guide.for_guest(apt, "booked")}
    assert "wifi" not in public and "wifi" in booked
    assert "keys" not in public and "keys" not in booked
    assert guest_guide.for_guest(apt, "host") == []


def test_drafts_and_skipped_cards_never_reach_guests(apartment):
    guest_guide.ensure_defaults(apartment)
    apt = apartment["id"]
    _finish_must_haves(apt)
    kinds = {r["kind"] for r in guest_guide.for_guest(apt, "booked")}
    assert "checkin" in kinds  # saved by the host, so confirmed
    guest_guide.add_kind(apt, "garage", source="booking")
    garage = _by_kind(apt)["garage"]
    db.execute("UPDATE guide_item SET steps = 'Remote in drawer', state = 'check' WHERE id = ?", (garage["id"],))
    assert "garage" not in {r["kind"] for r in guest_guide.for_guest(apt, "booked")}
    guest_guide.skip(apt, garage["id"])
    guest_guide.skip(apt, garage["id"], skipped=False)
    assert _by_kind(apt)["garage"]["state"] == "check"
    assert "garage" not in {r["kind"] for r in guest_guide.for_guest(apt, "booked")}
    guest_guide.skip(apt, _by_kind(apt)["trash"]["id"])
    progress = guest_guide.progress(apt)
    assert progress["check"] == 1
    assert progress["total"] == len(_by_kind(apt)) - 1
