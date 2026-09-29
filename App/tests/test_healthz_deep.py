"""AR-16: ``/healthz`` fails (503) when the database check fails.

An external monitor and the Docker HEALTHCHECK only see a real failure if the
endpoint actually probes the database, not just the data directory.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import db
from app.main import app


def test_healthz_is_degraded_when_the_database_check_fails(monkeypatch):
    db.init_db()

    def boom(*args, **kwargs):
        raise RuntimeError("database is down")

    monkeypatch.setattr(db, "query_one", boom)

    response = TestClient(app).get("/healthz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database_ok"] is False


def test_healthz_is_ok_when_the_database_answers():
    db.init_db()

    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database_ok"] is True
