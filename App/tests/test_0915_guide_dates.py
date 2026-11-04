"""0915: the guide matches the app, host dates read dd.mm.yyyy, and "Received" is a date."""
from __future__ import annotations

import re

import pytest

from app import db
from tests.test_privacy_requests import _cleanup, _login, _seed
from tests.test_submission_retry_cap import host as host  # noqa: F401

ISO_TEXT = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _visible_text(page: str) -> str:
    """The page without scripts, styles, tags and attribute values, so only shown text is checked."""
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S)
    page = re.sub(r"<[^>]+>", " ", page)
    return page


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def test_the_guide_has_no_language_buttons_and_lists_payments(host):
    for lang in ("en", "cs"):
        page = host.get(f"/guide?lang={lang}").text
        assert "EN, CS" not in page, lang
        assert "EN / CS" not in page, lang
        assert 'id="payments"' in page, lang


def test_the_guide_search_script_opens_only_heading_matches():
    from pathlib import Path

    script = (Path(__file__).resolve().parents[1] / "app" / "static" / "guide.js").read_text()
    assert 'topic.open = match && fold((topic.querySelector("summary") || topic).textContent)' in script


def test_a_received_date_is_a_date_input_and_lists_as_dd_mm_yyyy(host):
    _seed("dsr-dates", "dsrdates")
    client = _login("dsr-dates")

    form = client.get("/privacy-requests?lang=en").text
    assert '<input type="date" id="received_at" name="received_at"' in form

    response = client.post(
        "/privacy-requests",
        data={
            "received_at": "2026-11-01",
            "channel": "email",
            "request_type": "access",
            "subject_kind": "guest",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    row = db.query_one(
        "SELECT received_at FROM data_subject_request WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = 'dsr-dates')"
    )
    assert row["received_at"] == "2026-11-01T00:00:00+00:00"

    listing = client.get("/privacy-requests?lang=en").text
    assert "01.11.2026" in listing
    assert "2026-11-01T00:00:00" not in _visible_text(listing)


def test_a_sample_host_page_shows_no_raw_iso_date(host):
    page = host.get("/privacy-requests?lang=cs").text
    assert not ISO_TEXT.search(_visible_text(page))
