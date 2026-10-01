"""A Czech host must get the whole host UI in Czech, macros included.

Jinja's ``{% from ... import %}`` does not pass the render context, so a
``t()`` call inside an imported macro cannot see the request and silently
falls back to English. The strings exist in host_i18n; they just never get
asked for. That hits the status pill and the next-action line on every row
of the work queue, which is the part a host actually reads.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, db, host_i18n, reporting
from app.main import app

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
PASSWORD = "Secure-Password-123"


def _cleanup():
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", ("langtoken",)
    )
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))


def _host_with_a_stay_needing_action() -> TestClient:
    """A stay whose forms are done but whose passport is unchecked."""
    db.init_db()
    now, today = db.utcnow(), date.today()
    username = "czechhost"
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    uid = existing["id"] if existing else auth.create_account(
        username, PASSWORD, "Czech Host", must_change_password=False
    )
    _cleanup()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Demo Host s.r.o.", "owner_user_id": uid, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": uid,
            "internal_name": "Demo Street 12",
            "permalink_token": "langtoken",
            "automation_mode": "manual",
            "default_purpose": "10",
            "uby_mark": "DEMO1",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "lang-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "expected_guests_override": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "NGUYEN",
            "first_name": "MINH",
            "birth_date": "01011990",
            "nationality": "VNM",
            "doc_number": "P9988771",
            "res_street": "Le Loi 5",
            "res_city": "Hanoi",
            "res_country": "VNM",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "guest",
            "signature_png": "imported",
            "signed_at": now,
            "passport_photo_at": now,
            "identity_verified_at": None,
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    client = TestClient(app)
    client.post(
        "/login", data={"username": username, "password": PASSWORD}, follow_redirects=False
    )
    client.cookies.set(host_i18n.LANG_COOKIE, "cs")
    return client


def test_the_next_action_on_a_czech_queue_row_is_czech():
    page = _host_with_a_stay_needing_action().get("/")
    assert page.status_code == 200
    actions = re.findall(r'<div class="host-task-state next-action">(.*?)</div>', page.text, re.S)
    assert actions, "no next-action line on the queue at all"
    english = host_i18n.translate("en", "status.awaiting_verification")
    czech = host_i18n.translate("cs", "status.awaiting_verification")
    assert czech != english, "fixture is pointless if the two languages match"
    joined = " ".join(" ".join(a.split()) for a in actions)
    assert english not in joined, (
        "the instruction on the work queue is in English for a Czech host"
    )
    assert czech in joined


def test_the_status_pill_on_a_czech_queue_row_is_czech():
    page = _host_with_a_stay_needing_action().get("/")
    english = host_i18n.translate("en", "status.awaiting_verification")
    czech = host_i18n.translate("cs", "status.awaiting_verification")
    assert czech != english
    assert english not in page.text, "the status pill is in English for a Czech host"
    assert czech in page.text


def test_the_setup_steps_a_new_czech_host_reads_are_czech():
    """First run is the one screen a host cannot skip, so it cannot be English."""
    client = _host_with_a_stay_needing_action()
    page = client.get("/")
    assert page.status_code == 200
    banner = re.search(r'<aside class="onboarding-banner".*?</aside>', page.text, re.S)
    assert banner, "no onboarding banner while setup is unfinished"
    text = " ".join(banner.group(0).split())
    assert "Setup step" not in text, "the setup prompt is in English for a Czech host"
    assert host_i18n.translate("cs", "onboarding.step_of").split("%")[0].strip() in text


def test_onboarding_copy_lives_in_the_translation_tables():
    """onboarding.py must stay logic; the wording belongs with the other strings."""
    from app import onboarding

    for step in onboarding.progress(None)["steps"]:
        for part in ("title", "detail", "prepare", "why", "action"):
            key = f"onboarding.{step['id']}.{part}"
            for lang in ("en", "cs"):
                assert host_i18n.translate(lang, key) != key, f"missing {lang} {key}"


def test_every_macro_import_passes_the_render_context():
    """Structural guard: the bug is invisible until someone reads a page in Czech.

    Any ``{% from %}`` of a macro file has to say ``with context``, or every
    ``t()`` inside those macros quietly answers in English.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped.startswith("{% from"):
                continue
            if "with context" not in stripped:
                offenders.append(f"{path.relative_to(TEMPLATES)}: {stripped}")
    assert not offenders, (
        "macro imports that cannot translate:\n" + "\n".join(offenders)
    )
