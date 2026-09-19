"""Process-start guards: prod never on Render, never without production deployment."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config, env_guard
from app.main import app


def test_healthz_includes_env_outside_production():
    response = TestClient(app).get("/healthz")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] in {"ok", "degraded"}
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
    )
    assert warnings == ["guest e-mail is disabled on production"]


def test_warns_when_guest_pin_and_scheduler_off():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="test",
        deployment="production",
        guest_pin_required=False,
        scheduler_enabled=False,
        public_base_url="http://ubyhost.com",
        domain="ubyhost.com",
        environ={},
    )
    joined = " ".join(warnings)
    assert "GUEST_PIN" in joined
    assert "ENABLE_SCHEDULER" in joined
    assert "https://" in joined


def test_warns_when_public_url_host_mismatches_domain():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="test",
        deployment="production",
        guest_pin_required=True,
        scheduler_enabled=True,
        public_base_url="https://wrong.example",
        domain="ubyhost.com",
        environ={},
    )
    assert any("does not match" in item for item in warnings)


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
