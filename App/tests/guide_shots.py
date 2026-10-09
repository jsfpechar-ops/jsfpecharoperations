"""Makes the annotated door-lock pictures for the Help guide (task 0027).

Not part of the normal test run (the name does not start with test_). Run it
from App/ when the Digital door lock pages change:

    .venv/bin/python -m pytest tests/guide_shots.py -q

The repo is public: only the fake names below ever appear in a picture.
"""
from __future__ import annotations

import io
import json
import math
import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

import playwright.sync_api as sync_api

from app import auth, config, db
from app.main import app
from tests.conftest import login_as

APP_DIR = Path(__file__).resolve().parent.parent
OUT = APP_DIR / "app" / "static" / "guide"
PAGE_SHOTS = APP_DIR.parent / "docs" / "tasks" / "0027-screenshots"
SCALE = 2  # device pixels per CSS pixel, so the pictures stay sharp
WIDTH = 760
MARGIN = 28  # CSS pixels of page around each section
MARK = (214, 74, 26)
LOCK = {"lock_id": "10000001", "alias": "Front door", "battery": 90, "tz_offset_ms": 3600000}
USERS = ("guide-connect", "guide-share", "guide-list")


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
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _remove(username):
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (username,)):
        oid = row["id"]
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _host(username, *, receiver=None, locks=None, lock_on_property=False):
    """A fake host. Returns the id of their one property."""
    _remove(username)
    owner = auth.create_account(f"{username}@example.test", "Guide Host", username=username)
    now = db.utcnow()
    entity = db.insert(
        "legal_entity",
        {"name": "Guide Host", "seat": "Praha", "created_at": now, "owner_user_id": owner},
    )
    fields = {
        "legal_entity_id": entity,
        "owner_user_id": owner,
        "internal_name": "Sunny Flat",
        "permalink_token": f"{username}-tok",
        "automation_mode": "manual",
        "default_purpose": "10",
        "active": 1,
        "created_at": now,
    }
    if lock_on_property:
        fields.update(
            {"lock_provider": "ttlock", "lock_id": LOCK["lock_id"], "checkin_hour": 15, "checkout_hour": 10}
        )
    apartment = db.insert("apartment", fields)
    if receiver:
        db.insert(
            "lock_account",
            {
                "owner_user_id": owner,
                "provider": "ttlock",
                "username": receiver,
                "status": "ok",
                "locks_json": json.dumps(locks or []),
                "created_at": now,
                "updated_at": now,
            },
        )
    return apartment


def _session(username):
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client.cookies.get(auth.SESSION_COOKIE)


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _arrow(draw, start, tip):
    draw.line([start, tip], fill=MARK, width=4 * SCALE)
    angle = math.atan2(tip[1] - start[1], tip[0] - start[0])
    size = 13 * SCALE
    left = (tip[0] - size * math.cos(angle - 0.5), tip[1] - size * math.sin(angle - 0.5))
    right = (tip[0] - size * math.cos(angle + 0.5), tip[1] - size * math.sin(angle + 0.5))
    draw.polygon([tip, left, right], fill=MARK)


def _annotate(png, marks):
    """A ring around each target, a numbered badge, and an arrow from badge to ring."""
    image = Image.open(io.BytesIO(png)).convert("RGB")
    draw = ImageDraw.Draw(image)
    radius = 17 * SCALE
    pad = 6 * SCALE
    font = _font(20 * SCALE)
    for number, (x, y, w, h) in marks:
        x, y, w, h = (v * SCALE for v in (x, y, w, h))
        ring = [x - pad, y - pad, x + w + pad, y + h + pad]
        draw.rounded_rectangle(ring, radius=10 * SCALE, outline=MARK, width=3 * SCALE)
        if ring[0] - 90 * SCALE > radius:  # room on the left: badge left, arrow right
            cx, cy = ring[0] - 70 * SCALE, (ring[1] + ring[3]) / 2
            start, tip = (cx + radius, cy), (ring[0], cy)
        elif ring[1] - 80 * SCALE > radius:  # else above
            cx, cy = ring[0] + 24 * SCALE, ring[1] - 56 * SCALE
            start, tip = (cx, cy + radius), (cx, ring[1])
        else:  # else below
            cx, cy = ring[0] + 24 * SCALE, ring[3] + 56 * SCALE
            start, tip = (cx, cy - radius), (cx, ring[3])
        _arrow(draw, start, tip)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=MARK)
        draw.text((cx, cy), str(number), fill="white", font=font, anchor="mm")
    return image


def _shoot(page, section, targets, out_path):
    page.evaluate("window.scrollTo(0, 0)")
    box = page.locator(section).bounding_box()
    assert box, f"section {section} not on the page"
    left = max(box["x"] - MARGIN, 0)
    top = max(box["y"] - MARGIN, 0)
    clip = {
        "x": left,
        "y": top,
        "width": min(box["x"] + box["width"] + MARGIN, WIDTH) - left,
        "height": box["y"] + box["height"] + MARGIN - top,
    }
    marks = []
    for number, selector in targets:
        target = page.locator(selector).first.bounding_box()
        assert target, f"target {selector} not on the page"
        marks.append(
            (number, (target["x"] - clip["x"], target["y"] - clip["y"], target["width"], target["height"]))
        )
    image = _annotate(page.screenshot(clip=clip), marks)
    image = image.quantize(colors=256)
    image.save(out_path, optimize=True)


def test_make_door_lock_guide_pictures(base, monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "DOOR_CODES_LIVE", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    _host("guide-connect")
    _host("guide-share", receiver="hjhfa_uh1234abcd")
    flat = _host("guide-list", receiver="hjhfa_uh5678efgh", locks=[LOCK], lock_on_property=True)
    shots = [
        ("connect", "guide-connect", "/smart-locks", "#smart-locks-setup",
         [(1, "#smart-locks-setup #terms"), (2, "#smart-locks-setup button[type=submit]")]),
        ("name", "guide-share", "/smart-locks", "#smart-locks-share",
         [(1, "#smart-locks-share [data-copy]")]),
        ("connected", "guide-list", "/smart-locks", "#smart-locks-list",
         [(1, "#smart-locks-list p:has-text('✓')"), (2, "#smart-locks-list button.btn.primary")]),
        ("property", "guide-list", f"/apartments/{flat}", "#door-code",
         [(1, "#door_codes"), (2, "#lock_id"), (3, "#checkin_hour")]),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    PAGE_SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for lang in ("en", "cs"):
            for name, username, path, section, targets in shots:
                context = browser.new_context(
                    viewport={"width": WIDTH, "height": 2600}, device_scale_factor=SCALE
                )
                context.add_cookies(
                    [{"name": auth.SESSION_COOKIE, "value": _session(username), "url": base + "/"}]
                )
                page = context.new_page()
                page.goto(f"{base}{path}?lang={lang}")
                page.wait_for_selector(section, timeout=30000)
                page.add_style_tag(content=".toast-stack { display: none !important; }")
                _shoot(page, section, targets, OUT / f"door-lock-{name}-{lang}.png")
                context.close()
        # Rule 7: the guide page itself at three widths, after the template change.
        for width in (360, 390, 1280):
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies(
                [{"name": auth.SESSION_COOKIE, "value": _session("guide-list"), "url": base + "/"}]
            )
            page = context.new_page()
            page.goto(f"{base}/guide?lang=en#door-codes")
            page.wait_for_selector(".guide-shot img")
            page.evaluate("document.querySelectorAll('.guide-shot img').forEach(i => { i.loading = 'eager'; })")
            page.wait_for_load_state("networkidle")
            page.locator("#door-codes").screenshot(path=str(PAGE_SHOTS / f"guide-{width}.png"))
            context.close()
        browser.close()
    for username in USERS:
        _remove(username)
    for name, *_ in shots:
        for lang in ("en", "cs"):
            assert (OUT / f"door-lock-{name}-{lang}.png").stat().st_size < 400_000
