"""Static checks for the 1206 restricted app role (K-S11).

No Docker and no database: these tests read the SQL, the wrapper and the
compose file, and check the properties the owner relies on before the
server is touched. CI runs the SQL itself (ci.yml, "App works as the
non-superuser role").
"""

import os
import re
import stat
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "deploy/lightsail/scripts"
SQL = SCRIPTS / "pg-app-role.sql"
SH = SCRIPTS / "pg-app-role.sh"
COMPOSE = ROOT / "deploy/lightsail/docker-compose.yml"


def _without_comments(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith(("#", "--"))
    )


def test_script_syntax():
    result = subprocess.run(
        ["bash", "-n", str(SH)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_script_is_strict_and_executable():
    text = SH.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert SH.stat().st_mode & stat.S_IXUSR


def test_role_is_not_privileged():
    sql = SQL.read_text(encoding="utf-8")
    flags = "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN"
    assert sql.count(flags) >= 2
    assert re.search(r"(?<!NO)SUPERUSER", sql) is None


def test_sql_is_safe_to_rerun():
    sql = SQL.read_text(encoding="utf-8")
    for forbidden in ("DROP ", "REASSIGN OWNED", "PASSWORD", "GRANT ALL",
                      "ALTER SYSTEM", "CREATE DATABASE"):
        assert forbidden not in sql, forbidden
    assert "IF NOT EXISTS (SELECT 1 FROM pg_roles" in sql
    assert "ON_ERROR_STOP" in sql


def test_sql_moves_ownership():
    sql = SQL.read_text(encoding="utf-8")
    assert "ALTER SCHEMA public OWNER TO ubyhost_app" in sql
    assert sql.count("OWNER TO ubyhost_app") >= 4
    assert "deptype IN ('a','i')" in sql


def test_sql_proves_copy_program_refused():
    sql = SQL.read_text(encoding="utf-8")
    assert "COPY (SELECT 1) TO PROGRAM" in sql
    assert "insufficient_privilege" in sql


def test_wrapper_runs_admin_as_superuser():
    text = SH.read_text(encoding="utf-8")
    assert "-U ubyhost " in text
    assert "ubyhost_app@" not in text
    assert "-U ubyhost_app" not in text


def _env_dict(service: dict) -> dict:
    env = service.get("environment", {})
    if isinstance(env, dict):
        return env
    result = {}
    for item in env:
        key, _, value = str(item).partition("=")
        result[key] = value
    return result


def test_compose_does_not_hardcode_the_app_role():
    compose_text = COMPOSE.read_text(encoding="utf-8")
    assert "ubyhost_app" not in compose_text
    compose = yaml.safe_load(compose_text)
    services = compose["services"]
    assert _env_dict(services["postgres"]).get("POSTGRES_USER") == "ubyhost"
    assert _env_dict(services["ubyhost-go"])["UBYHOST_DATABASE_URL"] == "${UBYHOST_DATABASE_URL:-}"


def test_no_secret_in_new_files():
    for path in (SQL, SH):
        body = _without_comments(path.read_text(encoding="utf-8"))
        assert re.search(r"password|secret|token", body, re.IGNORECASE) is None, path.name
