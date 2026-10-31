"""Tests for the PostgreSQL backup and restore scripts (brief 0464).

Docker and age are not available in CI, so stub `docker` and `age` binaries on
PATH record every call and stand in for the real ones. No test touches a server.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "deploy/lightsail/scripts"

DOCKER_STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
case "$*" in
  *"ps -q --status running postgres"*) [ "${PG_RUNNING:-0}" = 1 ] && echo pgid ;;
  *"ps -aq ubyhost"*) echo ubyhostid ;;
  *"pg_dump"*) echo DUMP ;;
  *"pg_restore"*) cat >/dev/null ;;
  *"cat >"*) cat >/dev/null ;;
  *"ls -1 /data/backups"*) echo 20260101T000000Z ;;
  *"wc -c"*) echo 5 ;;
esac
exit 0
"""

AGE_STUB = r"""#!/usr/bin/env bash
for last; do :; done
if [ -f "$last" ]; then cat "$last"; else cat; fi
"""

PG_ENV = "UBYHOST_DATABASE_URL=postgresql://ubyhost@/ubyhost?host=/var/run/postgresql\n"


def make_tree(tmp_path, env_text):
    """Copy the scripts into a throwaway tree with its own .env and stub binaries."""
    root = tmp_path / "deploy" / "lightsail"
    (root / "scripts").mkdir(parents=True)
    for name in ("backup.sh", "pg-restore.sh"):
        shutil.copy(SCRIPTS / name, root / "scripts" / name)
    (root / ".env").write_text(env_text)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in (("docker", DOCKER_STUB), ("age", AGE_STUB)):
        stub = bindir / name
        stub.write_text(body)
        stub.chmod(0o755)
    return root, bindir, tmp_path / "stub.log"


def run_script(script, root, bindir, log, args=(), extra_env=None):
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log)}
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(root / "scripts" / script), *args],
        cwd=root, env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
    )


def calls(log):
    return log.read_text() if log.exists() else ""


@pytest.mark.parametrize("name", ["backup.sh", "pg-restore.sh", "pg-cutover.sh"])
def test_scripts_pass_bash_syntax(name):
    result = subprocess.run(["bash", "-n", str(SCRIPTS / name)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_pg_restore_refuses_while_app_is_on_sqlite(tmp_path):
    root, bindir, log = make_tree(tmp_path, "UBYHOST_DB=/data/ubyhost.db\n")
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    result = run_script("pg-restore.sh", root, bindir, log,
                        args=["20260101T000000Z"], extra_env={"AGE_IDENTITY_FILE": str(identity)})
    assert result.returncode == 2, result.stderr
    assert "stop" not in calls(log)


def test_pg_restore_streams_dump_into_pg_restore(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    result = run_script("pg-restore.sh", root, bindir, log, args=["20260101T000000Z"],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    assert "stop worker ubyhost" in recorded
    assert "pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction" in recorded
    assert "up -d ubyhost worker" in recorded


def test_pg_restore_rejects_bad_stamp(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    result = run_script("pg-restore.sh", root, bindir, log, args=["../etc"],
                        extra_env={"AGE_IDENTITY_FILE": "/nonexistent"})
    assert result.returncode == 1
    assert "stop" not in calls(log)


@pytest.mark.parametrize("running", [1, 0])
def test_backup_dumps_postgres_only_when_running(tmp_path, running):
    root, bindir, log = make_tree(tmp_path, "UBYHOST_BACKUP_AGE_RECIPIENT=age1testrecipient\n")
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": str(running)})
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    if running:
        assert "pg_dump -U ubyhost -Fc ubyhost" in recorded
        assert "cat > /data/backups/20260101T000000Z/ubyhost-pg.dump.age" in recorded
    else:
        assert "pg_dump" not in recorded


def test_backup_refuses_plaintext_dump_in_production(tmp_path):
    root, bindir, log = make_tree(tmp_path, "UBYHOST_DEPLOYMENT=production\n")
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 1
    assert "pg_dump" not in calls(log)
