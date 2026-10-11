"""Platform source badges use only local static logos."""
from __future__ import annotations

from markupsafe import Markup

from app import templating


def test_source_mark_renders_img_for_known_platform():
    html = templating.source_mark("airbnb")
    assert isinstance(html, Markup)
    assert "<img" in html
    assert 'src="/static/platforms/airbnb.svg"' in html
    assert 'alt=""' in html
    assert "http" not in html.lower().replace("/static/", "")


def test_source_mark_empty_for_manual_and_missing():
    assert templating.source_mark("manual") == ""
    assert templating.source_mark("not-a-platform") == ""
    assert templating.source_mark("UPPER") == ""


def test_source_badge_macro_includes_img_when_logo_exists():
    rendered = (
        templating.templates.env.from_string(
            '{% from "_components.html" import source_badge %}{{ source_badge("booking", "Booking.com") }}'
        )
        .render()
    )
    assert "<img" in rendered
    assert "Booking.com" in rendered
    assert 'src="/static/platforms/booking.svg"' in rendered


def test_source_badge_macro_label_only_without_logo():
    rendered = (
        templating.templates.env.from_string(
            '{% from "_components.html" import source_badge %}{{ source_badge("manual", "Direct booking") }}'
        )
        .render()
    )
    assert "<img" not in rendered
    assert "Direct booking" in rendered
    assert 'class="source-badge"' in rendered


def test_source_mark_rejects_invalid_keys():
    assert templating.source_mark("air bnb") == ""
    assert templating.source_mark("airbnb!") == ""


def test_source_mark_vrbo_and_trip_are_text_only():
    assert templating.source_mark("vrbo") == ""
    assert templating.source_mark("trip") == ""


def test_source_mark_echalupy_uses_cropped_logo():
    html = templating.source_mark("echalupy")
    assert 'src="/static/platforms/echalupy.svg"' in html


def test_source_mark_monkeypatched_cache(tmp_path, monkeypatch):
    monkeypatch.setitem(templating._PLATFORM_LOGO_KEYS, "demo", "demo.png")
    html = templating.source_mark("demo")
    assert 'src="/static/platforms/demo.png"' in html
    monkeypatch.delitem(templating._PLATFORM_LOGO_KEYS, "demo", raising=False)


def test_stays_list_platform_badge_screenshots():
    """Acceptance screenshots: Airbnb, Booking and e-chalupy badges on /reservations (brief §7)."""
    import os
    import secrets
    import socket
    import threading
    import time
    from datetime import timedelta

    import pytest
    import uvicorn

    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.test_invoice_stay_browser import _browser_session_cookie, _launch

    from app import auth, claim, db
    from app.main import app

    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    if not shots:
        pytest.skip("set UBYHOST_SHOTS_DIR to capture acceptance screenshots")

    db.init_db()
    username = f"badges{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Badge Shots", username=username)
    today = claim.prague_today()
    now = db.utcnow()
    for source, tag in (("airbnb", "a"), ("booking", "b"), ("echalupy", "e")):
        apartment_id = db.insert(
            "apartment",
            {
                "internal_name": f"Flat {tag}",
                "owner_user_id": owner,
                "permalink_token": f"badge-{tag}-{secrets.token_hex(3)}",
                "automation_mode": "manual",
                "default_purpose": "10",
                "active": 1,
                "created_at": now,
            },
        )
        db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": source,
                "uid": f"badge-{tag}-{secrets.token_hex(4)}",
                "date_from": (today - timedelta(days=5)).isoformat(),
                "date_to": (today - timedelta(days=2)).isoformat(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"
    session = _browser_session_cookie(username)

    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for width in (360, 390, 1280):
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
            page = context.new_page()
            page.goto(base + "/reservations?lang=en")
            page.wait_for_load_state("networkidle")
            assert 'src="/static/platforms/airbnb.svg"' in page.content()
            assert 'src="/static/platforms/booking.svg"' in page.content()
            assert 'src="/static/platforms/echalupy.svg"' in page.content()
            os.makedirs(shots, exist_ok=True)
            page.screenshot(
                path=os.path.join(shots, f"stays-platform-badges-{width}.png"),
                full_page=True,
            )
            context.close()
        browser.close()
    server.should_exit = True
    thread.join(timeout=5)
