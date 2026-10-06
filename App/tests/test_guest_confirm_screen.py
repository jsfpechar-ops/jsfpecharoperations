"""UX-116 (audit A-29): the confirm-from-e-mail screen's help and dates card.

WP17 (review 3.E item 10) then cut the help line altogether: "Yes, this is my
stay" already says what the tap does, so the card is the title and the button.
"""
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, claim, db, i18n
from app.main import app

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
TOKEN = "confirmhelp"
ENTITY = "Confirm Help Test"
ADMIN_USERNAME = "confirm-help-admin"

# The line WP17 cut, in both languages. It only repeated the button label.
CUT_COPY = {
    "en": "One tap to confirm it’s really you.",
    "cs": "Jedním klepnutím potvrďte, že jste to opravdu vy.",
}


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        (ENTITY,),
    )


def _ensure_admin() -> int:
    db.init_db()
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (ADMIN_USERNAME,))
    if account:
        return account["id"]
    return auth.create_account(f"{ADMIN_USERNAME}@example.test", "Confirm help admin", role="admin", username=ADMIN_USERNAME)


def _seed() -> int:
    """One apartment with a claimable three-night stay arriving in three days."""
    db.init_db()
    _cleanup()
    owner_id = _ensure_admin()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": ENTITY,
            "seat": "Praha 3",
            "contact_email": "confirm@confirmhelp.test",
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Confirm help flat",
            "city_en": "Prague",
            "permalink_token": TOKEN,
            "permalink_window_days": 30,
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "confirm-help-3",
            "date_from": (today + timedelta(days=3)).isoformat(),
            "date_to": (today + timedelta(days=6)).isoformat(),
            "summary": "Confirm help reservation",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def test_the_help_line_that_repeated_the_button_is_gone():
    for lang in ("en", "cs"):
        assert "claim_confirm_help" not in i18n.STRINGS[lang], lang
    template = _read("guest/confirm.html")
    assert "claim_confirm_help" not in template
    card = template[template.index('<div class="g-card">\n  <h2>{{ t(\'claim_confirm_title\') }}') :]
    assert "{{ t('claim_confirm_title') }}" in card
    assert "{{ t('claim_confirm_button') }}" in card
    assert 'class="g-intro"' not in card


def test_the_dates_card_carries_the_nights():
    template = _read("guest/confirm.html")
    card = template[template.index("g-stay-summary") : template.index("</div>")]
    assert "nights_label(reservation.date_from, reservation.date_to)" in card


def test_the_rendered_card_shows_the_stay_length():
    stay_id = _seed()
    try:
        response = TestClient(app).get(f"/l/{TOKEN}/{stay_id}/claim?lang=en")
        assert response.status_code == 200
        for cut in CUT_COPY.values():
            assert cut not in response.text
        assert i18n.STRINGS["en"]["claim_confirm_title"] in response.text
        assert i18n.STRINGS["en"]["nights_few"] % {"n": 3} in response.text
    finally:
        _cleanup()
