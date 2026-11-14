"""Go `ubyhost-web migrate` against Python pg_schema.py on a real PostgreSQL (brief 1260).

Runs when UBYHOST_TEST_DATABASE_URL or a PostgreSQL UBYHOST_DATABASE_URL is
set (CI job test-postgres-full) and a `go` binary is on PATH; skips otherwise,
except that under CI (env CI set) a missing `go` fails, so the job cannot go
green without running it.
Every check uses its own throwaway databases, never the session database.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
GO_DIR = APP_DIR.parent / "go"
GOOSE_DIR = APP_DIR / "migrations_pg"

_BASE_URL = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL") or ""
_GO = shutil.which("go")

pytestmark = pytest.mark.skipif(
    not _BASE_URL.startswith(("postgres://", "postgresql://")),
    reason="needs UBYHOST_TEST_DATABASE_URL or a PostgreSQL UBYHOST_DATABASE_URL",
)

APPLIED_SQL = (
    "SELECT DISTINCT ON (version_id) version_id, is_applied FROM goose_db_version "
    "ORDER BY version_id, id DESC"
)


def _url_for(database: str, base: str = "") -> str:
    parts = urlsplit(base or _BASE_URL)
    return urlunsplit((parts.scheme, parts.netloc, "/" + database, parts.query, ""))


def _admin():
    import psycopg

    return psycopg.connect(_BASE_URL, autocommit=True)


@pytest.fixture(scope="module")
def go_binary(tmp_path_factory):
    if not _GO:
        if os.environ.get("CI"):
            pytest.fail("go is not on PATH in CI; the Go schema parity test must run here")
        pytest.skip("go is not on PATH")
    out = tmp_path_factory.mktemp("gobin") / "ubyhost-web"
    env = dict(os.environ)
    # go.mod asks for go 1.25 (toolchain line); an older runner Go downloads it.
    env.setdefault("GOTOOLCHAIN", "auto")
    result = subprocess.run(
        [_GO, "build", "-o", str(out), "./cmd/ubyhost-web"],
        cwd=GO_DIR, env=env, capture_output=True, text=True, timeout=900, check=False,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    return out


@pytest.fixture
def throwaway():
    """Create empty databases on demand; drop them all afterwards."""
    made = []

    def make(suffix: str) -> str:
        name = f"ubyhost_go_migrate_{os.getpid()}_{suffix}"
        with _admin() as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
            conn.execute(f'CREATE DATABASE "{name}"')
        made.append(name)
        return name

    yield make
    with _admin() as conn:
        for name in made:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _env(url: str, data_dir: Path) -> dict:
    env = {
        key: value for key, value in os.environ.items()
        if key not in {"UBYHOST_DB", "UBYHOST_DATABASE_URL", "UBYHOST_TEST_DATABASE_URL", "UBYHOST_DATA_DIR"}
    }
    env.update(UBYHOST_DATABASE_URL=url, UBYHOST_DATA_DIR=str(data_dir), UBYHOST_MIGRATIONS_DIR=str(GOOSE_DIR))
    return env


def _python(action: str, database: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/pg_schema.py", action, "--expect-database", database],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300, check=False,
    )


def _go(binary: Path, action: str, database: str, env: dict, *, option_first: bool = False) -> subprocess.CompletedProcess:
    args = ["--expect-database", database, action] if option_first else [action, "--expect-database", database]
    return subprocess.run(
        [str(binary), "migrate", *args],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300, check=False,
    )


def _applied(url: str) -> set:
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        rows = conn.execute(APPLIED_SQL).fetchall()
    return {int(v) for v, ok in rows if ok and v != 0}


def _down_script(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "-- +goose Down"
    assert marker in text, f"{path.name} has no Down section"
    return text.split(marker, 1)[1]


def test_go_apply_matches_python(go_binary, throwaway, tmp_path):
    import psycopg

    database = throwaway("main")
    url = _url_for(database)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    env = _env(url, data_dir)

    result = _python("apply", database, env)
    assert result.returncode == 0, result.stderr[-2000:]
    sealed = _python("seal-authority", database, env)
    assert sealed.returncode == 0, sealed.stderr[-2000:]
    python_applied = _applied(url)
    files = sorted(GOOSE_DIR.glob("*.sql"))
    last_two = files[-2:]
    versions = [int(p.name[:5]) for p in last_two]
    assert python_applied == {int(p.name[:5]) for p in files}

    with psycopg.connect(url, autocommit=True) as conn:
        for path in reversed(last_two):
            conn.execute(_down_script(path))
        conn.execute("DELETE FROM goose_db_version WHERE version_id = ANY(%s)", (versions,))
    assert _applied(url) == python_applied - set(versions)
    assert _python("check", database, env).returncode == 1

    plan = _go(go_binary, "plan", database, env)
    assert plan.returncode == 0, plan.stderr
    assert f"goose pending=[{versions[0]}, {versions[1]}]; no changes made." in plan.stdout
    assert _applied(url) == python_applied - set(versions)

    applied = _go(go_binary, "apply", database, env)
    assert applied.returncode == 0, applied.stderr
    assert applied.stdout.startswith(f"PostgreSQL schema apply OK: database={database}, version=")
    assert applied.stdout.rstrip().endswith(f"goose={versions[1]}.")
    assert _applied(url) == python_applied

    python_check = _python("check", database, env)
    assert python_check.returncode == 0, python_check.stderr
    go_check = _go(go_binary, "check", database, env, option_first=True)
    assert go_check.returncode == 0, go_check.stderr
    # Same OK line apart from the action word.
    assert go_check.stdout == python_check.stdout

    again = _go(go_binary, "apply", database, env)
    assert again.returncode == 0, again.stderr
    assert _applied(url) == python_applied

    wrong = _go(go_binary, "check", "not_" + database, env)
    assert wrong.returncode == 1
    assert "Connected database does not match --expect-database." in wrong.stderr

    parts = urlsplit(url)
    host = parts.hostname or ""
    swap = {"localhost": "127.0.0.1", "127.0.0.1": "localhost"}.get(host)
    if swap:
        other_url = url.replace(f"@{host}", f"@{swap}", 1) if "@" in parts.netloc else url.replace(host, swap, 1)
        fenced = _go(go_binary, "check", database, _env(other_url, data_dir))
        assert fenced.returncode == 1
        assert "does not match the durable database authority marker" in fenced.stderr

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("ALTER TABLE user_account DROP COLUMN guest_details_mail")
    assert _python("check", database, env).returncode == 1
    broken = _go(go_binary, "check", database, env)
    assert broken.returncode == 1
    assert "PostgreSQL schema is not current" in broken.stderr


def test_go_apply_refuses_without_legacy_schema(go_binary, throwaway, tmp_path):
    database = throwaway("empty")
    url = _url_for(database)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    result = _go(go_binary, "apply", database, _env(url, data_dir))
    assert result.returncode == 1
    assert "legacy schema not set up; run App/scripts/pg_schema.py apply once" in result.stderr
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchone()[0]
    assert tables == 0


def _fresh(go_binary, throwaway, tmp_path, suffix):
    database = throwaway(suffix)
    url = _url_for(database)
    data_dir = tmp_path / f"data-{suffix}"
    data_dir.mkdir()
    env = _env(url, data_dir)
    result = _python("apply", database, env)
    assert result.returncode == 0, result.stderr[-2000:]
    return database, url, env


def test_go_check_fails_closed_on_python_owned_ddl(go_binary, throwaway, tmp_path):
    """Go applies goose files only; a changed function body needs one Python apply."""
    import psycopg

    database, url, env = _fresh(go_binary, throwaway, tmp_path, "ddl")
    assert _go(go_binary, "check", database, env).returncode == 0
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            "CREATE OR REPLACE FUNCTION ubyhost_invoice_note_guard() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$"
        )
    # Python's check compares trigger names only, so it does not see this.
    assert _python("check", database, env).returncode == 0
    for action in ("check", "apply"):
        stale = _go(go_binary, action, database, env)
        assert stale.returncode == 1, stale.stdout
        assert "Python-owned DDL" in stale.stderr and "pg_schema.py apply" in stale.stderr
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP TRIGGER invoice_item_insert_guard ON invoice_item")
        conn.execute(
            "CREATE TRIGGER invoice_item_insert_guard BEFORE UPDATE ON invoice_item "
            "FOR EACH ROW EXECUTE FUNCTION ubyhost_invoice_item_insert_guard()"
        )
    assert _go(go_binary, "check", database, env).returncode == 1
    restored = _python("apply", database, env)
    assert restored.returncode == 0, restored.stderr[-2000:]
    check = _go(go_binary, "check", database, env)
    assert check.returncode == 0, check.stderr


def test_go_apply_rolls_back_a_failing_goose_file(go_binary, throwaway, tmp_path):
    import psycopg

    database, url, env = _fresh(go_binary, throwaway, tmp_path, "rollback")
    migrations = tmp_path / "migrations_pg"
    shutil.copytree(GOOSE_DIR, migrations)
    last = max(int(p.name[:5]) for p in migrations.glob("*.sql"))
    (migrations / f"{last + 1:05d}_rollback_probe_ok.sql").write_text(
        "-- +goose Up\nCREATE TABLE go_rollback_probe (id BIGINT);\n"
        "INSERT INTO go_rollback_probe (id) VALUES (1);\n-- +goose Down\nDROP TABLE go_rollback_probe;\n",
        encoding="utf-8",
    )
    (migrations / f"{last + 2:05d}_rollback_probe_bad.sql").write_text(
        "-- +goose Up\nALTER TABLE user_account ADD COLUMN go_rollback_probe BIGINT;\n"
        "SELECT this_is_not_sql FROM;\n",
        encoding="utf-8",
    )
    with psycopg.connect(url, autocommit=True) as conn:
        before_rows = conn.execute("SELECT id, version_id, is_applied FROM goose_db_version ORDER BY id").fetchall()
    probe_env = dict(env, UBYHOST_MIGRATIONS_DIR=str(migrations))
    plan = _go(go_binary, "plan", database, probe_env)
    assert f"goose pending=[{last + 1}, {last + 2}]" in plan.stdout, plan.stdout + plan.stderr
    result = _go(go_binary, "apply", database, probe_env)
    assert result.returncode == 1, result.stdout
    assert f"goose {last + 2:05d}" in result.stderr
    with psycopg.connect(url, autocommit=True) as conn:
        after_rows = conn.execute("SELECT id, version_id, is_applied FROM goose_db_version ORDER BY id").fetchall()
        probe_table = conn.execute("SELECT to_regclass('public.go_rollback_probe')").fetchone()[0]
        probe_column = conn.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'user_account' AND column_name = 'go_rollback_probe'"
        ).fetchone()[0]
    assert after_rows == before_rows
    assert probe_table is None and probe_column == 0
    check = _go(go_binary, "check", database, env)
    assert check.returncode == 0, check.stderr


# Brief 1263: production has only ever run the goose twins after the SQLite
# migration (Python apply), where they are no-ops; Go runs the twin alone. The
# Go and Python checks compare names, types, NOT NULL, index names, triggers and
# functions only, so a twin with a wrong DEFAULT, a missing CHECK/FK/UNIQUE or a
# different index would pass both. This test compares those too. It cannot see
# a missing data backfill: the throwaway databases have no rows.
FINGERPRINT_SQL = {
    "column": (
        "SELECT table_name, column_name, coalesce(column_default, ''), is_identity, "
        "coalesce(identity_generation, '') FROM information_schema.columns "
        "WHERE table_schema = 'public'"
    ),
    "constraint": (
        "SELECT conrelid::regclass::text, conname, contype::text, pg_get_constraintdef(oid) "
        "FROM pg_constraint WHERE connamespace = 'public'::regnamespace"
    ),
    "index": "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'",
}
# Goose 00017 (brief 1471) made the 6 foreign keys of goose 4, 11 and 13
# DEFERRABLE INITIALLY IMMEDIATE, so no known drift is left. Keep this set
# empty: a new twin writes DEFERRABLE INITIALLY IMMEDIATE on every REFERENCES.
KNOWN_NOT_DEFERRABLE: set = set()


def _fingerprint(url: str) -> dict:
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        return {kind: sorted(tuple(row) for row in conn.execute(sql).fetchall()) for kind, sql in FINGERPRINT_SQL.items()}


def _fingerprint_diff(want: dict, got: dict) -> list:
    want = dict(want, constraint=[
        (table, name, kind, definition.removesuffix(" DEFERRABLE"))
        if (table, name) in KNOWN_NOT_DEFERRABLE else (table, name, kind, definition)
        for table, name, kind, definition in want["constraint"]
    ])
    lines = []
    for kind in FINGERPRINT_SQL:
        lines += [f"{kind} only in Python-built: {row}" for row in sorted(set(want[kind]) - set(got[kind]))]
        lines += [f"{kind} only in Go-applied: {row}" for row in sorted(set(got[kind]) - set(want[kind]))]
    return lines


def test_go_applied_goose_twins_match_python_defaults_and_constraints(go_binary, throwaway, tmp_path):
    """Every goose file after the baseline, run by Go alone, gives Python's schema."""
    import psycopg

    _python_db, python_url, _python_env = _fresh(go_binary, throwaway, tmp_path, "fp_python")
    database, url, env = _fresh(go_binary, throwaway, tmp_path, "fp_go")
    files = [p for p in sorted(GOOSE_DIR.glob("*.sql")) if int(p.name[:5]) > 1]
    versions = [int(p.name[:5]) for p in files]
    with psycopg.connect(url, autocommit=True) as conn:
        for path in reversed(files):
            conn.execute(_down_script(path))
        conn.execute("DELETE FROM goose_db_version WHERE version_id = ANY(%s)", (versions,))
    assert _applied(url) == {1}
    applied = _go(go_binary, "apply", database, env)
    assert applied.returncode == 0, applied.stderr
    assert _applied(url) == {1, *versions}

    want = _fingerprint(python_url)
    assert all(want.values()), want
    diff = _fingerprint_diff(want, _fingerprint(url))
    assert not diff, "a goose twin differs from its SQLite migration:\n" + "\n".join(diff[:40])

    # The comparison sees what both checks miss: a changed default and a lost constraint.
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("ALTER TABLE user_account ALTER COLUMN guest_details_mail SET DEFAULT 0")
        check_name = conn.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'stay_fee_rate'::regclass AND contype = 'c'"
        ).fetchone()[0]
        conn.execute(f'ALTER TABLE stay_fee_rate DROP CONSTRAINT "{check_name}"')
    assert _go(go_binary, "check", database, env).returncode == 0
    assert _python("check", database, env).returncode == 0
    drift = _fingerprint_diff(want, _fingerprint(url))
    assert any("guest_details_mail" in line for line in drift), drift
    assert any(check_name in line for line in drift), drift
