"""WP14 part B: host pages read guests in batches, and render the same as before.

The demo seed is loaded into a temporary database. Query counts are taken from
SQLite's own statement trace, so they include every helper and template call.
"""
from __future__ import annotations

import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, config, db, demo, reporting, stay_fee
from app.main import app
from tests.conftest import login_as

_CSRF = re.compile(r'((?:name="csrf-token" content|name="_csrf" value)=")[^"]*')


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    patcher = pytest.MonkeyPatch()
    db.close_connections()
    patcher.setattr(config, "DB_PATH", tmp_path_factory.mktemp("wp14") / "budget.sqlite3")
    patcher.setattr(config, "UBYPORT_ENV", "mock")

    def _no_network(*_args, **_kwargs):
        raise AssertionError("the demo seed must not fetch the sample calendar")

    patcher.setattr(demo.icalsync, "fetch_feed", _no_network)
    db.init_db()
    owner = auth.create_account("budget-host@example.test", "Budget", username="budget-host")
    assert demo.seed(owner)
    # Stay fees on, and one guest without a signature, so the stay-fee pages
    # have periods, lines and the "unsigned" issue to render.
    db.execute("UPDATE apartment SET stay_fee_rate_czk = 50 WHERE owner_user_id = ?", (owner,))
    unsigned = db.query_one(
        "SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "ORDER BY r.date_from DESC, g.id LIMIT 1"
    )
    db.update("guest", unsigned["id"], {"signature_png": None})
    client = TestClient(app)
    response = login_as(client, "budget-host", url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    try:
        yield client
    finally:
        db.close_connections()
        patcher.undo()


def _pages():
    month = date.today().strftime("%Y-%m")
    stays = [row["id"] for row in db.query("SELECT id FROM reservation ORDER BY id")]
    apartments = [row["id"] for row in db.query("SELECT id FROM apartment ORDER BY id")]
    pages = {
        "dashboard": "/",
        "reservations": "/reservations",
        "reservations_all": "/reservations?range=all",
        "stay_fees": "/stay-fees",
        "stay_fees_month": f"/stay-fees?month={month}",
        "invoices": "/invoices",
    }
    pages.update({f"stay_{sid}": f"/reservations/{sid}" for sid in stays})
    pages.update({f"fee_{aid}": f"/stay-fees/{aid}?month={month}" for aid in apartments})
    return pages


def _counted_get(client, path, monkeypatch):
    statements = []
    real_open = db._open

    def traced_open(*args, **kwargs):
        conn = real_open(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    db.close_connections()
    monkeypatch.setattr(db, "_open", traced_open)
    try:
        response = client.get(path, follow_redirects=False)
    finally:
        monkeypatch.setattr(db, "_open", real_open)
        db.close_connections()
    queries = [
        sql for sql in statements
        if sql.split(None, 1)[0].upper() not in ("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK")
    ]
    return response, queries


# WP33 merges overdue unfinished stays into the default Stays list via
# reporting.dashboard_rows, which adds a few reads on /reservations only.
_LIST_QUERY_BUDGET = {"/": 20, "/reservations": 25}


@pytest.mark.parametrize("path", ["/", "/reservations"])
def test_dashboard_and_stays_list_stay_under_twenty_queries(seeded, monkeypatch, path):
    seeded.get(path)  # first view may write one-off state (onboarding, alerts)
    response, queries = _counted_get(seeded, path, monkeypatch)
    assert response.status_code == 200
    assert len(queries) < _LIST_QUERY_BUDGET[path], "\n".join(queries)
    per_stay_guest_reads = [
        sql for sql in queries if re.search(r"FROM guest WHERE reservation_id = \d", sql)
    ]
    # The notification cards and the list share one batched read each.
    assert not per_stay_guest_reads, per_stay_guest_reads


def test_stay_fee_list_reads_each_period_once(seeded, monkeypatch):
    month = date.today().strftime("%Y-%m")
    seeded.get(f"/stay-fees?month={month}")
    response, queries = _counted_get(seeded, f"/stay-fees?month={month}", monkeypatch)
    assert response.status_code == 200
    guest_reads = [sql for sql in queries if "FROM guest g JOIN reservation r" in sql]
    properties = db.query_one("SELECT COUNT(*) AS n FROM apartment WHERE stay_fee_rate_czk > 0")["n"]
    assert len(guest_reads) == properties, guest_reads


def _normalised(text):
    return _CSRF.sub(r"\1", text)


def _render_all(client):
    pages = _pages()
    out = {}
    for name, path in pages.items():
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200, (name, response.status_code)
        out[name] = _normalised(response.text)
    return out


def test_batched_pages_render_exactly_as_the_per_stay_path(seeded, monkeypatch):
    """Every changed page, rendered with the batching and with the old per-stay reads."""
    _render_all(seeded)  # settle one-off writes from first views
    batched = _render_all(seeded)

    def per_stay(_ids):
        # The documented fallback: every stay reads its own guests again.
        raise db.DecryptionError("force the per-stay path")

    real_unsigned = stay_fee.unsigned_stays
    monkeypatch.setattr(reporting, "guests_by_reservation", per_stay)
    monkeypatch.setattr(
        alerts, "_preload_stays", lambda _alerts: {"reservations": {}, "guests": {}}
    )
    monkeypatch.setattr(
        stay_fee, "unsigned_stays",
        lambda apartment_id, first, last, period=None: real_unsigned(apartment_id, first, last),
    )
    monkeypatch.setattr(db, "is_decrypted", lambda _row: False)
    old_path = _render_all(seeded)

    assert batched.keys() == old_path.keys()
    differing = [name for name in batched if batched[name] != old_path[name]]
    assert not differing, differing
    # The pages are not trivially empty.
    assert "Vinohrady Studio (demo)" in batched["dashboard"]
    assert "Vinohrady Studio (demo)" in batched["reservations"]


def test_one_unreadable_stay_still_only_skips_that_stay(seeded, monkeypatch):
    """A guest that will not decrypt must not take the whole dashboard down."""
    target = db.query_one(
        "SELECT g.id, g.reservation_id FROM guest g WHERE g.doc_number_enc IS NOT NULL LIMIT 1"
    )
    original = db.query_one("SELECT doc_number_enc FROM guest WHERE id = ?", (target["id"],))
    db.execute("UPDATE guest SET doc_number_enc = 'not-a-token' WHERE id = ?", (target["id"],))
    try:
        rows = reporting.dashboard_rows(
            owner_user_id=db.query_one(
                "SELECT id FROM user_account WHERE username = 'budget-host'"
            )["id"]
        )
        assert target["reservation_id"] not in {row["reservation"]["id"] for row in rows}
        assert rows
    finally:
        db.execute(
            "UPDATE guest SET doc_number_enc = ? WHERE id = ?",
            (original["doc_number_enc"], target["id"]),
        )


def test_guests_by_reservation_matches_the_per_stay_read(seeded):
    ids = [row["id"] for row in db.query("SELECT id FROM reservation")]
    batched = reporting.guests_by_reservation(ids + [10_000_000])
    assert batched[10_000_000] == []
    for reservation_id in ids:
        single = db.query(
            "SELECT * FROM guest WHERE reservation_id = ? AND archived_at IS NULL "
            "ORDER BY is_lead DESC, id",
            (reservation_id,),
        )
        assert [dict(g) for g in batched[reservation_id]] == [dict(g) for g in single]


def test_guests_by_reservation_chunks_long_id_lists(seeded, monkeypatch):
    monkeypatch.setattr(reporting, "IN_CHUNK", 2)
    ids = [row["id"] for row in db.query("SELECT id FROM reservation")]
    assert len(ids) > 4
    batched = reporting.guests_by_reservation(ids)
    assert sum(len(v) for v in batched.values()) == db.query_one(
        "SELECT COUNT(*) AS n FROM guest WHERE archived_at IS NULL"
    )["n"]
