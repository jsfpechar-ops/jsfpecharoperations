"""Practice environments must be obvious; production should stay quiet."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app import auth, db, host_i18n, templating
from app.main import app


@pytest.fixture()
def client():
    db.init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def env(monkeypatch):
    """The deployment is read once into the template globals at import."""

    def use(name: str):
        monkeypatch.setitem(templating.templates.env.globals, "ubyport_env", name)

    return use


def test_the_login_page_says_nothing_is_being_reported(client, env):
    env("mock")

    page = client.get("/login")

    assert page.status_code == 200
    assert "env-banner" in page.text, "a host signing in could not tell this is practice"
    assert "mock" in page.text


def test_a_czech_host_is_warned_in_czech(client, env):
    env("mock")

    page = client.get("/login", cookies={host_i18n.LANG_COOKIE: "cs"})

    assert "env-banner" in page.text
    expected = host_i18n.translate("cs", "env.mock_title")
    assert expected in page.text, "the warning was left in English"


def test_production_does_not_show_a_persistent_warning(client, env):
    env("prod")

    page = client.get("/login")

    assert "env-banner" not in page.text
    assert "Live police reporting" not in page.text


def test_production_shows_a_quiet_named_sidebar_badge(client, env):
    env("prod")
    username = "quiet-production-ui"
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (username,)):
        auth.create_account(
            username,
            "Quiet-Production-Password-123",
            "Production host",
            role="admin",
            must_change_password=False,
        )
    client.post(
        "/login",
        data={"username": username, "password": "Quiet-Production-Password-123"},
        follow_redirects=False,
    )

    page = client.get("/")

    assert 'class="env-badge prod"' in page.text
    assert "Production" in page.text


def test_a_test_environment_is_not_shouted_about(client, env):
    """Only the two states that matter get a banner; test is unremarkable."""
    env("test")

    page = client.get("/login")

    assert "env-banner" not in page.text


def test_the_banner_is_defined_once_for_every_shell():
    """Two copies drift; the login page was already a year behind."""
    from pathlib import Path

    templates = Path("app/templates")
    inline = [
        path.name
        for path in templates.glob("*.html")
        if "env-banner" in path.read_text() and path.name != "_env_banner.html"
    ]
    assert not inline, f"these templates hand-roll the banner instead of including it: {inline}"
