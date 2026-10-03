"""Process-start guards: prod never on Render, never without production deployment."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import __version__, config, env_guard
from app.main import app

OPERATOR = {
    "UBYHOST_OPERATOR_NAME": "Example Operator",
    "UBYHOST_OPERATOR_ICO": "12345678",
    "UBYHOST_OPERATOR_ADDRESS": "Example Street 1, Praha",
}


def test_healthz_includes_env_outside_production():
    response = TestClient(app).get("/healthz")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] in {"ok", "degraded"}
    assert body["version"] == __version__ == "1.1.0"
    assert "data_dir_writable" in body
    assert body.get("deployment") == config.DEPLOYMENT
    assert body.get("ubyport_env") == config.UBYPORT_ENV


def test_refuse_prod_without_production_deployment():
    with pytest.raises(env_guard.EnvGuardError, match="requires UBYHOST_DEPLOYMENT=production"):
        env_guard.validate_runtime_env(ubyport_env="prod", deployment="staging")


def test_refuse_prod_on_render_flag():
    with pytest.raises(env_guard.EnvGuardError, match="not allowed on Render"):
        env_guard.validate_runtime_env(
            ubyport_env="prod",
            deployment="production",
            environ={"RENDER": "true"},
        )


def test_refuse_prod_when_public_url_is_onrender():
    with pytest.raises(env_guard.EnvGuardError, match="not allowed on Render"):
        env_guard.validate_runtime_env(
            ubyport_env="prod",
            deployment="production",
            environ={"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost-staging.onrender.com"},
        )


def test_test_endpoint_allowed_on_lightsail_production():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="test",
        deployment="production",
        guest_pin_required=True,
        scheduler_enabled=True,
        public_base_url="https://ubyhost.com",
        domain="ubyhost.com",
        environ={"UBYHOST_MAIL_BACKEND": "disabled"},
        operator_identity=OPERATOR,
    )
    assert warnings == ["guest e-mail is disabled on production"]


def test_prod_allowed_on_lightsail_production():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="prod",
        deployment="production",
        guest_pin_required=True,
        scheduler_enabled=True,
        public_base_url="https://ubyhost.com",
        domain="ubyhost.com",
        environ={"UBYHOST_MAIL_BACKEND": "disabled"},
        operator_identity=OPERATOR,
    )
    assert warnings == ["guest e-mail is disabled on production"]


def _production(**overrides):
    args = dict(
        ubyport_env="test",
        deployment="production",
        guest_pin_required=True,
        scheduler_enabled=True,
        public_base_url="https://ubyhost.com",
        domain="ubyhost.com",
        environ={"UBYHOST_MAIL_BACKEND": "disabled"},
        operator_identity=OPERATOR,
    )
    args.update(overrides)
    return env_guard.validate_runtime_env(**args)


def test_warns_when_scheduler_off():
    assert any("ENABLE_SCHEDULER" in item for item in _production(scheduler_enabled=False))


def test_refuse_production_without_guest_pin():
    with pytest.raises(env_guard.EnvGuardError, match="GUEST_PIN"):
        _production(guest_pin_required=False)


def test_refuse_production_without_https():
    with pytest.raises(env_guard.EnvGuardError, match="https://"):
        _production(public_base_url="http://ubyhost.com")


def test_refuse_production_when_public_url_host_mismatches_domain():
    with pytest.raises(env_guard.EnvGuardError, match="does not match"):
        _production(public_base_url="https://wrong.example")


def test_staging_only_warns_when_public_url_host_mismatches_domain():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="mock",
        deployment="staging",
        public_base_url="https://wrong.example",
        domain="ubyhost.com",
        environ={},
    )
    assert any("does not match" in item for item in warnings)


def test_refuse_production_without_operator_identity():
    with pytest.raises(env_guard.EnvGuardError, match="UBYHOST_OPERATOR_ICO"):
        _production(operator_identity={**OPERATOR, "UBYHOST_OPERATOR_ICO": " "})


def test_invalid_ubyport_env():
    with pytest.raises(env_guard.EnvGuardError, match="invalid"):
        env_guard.validate_runtime_env(ubyport_env="live", deployment="production")


def test_refuse_ses_mail_on_staging():
    with pytest.raises(env_guard.EnvGuardError, match="only allowed on production"):
        env_guard.validate_runtime_env(
            ubyport_env="mock",
            deployment="staging",
            environ={"UBYHOST_MAIL_BACKEND": "ses"},
        )


def test_console_mail_is_allowed_on_staging():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="mock",
        deployment="staging",
        environ={"UBYHOST_MAIL_BACKEND": "console"},
    )
    assert not any("MAIL_BACKEND" in item for item in warnings)


def test_refuse_production_on_mock_by_default():
    with pytest.raises(env_guard.EnvGuardError, match="nothing to the police"):
        env_guard.validate_runtime_env(
            ubyport_env="mock",
            deployment="production",
            environ={},
        )


def test_production_mock_allowed_with_explicit_opt_in():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="mock",
        deployment="production",
        guest_pin_required=True,
        public_base_url="https://ubyhost.com",
        domain="ubyhost.com",
        environ={"UBYHOST_ALLOW_PROD_MOCK": "1"},
        operator_identity=OPERATOR,
    )
    assert any("nothing is reported" in item for item in warnings)
