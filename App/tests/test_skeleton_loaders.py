"""Skeleton loaders (FR-1): the placeholder markup, script and copy exist."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import host_i18n
from app.main import app

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_host_base_has_hidden_page_skeleton_before_app_js():
    html = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8")
    assert "data-page-skeleton" in html
    assert 'role="status" hidden' in html
    assert html.index("/static/skeleton.js") < html.index("/static/app.js")


def test_host_loading_copy_in_both_languages():
    assert host_i18n.translate("en", "a11y.loading") == "Loading…"
    assert host_i18n.translate("cs", "a11y.loading") == "Načítá se…"


def test_skeleton_styles_do_not_loop():
    css = (APP_DIR / "static" / "components.css").read_text(encoding="utf-8")
    assert ".page-skeleton" in css
    assert "infinite" not in css


def test_skeleton_script_is_served():
    with TestClient(app) as client:
        response = client.get("/static/skeleton.js")
    assert response.status_code == 200
    assert "window.ubyhostSkeleton" in response.text
