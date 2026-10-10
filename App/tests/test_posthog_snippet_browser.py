"""Browser check that the PostHog snippet scrubs click ids before send."""
from __future__ import annotations

import json
import os
import socket
import threading
from urllib.parse import urlparse

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn

from app import config, db
from app.main import app


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base():
    db.init_db()
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = __import__("time").time() + 15
    while not server.started and __import__("time").time() < deadline:
        __import__("time").sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


API_KEY = "phc_test"
API_HOST = "https://analytics.example.invalid"
ASSETS_HOST = "https://assets.example.invalid"


@pytest.fixture
def posthog_on(monkeypatch):
    monkeypatch.setattr(config, "POSTHOG_PROJECT_API_KEY", API_KEY)
    monkeypatch.setattr(config, "POSTHOG_HOST", API_HOST)
    monkeypatch.setattr(config, "POSTHOG_ASSETS_HOST", ASSETS_HOST)
    db.init_db()


def test_before_send_scrubs_click_ids_and_urls(posthog_on, base):
    stand_in = (
        "window.posthog = { init: function (key, cfg) { window.__phCfg = cfg; }, "
        "capture: function () {} };"
    )
    sample_event = {
        "event": "$pageview",
        "properties": {
            "token": "phc_test",
            "utm_source": "google",
            "gclid": "G1",
            "fbclid": "F1",
            "ttclid": "T1",
            "$initial_gclid": "G1",
            "$session_entry_fbclid": "F1",
            "$current_url": (
                "https://ubyhost.example/?utm_source=google&gclid=G1&click=C1&email=a%40b.cz#frag"
            ),
            "$pathname": "/?gclid=G1",
            "$referrer": "https://www.google.com/?gclid=G1",
            "$set_once": {
                "$initial_current_url": "https://ubyhost.example/?gclid=G1&token=K1",
            },
        },
    }
    forbidden = ("G1", "F1", "T1", "C1", "K1", "a%40b.cz", "#frag")
    allowed_hosts = {urlparse(base).netloc, "assets.example.invalid"}

    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:
            if REQUIRE_BROWSER:
                pytest.fail(f"Chromium required: {exc}")
            pytest.skip(str(exc))
        page = browser.new_page()
        request_hosts: list[str] = []

        def on_request(request):
            host = urlparse(request.url).netloc
            if host:
                request_hosts.append(host)

        page.on("request", on_request)

        def fulfil_array(route):
            route.fulfill(status=200, content_type="application/javascript", body=stand_in)

        page.route("https://assets.example.invalid/static/array.js", fulfil_array)
        page.goto(
            base
            + "/?lang=en&utm_source=google&gclid=G1&fbclid=F1&click=C1&email=a%40b.cz#frag"
        )
        page.wait_for_function("window.__phCfg")
        result = page.evaluate(
            """(ev) => window.__phCfg.before_send(ev)""",
            sample_event,
        )
        cfg = page.evaluate("window.__phCfg")
        browser.close()

    result_text = json.dumps(result)
    for token in forbidden:
        assert token not in result_text
    assert result["properties"]["token"] == "phc_test"
    assert result["properties"]["utm_source"] == "google"
    assert result["properties"]["$current_url"] == "https://ubyhost.example/?utm_source=google"
    assert cfg["advanced_disable_flags"] is True
    assert cfg["cookieless_mode"] == "always"
    assert set(request_hosts) <= allowed_hosts
