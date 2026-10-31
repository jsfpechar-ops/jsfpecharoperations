from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo

import pytest

from app import auth, billing, config, db

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_billing_analytics.py"
_spec = importlib.util.spec_from_file_location("billing_analytics_export", SCRIPT)
export = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(export)


@pytest.fixture
def source_db(tmp_path, monkeypatch):
    db.close_connections()
    database = tmp_path / "source.sqlite"
    monkeypatch.setattr(config, "DB_PATH", database)
    db.init_db()
    stamp = uuid.uuid4().hex[:8]
    account_ids = {}
    specs = {
        "active": ("active", "month", 10, 3),
        "overdue": ("overdue", "year", 0, 0),
        "canceling": ("canceling", "month", 0, -5),
        "trialing": ("trialing", "month", 100, 0),
        "paused": ("paused", "month", 0, 0),
    }
    for label, (status, interval, discount, carry) in specs.items():
        username = f"u{label}{stamp}"
        owner_id = auth.create_account(
            f"{username}@example.test", f"PRIVATE NAME {label}", username=username
        )
        billing.ensure_account(owner_id)
        db.execute(
            "UPDATE billing_account SET status = ?, plan = 'standard', billing_interval = ?, "
            "apartments_billed = 1, discount_percent = ?, carry_czk = ?, buyer_name = ? "
            "WHERE owner_user_id = ?",
            (status, interval, discount, carry, f"PRIVATE BUYER {label}", owner_id),
        )
        account_ids[label] = owner_id

    def add_invoice(number, *, kind="invoice", issue="2026-10-05", paid=None,
                    amount=10000, voided=0, corrects_id=None):
        db.execute(
            "INSERT INTO platform_invoice (owner_user_id, kind, corrects_id, seq_year, seq_no, "
            "number, vs, issue_date, due_date, period_from, period_to, total_haler, voided, "
            "paid_on, paid_via, snapshot_json, created_at) "
            "VALUES (?, ?, ?, 2026, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '{}', ?)",
            (account_ids["active"], kind, corrects_id, len(number), number, f"VS-{number}",
             issue, "2026-11-10", issue, "2026-10-31", amount, voided, paid,
             datetime.now().isoformat()),
        )
        row = db.query_one("SELECT id FROM platform_invoice WHERE number = ?", (number,))
        return int(row["id"])

    first_id = add_invoice("SECRET-INVOICE-ONE", paid="2026-10-07", amount=10001)
    add_invoice("SECRET-STORNO", kind="storno", paid=None, amount=-250, corrects_id=first_id)
    add_invoice("SECRET-VOID", paid="2026-10-09", amount=777, voided=1)
    add_invoice("SECRET-PAID-LATER", issue="2026-10-10", paid="2026-11-01", amount=333)
    add_invoice("SECRET-PAID-EARLIER", issue="2026-10-11", paid="2026-09-30", amount=111)
    add_invoice("SECRET-ISSUED-EARLIER", issue="2026-09-30", paid="2026-10-04", amount=499)
    yield {"database": database, "ids": account_ids}
    db.close_connections()


def _export(source_db, tmp_path, monkeypatch=None):
    output = tmp_path / "billing.json"
    args = ["--from-month", "2026-10", "--through-month", "2026-10", "--output", str(output)]
    if monkeypatch:
        assert export.main(args) == 0
    else:
        payload = export.extract("2026-10", "2026-10")
        export.publish(payload, output, config.DB_PATH)
    return output


def test_export_uses_legacy_quote_semantics_and_exact_bounded_invoice_totals(source_db, tmp_path):
    output = _export(source_db, tmp_path)
    data = json.loads(output.read_text(encoding="utf-8"))
    portfolio = {row["status"]: row for row in data["portfolio_quote"]}
    assert portfolio["active"] == {
        "status": "active", "plan_account_count": 1,
        "legacy_quote_monthly_czk": 137, "legacy_quote_annual_czk": 1644,
    }
    assert portfolio["overdue"]["legacy_quote_monthly_czk"] == 99
    assert portfolio["overdue"]["legacy_quote_annual_czk"] == 1190
    assert portfolio["canceling"]["legacy_quote_monthly_czk"] == 144
    assert portfolio["trialing"]["plan_account_count"] == 1
    assert portfolio["trialing"]["legacy_quote_monthly_czk"] == 0
    assert portfolio["paused"]["legacy_quote_monthly_czk"] == 0

    totals = {(row["month"], row["basis"]): row for row in data["invoice_month_totals"]}
    assert totals[("2026-10", "issue_date")] == {
        "month": "2026-10", "basis": "issue_date", "currency": "CZK",
        "nonvoid_invoice_count": 4, "total_haler": 10195,
    }
    assert totals[("2026-10", "paid_on")] == {
        "month": "2026-10", "basis": "paid_on", "currency": "CZK",
        "nonvoid_invoice_count": 2, "total_haler": 10500,
    }
    assert "marked paid by paid_on" in data["definitions"]["paid_on"]
    assert "cash collections" in data["definitions"]["paid_on"]
    assert "CZK" in data["definitions"]["invoice_amount_currency"]
    snapshot = datetime.fromisoformat(data["source_snapshot_at_utc"])
    assert snapshot.astimezone(ZoneInfo("Europe/Prague")).date().isoformat() == data["as_of_date_prague"]
    assert datetime.fromisoformat(data["generated_at_utc"]) >= snapshot


def test_export_excludes_identifiers_and_sensitive_fields(source_db, tmp_path):
    output = _export(source_db, tmp_path)
    data = json.loads(output.read_text(encoding="utf-8"))
    serialized = output.read_text(encoding="utf-8")
    for forbidden in ("PRIVATE NAME", "PRIVATE BUYER", "SECRET-INVOICE", "owner_user_id",
                      "invoice_id", "discount_reason", "bank_tx_id"):
        assert forbidden not in serialized
    assert set(data) == {
        "schema_version", "source_snapshot_at_utc", "as_of_date_prague", "generated_at_utc",
        "range", "definitions", "portfolio_quote", "invoice_month_totals",
    }


def test_repeated_extract_keeps_business_sections_stable(source_db, tmp_path):
    first = _export(source_db, tmp_path)
    first_data = json.loads(first.read_text(encoding="utf-8"))
    second = _export(source_db, tmp_path)
    second_data = json.loads(second.read_text(encoding="utf-8"))
    assert second_data["portfolio_quote"] == first_data["portfolio_quote"]
    assert second_data["invoice_month_totals"] == first_data["invoice_month_totals"]
    assert second_data["range"] == first_data["range"]


def test_invalid_ranges_fail_before_database_access(source_db, tmp_path, monkeypatch):
    monkeypatch.setattr(export.db, "readonly_cursor", lambda: pytest.fail("DB opened"))
    output = tmp_path / "never-created" / "billing.json"
    assert export.main(["--from-month", "2026-13", "--through-month", "2026-10",
                        "--output", str(output)]) == 1
    assert not output.parent.exists()
    assert export.main(["--from-month", "2026-11", "--through-month", "2026-10",
                        "--output", str(output)]) == 1
    assert not output.parent.exists()


@pytest.mark.parametrize("alias_kind", ["db", "wal", "shm", "journal", "symlink", "hardlink"])
def test_output_aliases_are_rejected_before_extract(source_db, tmp_path, monkeypatch, alias_kind):
    database = source_db["database"]
    if alias_kind == "db":
        output = database
    elif alias_kind in {"wal", "shm", "journal"}:
        output = Path(f"{database}-{alias_kind}")
    elif alias_kind == "symlink":
        output = tmp_path / "db-symlink"
        output.symlink_to(database)
    else:
        output = tmp_path / "db-hardlink"
        os.link(database, output)
    called = []

    def forbidden_extract(*args):
        called.append(True)
        raise RuntimeError("extract called before alias refusal")

    monkeypatch.setattr(export, "extract", forbidden_extract)
    assert export.main(["--from-month", "2026-10", "--through-month", "2026-10",
                        "--output", str(output)]) == 1
    assert called == []


def test_pre_replace_failure_keeps_old_output_and_cleans_temp(source_db, tmp_path, monkeypatch):
    output = tmp_path / "billing.json"
    output.write_text('{"old":true}\n', encoding="utf-8")
    before = output.read_bytes()
    monkeypatch.setattr(export.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(OSError, match="replace failed"):
        export.publish({"new": True}, output, config.DB_PATH)
    assert output.read_bytes() == before
    assert list(tmp_path.glob(".billing.json.*.tmp")) == []


def test_directory_fsync_failure_reports_complete_new_output_published(source_db, tmp_path, monkeypatch):
    output = tmp_path / "billing.json"
    output.write_text('{"old":true}\n', encoding="utf-8")
    monkeypatch.setattr(export, "_fsync_directory", lambda path: (_ for _ in ()).throw(OSError("fsync failed")))
    with pytest.raises(export.PublishedButNotDurableError, match="new complete export is published"):
        export.publish({"new": True}, output, config.DB_PATH)
    assert json.loads(output.read_text(encoding="utf-8")) == {"new": True}
    assert list(tmp_path.glob(".billing.json.*.tmp")) == []
