# 0027: The door-lock guide shows annotated screenshots

Status: todo
Depends on: PR #325 merged (the Digital door lock pages) | Base commit: `main` after PR #325 | Branch: task/0027-door-lock-guide-screenshots
Executor: Claude Haiku 5.5, effort high (or Cursor composer, Kimi, GLM) | Fits one session

## 1. Objective

The Help guide's "Digital door lock" steps get four screenshots, in English and Czech, with orange numbered markers and arrows on what to tap. The pictures are made by a script from fake data, so they can be remade whenever the page changes.

## 2. Context

Owner request 2026-10-09: use screenshots for an easy TTLock setup guide, with arrows.

Why not the PR #325 screenshots: they show the "Mock" banner, notification pop-ups over the steps and a real staging lock username. This repo is **public** (rule 3): the pictures must show only the fake names below.

Rules: 3 (fake data only), 4 (no new dependency: Pillow is in `App/requirements.lock`, Playwright is already used by `tests/test_host_geometry.py`), 6 (light mode), 7 (template + CSS change: browser and geometry tests, 0 skipped, screenshots in the report), 9 (alt text says what is marked; it does not repeat the step).

Fake data used everywhere: host "Guide Host", property "Sunny Flat", lock "Front door" ID 10000001, UbyHost name `hjhfa_uh1234abcd` (the example the guide text already uses).

Pictures (made in step 1), and where they go in the guide:

| Shot | Page section | Markers | Shown under guide step |
|---|---|---|---|
| `connect` | `/smart-locks` `#smart-locks-setup` | 1 terms checkbox, 2 Connect my lock | 2 |
| `name` | `/smart-locks` `#smart-locks-share` | 1 copy button | 2 |
| `connected` | `/smart-locks` `#smart-locks-list` | 1 the ✓ Connected line, 2 Check connection | 7 |
| `property` | `/apartments/<id>` `#door-code` | 1 switch on, 2 lock, 3 check-in time | 8 |

Steps 3 to 6 happen in the TTLock phone app. They get pictures later, from the owner's phone (see Owner steps); do not invent them.

Anchor D1, `App/app/templates/guide.html` (exactly once):
```html
      <ol class="guide-steps">{% for n in range(1, 10) %}<li><strong>{{ t('guide.door_codes.step' ~ n ~ '_title') }}:</strong> {{ t('guide.door_codes.step' ~ n) }}</li>{% endfor %}</ol>
```
Anchor D2, `App/app/static/app.css` (exactly once):
```css
.guide-steps { margin: 0; padding-left: 1.2rem; display: grid; gap: 10px; }
```
Anchor D3, `App/app/guide_i18n.py`: the line starting `        "guide.door_codes.step9_title":` appears exactly twice (English block first, Czech second).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/guide_shots.py` | create | the picture script (full code in step 1; not collected by a normal test run because its name does not start with `test_`) |
| `App/app/static/guide/door-lock-{connect,name,connected,property}-{en,cs}.png` | create (by the script) | 8 pictures |
| `App/app/templates/guide.html` | edit | pictures under steps 2, 7, 8 |
| `App/app/static/app.css` | edit | one rule |
| `App/app/guide_i18n.py` | edit | 4 alt texts × 2 languages |
| `App/tests/test_guide_door_lock_images.py` | create | 3 tests (full code in step 6) |
| `docs/tasks/0027-screenshots/guide-{360,390,1280}.png` | create (by the script) | rule 7 screenshots |
| `docs/tasks/0027-report.md` | create | report |

No other file may change.

## 4. Steps

1. Create `App/tests/guide_shots.py` with exactly this content:
```python
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
```
2. Replace anchor D1 with:
```html
      {% set door_shots = {2: ['connect', 'name'], 7: ['connected'], 8: ['property']} %}
      {% set shot_lang = 'cs' if lang == 'cs' else 'en' %}
      <ol class="guide-steps">{% for n in range(1, 10) %}<li><strong>{{ t('guide.door_codes.step' ~ n ~ '_title') }}:</strong> {{ t('guide.door_codes.step' ~ n) }}{% for shot in door_shots.get(n, []) %}<figure class="guide-shot"><img src="/static/guide/door-lock-{{ shot }}-{{ shot_lang }}.png?v=20261009" alt="{{ t('guide.door_codes.shot_' ~ shot) }}" loading="lazy"></figure>{% endfor %}</li>{% endfor %}</ol>
```
3. After anchor D2 add this line:
```css
.guide-shot { margin: 12px 0 4px; } .guide-shot img { display: block; max-width: 100%; height: auto; border: 1px solid var(--border); border-radius: var(--radius-lg); }
```
4. In `guide_i18n.py`, directly **above the first** D3 line (English) insert:
```python
        "guide.door_codes.shot_connect": 'Marked: 1 the door-code terms box, 2 the Connect my lock button.',
        "guide.door_codes.shot_name": 'Marked: the copy button next to your UbyHost name.',
        "guide.door_codes.shot_connected": 'Marked: 1 the Connected line of your lock, 2 the Check connection button.',
        "guide.door_codes.shot_property": 'Marked: 1 switch on door codes, 2 choose the lock, 3 the check-in time.',
```
and directly **above the second** D3 line (Czech) insert:
```python
        "guide.door_codes.shot_connect": 'Vyznačeno: 1 políčko s podmínkami kódů ke dveřím, 2 tlačítko Připojit můj zámek.',
        "guide.door_codes.shot_name": 'Vyznačeno: tlačítko pro zkopírování vašeho jména UbyHost.',
        "guide.door_codes.shot_connected": 'Vyznačeno: 1 řádek Připojeno u vašeho zámku, 2 tlačítko Zkontrolovat připojení.',
        "guide.door_codes.shot_property": 'Vyznačeno: 1 zapnutí kódů ke dveřím, 2 výběr zámku, 3 čas příjezdu.',
```
5. From `App/`: `.venv/bin/python -m pytest tests/guide_shots.py -q` → `1 passed`. Then open each of the 8 pictures in `app/static/guide/` and the 3 in `docs/tasks/0027-screenshots/`, and check: every marker sits on its target; the only names visible are Guide Host, Sunny Flat, Front door, 10000001, hjhfa_uh1234abcd or hjhfa_uh5678efgh; no pop-up, no "Mock" banner. A marker in the wrong place or any other name → STOP (§8).
6. Create `App/tests/test_guide_door_lock_images.py` with exactly this content:
```python
"""The door-lock guide pictures exist, are small, and have alt text (task 0027)."""
from pathlib import Path

from app.guide_i18n import GUIDE_STRINGS

APP = Path(__file__).resolve().parent.parent / "app"
SHOTS = ("connect", "name", "connected", "property")


def test_every_picture_exists_in_both_languages_and_stays_small():
    for shot in SHOTS:
        for lang in ("en", "cs"):
            path = APP / "static" / "guide" / f"door-lock-{shot}-{lang}.png"
            assert path.exists(), path
            assert path.stat().st_size < 400_000, path


def test_every_picture_has_alt_text_in_both_languages():
    for lang in ("en", "cs"):
        for shot in SHOTS:
            assert GUIDE_STRINGS[lang][f"guide.door_codes.shot_{shot}"].strip()


def test_the_guide_shows_the_pictures():
    template = (APP / "templates" / "guide.html").read_text(encoding="utf-8")
    assert "/static/guide/door-lock-" in template
    assert 'class="guide-shot"' in template
```
7. Run the §6 commands in order.

## 5. Do not touch

`smart_locks.html`, `apartment_form.html`, routes, any other guide section, the PR #325 screenshot folder. Rule 3: never put a real name, e-mail, lock ID or username in a picture. Rule 6: light mode only.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/guide_shots.py -q` → `1 passed` (if Chromium is missing: do not install anything, STOP).
- `.venv/bin/python -m pytest tests/test_guide_door_lock_images.py -q` → `3 passed`.
- `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_wp28_geometry.py tests/test_download_skeleton_browser.py -q -rs` → 0 failed, no `SKIPPED` line.
- `.venv/bin/python -m pytest tests -q` → 0 failed apart from the four DNS tests listed in 0023 §2.

From the repo root: `python3 scripts/context_lint.py` → last line `context lint: OK`.

## 7. Acceptance

- [ ] 8 PNGs in `App/app/static/guide/`, each under 400 KB; 3 PNGs in `docs/tasks/0027-screenshots/`.
- [ ] Step 5's visual check is done and written in the report, one line per picture.
- [ ] §6 passes as stated.
- [ ] `git diff --stat main` lists only §3 files.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found as stated; a selector in step 1 finds nothing (write which one); a marker is off its target; a picture shows any other name; Chromium is missing; a test fails twice; a file outside §3 needs a change; a step is unclear; you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0027-report.md` (1,500 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, the step 5 check per picture, deviations, questions, owner steps left.

## Risk list (for the reviewer)

Look at all 11 pictures (names, marker placement); `guide.html` (pictures only under steps 2, 7, 8; alt text from `guide_i18n`).

## Owner steps

1. For steps 3 to 6 (the TTLock phone app), take these phone screenshots, crop out your e-mail and real lock name if you can, and upload them in a chat with the orchestrator: the lock screen with the Authorized Admin icon; the Authorized Admin list with Create Admin; the filled form (Permanent, Recipient, Name); the "Manage their own users only" switch with Send. The orchestrator then writes a short brief to add them with markers.
