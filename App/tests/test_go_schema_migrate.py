"""Go `ubyhost-web migrate` against Python pg_schema.py on a real PostgreSQL (brief 1260).

Runs when UBYHOST_TEST_DATABASE_URL or a PostgreSQL UBYHOST_DATABASE_URL is
set (CI job test-postgres-full) and a `go` binary is on PATH; skips otherwise.
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
    not _BASE_URL.startswith(("postgres://", "postgresql://")) or not _GO,
    reason="needs UBYHOST_TEST_DATABASE_URL or a PostgreSQL UBYHOST_DATABASE_URL, and go on PATH",
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
    out = tmp_path_factory.mktemp("gobin") / "ubyhost-web"
    result = subprocess.run(
        [_GO, "build", "-o", str(out), "./cmd/ubyhost-web"],
        cwd=GO_DIR, capture_output=True, text=True, timeout=900, check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
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


def _go(binary: Path, action: str, database: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(binary), "migrate", action, "--expect-database", database],
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
    go_check = _go(go_binary, "check", database, env)
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
