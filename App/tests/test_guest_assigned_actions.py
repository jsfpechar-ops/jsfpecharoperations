"""The "stay already assigned" screen's ways out, and its copy.

A-27 [UX-114] found three tidy-ups on this screen. DESIGN.md says the secondary
back / not-mine action appears "when other stays are available", but the
template rendered both unconditionally -- so a guest with one stay was offered
"This is not my reservation", which led to the "no stays" page. The last-sent
date was printed as raw ISO while every other date on the flow is `date_cz`.
And the masked e-mail was printed twice, once inside a stiff sentence.

This file pins all three: both ways out are gated on `can_pick_other`, the date
goes through the shared filter, and the body names the e-mail only by pointing
at the note box below it.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import claim, db, i18n
from app.main import app
from tests.conftest import complete_guest_claim

TOKEN = "assignedact"
ENTITY = "Assigned Test"

APP_DIR = Path(__file__).resolve().parents[1]

AUDIT_COPY = {
    "assigned_body": (
        "This stay is already linked to the e-mail below. If that's you, we can "
        "send the private link again.",
        "Tento pobyt je už propojený s e-mailem níže. Pokud jste to vy, pošleme "
        "vám soukromý odkaz znovu.",
    ),
}


def _read(name: str) -> str:
    return (APP_DIR / "app" / "templates" / "guest" / name).read_text(encoding="utf-8")


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if apartment:
        db.execute(
            "DELETE FROM email_outbox WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
        db.execute(
            "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
            "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
            (ENTITY,),
        )
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope LIKE 'claim_%' OR scope = 'claim_start'"
    )


def _seed(*, other_stay: bool = True):
    """One claimable stay, plus an optional second one inside the pick window."""
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {"name": ENTITY, "contact_email": "host@assigned.test", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Assigned flat",
            "uby_name": "Assigned Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 2,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )

    def stay(uid: str, start: int) -> int:
        return db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": "airbnb",
                "uid": uid,
                "date_from": (today + timedelta(days=start)).isoformat(),
                "date_to": (today + timedelta(days=start + 3)).isoformat(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )

    # The stay the link names. Past-dated, so it is reachable by the stay-specific
    # link but is not one of the picker's "other stays".
    linked = stay("assigned-linked", -10)
    if other_stay:
        stay("assigned-other", 0)
    return apartment_id, linked


def _assigned_page(linked: int, lang: str = "en"):
    """A browser that has no claim cookie, looking at an assigned stay."""
    token, _stay = TOKEN, linked
    claimer = TestClient(app)
    complete_guest_claim(claimer, token, linked, lang=lang)
    stranger = TestClient(app)
    page = stranger.get(f"/l/{token}/{linked}?lang={lang}")
    assert page.status_code == 200, page.status_code
    return page


def test_both_ways_out_are_gated_on_another_stay_being_available():
    template = _read("assigned.html")
    assert template.count("{% if can_pick_other %}") == 2
    for marker in ('class="g-back"', 'class="g-btn ghost"'):
        assert f"{{% if can_pick_other %}}\n<a {marker}" in template, marker


def test_the_body_copy_is_the_audits_wording():
    for key, (english, czech) in AUDIT_COPY.items():
        assert i18n.STRINGS["en"][key] == english, key
        assert i18n.STRINGS["cs"][key] == czech, key


def test_the_body_stops_restating_the_masked_address():
    # The note box below already shows it; the sentence points at it instead.
    assert "%(email)s" not in i18n.STRINGS["en"]["assigned_body"]
    assert "%(email)s" not in i18n.STRINGS["cs"]["assigned_body"]
    template = _read("assigned.html")
    assert "{{ t('assigned_body') }}" in template
    assert "assigned_body', email" not in template
    # ...and the address itself is printed exactly once.
    assert template.count("claim.email_masked") == 1


def test_the_last_sent_date_goes_through_the_shared_filter():
    template = _read("assigned.html")
    assert "claim_last_sent_at | date_cz" in template
    assert "claim_last_sent_at[:10]" not in template


def test_a_guest_with_another_stay_can_go_back_or_disown_the_stay():
    _apartment_id, linked = _seed(other_stay=True)
    try:
        page = _assigned_page(linked)
        assert f'href="/l/{TOKEN}?lang=en"' in page.text
        assert i18n.STRINGS["en"]["assigned_not_mine"] in page.text
    finally:
        _cleanup()


def test_a_guest_with_no_other_stay_gets_neither_way_out():
    _apartment_id, linked = _seed(other_stay=False)
    try:
        page = _assigned_page(linked)
        assert i18n.STRINGS["en"]["assigned_not_mine"] not in page.text
        assert f'href="/l/{TOKEN}?lang=en"' not in page.text
        # The primary action is untouched -- the screen still works.
        assert i18n.STRINGS["en"]["assigned_resend"] in page.text
    finally:
        _cleanup()


def test_the_rendered_date_is_not_raw_iso():
    apartment_id, linked = _seed()
    try:
        # The suite's console mail backend never stamps sent_at, so the row the
        # screen reads is written here: without it the filter has nothing to
        # prove and the assertion would pass on an empty string.
        now = db.utcnow()
        db.insert(
            "email_outbox",
            {
                "idempotency_key": "assigned-act-sent",
                "kind": "claim",
                "reservation_id": linked,
                "apartment_id": apartment_id,
                "to_email": "guest@assigned.test",
                "state": "sent",
                "attempts": 1,
                "created_at": now,
                "updated_at": now,
                "sent_at": "2031-07-08T09:15:00+00:00",
            },
        )
        page = _assigned_page(linked)
        assert "2031-07-08" not in page.text
        assert "08.07.2031" in page.text
    finally:
        _cleanup()
