"""2000 / 1171: _apartment_files_with_ubyhost must stay aligned with FILES_WITH_UBYHOST_SQL."""

from __future__ import annotations

import pytest

from app import db, reporting


def test_unknown_apartment_counts_as_filing():
    assert reporting._apartment_files_with_ubyhost(None) is True
    # Falsy apartment rows are treated like unknown (keep legacy behaviour).
    assert reporting._apartment_files_with_ubyhost({}) is True


@pytest.mark.parametrize("field", ("uby_idub", "uby_ws_user", "uby_ws_password_enc"))
@pytest.mark.parametrize("blank", (None, "", "   "))
def test_one_blank_ubyport_field_means_no_filing(field, blank):
    full = {
        "uby_idub": "123456789012",
        "uby_ws_user": "uby-ws1a2b3c",
        "uby_ws_password_enc": "enc",
    }
    row = {**full, field: blank}
    assert reporting._apartment_files_with_ubyhost(row) is False


def test_whitespace_only_fields_are_treated_as_blank():
    assert (
        reporting._apartment_files_with_ubyhost(
            {
                "uby_idub": "  123456789012  ",
                "uby_ws_user": "  uby-ws1a2b3c  ",
                "uby_ws_password_enc": "  enc  ",
            }
        )
        is True
    )


def test_all_three_fields_trimmed_means_filing():
    row = {
        "uby_idub": " 123456789012 ",
        "uby_ws_user": " uby-ws1a2b3c ",
        "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
    }
    assert reporting._apartment_files_with_ubyhost(row) is True


def test_helper_matches_sql_on_saved_apartment(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "files-with-ubyhost.sqlite3")
    db.init_db()
    apt_id = db.insert(
        "apartment",
        {
            "internal_name": "Coverage flat",
            "permalink_token": "covtoken",
            "active": 1,
            "created_at": db.utcnow(),
            "uby_idub": "  ",
            "uby_ws_user": "ws-user",
            "uby_ws_password_enc": db.encrypt_secret("secret"),
        },
    )
    apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,))
    sql = (
        "SELECT CASE WHEN "
        + reporting.FILES_WITH_UBYHOST_SQL.replace("a.", "")
        + " THEN 1 ELSE 0 END AS flag FROM apartment WHERE id = ?"
    )
    sql_flag = bool(db.query_one(sql, (apt_id,))["flag"])
    assert reporting._apartment_files_with_ubyhost(apt) is sql_flag