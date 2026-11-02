"""0525: the stay page on desktop: lead guest as h1, header actions, guest table rows, large door code."""
from __future__ import annotations

import re
from datetime import date, timedelta

from app import claim, db, door_codes, mail
from tests.test_status_colours import host  # noqa: F401


def _h1_text(page: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    assert match, "page has no h1"
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def _section(page: str, start: str, end: str) -> str:
    return page[page.index(start):page.index(end)]


def test_h1_is_the_lead_guest_and_an_empty_stay_shows_the_property_name(host):
    client, apartment_id, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert _h1_text(page) == "MINH NGUYEN"

    today = date.today()
    empty_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "status-stay-empty-0525",
            "date_from": (today + timedelta(days=10)).isoformat(),
            "date_to": (today + timedelta(days=12)).isoformat(),
            "status": "active",
            "expected_guests_override": 1,
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )
    empty = client.get(f"/reservations/{empty_id}?lang=en").text
    assert _h1_text(empty) == "Status 1"


def test_sub_line_links_the_property_and_there_is_no_jump_tab_strip(host):
    client, apartment_id, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert f'href="/apartments/{apartment_id}"' in page
    assert "stay-jump" not in page


def test_door_code_is_in_its_own_section_not_in_the_now_panel(host, monkeypatch):
    client, _, reservation_id = host
    monkeypatch.setattr(
        door_codes,
        "view",
        lambda reservation, apartment: {
            "state": "issued",
            "pin": "4821",
            "works_from": "2026-11-01 15:00",
            "works_until": "2026-11-04 11:00",
        },
    )
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    door = page[page.index('id="door-code"'):]
    door = door[:door.index("</section>")]
    assert 'id="door-code-line"' in door
    now = _section(page, 'police-card', 'id="guests"')
    assert "door-code-line" not in now


def test_guest_row_shows_the_doc_type_label_and_never_the_document_number(host):
    client, _, reservation_id = host
    db.execute(
        "UPDATE guest SET doc_type = ? WHERE reservation_id = ?", ("P", reservation_id)
    )
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    match = re.search(r'class="guest-doc">([^<]*)</td>', page)
    assert match and match.group(1).strip() not in ("", "—")
    # The guest row only: the doc type sits in its own cell and the number is never shown in the row.
    row = page[page.rindex('<tr', 0, match.start()):page.index('</tr>', match.start())]
    assert "P9988771" not in row


def test_header_copy_link_only_for_an_active_stay(host):
    client, _, reservation_id = host
    active = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert active.count("data-stay-header-copy") == 1
    assert active.index("data-stay-header-copy") < active.index('police-card')

    db.execute(
        "UPDATE reservation SET archived_at = ? WHERE id = ?", (db.utcnow(), reservation_id)
    )
    archived = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert "data-stay-header-copy" not in archived


def test_resend_claim_is_once_in_the_page_header_for_a_claimed_stay(host, monkeypatch):
    client, _, reservation_id = host
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    claim.ensure_row(reservation_id)
    db.execute(
        "UPDATE reservation_claim SET state = ? WHERE reservation_id = ?",
        (claim.CLAIMED, reservation_id),
    )
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert page.count("data-resend-claim") == 1
    assert page.index("data-resend-claim") < page.index('id="guests"')
    guests = _section(page, 'id="guests"', 'id="reports"')
    assert "data-resend-claim" not in guests
