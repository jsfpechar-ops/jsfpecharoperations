"""Tests for deploy/lightsail/scripts/pg-cutover.sh and the Compose postgres service (brief 0463).

The script needs Docker, which is not available in CI, so the tests cover the
pure shell functions (env switch and restore), the syntax, and the Compose file.
"""

import os
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy/lightsail/scripts/pg-cutover.sh"
COMPOSE = ROOT / "deploy/lightsail/docker-compose.yml"
PG_URL = "postgresql://ubyhost@/ubyhost?host=/var/run/postgresql"


def run_fn(fn, *args):
    """Source the script without running a command, then call one of its functions."""
    env = {"PG_CUTOVER_LIB": "1", "PATH": os.environ["PATH"]}
    return subprocess.run(
        ["bash", "-c", f'source "$0"; {fn} "$@"', str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_script_parses_and_is_strict():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "set -euo pipefail" in SCRIPT.read_text()


def test_script_guards_app_config_and_report_keys():
    text = SCRIPT.read_text()
    assert "unset UBYHOST_DB" in text
    assert '"status"' not in text


def test_postgres_has_no_network_and_no_password_anywhere():
    services = yaml.safe_load(COMPOSE.read_text())["services"]
    pg = services["postgres"]
    assert pg["network_mode"] == "none"
    assert "ports" not in pg
    assert any("listen_addresses=" in part for part in pg["command"])
    assert "POSTGRES_PASSWORD" not in pg["environment"]
    for path in (ROOT / "deploy/lightsail").rglob("*"):
        if path.is_file():
            assert "UBYHOST_PG_PASSWORD" not in path.read_text(errors="ignore"), path
    assert "UBYHOST_PG_PASSWORD" not in SCRIPT.read_text()


def test_env_switch_removes_sqlite_setting_and_sets_url(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "UBYHOST_DOMAIN=example.test\n"
        "UBYHOST_DB=/data/ubyhost.db\n"
        "ACME_EMAIL=ops@example.test\n"
    )
    result = run_fn("env-switch", str(env_file), PG_URL)
    assert result.returncode == 0, result.stderr
    lines = env_file.read_text().splitlines()
    assert not any(line.startswith("UBYHOST_DB=") for line in lines)
    assert lines.count(f"UBYHOST_DATABASE_URL={PG_URL}") == 1
    assert "UBYHOST_DOMAIN=example.test" in lines
    assert "ACME_EMAIL=ops@example.test" in lines


def test_env_switch_replaces_an_existing_url(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("UBYHOST_DATABASE_URL=postgresql://old\nKEEP=1\n")
    assert run_fn("env-switch", str(env_file), PG_URL).returncode == 0
    lines = env_file.read_text().splitlines()
    assert lines == ["KEEP=1", f"UBYHOST_DATABASE_URL={PG_URL}"]


def test_env_restore_is_byte_identical(tmp_path):
    original = b"UBYHOST_DOMAIN=example.test\nUBYHOST_DB=/data/ubyhost.db\nSECRET=x\n"
    env_file = tmp_path / ".env"
    env_file.write_bytes(original)
    copy = tmp_path / ".env.sqlite-test"
    shutil.copy2(env_file, copy)
    assert run_fn("env-switch", str(env_file), PG_URL).returncode == 0
    assert env_file.read_bytes() != original
    assert run_fn("env-restore", str(env_file), str(copy)).returncode == 0
    assert env_file.read_bytes() == original


def test_compose_postgres_is_private_and_limited():
    data = yaml.safe_load(COMPOSE.read_text())
    services = data["services"]
    pg = services["postgres"]
    assert "ports" not in pg
    assert pg["mem_limit"] == "1g"
    assert pg["image"].startswith("postgres:16-alpine@sha256:")
    for name in ("ubyhost", "worker"):
        assert "ubyhost-pgsock:/var/run/postgresql" in services[name]["volumes"]
    assert {"ubyhost-pgdata", "ubyhost-pgsock"} <= set(data["volumes"])
