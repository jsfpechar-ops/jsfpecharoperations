"""Every UBYHOST_* env var read in go/ must appear in ubyhost-go compose (brief 2029)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "deploy/lightsail/docker-compose.yml").read_text()
GO_ROOT = ROOT / "go"


def _go_env_block() -> list[str]:
    start = COMPOSE.index("\n  ubyhost-go:\n")
    end = COMPOSE.index("\n  mock-ubyport:", start)
    blk = COMPOSE[start:end]
    env = blk[blk.index("    environment:\n"):blk.index("    volumes:\n")]
    return env.splitlines()[1:]


def _go_reads_ubyhost() -> set[str]:
    found: set[str] = set()
    for path in GO_ROOT.rglob("*.go"):
        if path.name.endswith("_test.go"):
            continue
        text = path.read_text()
        found.update(re.findall(r'"(UBYHOST_[A-Z0-9_]+)"', text))
    return found


NOT_PASSED = {
    # go/Dockerfile ENV — not passed through compose
    "UBYHOST_GO_ADDR",
    "UBYHOST_MIGRATIONS_DIR",
    "UBYHOST_APP_ROOT",
    # test/dev only — must never reach production
    "UBYHOST_TEST_OCR_VALUES",
    "UBYHOST_REPO_ROOT",
    # per-key vars are listed; these are string prefixes in code, not env keys
    "UBYHOST_AI_KEY_DAILY_USD_",
    "UBYHOST_AI_MONTHLY_USD_",
}


def test_compose_passes_every_ubyhost_var_go_reads():
    read = _go_reads_ubyhost()
    passed = {ln.strip().split(":")[0] for ln in _go_env_block() if ln.strip()}
    missing = sorted(read - passed - NOT_PASSED)
    assert not missing, f"ubyhost-go compose missing: {missing}"


def test_not_passed_allowlist_still_referenced_in_go():
    read = _go_reads_ubyhost()
    stale = sorted(NOT_PASSED - read)
    assert not stale, f"NOT_PASSED entries no longer read in go/: {stale}"


def test_new_bare_keys_have_no_value_in_compose():
    new_bare = {
        "UBYHOST_ADMIN_EMAIL",
        "UBYHOST_ADMIN_USERNAME",
        "UBYHOST_ADS_CONVERSION_NAME",
        "UBYHOST_AI_MAX_INPUT_TOKENS",
        "UBYHOST_AI_MAX_TOKENS",
        "UBYHOST_AI_MODEL",
        "UBYHOST_ALERT_RETENTION_DAYS",
        "UBYHOST_AUDIT_RETENTION_DAYS",
        "UBYHOST_DEMO_ENABLED",
        "UBYHOST_GO_RETENTION_APPLY",
        "UBYHOST_GO_ACCESS_PAGE",
        "UBYHOST_GUEST_LANGS",
        "UBYHOST_GUEST_NOTICE_VERSION",
        "UBYHOST_GUEST_PIN",
        "UBYHOST_GUIDE_PHOTOS_DIR",
        "UBYHOST_HAVEL_MONTHLY",
        "UBYHOST_HAVEL_WEEKLY",
        "UBYHOST_HEADCOUNT_LEAD_LIVE",
        "UBYHOST_HEARTBEAT_MAIL_URL",
        "UBYHOST_LEGAL_EFFECTIVE_DATE",
        "UBYHOST_LIFECYCLE_MAIL",
        "UBYHOST_MAIL_ENABLED",
        "UBYHOST_OPERATOR_REGISTRY_URL",
        "UBYHOST_RATE_LIMIT_RETENTION_HOURS",
        "UBYHOST_RETENTION_AUTOPURGE",
        "UBYHOST_RETENTION_NOTICE_DAYS",
        "UBYHOST_RUIAN_URL",
        "UBYHOST_SECRET",
        "UBYHOST_SECURE_COOKIES",
        "UBYHOST_SMTP_HOST",
        "UBYHOST_STAGING_LOGIN_PASSWORD",
        "UBYHOST_TTLOCK_API_BASE",
    }
    for ln in _go_env_block():
        key = ln.strip().split(":")[0] if ln.strip() else ""
        if key not in new_bare:
            continue
        rest = ln.split(":", 1)[1].strip() if ":" in ln else ""
        assert not rest, f"{key} must be a bare key with no value in the repo"