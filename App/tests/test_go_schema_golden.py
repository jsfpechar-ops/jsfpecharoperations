"""The Go schema fixtures are fresh and agree with Python (brief 1260).

go/internal/schema embeds expected_schema.json and tests its goose parser and
target fingerprint against testdata/*.json. All three come from
scripts/pg_schema_golden.py. A new goose or migrations file makes them stale:
regenerate with `cd App && .venv/bin/python scripts/pg_schema_golden.py`.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app import config, db

APP_DIR = Path(__file__).resolve().parent.parent
REGEN = "cd App && .venv/bin/python scripts/pg_schema_golden.py"


def _golden():
    spec = importlib.util.spec_from_file_location("pg_schema_golden", APP_DIR / "scripts" / "pg_schema_golden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_go_schema_fixtures_are_fresh():
    for path, text in _golden().render().items():
        rel = path.relative_to(APP_DIR.parent)
        assert path.exists(), f"{rel} is missing; regenerate with: {REGEN}"
        assert path.read_text(encoding="utf-8") == text, f"{rel} is stale; regenerate with: {REGEN}"


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakePG:
    """Answers postgres_schema_status's catalog queries from a snapshot."""

    def __init__(self, snapshot):
        self.snapshot = snapshot

    def execute_native(self, sql, params=None):
        if "current_schema() AS name" in sql:
            return _Rows([{"name": "public"}])
        if "information_schema.columns" in sql:
            return _Rows([
                {"table_name": table, "column_name": col["name"], "data_type": col["type"],
                 "is_nullable": "NO" if col["not_null"] else "YES"}
                for table in sorted(self.snapshot["tables"])
                for col in self.snapshot["tables"][table]
            ])
        if "pg_indexes" in sql:
            return _Rows([{"name": name} for name in self.snapshot["indexes"]])
        if "pg_trigger" in sql:
            return _Rows([{"name": name} for name in self.snapshot["triggers"]])
        if "information_schema.tables" in sql:
            return _Rows([{"exists": 1}])
        if "to_regclass" in sql:
            return _Rows([{"name": None}])
        raise AssertionError(f"unexpected query: {sql}")

    def execute(self, sql, params=None):
        assert "MAX(version)" in sql, sql
        return _Rows([{"v": self.snapshot["expected_version"]}])


def _status(monkeypatch, snapshot):
    monkeypatch.setattr(config, "DB_BACKEND", "postgresql")
    return db.postgres_schema_status(_FakePG(snapshot))


def test_snapshot_satisfies_python_schema_status(monkeypatch):
    snapshot = _golden().expected_schema()
    status = _status(monkeypatch, snapshot)
    assert status["current"], status
    assert status["expected_tables"] == len(snapshot["tables"])
    assert status["extra_tables"] == 0
    assert status["missing_indexes"] == 0
    assert status["missing_triggers"] == status["extra_triggers"] == 0
    assert "" not in {col["type"] for cols in snapshot["tables"].values() for col in cols}


def test_snapshot_is_exact_not_loose(monkeypatch):
    snapshot = _golden().expected_schema()
    status = _status(monkeypatch, dict(snapshot, indexes=snapshot["indexes"][1:]))
    assert not status["current"] and status["missing_indexes"] == 1
    status = _status(monkeypatch, dict(snapshot, triggers=snapshot["triggers"][1:]))
    assert not status["current"] and status["missing_triggers"] == 1
    tables = dict(snapshot["tables"])
    tables["user_account"] = tables["user_account"][:-1]
    assert not _status(monkeypatch, dict(snapshot, tables=tables))["current"]


def test_embedded_snapshot_matches_files_on_disk():
    on_disk = json.loads((APP_DIR.parent / "go" / "internal" / "schema" / "expected_schema.json").read_text())
    assert on_disk["expected_version"] == db.expected_schema_version()
    assert "schema_migrations" in on_disk["tables"]


def test_snapshot_has_the_python_owned_functions_and_triggers():
    from app import db_postgres

    snapshot = _golden().expected_schema()
    sources = "".join([db_postgres.PG_SQLITE_DATE_FUNCTION, *db_postgres.PG_TRIGGERS])
    assert len(snapshot["functions"]) == 1 + len(db_postgres.PG_TRIGGERS)
    assert set(snapshot["trigger_defs"]) == set(db_postgres.PG_TRIGGER_NAMES) == set(snapshot["triggers"])
    for name, _table, _event, function in db_postgres.PG_TRIGGER_DDL:
        assert function in snapshot["functions"], name
        assert snapshot["trigger_defs"][name].endswith(f"EXECUTE FUNCTION {function}()")
    for name, body in snapshot["functions"].items():
        assert "$$" + body + "$$" in sources, name
