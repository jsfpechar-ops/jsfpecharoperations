"""Tests for the PostgreSQL backup and restore scripts (brief 0464).

Docker and age are not available in CI, so stub `docker` and `age` binaries on
PATH record every call and stand in for the real ones. No test touches a server.
"""

import os
import re
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
    root, bindir, log = make_tree(
        tmp_path, "UBYHOST_BACKUP_AGE_RECIPIENT=age1testrecipient\n" + PG_ENV)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": str(running)})
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    if running:
        assert "pg_dump -U ubyhost -Fc ubyhost" in recorded
        assert "cat > /data/backups/20260101T000000Z/ubyhost-pg.dump.age" in recorded
        assert "ubyhost-pg.dump.age.tmp && mv" in recorded
    else:
        assert "pg_dump" not in recorded


def test_backup_skips_dump_before_cutover(tmp_path):
    # postgres runs, but the app is still on SQLite: no dump may be taken
    root, bindir, log = make_tree(tmp_path, "UBYHOST_BACKUP_AGE_RECIPIENT=age1testrecipient\n")
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 0, result.stderr
    assert "pg_dump" not in calls(log)


def test_backup_refuses_plaintext_dump_in_production(tmp_path):
    root, bindir, log = make_tree(tmp_path, "UBYHOST_DEPLOYMENT=production\n" + PG_ENV)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 1
    assert "pg_dump" not in calls(log)


PROD_ENV = "UBYHOST_DEPLOYMENT=production\nUBYHOST_BACKUP_AGE_RECIPIENT=age1testrecipient\n" \
    "UBYHOST_BACKUP_PING_URL=https://ping.invalid/x\n"


def add_curl_stub(bindir):
    """A curl stub on PATH that records the ping instead of sending it."""
    curl = bindir / "curl"
    curl.write_text('#!/usr/bin/env bash\necho "curl $*" >> "$STUB_LOG"\n')
    curl.chmod(0o755)


def test_backup_fails_in_production_without_database_url_but_keeps_snapshot(tmp_path):
    root, bindir, log = make_tree(tmp_path, PROD_ENV)
    add_curl_stub(bindir)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 1
    assert "UBYHOST_DATABASE_URL is unset" in result.stderr
    recorded = calls(log)
    assert "backup_data.sh" in recorded
    assert "pg_dump" not in recorded
    assert "curl" not in recorded


def test_backup_fails_in_production_when_postgres_not_running_before_any_snapshot(tmp_path):
    root, bindir, log = make_tree(tmp_path, PROD_ENV + PG_ENV)
    add_curl_stub(bindir)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "0"})
    assert result.returncode == 1
    assert "postgres container is not running" in result.stderr
    recorded = calls(log)
    assert "backup_data.sh" not in recorded
    assert "pg_dump" not in recorded
    assert "curl" not in recorded


def test_backup_production_with_running_postgres_dumps_and_pings(tmp_path):
    root, bindir, log = make_tree(tmp_path, PROD_ENV + PG_ENV)
    add_curl_stub(bindir)
    result = run_script("backup.sh", root, bindir, log, extra_env={"PG_RUNNING": "1"})
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    assert "pg_dump -U ubyhost -Fc ubyhost" in recorded
    assert "curl -fsS -m 10 --retry 3 https://ping.invalid/x" in recorded


COMPOSE = ROOT / "deploy/lightsail/docker-compose.yml"
WALG_DIR = ROOT / "deploy/lightsail/walg"
PINNED_PG = "postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab"


def compose_services():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(COMPOSE.read_text())["services"]


def archive_command():
    command = compose_services()["postgres"]["command"]
    return next(p for p in command if p.startswith("archive_command=")).split("=", 1)[1]


def test_walg_dockerfile_pins_debian_postgres_and_verifies_checksum():
    text = (WALG_DIR / "Dockerfile").read_text()
    assert re.search(r"^FROM postgres:16\.\d+-bookworm@sha256:[0-9a-f]{64}$", text, re.M)
    assert "sha256sum -c" in text
    assert re.search(r"^ARG WALG_SHA256=[0-9a-f]{64}$", text, re.M), "never PENDING"
    assert re.search(r"^ARG WALG_VERSION=v\d+\.\d+\.\d+$", text, re.M)
    assert re.search(r"^ARG WALG_ASSET=wal-g-pg-ubuntu-(20|22)\.04-amd64\.tar\.gz$", text, re.M)


def test_postgres_keeps_its_image_and_no_network_and_archives_to_the_spool():
    pg = compose_services()["postgres"]
    assert pg["image"] == PINNED_PG
    assert pg["network_mode"] == "none"
    assert "archive_mode=${UBYHOST_PG_ARCHIVE:-off}" in pg["command"]
    assert "archive_timeout=300" in pg["command"]
    assert "wal-g" not in " ".join(pg["command"])  # the database container never talks to S3
    assert "ubyhost-walspool:/walspool" in pg["volumes"]


def test_archive_command_copies_durably_and_never_overwrites(tmp_path):
    spool = tmp_path / "walspool"
    spool.mkdir()
    wal = tmp_path / "000000010000000000000007"
    wal.write_bytes(b"x" * 4096)
    cmd = archive_command().replace("/walspool", str(spool)).replace("%p", str(wal)).replace("%f", wal.name)

    def run():
        return subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=30)

    first = run()
    assert first.returncode == 0, first.stderr
    assert (spool / wal.name).read_bytes() == wal.read_bytes()
    assert not (spool / f"{wal.name}.tmp").exists()
    assert run().returncode == 0  # Postgres may retry the same file after a crash
    (spool / wal.name).write_bytes(b"different")
    assert run().returncode != 0  # a different file with the same name is an error
    assert (spool / wal.name).read_bytes() == b"different"


def test_walg_sidecar_is_profiled_unprivileged_and_has_no_secrets():
    walg = compose_services()["walg"]
    assert walg["profiles"] == ["walg"]
    assert walg["user"] == "70:70"
    assert walg["env_file"] == [{"path": ".env.walg", "required": False}]
    assert "ubyhost-pgdata:/var/lib/postgresql/data:ro" in walg["volumes"]
    assert "ubyhost-pgsock:/var/run/postgresql" in walg["volumes"]
    for key in ("ports", "expose", "network_mode", "networks", "environment"):
        assert key not in walg
    text = COMPOSE.read_text() + (WALG_DIR / "Dockerfile").read_text()
    for forbidden in ("AWS_SECRET", "AKIA", "LIBSODIUM_KEY=", "s3://"):
        assert forbidden not in text


def test_walg_ship_script_syntax():
    result = subprocess.run(["sh", "-n", str(WALG_DIR / "walg-ship.sh")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def run_ship(tmp_path, push_ok, prefix="s3://test-bucket/postgres-wal"):
    spool = tmp_path / "spool"
    spool.mkdir()
    (spool / "000000010000000000000002").write_text("w2")
    (spool / "000000010000000000000001").write_text("w1")
    (spool / "000000010000000000000003.tmp").write_text("half")
    (spool / "walg_status").mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "wal-g"
    stub.write_text('#!/bin/sh\necho "$*" >> "$STUB_LOG"\n[ "$PUSH_OK" = 1 ]\n')
    stub.chmod(0o755)
    log = tmp_path / "stub.log"
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log),
           "PUSH_OK": "1" if push_ok else "0", "WALG_SPOOL": str(spool), "WALG_SHIP_ONCE": "1",
           "WALG_S3_PREFIX": prefix}
    result = subprocess.run(["sh", str(WALG_DIR / "walg-ship.sh")], env=env,
                            capture_output=True, text=True, timeout=30)
    pushed = log.read_text().splitlines() if log.exists() else []
    return result, spool, pushed


@pytest.mark.parametrize("push_ok", [True, False])
def test_walg_ship_deletes_only_after_a_good_push(tmp_path, push_ok):
    result, spool, pushed = run_ship(tmp_path, push_ok)
    assert (spool / "000000010000000000000003.tmp").exists()  # never shipped
    assert (spool / "walg_status").is_dir()  # not a WAL name: ignored
    if push_ok:
        assert result.returncode == 0, result.stderr
        assert [p.rsplit("/", 1)[-1] for p in pushed] == ["000000010000000000000001", "000000010000000000000002"]
        assert sorted(p.name for p in spool.iterdir()) == ["000000010000000000000003.tmp", "walg_status"]
    else:
        assert result.returncode == 1
        assert len(pushed) == 1  # stops at the first failure, oldest first
        assert (spool / "000000010000000000000001").exists() and (spool / "000000010000000000000002").exists()


def test_walg_ship_refuses_without_a_destination(tmp_path):
    result, spool, pushed = run_ship(tmp_path, True, prefix="")
    assert result.returncode == 1
    assert pushed == []
    assert (spool / "000000010000000000000001").exists()
