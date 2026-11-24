"""Static and mocked-docker checks for 1830 slot helpers (deploy.sh + go-slot.sh)."""
from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "deploy/lightsail/scripts"
SLOT = SCRIPTS / "go-slot.sh"
DEPLOY = SCRIPTS / "deploy.sh"
COMPOSE = ROOT / "deploy/lightsail/docker-compose.yml"


def test_scripts_parse_and_are_strict():
    for path in (SLOT, DEPLOY):
        result = subprocess.run(
            ["bash", "-n", str(path)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr
        text = path.read_text(encoding="utf-8")
        assert "set -euo pipefail" in text
        assert path.stat().st_mode & stat.S_IXUSR


def test_compose_go_services_use_slot_tags():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "image: ubyhost-go:slot-a" in text
    assert "image: ubyhost-go:slot-b" in text
    assert "ubyhost-go-b:" in text


def test_deploy_requires_go_scheduler_and_go_health():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "UBYHOST_SCHEDULER must be go before deploy" in text
    assert "go_exec ubyhost-web backfill-legal-acceptance" in text
    assert "Waiting for the background worker" not in text
    assert 'http://127.0.0.1:8081/healthz' in text


def test_go_exec_targets_whichever_go_slot_is_running():
    """#1221: after a slot swap the live container may be ubyhost-go-b, not ubyhost-go."""
    text = DEPLOY.read_text(encoding="utf-8")
    block = text.split("go_exec() {", 1)[1].split("\n}\n", 1)[0]
    assert 'local svc=""' in block
    assert "ps -q --status running ubyhost-go-b" in block
    assert 'svc=ubyhost-go-b' in block
    assert 'exec -T "${svc}"' in block


def test_deploy_production_go_stack_requires_ubyhost_go_before_mandatory_backup():
    text = DEPLOY.read_text(encoding="utf-8")
    assert (
        "Refusing deploy: ubyhost-go must be running for mandatory pre-deploy backup"
        in text
    )


def test_deploy_internal_health_never_execs_python_without_ubyhost_service():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "compose_has_go_service()" in text
    assert "ERROR: no running app container (expected ubyhost-go on the Go-only stack)." in text
    health = text.split('echo "Health (internal):"', 1)[1].split("echo \"==> Backfilling", 1)[0]
    assert "elif running_python_app;" in health
    assert health.index("elif running_python_app;") < health.index("docker compose exec -T ubyhost")


def test_deploy_rollback_drops_guide_import_column_before_up():
    text = DEPLOY.read_text(encoding="utf-8")
    rollback = text.split("rollback() {", 1)[1].split("\n}\n", 1)[0]
    assert "rollback_drop_guide_import_00024" in rollback
    assert rollback.index("rollback_drop_guide_import_00024") < rollback.index("docker compose up -d")


def test_deploy_seeds_slot_tags_before_schema_apply_and_up():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "go_ensure_slot_images" in text
    assert "go_alias_built_to_local" in text
    assert "go_pin_live_slot_image" in text
    assert "go_rollback_slots" in text
    assert "go_non_slot_services" in text
    apply_at = text.index("Applying PostgreSQL goose migrations (new Go image)")
    stack_at = text.index('echo "==> Starting stack"')
    up_at = text.index("docker compose up -d --remove-orphans", stack_at)
    first_ensure = text.index("go_ensure_slot_images")
    assert first_ensure < apply_at
    assert text[:up_at].count("go_ensure_slot_images") >= 1
    assert text.find("go_pin_live_slot_image", stack_at) < up_at
    assert "$(go_non_slot_services)" in text[stack_at:up_at + 80]
    assert text.index("go_rollback_slots") < stack_at
    assert 'docker compose --profile go stop "$(go_svc "${NEW_SLOT}")" || true' in text
    assert text.index('stop "$(go_svc "${NEW_SLOT}")"') < text.index(
        "Starting ubyhost-go slot ${NEW_SLOT} beside slot ${LIVE_SLOT}"
    )
    # A CI pull must not copy an old slot-a over the new :local tag.
    head = text[:apply_at]
    assert 'if [ "${GO_IMAGE_PULLED}" != "1" ]; then' in head
    assert head.index('if [ "${GO_IMAGE_PULLED}" != "1" ]; then') < head.index(
        "go_alias_built_to_local"
    )


def _fake_docker(tmp_path: Path, present: set[str]) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "docker.log"
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        f'echo "$@" >> "{log}"\n'
        'if [ "${1:-}" = "image" ] && [ "${2:-}" = "inspect" ]; then\n'
        f'  present="{" ".join(sorted(present))}"\n'
        '  case " $present " in\n'
        '    *" $3 "*) exit 0 ;;\n'
        "    *) exit 1 ;;\n"
        "  esac\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    return fake_bin


def _run_slot(tmp_path: Path, fake_bin: Path, fn: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", "-c", f'source "$1"; {fn}', "_", str(SLOT)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        check=False,
    )


def test_ensure_slot_images_aliases_local_and_fills_missing_b(tmp_path):
    fake_bin = _fake_docker(tmp_path, {"ubyhost-go:local", "ubyhost-go:previous"})
    result = _run_slot(tmp_path, fake_bin, "go_ensure_slot_images")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8").splitlines()
    assert "tag ubyhost-go:local ubyhost-go:slot-a" in log
    assert "tag ubyhost-go:previous ubyhost-go:slot-b" in log


def test_ensure_slot_images_overwrites_slot_a_from_local(tmp_path):
    fake_bin = _fake_docker(
        tmp_path, {"ubyhost-go:local", "ubyhost-go:slot-a", "ubyhost-go:slot-b"}
    )
    result = _run_slot(tmp_path, fake_bin, "go_ensure_slot_images")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8").splitlines()
    assert "tag ubyhost-go:local ubyhost-go:slot-a" in log
    assert not any(line.endswith("ubyhost-go:slot-b") for line in log if line.startswith("tag "))


def test_ensure_slot_images_does_not_retag_existing_slot_b(tmp_path):
    fake_bin = _fake_docker(
        tmp_path, {"ubyhost-go:local", "ubyhost-go:previous", "ubyhost-go:slot-b"}
    )
    result = _run_slot(tmp_path, fake_bin, "go_ensure_slot_images")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert "tag ubyhost-go:local ubyhost-go:slot-a" in log
    assert "slot-b" not in "".join(
        line for line in log.splitlines() if line.startswith("tag ")
    )


def test_ensure_slot_images_noop_without_local(tmp_path):
    fake_bin = _fake_docker(tmp_path, set())
    result = _run_slot(tmp_path, fake_bin, "go_ensure_slot_images")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert "tag " not in log


def test_alias_built_to_local(tmp_path):
    fake_bin = _fake_docker(tmp_path, {"ubyhost-go:slot-a"})
    result = _run_slot(tmp_path, fake_bin, "go_alias_built_to_local")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8").splitlines()
    assert "tag ubyhost-go:slot-a ubyhost-go:local" in log


def _fake_docker_slots(
    tmp_path: Path,
    present: set[str],
    *,
    services: tuple[str, ...] = (
        "postgres",
        "caddy",
        "ubyhost-go",
        "ubyhost-go-b",
    ),
    running: dict[str, str] | None = None,
    image_ids: dict[str, str] | None = None,
) -> Path:
    """Fake docker for pin/rollback: inspect, ps -q, and compose config."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "docker.log"
    running = running or {}
    image_ids = image_ids or {}
    svc_lines = "\\n".join(services)
    run_cases = "\n".join(
        f'    "{svc}") echo "{cid}" ;;' for svc, cid in running.items()
    )
    id_cases = "\n".join(
        f'    "{name}") echo "{iid}" ;;' for name, iid in image_ids.items()
    )
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        f'echo "$@" >> "{log}"\n'
        'if [ "${1:-}" = "compose" ] && [ "${2:-}" = "config" ] && [ "${3:-}" = "--services" ]; then\n'
        f'  printf "%b\\n" "{svc_lines}"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "${1:-}" = "compose" ]; then\n'
        '  svc=""\n'
        '  for arg in "$@"; do svc="$arg"; done\n'
        '  if [ "${4:-}" = "ps" ] && [ "${5:-}" = "-q" ]; then\n'
        "    case \"${svc}\" in\n"
        f"{run_cases}\n"
        "    esac\n"
        "    exit 0\n"
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        'if [ "${1:-}" = "inspect" ]; then\n'
        '  target=""\n'
        '  for arg in "$@"; do target="$arg"; done\n'
        "  case \"${target}\" in\n"
        f"{id_cases}\n"
        "  esac\n"
        "  exit 0\n"
        "fi\n"
        'if [ "${1:-}" = "image" ] && [ "${2:-}" = "inspect" ]; then\n'
        '  img="${@: -1}"\n'
        '  if [ "${3:-}" = "-f" ]; then\n'
        "    case \"${img}\" in\n"
        f"{id_cases}\n"
        "    esac\n"
        "  fi\n"
        f'  present="{" ".join(sorted(present))}"\n'
        '  case " $present " in\n'
        '    *" $img "*) exit 0 ;;\n'
        "    *) exit 1 ;;\n"
        "  esac\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    return fake_bin


def test_non_slot_services_drop_go_slots(tmp_path):
    fake_bin = _fake_docker_slots(tmp_path, set())
    result = _run_slot(tmp_path, fake_bin, "go_non_slot_services")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["postgres", "caddy"]


def test_pin_live_slot_is_noop_when_not_running(tmp_path):
    fake_bin = _fake_docker_slots(tmp_path, {"ubyhost-go:local"})
    result = _run_slot(tmp_path, fake_bin, "go_pin_live_slot_image")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert "tag " not in log


def test_pin_live_slot_retags_running_image(tmp_path):
    (tmp_path / ".go-slot").write_text("a\n", encoding="utf-8")
    fake_bin = _fake_docker_slots(
        tmp_path,
        {"ubyhost-go:local"},
        running={"ubyhost-go": "cid-a"},
        image_ids={"cid-a": "sha256:old"},
    )
    result = _run_slot(tmp_path, fake_bin, "go_pin_live_slot_image")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8").splitlines()
    assert "tag sha256:old ubyhost-go:slot-a" in log


def test_rollback_slots_keeps_live_when_already_previous(tmp_path):
    (tmp_path / ".go-slot").write_text("a\n", encoding="utf-8")
    fake_bin = _fake_docker_slots(
        tmp_path,
        {"ubyhost-go:previous"},
        running={"ubyhost-go": "cid-a"},
        image_ids={"ubyhost-go:previous": "sha256:old", "cid-a": "sha256:old"},
    )
    result = _run_slot(tmp_path, fake_bin, "go_rollback_slots")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert "tag ubyhost-go:previous ubyhost-go:slot-a" in log
    assert "tag ubyhost-go:previous ubyhost-go:slot-b" in log
    assert "force-recreate" not in log
    assert "stop ubyhost-go-b" in log


def test_rollback_slots_recreates_live_when_image_moved(tmp_path):
    (tmp_path / ".go-slot").write_text("b\n", encoding="utf-8")
    fake_bin = _fake_docker_slots(
        tmp_path,
        {"ubyhost-go:previous"},
        running={"ubyhost-go-b": "cid-b"},
        image_ids={"ubyhost-go:previous": "sha256:old", "cid-b": "sha256:new"},
    )
    result = _run_slot(tmp_path, fake_bin, "go_rollback_slots")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert "tag ubyhost-go:previous ubyhost-go:slot-a" in log
    assert "force-recreate ubyhost-go-b" in log
    assert "stop ubyhost-go" in log
    assert "stop ubyhost-go-b" not in log.replace("force-recreate ubyhost-go-b", "")


def test_rollback_prep_deletes_goose_row_in_one_transaction():
    prep = (SCRIPTS / "rollback-schema-prep.sh").read_text(encoding="utf-8")
    assert "BEGIN; ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out; DELETE FROM goose_db_version WHERE version_id = 24; COMMIT;" in prep
    assert "ON_ERROR_STOP=1" in prep
    deploy = DEPLOY.read_text(encoding="utf-8")
    rollback = deploy.split("rollback() {", 1)[1].split("\n}\n", 1)[0]
    assert "ERROR: schema rollback prep failed; old release may not start" in rollback
    assert "rollback_drop_guide_import_00024 || true" not in rollback


def test_deploy_keeps_rollback_copies_after_unfinished_deploy():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "previous deploy did not finish; keeping existing rollback copies" in text
    marker = text.index("git rev-parse HEAD > .deploy-in-progress")
    assert marker > text.index("cp caddy/Caddyfile.active caddy/Caddyfile.previous")
    assert marker > text.index("docker tag ubyhost-go:local ubyhost-go:previous")
    assert text.count('"${KEEP_ROLLBACK_COPIES}" != "1"') == 3
    assert text.index("git rev-parse HEAD > .deployed-sha\nrm -f .deploy-in-progress") > marker
    assert ".deploy-in-progress" in (ROOT / "deploy/lightsail/.gitignore").read_text(encoding="utf-8")


def test_deploy_failures_after_switch_print_the_rollback_command():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "ROLLBACK_CONFIRM=yes ./scripts/rollback-prod.sh" in text
    assert "DEPLOY FAILED AFTER SWITCH: the site runs the new release. Do not re-run the workflow." in text
    tail = text.split('echo "==> Removing retired compose services"', 1)[1]
    assert tail.count("fail_after_switch ") == 6


def _pipefail_script_files() -> list[Path]:
    files = [
        path
        for path in sorted(SCRIPTS.glob("*.sh"))
        if "pipefail" in path.read_text(encoding="utf-8")
        or path.name in {"lib-docker.sh", "go-slot.sh", "rollback-schema-prep.sh"}
    ]
    files.append(ROOT / "scripts/rollback-prod.sh")
    return files


def _grep_hits(pattern: re.Pattern[str]) -> list[str]:
    hits = []
    for path in _pipefail_script_files():
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{num}")
    return hits


def test_pipefail_scripts_never_grep_q_on_a_pipe():
    # grep -q exits at the first match; the producer then dies of SIGPIPE (141) and under
    # pipefail the pipeline reports failure although the line matched. Use grep >/dev/null.
    hits = _grep_hits(re.compile(r"\|\s*grep\s+-[A-Za-z]*q"))
    assert not hits, (
        "grep -q exits at the first match, the producer then dies of SIGPIPE (141) and under "
        "pipefail the pipeline reports failure although the line matched; use `grep ... >/dev/null`: "
        + ", ".join(hits)
    )


def test_pipefail_scripts_grep_has_no_lone_dash_argument():
    # A bare `grep - PATTERN FILE` reads `-` as the pattern and PATTERN as a file name,
    # so the check never matches what it was meant to match. Drop the lone `-`.
    hits = _grep_hits(re.compile(r"\bgrep\s+-(\s|$)"))
    assert not hits, (
        "lone `-` argument after grep: grep takes `-` as the PATTERN and the real pattern as a "
        "file name; write `grep PATTERN >/dev/null` without the `-`: " + ", ".join(hits)
    )
