"""0976: read-only audience matrix for the Keys card. Asserts today's behaviour; changes none."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import guest_guide
from app.main import app
from tests.conftest import login_as
from tests.test_guest_guide_view import TOKEN, _cards, _go_live, _qr, _stay, ws  # noqa: F401

SYNTHETIC = "SYNTHETIC-0976 key box instruction"


def _selected(html: str) -> str:
    select = re.search(r'<select[^>]*name="visibility".*?</select>', html, re.S)
    assert select, "visibility select not found"
    chosen = re.search(r'<option[^>]*value="(\w+)"[^>]*selected', select.group(0)) or re.search(
        r'<option[^>]*selected[^>]*value="(\w+)"', select.group(0))
    return chosen.group(1) if chosen else "first-option"


def _levels(ws, visibility):
    """(editor default, QR sees it, booked-window stay sees it, outside-window stay sees it)."""
    cards = _go_live(ws["home"], keys={"steps": SYNTHETIC, "visibility": visibility})
    qr = ws["client"].get(f"/g/{_qr(ws)}?lang=en").text
    inside = ws["client"].get(f"/l/{TOKEN}/{_stay(ws['home'], 0)}/guide?lang=en").text
    outside = ws["client"].get(f"/l/{TOKEN}/{_stay(ws['home'], 30)}/guide?lang=en").text
    return SYNTHETIC in qr, SYNTHETIC in inside, SYNTHETIC in outside


def test_fresh_keys_card_default_is_stored_everyone_and_shown_selected(ws):
    keys = _cards(ws["home"])["keys"]
    assert keys["visibility"] == "everyone"  # migration 0013 column default; no code overrides it
    host = TestClient(app)
    assert login_as(host, "view-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    html = host.get(f"/apartments/{ws['home']}/guide/{keys['id']}?lang=en").text
    print("EDITOR_DEFAULT", _selected(html))
    assert _selected(html) in ("everyone", "first-option")  # record which in the report


@pytest.mark.parametrize("visibility,qr,inside,outside", [
    ("everyone", True, True, True),
    ("booked", False, True, False),
    ("host", False, False, False),
])
def test_keys_card_matrix(ws, visibility, qr, inside, outside):
    assert _levels(ws, visibility) == (qr, inside, outside)
