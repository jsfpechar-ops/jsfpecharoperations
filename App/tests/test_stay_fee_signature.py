"""Encrypted legal-entity signatures for stay-fee remittance."""
from __future__ import annotations

import base64
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import auth, db, stay_fee, stay_fee_remittance_pdf
from app.main import app
from tests.conftest import login_as

USERNAME = "stay-fee-signature-host"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/h48AAAAASUVORK5CYII="
)
JPEG_BYTES = b"\xff\xd8\xff" + (b"\x00" * 60)
JPEG_DATA_URL = "data:image/jpeg;base64," + base64.b64encode(JPEG_BYTES).decode("ascii")


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner["id"],))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner["id"],))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner["id"],))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner["id"],))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner["id"],))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Signature Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _entity_form(name):
    return {
        "name": name,
        "seat": "Demo 1, Praha",
        "ico": "04656679",
        "contact_email": "entity@example.test",
    }


def test_jpeg_drawn_signature_is_accepted_on_entity_edit(host):
    host.post("/entities?lang=en", data=_entity_form("JPEG Drawn s.r.o."))
    entity = db.query_one(
        "SELECT id FROM legal_entity WHERE name = ?",
        ("JPEG Drawn s.r.o.",),
    )
    assert entity is not None
    response = host.post(
        f"/entities/{entity['id']}?lang=en",
        data={**_entity_form("JPEG Drawn s.r.o."), "signature_drawn": JPEG_DATA_URL},
        follow_redirects=False,
    )
    assert response.status_code == 303
    saved = db.query_one(
        "SELECT signature_png_enc FROM legal_entity WHERE id = ?",
        (entity["id"],),
    )
    assert db.decrypt_field(saved["signature_png_enc"]).startswith("data:image/jpeg;base64,")


def test_png_signature_is_encrypted_at_rest(host):
    host.post(
        "/entities?lang=en",
        data=_entity_form("Signature PNG s.r.o."),
        files={"signature_file": ("signature.png", PNG_BYTES, "image/png")},
    )
    row = db.query_one(
        "SELECT signature_png_enc FROM legal_entity WHERE name = ?",
        ("Signature PNG s.r.o.",),
    )
    assert row is not None
    assert not row["signature_png_enc"].startswith("data:")
    assert db.decrypt_field(row["signature_png_enc"]).startswith("data:image/png;base64,")


def test_signature_over_300_kb_is_rejected(host):
    oversized = b"\x89PNG" + b"x" * (301 * 1024 - 4)
    response = host.post(
        "/entities?lang=en",
        data=_entity_form("Oversized Signature s.r.o."),
        files={"signature_file": ("signature.png", oversized, "image/png")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "The signature must be a PNG or JPEG image up to 300 KB." in response.text
    assert db.query_one(
        "SELECT 1 AS x FROM legal_entity WHERE name = ?",
        ("Oversized Signature s.r.o.",),
    ) is None


def test_text_named_png_is_rejected(host):
    response = host.post(
        "/entities?lang=en",
        data=_entity_form("Text Signature s.r.o."),
        files={"signature_file": ("signature.png", b"not an image", "image/png")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "The signature must be a PNG or JPEG image up to 300 KB." in response.text
    assert db.query_one(
        "SELECT 1 AS x FROM legal_entity WHERE name = ?",
        ("Text Signature s.r.o.",),
    ) is None


def test_remove_signature_and_save_typed_name(host):
    host.post(
        "/entities?lang=en",
        data={**_entity_form("Remove Signature s.r.o."), "signature_name": "Old Name"},
        files={"signature_file": ("signature.png", PNG_BYTES, "image/png")},
    )
    entity = db.query_one(
        "SELECT id FROM legal_entity WHERE name = ?",
        ("Remove Signature s.r.o.",),
    )
    assert entity is not None

    page = host.get(f"/entities?edit={entity['id']}&lang=en")
    assert "data:image/png;base64," in page.text
    response = host.post(
        f"/entities/{entity['id']}?lang=en",
        data={**_entity_form("Remove Signature s.r.o."),
              "signature_remove": "1", "signature_name": "  Jane Doe  "},
        follow_redirects=False,
    )
    assert response.status_code == 303
    saved = db.query_one(
        "SELECT signature_png_enc, signature_name FROM legal_entity WHERE id = ?",
        (entity["id"],),
    )
    assert saved["signature_png_enc"] is None
    assert saved["signature_name"] == "Jane Doe"


def test_remittance_pdf_contains_typed_name_without_image(host):
    host.post(
        "/entities?lang=en",
        data={**_entity_form("Typed Name s.r.o."), "signature_name": "Jane Doe"},
    )
    row = db.query_one("SELECT * FROM legal_entity WHERE name = ?", ("Typed Name s.r.o.",))
    assert row is not None
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Demo property",
            "owner_user_id": row["owner_user_id"],
            "legal_entity_id": row["id"],
            "stay_fee_rate_czk": 50,
            "stay_fee_vs": "123",
            "stay_fee_cadence": "monthly",
            "stay_fee_authority_name": "Demo authority",
            "created_at": db.utcnow(),
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    report = stay_fee.hlaseni(
        stay_fee.report_group(apartment, date(2026, 8, 1)),
        date(2026, 9, 12),
    )
    text = PdfReader(io.BytesIO(stay_fee_remittance_pdf.render(report))).pages[0].extract_text()
    assert report["signature_png"] == ""
    assert "Jane Doe" in text
