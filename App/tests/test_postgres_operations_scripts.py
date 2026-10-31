"""Static safety tests for the PostgreSQL operations and cutover kit (0456).

These tests are CI-runnable **without Docker, without a PostgreSQL server and
without any secret**: they check file modes, shell syntax, YAML structure,
required safety tokens, documented commands and secret hygiene on the deploy
kit that ships in ``deploy/lightsail/`` plus the supporting scripts in
``App/scripts/``.

They are deliberately static. Passing them means the kit is wired safely and
the safety guards are present in the sources; it does **not** mean the kit was
rehearsed. A real pgBackRest restore/PITR rehearsal and the cutover itself are
owner operations performed on the server, and no test here claims one happened.

Run from ``App/``::

    .venv/bin/python -m pytest tests/test_postgres_operations_scripts.py -q --tb=short -x
"""
from __future__ import annotations

import py_compile
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_DIR.parent
DEPLOY = REPO_ROOT / "deploy" / "lightsail"
OPS_SCRIPTS = DEPLOY / "scripts"
POSTGRES_IMAGE = DEPLOY / "postgres"
APP_SCRIPTS = PROJECT_DIR / "scripts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


# --- 1. shell scripts: executable and syntactically valid ------------------


def _postgres_shell_scripts() -> list[Path]:
    scripts = set(OPS_SCRIPTS.glob("postgres-*.sh"))
    scripts.update(POSTGRES_IMAGE.glob("*.sh"))
    scripts.add(APP_SCRIPTS / "postgres_cutover_transfer.sh")
    return sorted(path for path in scripts if path.is_file())


def test_postgres_shell_scripts_are_executable_and_parse():
    scripts = _postgres_shell_scripts()
    # The required entry points, whatever else the kit adds.
    required = {
        OPS_SCRIPTS / "postgres-cutover.sh",
        OPS_SCRIPTS / "postgres-restore.sh",
        OPS_SCRIPTS / "postgres-lib.sh",
        OPS_SCRIPTS / "postgres-key-backup.sh",
        APP_SCRIPTS / "postgres_cutover_transfer.sh",
    }
    assert required <= set(scripts), sorted(_relative(path) for path in required - set(scripts))

    bash = shutil.which("bash")
    assert bash, "bash is required to validate the operations shell scripts"
    problems: list[str] = []
    for path in scripts:
        mode = path.stat().st_mode
        if not mode & 0o111:
            problems.append(f"{_relative(path)} is not executable (mode {oct(mode & 0o777)})")
        result = subprocess.run(
            [bash, "-n", str(path)], capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            problems.append(
                f"{_relative(path)}: bash -n failed: {result.stderr.strip()}"
            )
    assert problems == [], "\n".join(problems)


# --- 2. Caddy: visible maintenance window before the app -------------------


CADDY_FILES = [
    DEPLOY / "caddy" / "Caddyfile.acme",
    DEPLOY / "caddy" / "Caddyfile.cloudflare",
]


def test_caddyfiles_exist():
    for path in CADDY_FILES:
        assert path.is_file(), _relative(path)


@pytest.mark.parametrize("path", CADDY_FILES, ids=[path.name for path in CADDY_FILES])
def test_caddy_serves_a_503_maintenance_window_before_the_app(path):
    text = _read(path)
    assert "@maintenance" in text, f"{_relative(path)} lacks the maintenance matcher"
    assert "UBYHOST_MAINTENANCE" in text, (
        f"{_relative(path)} must drive the matcher from UBYHOST_MAINTENANCE"
    )
    respond = re.search(r"respond\s+@maintenance\b[^\n]*\b503\b", text)
    assert respond, f"{_relative(path)} lacks a 503 response for @maintenance"
    proxy = re.search(r"\breverse_proxy\b", text)
    assert proxy, f"{_relative(path)} lacks reverse_proxy"
    # The file order mirrors the intended route order; Caddy's fixed directive
    # order also puts respond before reverse_proxy.
    assert respond.start() < proxy.start(), (
        f"{_relative(path)}: the maintenance 503 must be declared before reverse_proxy"
    )
    assert re.search(r"header\s+@maintenance\b[^\n]*Retry-After", text), (
        f"{_relative(path)} should tell clients when to retry"
    )


def test_cloudflare_caddyfile_keeps_the_origin_guard_and_ranges():
    text = _read(DEPLOY / "caddy" / "Caddyfile.cloudflare")
    assert "@not_cloudflare" in text
    assert re.search(r"abort\s+@not_cloudflare", text)
    # IPv4 and IPv6 Cloudflare ranges must stay on both the trusted_proxies
    # list and the origin guard; a partial list silently accepts direct hits.
    for cidr in (
        "173.245.48.0/20",
        "104.16.0.0/13",
        "2400:cb00::/32",
        "2c0f:f248::/32",
    ):
        assert cidr in text, f"Cloudflare range {cidr} missing from the origin guard"


# --- 3. cutover state machine safety --------------------------------------


def test_cutover_script_never_blanks_the_postgres_dsn_and_keeps_guards():
    text = _read(OPS_SCRIPTS / "postgres-cutover.sh")
    # 0455 rejects "UBYHOST_DATABASE_URL set but empty"; SQLite abort must
    # remove the line instead of writing an empty value.
    assert 'set_env_value UBYHOST_DATABASE_URL ""' not in text
    assert not re.search(
        r"set_env_value\s+UBYHOST_DATABASE_URL\s+(''|\"\")\s*$", text, re.MULTILINE
    ), "abort must not set UBYHOST_DATABASE_URL to an empty value"
    assert "remove_env_value UBYHOST_DATABASE_URL" in text

    # A failed transfer must be retryable only after proving the target is
    # still empty, and the ambiguous branch must point at recovery verification.
    assert "transfer-retry" in text
    assert "transfer-recovery-verify" in text
    assert re.search(r"transfer-retry\)", text)

    # Two operators (or a cron) must not interleave phases: flock lives on the
    # state directory's lock file.
    assert "flock" in text
    assert "LOCK_FILE" in text and "STATE_DIR" in text
    assert "${STATE_DIR}/lock" in text

    # The SQLite replica must be quiesced before the final snapshot.
    assert "stop_litestream" in text
    assert "litestream" in text.lower()
    assert "quiesc" in text.lower()

    # Both owner acknowledgements stay mandatory, in their exact spelling.
    assert "--owner-ack=POSTGRES_IS_AUTHORITATIVE" in text
    assert "--owner-ack=POST_CUTOVER_CHECKS_PASSED" in text


def test_cutover_lib_refuses_contradictory_backend_configuration():
    text = _read(OPS_SCRIPTS / "postgres-lib.sh")
    assert "require_postgres_identity" in text
    # The app config rejects both settings at once, so the ops lib must too.
    assert "UBYHOST_DB must be unset" in text
    assert "UBYHOST_LITESTREAM_ENABLED" in text
    # Never print expanded Compose config (it interpolates DSNs and secrets).
    assert "Never print expanded Compose config" in text


# --- 4. restore layout and cluster verification ---------------------------


def test_restore_matches_the_rehearsal_layout_and_verifies_the_cluster():
    restore = _read(OPS_SCRIPTS / "postgres-restore.sh")
    assert "/restore/18/docker" in restore, (
        "restore must target the PostgreSQL 18 PGDATA layout used by the rehearsal"
    )
    assert re.search(r"\bPG_VERSION\b", restore)
    assert "pg_controldata" in restore
    assert re.search(r"pgbackrest|pg_compose\s+run[^\n]*postgres-restore", restore)
    assert "restore" in restore.lower()

    compose = _read(DEPLOY / "docker-compose.postgres.yml")
    assert "PGDATA: /var/lib/postgresql/18/docker" in compose, (
        "the postgres-rehearsal service must mount the restored 18/docker cluster"
    )


# --- 5. compose isolation --------------------------------------------------


def _service_networks(service: dict) -> set[str]:
    networks = service.get("networks", [])
    if isinstance(networks, dict):
        return set(networks)
    return set(networks or [])


def test_postgres_compose_is_valid_yaml_and_is_isolated():
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load(_read(DEPLOY / "docker-compose.postgres.yml"))
    assert isinstance(compose, dict) and isinstance(compose.get("services"), dict)
    services = compose["services"]
    networks = compose.get("networks") or {}

    for name, service in services.items():
        assert not service.get("ports"), (
            f"{name} publishes host ports in the cutover overlay; "
            "PostgreSQL must stay compose-internal"
        )

    postgres = services["postgres"]
    assert "database" in _service_networks(postgres)
    assert networks.get("database", {}).get("internal") is True, (
        "the database network must be internal"
    )

    restore = services["postgres-restore"]
    rehearsal = services["postgres-rehearsal"]
    restore_networks = _service_networks(restore)
    rehearsal_networks = _service_networks(rehearsal)
    # The restore job needs S3 egress; the read-only rehearsal server must not
    # keep that route once the restore has finished.
    assert "postgres-restore-egress" in restore_networks
    assert "postgres-restore-egress" not in rehearsal_networks, (
        "postgres-rehearsal must not join the egress network"
    )
    assert "postgres-restore-isolated" in rehearsal_networks
    assert networks.get("postgres-restore-isolated", {}).get("internal") is True
    assert rehearsal.get("environment", {}).get("PGDATA") == "/var/lib/postgresql/18/docker"
    assert rehearsal.get("restart") == "no"


# --- 6. environment variable contract -------------------------------------


REQUIRED_PG_ENV = (
    "UBYHOST_DATABASE_URL",
    "UBYHOST_PG_DATABASE",
    "UBYHOST_PG_SUPERUSER",
    "UBYHOST_PG_SUPERUSER_PASSWORD_FILE",
    "UBYHOST_PG_BACKREST_BUCKET",
    "UBYHOST_PG_BACKREST_ENDPOINT",
    "UBYHOST_PG_BACKREST_REGION",
    "UBYHOST_PG_BACKREST_S3_KEY_FILE",
    "UBYHOST_PG_BACKREST_S3_SECRET_FILE",
    "UBYHOST_PG_BACKREST_CIPHER_PASS_FILE",
    "UBYHOST_S3_BUCKET",
)


def test_env_example_lists_postgres_variable_names_without_secret_values():
    text = _read(DEPLOY / ".env.example")
    missing = [
        name
        for name in REQUIRED_PG_ENV
        if not re.search(rf"^\s*#?\s*{re.escape(name)}\s*=", text, re.MULTILINE)
    ]
    assert missing == [], f".env.example does not document {missing}"

    # Secret-bearing variables are names only: commented placeholders or empty
    # assignments, never a literal credential.
    secret_names = [
        name
        for name in REQUIRED_PG_ENV
        if any(part in name for part in ("PASSWORD", "SECRET", "KEY", "CIPHER"))
    ]
    for name in secret_names:
        for line in text.splitlines():
            match = re.match(rf"^\s*(#?)\s*{re.escape(name)}\s*=\s*(.*)$", line)
            if not match:
                continue
            commented, value = match.group(1) == "#", match.group(2).strip()
            assert commented or value == "", (
                f".env.example gives {name} a literal value; names only"
            )
    # The app DSN is owner-supplied; the example must not ship a working one.
    assert "REPLACE" in text.upper() or "CHANGE" in text.upper() or "your-" in text.lower()


# --- 7. owner runbook ------------------------------------------------------


RUNBOOK = REPO_ROOT / "docs" / "plans" / "postgresql" / "owner-cutover-runbook.md"


def test_owner_cutover_runbook_exists_and_documents_the_real_commands():
    assert RUNBOOK.is_file(), f"missing owner runbook: {_relative(RUNBOOK)}"
    text = _read(RUNBOOK)
    numbered = re.findall(r"^\s*\d+[.)]\s+\S", text, re.MULTILINE)
    assert len(numbered) >= 5, "the runbook must be a numbered click-by-click sequence"
    assert "postgres-cutover.sh" in text
    assert "--owner-ack=POSTGRES_IS_AUTHORITATIVE" in text
    assert "--owner-ack=POST_CUTOVER_CHECKS_PASSED" in text
    assert "pgbackrest" in text.lower()
    assert re.search(r"(?i)\bPITR\b|point[- ]in[- ]time", text), (
        "the runbook must document the point-in-time restore path"
    )
    assert "restore" in text.lower()
    assert "abort-to-sqlite" in text


# --- 8. operations Python scripts compile ----------------------------------


OPERATIONS_PYTHON = (
    APP_SCRIPTS / "create_postgres_cutover_snapshot.py",
    APP_SCRIPTS / "postgres_key_bundle.py",
    APP_SCRIPTS / "pg_schema.py",
    APP_SCRIPTS / "sqlite_to_postgres.py",
)


def test_operations_python_scripts_compile(tmp_path):
    for path in OPERATIONS_PYTHON:
        assert path.is_file(), _relative(path)
        try:
            py_compile.compile(
                str(path), cfile=str(tmp_path / f"{path.name}.pyc"), doraise=True
            )
        except py_compile.PyCompileError as exc:
            raise AssertionError(f"{_relative(path)} does not compile: {exc}") from exc


# --- 9. no secrets in the operations kit ----------------------------------

_PLACEHOLDER = re.compile(
    r"(?i)replace|change[_-]?me|placeholder|example|your[_-]|dummy|sample|"
    r"\$\{|<[a-z_-]+>|x{4,}|\*{3,}|\.\.\."
)


def _operations_text_files() -> list[Path]:
    files: list[Path] = []
    for path in DEPLOY.rglob("*"):
        if path.is_file():
            files.append(path)
    files.extend(
        (
            APP_SCRIPTS / "postgres_cutover_transfer.sh",
            APP_SCRIPTS / "postgres_key_bundle.py",
            APP_SCRIPTS / "create_postgres_cutover_snapshot.py",
            APP_SCRIPTS / "pg_schema.py",
            APP_SCRIPTS / "sqlite_to_postgres.py",
        )
    )
    if RUNBOOK.is_file():
        files.append(RUNBOOK)
    return sorted(set(files))


def _scan_for_secrets(path: Path) -> list[str]:
    try:
        text = _read(path)
    except OSError:
        return []
    where = _relative(path)
    findings: list[str] = []
    if re.search(r"\bAKIA[0-9A-Z]{16}\b", text):
        findings.append(f"{where}: AWS access key id")
    if re.search(r"\bghp_[A-Za-z0-9]{20,}", text):
        findings.append(f"{where}: GitHub personal access token")
    if re.search(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", text):
        findings.append(f"{where}: private key header")
    for match in re.finditer(r"postgres(?:ql)?://[^\s:/@]+:([^\s/@]+)@", text):
        password = match.group(1)
        if not _PLACEHOLDER.search(password):
            findings.append(f"{where}: PostgreSQL DSN with a credential value")
    for match in re.finditer(
        r"(?m)^\s*([A-Za-z0-9_]*PASSWORD[A-Za-z0-9_]*)\s*=\s*(\S+)", text
    ):
        name, raw_value = match.groups()
        # Shell/env indirection (`$VAR`, `$(cat file)`, `env(...)`) is a name,
        # not a literal credential; only a bare literal is a finding.
        value = raw_value.lstrip("\"'")
        if name.endswith("_FILE") or value.startswith(
            ("env(", "${", "$(", "$")
        ):
            continue
        if not _PLACEHOLDER.search(value):
            findings.append(f"{where}: {name}= looks like a literal value")
    return findings


def test_operations_kit_contains_no_secrets():
    files = _operations_text_files()
    assert len(files) >= 15, "the operations kit file set looks incomplete"
    findings: list[str] = []
    for path in files:
        findings.extend(_scan_for_secrets(path))
    assert findings == [], "possible secrets in the operations kit:\n" + "\n".join(findings)


# --- 10. optional roles proposal ------------------------------------------


def test_roles_proposal_if_present_has_no_plaintext_passwords():
    """The roles proposal is optional; it must not ship credentials if added."""
    candidates = sorted(POSTGRES_IMAGE.glob("roles.sql")) + sorted(
        OPS_SCRIPTS.glob("postgres-create-roles.sh")
    )
    candidates = [path for path in candidates if path.is_file()]
    if not candidates:
        pytest.skip("the kit ships no roles.sql / postgres-create-roles.sh proposal")

    for path in candidates:
        text = _read(path)
        assert text.strip(), f"{_relative(path)} is empty"
        # No literal password in SQL or shell: values must be supplied by the
        # owner through the environment/secret files.
        assert not re.search(
            r"(?i)PASSWORD\s+'(?!\$\{|\$|:)[^']+'", text
        ), f"{_relative(path)} contains a literal SQL role password"
        assert not re.search(
            r"(?i)(?:PASSWORD|PGPASSWORD)\s*=\s*(?![\"']?(?:\$\{|env\())[^\s\"']{6,}",
            text,
        ), f"{_relative(path)} contains a literal password assignment"
        # The application DSN stays owner-supplied, never baked into the kit.
        for match in re.finditer(r"postgres(?:ql)?://[^\s:/@]+:([^\s/@]+)@", text):
            assert _PLACEHOLDER.search(match.group(1)), (
                f"{_relative(path)} embeds a PostgreSQL credential"
            )
        if path.name == "postgres-create-roles.sh":
            assert "UBYHOST_DATABASE_URL" in text, (
                "the roles script must keep the app DSN as the owner-supplied variable"
            )
