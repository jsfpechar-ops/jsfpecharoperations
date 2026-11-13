"""Brief 1473: deploy/lightsail/scripts/pg-schema-dump.sh stays read-only.

No Docker and no database: a fake ``docker`` on PATH records every call and
prints a canned dump, so these tests check what the owner relies on before
the script is run on the server.
"""

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SH = ROOT / "deploy/lightsail/scripts/pg-schema-dump.sh"

FAKE_DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_LOG"
case " $* " in
  *" ps "*) echo fakeid ;;
  *" pg_dump "*) cat "$FAKE_DUMP" ;;
  *" psql "*) echo "guest 3" ;;
esac
"""

SCHEMA = (
    "SET statement_timeout = 0;\n"
    "CREATE TABLE public.guest (\n    id bigint NOT NULL\n);\n"
)


def _run(tmp_path, *args, dump=SCHEMA):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
    (tmp_path / "dump.sql").write_text(dump)
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_LOG"] = str(tmp_path / "docker.log")
    env["FAKE_DUMP"] = str(tmp_path / "dump.sql")
    return subprocess.run(
        ["bash", str(SH), *args], capture_output=True, text=True, env=env,
        cwd=tmp_path, check=False,
    )


def _calls(tmp_path):
    log = tmp_path / "docker.log"
    return log.read_text() if log.exists() else ""


def test_script_is_strict_executable_and_parses():
    assert "set -euo pipefail" in SH.read_text(encoding="utf-8")
    assert SH.stat().st_mode & stat.S_IXUSR
    result = subprocess.run(["bash", "-n", str(SH)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_script_never_names_a_writing_command():
    code = "\n".join(
        line for line in SH.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    for word in ("UPDATE ", "DELETE ", "DROP ", "ALTER ", "TRUNCATE", "GRANT ",
                 "pg_restore", "createdb", "dropdb", "read_only=off", "--clean"):
        assert word not in code, word


def test_refuses_an_existing_output_and_reads_nothing(tmp_path):
    out = tmp_path / "schema.sql"
    out.write_text("keep me")
    result = _run(tmp_path, str(out))
    assert result.returncode == 2
    assert "already exists" in result.stderr
    assert out.read_text() == "keep me"
    assert _calls(tmp_path) == ""


def test_refuses_no_argument_and_an_option(tmp_path):
    assert _run(tmp_path).returncode == 2
    assert _run(tmp_path, "--schema").returncode == 2
    assert _calls(tmp_path) == ""


def test_writes_a_private_schema_only_dump_in_a_read_only_session(tmp_path):
    result = _run(tmp_path, "schema.sql")
    assert result.returncode == 0, result.stderr
    out = tmp_path / "schema.sql"
    assert out.read_text() == SCHEMA
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    assert not (tmp_path / "schema.sql.partial").exists()
    assert "1 tables" in result.stdout
    dump_call = [line for line in _calls(tmp_path).splitlines() if "pg_dump" in line]
    assert len(dump_call) == 1
    assert "-e PGOPTIONS=-c default_transaction_read_only=on postgres pg_dump" in dump_call[0]
    for flag in ("--schema-only", "--no-owner", "--no-privileges", "-U ubyhost", "-d ubyhost"):
        assert flag in dump_call[0], flag


def test_a_dump_with_data_lines_is_deleted(tmp_path):
    for line in ("COPY public.guest (id) FROM stdin;\n",
                 "INSERT INTO public.guest VALUES (1);\n",
                 "SELECT pg_catalog.setval('public.guest_id_seq', 5, true);\n"):
        result = _run(tmp_path, "schema.sql", dump=SCHEMA + line)
        assert result.returncode == 1, line
        assert "data lines" in result.stderr
        assert not (tmp_path / "schema.sql").exists()
        assert not (tmp_path / "schema.sql.partial").exists()


def test_counts_are_read_only_and_only_for_two_databases(tmp_path):
    result = _run(tmp_path, "--counts")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "guest 3\n"
    call = next(line for line in _calls(tmp_path).splitlines() if "psql" in line)
    assert "-e PGOPTIONS=-c default_transaction_read_only=on postgres psql -U ubyhost -d ubyhost" in call
    assert "-c SELECT table_name" in call
    assert _run(tmp_path, "--counts", "ubyhost_restoretest").returncode == 0
    bad = _run(tmp_path, "--counts", "postgres")
    assert bad.returncode == 2
    assert "postgres psql -U ubyhost -d postgres" not in _calls(tmp_path)
