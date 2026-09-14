"""Static annotated UbyPort web-service credential sample PDF and UI links."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from app.ubyport_sample_pdf import (
    RIGHT_MARGIN,
    SAMPLE_IDUB,
    SAMPLE_WS_PASSWORD,
    SAMPLE_ZKRATKA,
    SAMPLE_WS_USER,
    VALUE_COL,
    WATERMARK_LINE_2,
    build_sample_pdf,
    default_static_path,
    page_content_streams,
)

SAMPLE_URL = "/static/docs/ubyport-ws-credential-sample.pdf"
PASSWORD = "Sample-Pdf-Test-Password-123"


@pytest.fixture()
def authed_client():
    db.init_db()
    username = "sample-pdf-host"
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    if existing:
        user_id = existing["id"]
    else:
        user_id = auth.create_account(
            username, PASSWORD, "Sample PDF host", role="host", must_change_password=False
        )
    entity_id = db.insert(
        "legal_entity",
        {"name": "Sample entity", "owner_user_id": user_id, "created_at": db.utcnow()},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": user_id,
            "internal_name": "Sample flat",
            "permalink_token": "samplepdftok",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    assert client.post(
        "/login", data={"username": username, "password": PASSWORD}, follow_redirects=False
    ).status_code == 303
    yield client, apartment_id
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    if not existing:
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def test_committed_sample_pdf_exists_and_is_pdf():
    path = default_static_path()
    assert path.is_file(), "Run python tools/generate_ubyport_sample_pdf.py to refresh the static PDF"
    header = path.read_bytes()[:5]
    assert header == b"%PDF-"


def test_build_sample_pdf_bytes_are_valid_pdf():
    data = build_sample_pdf()
    assert data.startswith(b"%PDF-")
    assert len(data) > 12000


def test_sample_pdf_has_two_pages_and_czech_official_headings():
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(build_sample_pdf()))
    assert len(reader.pages) == 2
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "ŘEDITELSTVÍ SLUŽBY CIZINECKÉ POLICIE" in text
    assert "VÝPIS Z DATABÁZE PŘIHLAŠOVACÍCH ÚDAJŮ" in text
    assert "Přihlašovací jméno:" in text
    assert "Poučení:" in text
    assert SAMPLE_WS_USER in text
    assert SAMPLE_IDUB in text


def test_extract_page_text_stays_inside_right_margin():
    from reportlab.pdfbase import pdfmetrics

    from app.ubyport_sample_pdf import FONT_REGULAR, FONT_MONO, POUCENI_TEXT_X, _wrap_to_width

    pouceni_items = (
        "Tento účet slouží pro robotické vkládání dat prostřednictvím webové služby a "
        "nemůže být použit k jiným účelům.",
        "Ztratí-li nebo zapomene-li uživatel heslo, může požádat Ředitelství služby "
        "cizinecké policie o vygenerování nového hesla.",
        "Uživatel se řídí provozním řádem Internetové aplikace Ubyport.",
        "Při podezření na porušení provozního řádu Internetové aplikace Ubyport nebo "
        "jiné činnosti ohrožující kybernetickou",
        "bezpečnost může být uživatel zablokován.",
    )
    wrap_width = RIGHT_MARGIN - POUCENI_TEXT_X
    for item in pouceni_items:
        for line in _wrap_to_width(item, wrap_width, FONT_REGULAR, 11):
            assert pdfmetrics.stringWidth(line, FONT_REGULAR, 11) <= wrap_width + 0.5

    for label, value in (
        ("Přihlašovací jméno:", SAMPLE_WS_USER),
        ("Přístupové heslo:", SAMPLE_WS_PASSWORD),
    ):
        assert pdfmetrics.stringWidth(label, FONT_REGULAR, 11) + 10 < VALUE_COL
        assert pdfmetrics.stringWidth(value, FONT_MONO, 14) + VALUE_COL <= RIGHT_MARGIN + 0.5


def test_watermark_in_pdf_content_streams():
    data = build_sample_pdf()
    streams = page_content_streams(data)
    assert len(streams) == 2
    for stream in streams:
        assert b"SAMPLE" in stream
        assert b"NOT REAL" in stream
        assert b"ZKA" in stream
        assert WATERMARK_LINE_2.encode("utf-8") in data or b"NEPOU" in stream


def test_watermark_czech_diacritics_in_extracted_text():
    from pypdf import PdfReader

    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(io.BytesIO(build_sample_pdf())).pages
    )
    assert "NEPOUŽÍVAT" in text
    assert "NEPOUZÍVAT" not in text
    assert "UKÁZKA" in text


def test_watermark_renders_as_non_white_pixels():
    pdfplumber = pytest.importorskip("pdfplumber")

    data = build_sample_pdf()
    with pdfplumber.open(io.BytesIO(data)) as doc:
        for page in doc.pages:
            image = page.to_image(resolution=100).original.convert("L")
            w, h = image.size
            crop = image.crop((w // 5, h // 5, 4 * w // 5, 4 * h // 5))
            grey_pixels = sum(1 for px in crop.getdata() if px < 235)
            assert grey_pixels > 250, "expected visible diagonal watermark pixels on page"


def test_dulezite_prefix_has_space_before_body():
    from reportlab.pdfbase import pdfmetrics

    from app.ubyport_sample_pdf import FONT_BOLD, FONT_REGULAR

    prefix = "DŮLEŽITÉ:"
    prefix_end = (
        56.7
        + pdfmetrics.stringWidth(prefix, FONT_BOLD, 11)
        + pdfmetrics.stringWidth(" ", FONT_REGULAR, 11)
    )
    assert prefix_end > 118.5


def test_sample_constants_are_fictional():
    assert SAMPLE_IDUB == "209988776655"
    assert SAMPLE_ZKRATKA == "DEMO1"
    assert SAMPLE_WS_USER == "UBY-WS_DEMO1"
    assert SAMPLE_IDUB != "100124005169"


def test_sample_pdf_is_served():
    client = TestClient(app)
    response = client.get(SAMPLE_URL, follow_redirects=False)
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert response.content[:5] == b"%PDF-"


def test_apartment_form_links_to_sample_pdf(authed_client):
    client, apartment_id = authed_client
    page = client.get(f"/apartments/{apartment_id}")
    assert page.status_code == 200
    assert "Open annotated sample PDF" in page.text
    assert SAMPLE_URL in page.text
    assert "Where each UbyHost field comes from" in page.text


def test_automation_page_links_to_sample_and_property_setup(authed_client):
    client, apartment_id = authed_client
    page = client.get("/automation")
    assert page.status_code == 200
    assert SAMPLE_URL in page.text
    assert "Open annotated sample PDF" in page.text
    assert f"/apartments/{apartment_id}#ubyport" in page.text
