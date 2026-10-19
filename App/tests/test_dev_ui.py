"""/dev/ui: admin-only living catalog (MASTER 11.3)."""
import json
import secrets
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "docs" / "design" / "catalog.json").read_text(encoding="utf-8"))

MUST_SHOW = [
    "ui-btn-primary", "ui-btn-secondary", "ui-btn-quiet", "ui-btn-danger", "ui-btn-compact", "ui-btn-icon", "ui-btn-loading",
    "ui-field-err", "ui-select", "ui-textarea", "ui-check", "ui-switch",
    "ui-badge-action", "ui-badge-attention", "ui-badge-done", "ui-badge-neutral", "ui-badge-overdue",
    "ui-chip", "ui-toolbar", "ui-table", "ui-cards", "ui-card", "ui-menu-panel", "ui-dialog", "ui-empty", "ui-tip",
    "ui-pagination", "ui-facts", "ui-stats", "ui-banner-attention", "ui-banner-neutral",
    'data-skeleton-kind="list"', 'data-skeleton-kind="detail"', 'data-skeleton-kind="form"', 'data-skeleton-kind="settings"',
]


def _client(role):
    db.init_db()
    username = f"devui{secrets.token_hex(3)}"
    auth.create_account(f"{username}@example.test", "Dev UI", role=role, username=username)
    client = TestClient(app)
    login_as(client, username)
    return client


def test_a_host_cannot_see_the_catalog():
    assert _client("host").get("/dev/ui").status_code == 404


def test_the_catalog_is_enforced_by_the_design_lint():
    assert "App/app/templates/dev_ui.html" in CATALOG["enforced_templates"]


def test_an_admin_sees_every_component_state_and_skeleton():
    html = _client("admin").get("/dev/ui?lang=en").text
    assert html.count("<h1") == 1
    for marker in MUST_SHOW:
        assert marker in html, marker
    # header primary action plus the "Primary" sample in the Buttons section
    assert html.count('class="ui-btn ui-btn-primary"') == 2
