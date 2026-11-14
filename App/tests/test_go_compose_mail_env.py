"""The Go service must receive the SES settings its mail sender reads (brief 1632)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "deploy/lightsail/docker-compose.yml").read_text()
MAIL_CONFIG = (ROOT / "go/internal/mail/outbox_config.go").read_text()

SES_KEYS = (
    "UBYHOST_MAIL_BACKEND",
    "UBYHOST_MAIL_FROM",
    "UBYHOST_SES_REGION",
    "UBYHOST_AWS_ACCESS_KEY_ID",
    "UBYHOST_AWS_SECRET_ACCESS_KEY",
    "UBYHOST_DEPLOYMENT",
    "UBYHOST_DATA_KEYS",
)


def _go_env_block() -> list[str]:
    start = COMPOSE.index("\n  ubyhost-go:\n")
    end = COMPOSE.index("\n  mock-ubyport:", start)
    blk = COMPOSE[start:end]
    env = blk[blk.index("    environment:\n"):blk.index("    volumes:\n")]
    return env.splitlines()[1:]


def test_go_service_receives_ses_keys_as_bare_keys():
    lines = _go_env_block()
    for key in SES_KEYS:
        assert f"      {key}:" in lines, f"{key} must be a bare key under ubyhost-go"


def test_go_mail_config_reads_only_passed_keys():
    read = set(re.findall(r'getenv\("(UBYHOST_[A-Z_]+)"\)', MAIL_CONFIG))
    passed = {ln.strip().rstrip(":") for ln in _go_env_block() if ln.strip().endswith(":")}
    assert read <= passed, f"outbox_config.go reads {sorted(read - passed)} but compose does not pass them"


def test_no_ses_value_in_compose():
    for ln in _go_env_block():
        if "AWS_" in ln or "MAIL_FROM" in ln or "SES_REGION" in ln:
            assert ln.rstrip().endswith(":"), "pass the key bare; never write a value in the repo"
