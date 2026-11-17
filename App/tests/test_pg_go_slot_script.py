"""Static and mocked-docker checks for 1830 slot helpers (deploy.sh + go-slot.sh)."""
from __future__ import annotations

import os
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


def test_deploy_seeds_slot_tags_before_schema_apply_and_up():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "go_ensure_slot_images" in text
    assert "go_alias_built_to_local" in text
    apply_at = text.index("Applying PostgreSQL goose migrations (new Go image)")
    up_at = text.index("docker compose up -d --remove-orphans")
    first_ensure = text.index("go_ensure_slot_images")
    assert first_ensure < apply_at
    assert text[:up_at].count("go_ensure_slot_images") >= 1
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
