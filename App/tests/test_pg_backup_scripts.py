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
  *"compose stop"*) [ "${STOP_FAILS:-0}" = 1 ] && exit 1 ;;
  *"ps -q --status running postgres"*) [ "${PG_RUNNING:-0}" = 1 ] && echo pgid ;;
  *"ps -aq ubyhost"*) echo ubyhostid ;;
  *"config --services"*) echo ubyhost; echo worker; [ "${GO_PROFILE:-0}" = 1 ] && echo ubyhost-go ;;
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
    for name in ("backup.sh", "pg-restore.sh", "filing-guard.sh"):
        shutil.copy(SCRIPTS / name, root / "scripts" / name)
    (root / ".env").write_text(env_text)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in (("docker", DOCKER_STUB), ("age", AGE_STUB)):
        stub = bindir / name
        stub.write_text(body)
        stub.chmod(0o755)
    return root, bindir, tmp_path / "stub.log"


def run_script(script, root, bindir, log, args=(), extra_env=None, input_text=None):
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log)}
    env.update(extra_env or {})
    stdin = {"stdin": subprocess.DEVNULL} if input_text is None else {"input": input_text}
    return subprocess.run(
        ["bash", str(root / "scripts" / script), *args],
        cwd=root, env=env, capture_output=True, text=True, timeout=60, **stdin,
    )


def calls(log):
    return log.read_text() if log.exists() else ""


@pytest.mark.parametrize("name", ["backup.sh", "pg-restore.sh", "pg-cutover.sh", "filing-guard.sh", "preflight.sh"])
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
    assert not (root / ".restored-box").exists()


def test_pg_restore_rejects_bad_stamp(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    result = run_script("pg-restore.sh", root, bindir, log, args=["../etc"],
                        extra_env={"AGE_IDENTITY_FILE": "/nonexistent"})
    assert result.returncode == 1
    assert "stop" not in calls(log)


FILING_OFF = "UBYHOST_ENABLE_SCHEDULER=0\nUBYHOST_GO_JOB_KINDS=ical,push\nUBYHOST_JOB_QUEUE_KINDS=ical,push\n"


def make_dump_file(tmp_path, name="ubyhost-pg.dump.age", text="ciphertext"):
    dump = tmp_path / name
    dump.write_text(text)
    return dump


def test_pg_restore_file_form_streams_host_file_without_docker_cp(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + FILING_OFF)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    assert "cp " not in recorded
    assert "stop worker ubyhost\n" in recorded
    assert "ubyhost-go" not in recorded
    assert "pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction" in recorded
    assert "compose up -d\n" in recorded
    assert "from ubyhost-pg.dump.age" in (root / ".restored-box").read_text()


def test_pg_restore_file_form_also_stops_the_go_service(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + FILING_OFF)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes", "GO_PROFILE": "1"})
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    assert "stop worker ubyhost-go ubyhost" in recorded
    assert recorded.index("stop worker ubyhost-go ubyhost") < recorded.index("pg_restore")
    assert "compose up -d\n" in recorded


def test_pg_restore_file_form_rerun_with_marker_present(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + FILING_OFF)
    (root / ".restored-box").write_text("restored 2026-11-01T00:00:00Z from old.dump.age\n")
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 0, result.stderr
    assert "from ubyhost-pg.dump.age" in (root / ".restored-box").read_text()
    assert "pg_restore" in calls(log)


def test_pg_restore_file_form_refuses_while_filing_is_on(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + "UBYHOST_GO_JOB_KINDS=ical,submit\n")
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 3, result.stderr
    assert "RESTORED BOX" in result.stderr
    assert not (root / ".restored-box").exists()
    assert "stop" not in calls(log)


def test_pg_restore_file_form_refuses_submit_in_the_shell_environment(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + "UBYHOST_ENABLE_SCHEDULER=0\n")
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes",
                                   "UBYHOST_GO_JOB_KINDS": "ical,submit"})
    assert result.returncode == 3, result.stderr
    assert "in the shell environment" in result.stderr
    assert not (root / ".restored-box").exists()
    assert "stop" not in calls(log)


def test_pg_restore_file_form_declined_confirm_leaves_no_marker(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + FILING_OFF)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity)}, input_text="no\n")
    assert result.returncode == 1, result.stderr
    assert "aborted" in result.stderr
    assert not (root / ".restored-box").exists()
    assert "stop" not in calls(log)


def test_pg_restore_file_form_with_override_writes_the_marker(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + "UBYHOST_GO_JOB_KINDS=ical,submit\n")
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes",
                                   "UBYHOST_FILING_GUARD_OVERRIDE": "1"})
    assert result.returncode == 0, result.stderr
    assert "WARNING: UBYHOST_FILING_GUARD_OVERRIDE=1" in result.stderr
    assert "from ubyhost-pg.dump.age" in (root / ".restored-box").read_text()
    assert "pg_restore" in calls(log)


def test_pg_restore_restarts_the_app_when_stop_fails(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    result = run_script("pg-restore.sh", root, bindir, log, args=["20260101T000000Z"],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes",
                                   "STOP_FAILS": "1"})
    assert result.returncode != 0
    recorded = calls(log)
    assert "pg_restore" not in recorded
    assert "compose up -d ubyhost worker" in recorded
    assert recorded.index("compose stop worker ubyhost") < recorded.index("compose up -d ubyhost worker")


def test_pg_restore_file_form_missing_file_exits_1_before_stopping(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    result = run_script("pg-restore.sh", root, bindir, log,
                        args=["--file", str(tmp_path / "missing.age")],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 1
    assert "stop" not in calls(log)


def test_pg_restore_file_form_refuses_a_name_that_is_not_age(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path, name="ubyhost-pg.dump")
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 1
    assert "stop" not in calls(log)


@pytest.mark.parametrize("args", [[], ["20260101T000000Z", "--file", "x.age"], ["--file"]])
def test_pg_restore_needs_exactly_one_source(tmp_path, args):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    result = run_script("pg-restore.sh", root, bindir, log, args=args,
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 1
    assert "usage:" in result.stderr
    assert "stop" not in calls(log)


# Brief 1169: the filing guard on a restored box (marker .restored-box).
PREFLIGHT_ENV = (
    "UBYHOST_DOMAIN=ubyhost.example\n"
    "ACME_EMAIL=ops@ubyhost.example\n"
    "UBYHOST_PUBLIC_BASE_URL=https://ubyhost.example\n"
    "UBYHOST_DEPLOYMENT=production\n"
    "UBYHOST_UBYPORT_ENV=prod\n"
    "UBYHOST_BACKUP_AGE_RECIPIENT=age1test\n"
    "UBYHOST_BACKUP_PING_URL=https://ping.example/backup\n"
)
SUBMIT_ON = "UBYHOST_GO_JOB_KINDS=ical,submit\nUBYHOST_JOB_QUEUE_KINDS=ical,submit\n"


def make_guard_tree(tmp_path, env_text, marker):
    """A throwaway deploy/lightsail tree with preflight, the guard and site_urls.py."""
    root = tmp_path / "deploy" / "lightsail"
    (root / "scripts").mkdir(parents=True)
    for name in ("preflight.sh", "filing-guard.sh"):
        shutil.copy(SCRIPTS / name, root / "scripts" / name)
    (tmp_path / "App" / "app").mkdir(parents=True)
    shutil.copy(ROOT / "App/app/site_urls.py", tmp_path / "App" / "app" / "site_urls.py")
    (root / ".env").write_text(env_text)
    if marker:
        (root / ".restored-box").write_text("restored 2026-11-12T00:00:00Z from ubyhost-pg.dump.age\n")
    return root


def run_guard(root, script="filing-guard.sh", extra_env=None, args=()):
    env = {"PATH": os.environ["PATH"], "UBYHOST_ALLOW_SMALL_HOST": "1"}
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(root / "scripts" / script), *args],
        cwd=root, env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
    )


def test_filing_guard_without_marker_is_silent_even_with_submit(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON, marker=False)
    result = run_guard(root)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize("env_text", [
    "",
    "UBYHOST_ENABLE_SCHEDULER=1\n",
    "UBYHOST_ENABLE_SCHEDULER=0\nUBYHOST_GO_JOB_KINDS=\"ical, submit\"\n",
    "UBYHOST_ENABLE_SCHEDULER=0\nUBYHOST_JOB_QUEUE_KINDS=submit\n",
    "UBYHOST_ENABLE_SCHEDULER=0\nexport UBYHOST_ENABLE_SCHEDULER=1\n",
    "UBYHOST_ENABLE_SCHEDULER=0\nexport UBYHOST_GO_JOB_KINDS=submit\n",
])
def test_filing_guard_blocks_restored_box_while_filing_can_run(tmp_path, env_text):
    root = make_guard_tree(tmp_path, env_text, marker=True)
    result = run_guard(root)
    assert result.returncode == 3, result.stderr
    assert "RESTORED BOX" in result.stderr
    assert "ERROR: automatic filing stays blocked" in result.stderr


@pytest.mark.parametrize("scheduler", ["0", "false", "no"])
def test_filing_guard_allows_restored_box_with_filing_off(tmp_path, scheduler):
    env_text = FILING_OFF.replace("UBYHOST_ENABLE_SCHEDULER=0", f"UBYHOST_ENABLE_SCHEDULER={scheduler}")
    root = make_guard_tree(tmp_path, env_text, marker=True)
    result = run_guard(root)
    assert result.returncode == 0, result.stderr
    assert "NOTE: restored box" in result.stderr
    assert "scheduled filing is off; apartments in immediate mode still file" in result.stderr
    assert "RESTORED BOX" not in result.stderr


def test_filing_guard_blocks_submit_in_the_shell_environment(tmp_path):
    root = make_guard_tree(tmp_path, FILING_OFF, marker=True)
    for name in ("UBYHOST_GO_JOB_KINDS", "UBYHOST_JOB_QUEUE_KINDS"):
        result = run_guard(root, extra_env={name: "ical,submit"})
        assert result.returncode == 3, result.stderr
        assert f"submit is in {name} in the shell environment" in result.stderr


def test_filing_guard_marker_without_env_file_exits_3(tmp_path):
    root = make_guard_tree(tmp_path, FILING_OFF, marker=True)
    (root / ".env").unlink()
    result = run_guard(root)
    assert result.returncode == 3, result.stderr
    assert "no .env" in result.stderr


def test_filing_guard_env_file_that_fails_to_source_is_not_ok(tmp_path):
    root = make_guard_tree(tmp_path, FILING_OFF + "BROKEN=\"unterminated\n", marker=True)
    result = run_guard(root)
    assert result.returncode != 0, result.stderr
    assert "NOTE: restored box" not in result.stderr


@pytest.mark.parametrize("line", [
    "MARKER=nothing-here", "OVERRIDE=1", "ASSUME_RESTORED=0", "CALLER_GO_JOB_KINDS=ical",
])
def test_filing_guard_env_file_cannot_overwrite_marker_or_override(tmp_path, line):
    # Filing is off: only the refused first line can make the guard exit 3.
    root = make_guard_tree(tmp_path, line + "\n" + FILING_OFF, marker=True)
    result = run_guard(root)
    assert result.returncode == 3, result.stderr
    assert "a line in" in result.stderr
    assert "NOTE: restored box" not in result.stderr
    assert "WARNING" not in result.stderr


def test_filing_guard_env_file_with_a_failing_middle_line_exits_3(tmp_path):
    env_text = "UBYHOST_ENABLE_SCHEDULER=0\nUBYHOST_GO_JOB_KINDS = ical,submit\nUBYHOST_JOB_QUEUE_KINDS=ical,push\n"
    root = make_guard_tree(tmp_path, env_text, marker=True)
    result = run_guard(root)
    assert result.returncode == 3, result.stderr
    assert "a line in" in result.stderr
    assert "NOTE: restored box" not in result.stderr
    assert "ical,submit" not in result.stderr


def test_filing_guard_assume_restored_checks_without_marker(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON, marker=False)
    result = run_guard(root, args=["--assume-restored"])
    assert result.returncode == 3, result.stderr
    assert "RESTORED BOX" in result.stderr
    root_off = make_guard_tree(tmp_path / "off", FILING_OFF, marker=False)
    result = run_guard(root_off, args=["--assume-restored"])
    assert result.returncode == 0, result.stderr
    assert "NOTE: restored box" in result.stderr
    assert not (root_off / ".restored-box").exists()


def test_filing_guard_reads_env_file_not_the_caller(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON, marker=True)
    result = run_guard(root, extra_env={"UBYHOST_ENABLE_SCHEDULER": "0", "UBYHOST_GO_JOB_KINDS": "ical"})
    assert result.returncode == 3, result.stderr


def test_filing_guard_override_for_one_run_warns_and_passes(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON, marker=True)
    result = run_guard(root, extra_env={"UBYHOST_FILING_GUARD_OVERRIDE": "1"})
    assert result.returncode == 0, result.stderr
    assert "RESTORED BOX" in result.stderr
    assert "WARNING: UBYHOST_FILING_GUARD_OVERRIDE=1" in result.stderr


def test_filing_guard_refuses_override_kept_in_env_file(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON + "UBYHOST_FILING_GUARD_OVERRIDE=1\n", marker=True)
    result = run_guard(root, extra_env={"UBYHOST_FILING_GUARD_OVERRIDE": "1"})
    assert result.returncode == 3, result.stderr
    assert "must not be in .env" in result.stderr


def test_preflight_passes_on_a_normal_box_with_submit(tmp_path):
    root = make_guard_tree(tmp_path, PREFLIGHT_ENV + SUBMIT_ON, marker=False)
    result = run_guard(root, script="preflight.sh")
    assert result.returncode == 0, result.stderr
    assert "Preflight OK" in result.stdout
    assert "RESTORED BOX" not in result.stderr


def test_preflight_fails_on_a_restored_box_with_submit(tmp_path):
    root = make_guard_tree(tmp_path, PREFLIGHT_ENV + SUBMIT_ON, marker=True)
    result = run_guard(root, script="preflight.sh")
    assert result.returncode == 1
    assert "ERROR: filing guard: restored box with automatic filing on" in result.stderr
    assert "Preflight failed." in result.stderr


def test_preflight_passes_on_a_restored_box_with_filing_off(tmp_path):
    root = make_guard_tree(tmp_path, PREFLIGHT_ENV + FILING_OFF, marker=True)
    result = run_guard(root, script="preflight.sh")
    assert result.returncode == 0, result.stderr
    assert "Preflight OK" in result.stdout
    assert "NOTE: restored box" in result.stderr


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
    assert re.search(r"^ARG WALG_ASSET=wal-g-pg-(20|22)\.04-amd64\.tar\.gz$", text, re.M)


def test_walg_dockerfile_has_a_passwd_entry_for_uid_70():
    # compose runs the walg service as 70:70; wal-g fails with "unknown userid 70" without it
    text = (WALG_DIR / "Dockerfile").read_text()
    assert re.search(r"^RUN groupadd -g 70 \w+ && useradd -u 70 -g 70 ", text, re.M)
    assert compose_services()["walg"]["user"] == "70:70"


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


CHECK_DOCKER_STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
case "$*" in
  *"ps -q --status running walg"*) [ "${WALG_RUNNING:-1}" = 1 ] && echo walgid ;;
  *pg_stat_archiver*) echo "${ARCH_ROW:-60|0}" ;;
  *"stat -c %Y"*) [ -n "${SPOOL_MTIME:-}" ] && echo "$SPOOL_MTIME" ;;
  *"du -sm /walspool"*) echo "${SPOOL_MB:-1}" ;;
  *"du -sm /var/lib/postgresql/data/pg_wal"*) echo "${PGWAL_MB:-100}" ;;
  *"backup-push"*) [ "${BACKUP_FAIL:-0}" = 1 ] && exit 1 ;;
esac
exit 0
"""


def make_check_tree(tmp_path):
    root = tmp_path / "deploy" / "lightsail"
    (root / "scripts").mkdir(parents=True)
    for name in ("walg-check.sh", "walg-backup.sh"):
        shutil.copy(SCRIPTS / name, root / "scripts" / name)
    (root / ".env").write_text("")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "docker").write_text(CHECK_DOCKER_STUB)
    (bindir / "docker").chmod(0o755)
    curl = bindir / "curl"
    curl.write_text('#!/usr/bin/env bash\necho "curl $*" >> "$STUB_LOG"\n')
    curl.chmod(0o755)
    return root, bindir, tmp_path / "stub.log"


def run_walg(script, tmp_path, extra=None):
    root, bindir, log = make_check_tree(tmp_path)
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log),
           "WALG_CHECK_STATE": str(tmp_path / "state"),
           "UBYHOST_WALG_PING_URL": "https://ping.invalid/check",
           "UBYHOST_WALG_BACKUP_PING_URL": "https://ping.invalid/base"}
    env.update(extra or {})
    result = subprocess.run(["bash", str(root / "scripts" / script)], cwd=root, env=env,
                            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    return result, calls(log)


@pytest.mark.parametrize("script", ["walg-check.sh", "walg-backup.sh"])
def test_walg_scripts_pass_bash_syntax(script):
    result = subprocess.run(["bash", "-n", str(SCRIPTS / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("extra,expected_fail", [
    ({}, False),
    ({"ARCH_ROW": "4000|0"}, True),      # last archive older than 30 minutes
    ({"ARCH_ROW": "-1|0"}, True),        # never archived (UBYHOST_PG_ARCHIVE not on)
    ({"PGWAL_MB": "6000"}, True),        # pg_wal over 5 GB
    ({"SPOOL_MB": "3000"}, True),        # spool over 2 GB
    ({"SPOOL_MTIME": "1000"}, True),     # spool file from 1970: upload stuck
    ({"WALG_RUNNING": "0"}, True),       # sidecar down
])
def test_walg_check_exit_codes(tmp_path, extra, expected_fail):
    result, recorded = run_walg("walg-check.sh", tmp_path, extra)
    assert (result.returncode != 0) == expected_fail, result.stderr
    assert ("ping.invalid/check" in recorded) == (not expected_fail)  # dead-man ping only when healthy
    assert "wal-g" not in recorded  # the monitor never calls WAL-G or S3


def test_walg_check_flags_rising_failed_count(tmp_path):
    (tmp_path / "state").write_text("2")
    result, _ = run_walg("walg-check.sh", tmp_path, {"ARCH_ROW": "60|5"})
    assert result.returncode == 1
    assert "failed_count rose" in result.stderr


def test_walg_backup_pushes_then_retains_seven_then_pings(tmp_path):
    result, recorded = run_walg("walg-backup.sh", tmp_path)
    assert result.returncode == 0, result.stderr
    push = recorded.index("exec -T walg wal-g backup-push /var/lib/postgresql/data")
    delete = recorded.index("exec -T walg wal-g delete retain FULL 7 --confirm")
    assert push < delete < recorded.index("ping.invalid/base")


def test_walg_backup_failure_deletes_nothing_and_does_not_ping(tmp_path):
    result, recorded = run_walg("walg-backup.sh", tmp_path, {"BACKUP_FAIL": "1"})
    assert result.returncode != 0
    assert "delete retain" not in recorded
    assert "ping.invalid" not in recorded
