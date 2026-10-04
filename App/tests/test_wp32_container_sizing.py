"""WP32: container sizing for the 8 GB / 2 vCPU Lightsail server.

`docker compose config` cannot run in CI, so the compose file is parsed as YAML
and the variable substitutions are checked against the documented defaults.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "deploy" / "lightsail" / "docker-compose.yml"
DOCKERFILE = REPO_ROOT / "Dockerfile"
ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"
ENV_EXAMPLE = REPO_ROOT / "deploy" / "lightsail" / ".env.example"
LIGHTSAIL_DOC = REPO_ROOT / "docs" / "LIGHTSAIL.md"

EXPECTED_MEM = {
    "ubyhost": "${UBYHOST_WEB_MEM:-2g}",
    "worker": "${UBYHOST_WORKER_MEM:-1g}",
    "litestream": "${UBYHOST_LITESTREAM_MEM:-256m}",
    "caddy": "${UBYHOST_CADDY_MEM:-256m}",
}

_SUBST = re.compile(r"\$\{([A-Z0-9_]+):-([^}]*)\}")


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _expand(value: str, env: dict[str, str]) -> str:
    """Compose's `${VAR:-default}`: the default when VAR is unset or empty."""
    return _SUBST.sub(lambda m: env.get(m.group(1)) or m.group(2), value)


def test_compose_file_is_valid_yaml_with_the_expected_services():
    services = _compose()["services"]
    for name in ("ubyhost", "worker", "litestream", "caddy", "mock-ubyport"):
        assert name in services


def test_memory_limits_use_env_variables_with_the_documented_defaults():
    services = _compose()["services"]
    for name, expected in EXPECTED_MEM.items():
        assert services[name]["mem_limit"] == expected, name


def test_memory_defaults_expand_and_can_be_lowered_from_env():
    services = _compose()["services"]
    defaults = {n: _expand(services[n]["mem_limit"], {}) for n in EXPECTED_MEM}
    assert defaults == {
        "ubyhost": "2g",
        "worker": "1g",
        "litestream": "256m",
        "caddy": "256m",
    }
    staging = {
        "UBYHOST_WEB_MEM": "896m",
        "UBYHOST_WORKER_MEM": "448m",
        "UBYHOST_LITESTREAM_MEM": "128m",
        "UBYHOST_CADDY_MEM": "128m",
    }
    lowered = {n: _expand(services[n]["mem_limit"], staging) for n in EXPECTED_MEM}
    assert lowered == {
        "ubyhost": "896m",
        "worker": "448m",
        "litestream": "128m",
        "caddy": "128m",
    }


def test_no_hard_coded_worker_count_in_the_image():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert '"--workers", "2"' not in text
    assert "UBYHOST_WEB_WORKERS=2" in text
    cmd = [line for line in text.splitlines() if line.startswith("CMD ")]
    assert len(cmd) == 1
    assert '--workers \\"${UBYHOST_WEB_WORKERS:-2}\\"' in cmd[0]


def _run_entrypoint(workers: str | None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "UBYHOST_WEB_WORKERS"}
    if workers is not None:
        env["UBYHOST_WEB_WORKERS"] = workers
    # Stop before env_guard: only the worker-count check is under test.
    script = ENTRYPOINT.read_text(encoding="utf-8").split("python -c", 1)[0]
    return subprocess.run(
        ["sh", "-c", script + "\necho checked"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize("workers", [None, "1", "2", "4", "16"])
def test_entrypoint_accepts_a_sane_worker_count(workers):
    result = _run_entrypoint(workers)
    assert result.returncode == 0, result.stderr
    assert "checked" in result.stdout


@pytest.mark.parametrize("workers", ["0", "17", "two", "4x", "-1", "04"])
def test_entrypoint_refuses_a_bad_worker_count(workers):
    result = _run_entrypoint(workers)
    assert result.returncode != 0
    assert "UBYHOST_WEB_WORKERS" in result.stderr


def test_env_example_and_docs_describe_the_8gb_server():
    env_example = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "UBYHOST_WEB_WORKERS=4" in env_example
    for var in ("UBYHOST_WEB_MEM", "UBYHOST_WORKER_MEM", "UBYHOST_LITESTREAM_MEM", "UBYHOST_CADDY_MEM"):
        assert var in env_example
    # The code default for local snapshots stays 30; 7 is documented.
    assert "UBYHOST_BACKUP_RETENTION_DAYS=30" in env_example
    doc = LIGHTSAIL_DOC.read_text(encoding="utf-8")
    assert "## Sizing (WP32)" in doc
    assert "docker compose build" in doc
    assert "UBYHOST_BACKUP_RETENTION_DAYS" in doc
