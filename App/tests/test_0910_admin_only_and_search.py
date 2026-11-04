"""0910: the technical settings are admin-only, the command palette finds stays by guest name, and the Stays filter starts closed."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app import db
from tests.test_signed_in_chrome import USERNAME, empty_host, host_with_property  # noqa: F401  (fixtures)

APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"


def _set_role(role: str) -> None:
    db.execute("UPDATE user_account SET role = ? WHERE username = ?", (role, USERNAME))


def _owner_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _apartment_id() -> int:
    return db.query_one(
        "SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id LIMIT 1", (_owner_id(),)
    )["id"]


def _seed_stay_with_guest(first_name: str, surname: str) -> int:
    now = db.utcnow()
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": _apartment_id(),
            "source": "manual",
            "uid": f"0910-{surname}-{first_name}",
            "date_from": "2026-12-01",
            "date_to": "2026-12-04",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "is_lead": 1,
            "first_name": first_name,
            "surname": surname,
            "created_at": now,
            "updated_at": now,
        },
    )
    return reservation_id


def test_technical_diagnostics_are_hidden_from_a_customer_and_shown_to_an_admin(host_with_property):
    _set_role("host")
    page = host_with_property.get("/settings/technical?lang=en").text
    assert 'id="settings-overview"' not in page and 'id="settings-codelists"' not in page
    assert 'id="settings-audit"' in page

    _set_role("admin")
    page = host_with_property.get("/settings/technical?lang=en").text
    assert 'id="settings-overview"' in page and 'id="settings-codelists"' in page


def test_settings_data_hides_the_retention_count_string_from_a_customer(host_with_property):
    _set_role("host")
    db.set_setting(
        "retention_last_run",
        json.dumps({"dry_run": True, "owner_user_id": None, "counts": {"0910_probe_rows": 3}, "at": db.utcnow()}),
    )
    try:
        page = host_with_property.get("/settings/data?lang=en").text
        assert "0910_probe_rows=3" not in page
    finally:
        db.set_setting("retention_last_run", "null")


def test_command_palette_returns_a_stay_whose_keywords_hold_the_guest_surname(host_with_property):
    _set_role("host")
    _seed_stay_with_guest("Beatrice", "Nováková")

    items = host_with_property.get("/api/command-palette?lang=en").json()["items"]
    keywords = [item.get("keywords") or "" for item in items]

    assert any("Nováková" in k and "Beatrice" in k for k in keywords)


def test_command_palette_script_folds_accents_and_shows_a_no_results_line():
    source = APP_JS.read_text(encoding="utf-8")

    assert 'normalize("NFD")' in source
    assert "noMatch" in source
    assert 'command-empty' in source


def test_stays_filter_panel_arrives_collapsed_in_the_server_html(host_with_property):
    _set_role("host")
    page = host_with_property.get("/reservations?lang=en").text

    form = re.search(r'<form id="stays-filter-panel"[^>]*>', page)
    assert form is not None
    assert "is-collapsed" in form.group(0)
    assert "app-nojs.css" in host_with_property.get("/reservations?lang=en").text
