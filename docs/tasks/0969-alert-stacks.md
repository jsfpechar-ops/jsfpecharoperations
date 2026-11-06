# 0969: Reduce repeated alert stacks without losing urgency (B11, finding S03)

Status: blocked (4 pre-existing failures in test_host_ux_acceptance.py, also on base 7b0355c; see docs/tasks/0969-report.md)
Depends on: none (B03, B10 are merged in the base) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0969-b11-alerts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Pages that are not about stays (Settings, Archive, Entities) and alerts of another property on a filtered Stays list show compact alert lines instead of a stack of large red cards, and alerts that are not about filing fold into the one dashboard line. Every filing alert (deadline, stay link, deadline text, dismiss) stays visible on every page at every width: this is presentation only.

## 2. Context

Worktree `/tmp/ubyhost-b11-worktree` already exists on branch `codex/0969-b11-alerts` at the base commit; work there, from `App/`. `App/.venv` is already a symlink to `/tmp/ubyhost-0958-worktree/App/.venv`; if `App/.venv/bin/python` is missing run `ln -s /tmp/ubyhost-0958-worktree/App/.venv /tmp/ubyhost-b11-worktree/App/.venv`.

Rules that apply (AGENTS.md): UbyPort filing correctness beats everything; light mode only; one explanation in one place; copy has no em dashes; no new dependency; no secrets or guest data in the repo. Template change: browser tests 0 skipped plus one 390 px screenshot per changed page, and the UX gate in AGENTS rule 10 is done by the reviewer, not you.

The one shared alert partial is `App/app/templates/_host_alerts.html` (40 lines). It is included by `reservations.html` line 26, `settings.html` line 11, `settings_archived.html` line 10, `entities.html` line 16, `reservation_detail.html` line 21, `dashboard.html` (with `alerts_expanded = true`) and by `base.html` line 83 for pages that do not include it themselves. `host_page.html` only has `{% block body %}` and needs NO change. Its current head (anchor):

```
{% if open_alerts %}
{% set red = open_alerts | selectattr('level', 'equalto', 'critical') | list %}
{% set rest = open_alerts | rejectattr('level', 'equalto', 'critical') | list %}
```
and `<article class="notification-bubble {{ alert.level }}{{ ' ph-hide' if ph_hide_pin | default(false) and alert.kind == 'guest_pin_rotated' else '' }}" data-notification>` and `{% if rest_count > 1 and not (alerts_expanded | default(false)) %}`.

What the patch does, all in the template (the alert rows themselves are untouched Python data):
- `request.url.path` decides the page: `/`, `/reservations`, `/reservations/<id>`, `/apartments/...` and any include with `alerts_expanded` keep today's large lines. Every other page is a "compact page".
- On `/reservations?apartment=N`, an alert whose `apartment_id` is another property is an "outside" alert: it keeps its title, deadline text, link and dismiss, gets `data-alert-scope="workspace"` and a small label `notification.workspace.label`.
- Compact page and outside alerts lose only the `notification-action` line (the whole line still links to the fix). They are marked `data-alert-compact`.
- Only these kinds fold into the existing dashboard summary line (`/#needs-action`) on compact pages or when outside: `guest_pin_rotated`, `guest_pin_abuse`, `guest_pin_locked_out`, `guest_pin_challenged`, `guest_question`, `ttlock_budget`. Every other kind (all filing kinds, deadline, submission_*, feed_*, job_failed, turnstile) is never folded.
- Alert generation, persistence, dismissal route, send readiness and retry rules are NOT touched. Existing tests read `data-notification>` literally, so the new attributes sit before `data-notification`.

If an anchor above is not found verbatim, STOP (section 8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_host_alerts.html | edit (patch A) | compact and workspace presentation |
| App/app/host_i18n.py | edit (patch A) | key `notification.workspace.label` in en and cs |
| App/app/host_vi_i18n.py | edit (patch A) | same key in vi |
| App/tests/test_host_alert_stack_browser.py | new (patch B) | Chromium tests |
| App/tests/static_versions.json | only if `test_static_versions.py` fails | regenerate, expected unchanged because no static file changes |
| docs/tasks/0969-report.md | new | the report |

No other file may change. Not `host_page.html`, not CSS, not Python outside the two i18n files.

## 4. Steps

### Step 1: add the tests first and prove the baseline on the OLD template

From the repo root `/tmp/ubyhost-b11-worktree`:

```bash
git apply <<'PATCH_B_END'
diff --git a/App/tests/test_host_alert_stack_browser.py b/App/tests/test_host_alert_stack_browser.py
new file mode 100644
index 00000000..ea0b0b0a
--- /dev/null
+++ b/App/tests/test_host_alert_stack_browser.py
@@ -0,0 +1,331 @@
+"""0969: repeated alert stacks stay compact, filing urgency stays fully visible.
+
+Presentation only. Every deadline alert (its stay link, title and deadline text)
+must be on every host page at every width; pages that are not about stays and
+alerts of another property on a filtered Stays list show compact lines.
+"""
+from __future__ import annotations
+
+import os
+import secrets
+import socket
+import threading
+import time
+from datetime import timedelta
+from pathlib import Path
+
+import pytest
+
+REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
+if REQUIRE_BROWSER:
+    import playwright.sync_api as sync_api
+else:
+    sync_api = pytest.importorskip("playwright.sync_api")
+
+import uvicorn
+from fastapi.testclient import TestClient
+
+from app import alerts, auth, claim, db, onboarding
+from app.main import app
+from tests.browser_support import chromium_launch_kwargs
+from tests.conftest import login_as
+
+SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b11")
+WIDTHS = (390, 768, 1280)
+
+READ_JS = """() => {
+  const rows = [...document.querySelectorAll('[data-host-alerts] article[data-notification]')].map(a => {
+    const box = a.getBoundingClientRect();
+    const link = a.querySelector('a.notification-link');
+    const reasons = [...a.querySelectorAll('small')]
+      .filter(s => !s.classList.contains('notification-action') && !s.hasAttribute('data-workspace-label'))
+      .map(s => s.textContent.trim());
+    const label = a.querySelector('[data-workspace-label]');
+    return {
+      id: a.dataset.alertId, scope: a.dataset.alertScope || '', compact: a.hasAttribute('data-alert-compact'),
+      title: a.querySelector('strong').textContent.trim(), reasons: reasons,
+      href: link ? link.getAttribute('href') : '', action: !!a.querySelector('.notification-action'),
+      label: label ? label.textContent.trim() : '', dismiss: !!a.querySelector('form[data-notification-dismiss]'),
+      h: box.height, right: box.right, left: box.left,
+    };
+  });
+  const summary = document.querySelector('[data-host-alerts] [data-notification-summary]');
+  return {rows: rows, summary: summary ? summary.textContent.trim() : '',
+          summaryHref: summary ? summary.querySelector('a').getAttribute('href') : '',
+          overflow: document.documentElement.scrollWidth - innerWidth, width: innerWidth,
+          stack: !!document.querySelector('[data-host-alerts]')};
+}"""
+
+
+@pytest.fixture(scope="module")
+def base():
+    db.init_db()
+    with socket.socket() as sock:
+        sock.bind(("127.0.0.1", 0))
+        port = sock.getsockname()[1]
+    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
+    thread = threading.Thread(target=server.run, daemon=True)
+    thread.start()
+    deadline = time.time() + 15
+    while not server.started and time.time() < deadline:
+        time.sleep(0.05)
+    if not server.started:
+        pytest.fail("the alert stack test server did not start")
+    yield f"http://127.0.0.1:{port}"
+    server.should_exit = True
+    thread.join(timeout=5)
+
+
+@pytest.fixture(scope="module")
+def browser():
+    with sync_api.sync_playwright() as playwright:
+        try:
+            instance = playwright.chromium.launch(**chromium_launch_kwargs())
+        except Exception:
+            if REQUIRE_BROWSER:
+                raise
+            pytest.skip("Chromium is required for alert stack coverage")
+        yield instance
+        instance.close()
+
+
+@pytest.fixture
+def workspace():
+    """Factory: a host with two properties, overdue stays, deadline alerts and two foldable alerts."""
+    made = []
+
+    def build(tag, karlin=2, vinohrady=1, foldable=True):
+        username = f"b11-{tag}-{secrets.token_hex(4)}"
+        owner_id = auth.create_account(
+            f"{username}@example.test", "B11 Alerts", role="host", username=username
+        )
+        now = db.utcnow()
+        entity_id = db.insert("legal_entity", {
+            "name": "B11 Alerts s.r.o.", "seat": "Praha", "ico": "11223344",
+            "contact_email": "b11@example.test", "owner_user_id": owner_id, "created_at": now,
+        })
+
+        def prop(name):
+            return db.insert("apartment", {
+                "legal_entity_id": entity_id, "owner_user_id": owner_id, "internal_name": name,
+                "permalink_token": f"b11{secrets.token_hex(4)}", "permalink_pin": "123456",
+                "automation_mode": "manual", "submit_after_hours": 24, "active": 1, "created_at": now,
+            })
+
+        karlin_id, vinohrady_id = prop("Karlin Flat"), prop("Vinohrady Flat")
+        today = claim.prague_today()
+
+        def overdue_stay(apartment_id, index):
+            start = today - timedelta(days=10 + index)
+            reservation_id = db.insert("reservation", {
+                "apartment_id": apartment_id, "source": "manual",
+                "uid": f"b11-{apartment_id}-{index}-{secrets.token_hex(3)}",
+                "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
+                "expected_guests_override": 1, "status": "active", "created_at": now, "updated_at": now,
+            })
+            alerts.raise_alert(
+                "critical", "deadline", f"Deadline {reservation_id}", apartment_id=apartment_id,
+                reservation_id=reservation_id, owner_user_id=owner_id,
+                dedupe_key=f"deadline:{reservation_id}",
+            )
+            return reservation_id
+
+        stays = [overdue_stay(karlin_id, i) for i in range(karlin)]
+        stays += [overdue_stay(vinohrady_id, 10 + i) for i in range(vinohrady)]
+        if foldable:
+            alerts.raise_alert(
+                "critical", "guest_pin_abuse", "Guest link tried too often",
+                apartment_id=vinohrady_id, owner_user_id=owner_id,
+                dedupe_key=f"guest_pin_abuse:{vinohrady_id}",
+            )
+        onboarding.set_dismissed(owner_id, True)
+        client = TestClient(app)
+        response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
+        assert response.status_code == 303, response.text
+        cards = [
+            card for card in alerts.present_many(alerts.open_alerts(owner_id), "en")
+            if card["kind"] == "deadline"
+        ]
+        made.append((owner_id, entity_id, [karlin_id, vinohrady_id]))
+        return {
+            "cookie": client.cookies.get(auth.SESSION_COOKIE), "owner": owner_id,
+            "karlin": karlin_id, "vinohrady": vinohrady_id, "stays": stays,
+            # Issue ids (the stay in the link) and deadline texts every page must keep showing.
+            "expected": {
+                (card["action_href"], card["display_title"], card["display_reason"]) for card in cards
+            },
+        }
+
+    yield build
+    for owner_id, entity_id, apartment_ids in made:
+        db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
+        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
+        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
+        for apartment_id in apartment_ids:
+            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
+            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
+        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
+        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))
+
+
+def _visit(browser, base, ws, path, width):
+    context = browser.new_context(viewport={"width": width, "height": 900})
+    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["cookie"], "url": base + "/"}])
+    page = context.new_page()
+    errors = []
+    page.on("pageerror", lambda error: errors.append(str(error)))
+    joiner = "&" if "?" in path else "?"
+    page.goto(f"{base}{path}{joiner}lang=en")
+    page.wait_for_load_state("networkidle")
+    later = page.locator("#security-prompt [data-security-prompt-later]")
+    if later.is_visible():
+        later.click()
+    page.evaluate("window.scrollTo(0, 0)")
+    return context, page, errors
+
+
+def _read(browser, base, ws, path, width, shot=None):
+    context, page, errors = _visit(browser, base, ws, path, width)
+    try:
+        data = page.evaluate(READ_JS)
+        if shot:
+            SHOTS.mkdir(parents=True, exist_ok=True)
+            page.screenshot(path=str(SHOTS / f"{shot}-{width}.png"))
+        assert not errors, errors
+        return data
+    finally:
+        context.close()
+
+
+def _filing(data, ws):
+    """The deadline alerts on a page as (stay link, title, deadline text) keys."""
+    wanted = {key[0] for key in ws["expected"]}
+    return [
+        (row["href"], row["title"], row["reasons"][0] if row["reasons"] else "")
+        for row in data["rows"] if row["href"] in wanted
+    ]
+
+
+def _pages(ws):
+    return [
+        "/reservations", f"/reservations?apartment={ws['karlin']}",
+        f"/reservations?apartment={ws['vinohrady']}", "/settings", "/settings/archived", "/entities",
+    ]
+
+
+# --- baseline: must pass before and after the template change -------------------------------
+
+def test_same_filing_issues_and_deadlines_on_every_page(browser, base, workspace):
+    ws = workspace("same")
+    assert len(ws["expected"]) == 3
+    for width in WIDTHS:
+        for path in _pages(ws):
+            data = _read(browser, base, ws, path, width)
+            found = _filing(data, ws)
+            assert len(found) == 3, (path, width, found)
+            assert set(found) == ws["expected"], (path, width, found, ws["expected"])
+            assert data["overflow"] <= 1, (path, width, data["overflow"])
+            for row in data["rows"]:
+                if row["href"] in {key[0] for key in ws["expected"]}:
+                    assert row["dismiss"], (path, width, row["href"])
+                    assert row["right"] <= width + 1 and row["left"] >= -1, (path, width, row)
+
+
+def test_zero_alerts_render_no_stack(browser, base, workspace):
+    ws = workspace("zero", karlin=0, vinohrady=0, foldable=False)
+    for path in ("/reservations", "/settings"):
+        data = _read(browser, base, ws, path, 390, shot="zero-stays" if path == "/reservations" else None)
+        assert data["stack"] is False and data["rows"] == [], (path, data)
+
+
+# --- 0969 behaviour ---------------------------------------------------------------------------
+
+def test_one_alert_is_large_on_stays_and_compact_elsewhere(browser, base, workspace):
+    ws = workspace("one", karlin=1, vinohrady=0, foldable=False)
+    stays = _read(browser, base, ws, "/reservations", 390, shot="one-stays")
+    settings = _read(browser, base, ws, "/settings", 390, shot="one-settings")
+    assert len(stays["rows"]) == 1 and len(settings["rows"]) == 1
+    large, small = stays["rows"][0], settings["rows"][0]
+    assert large["action"] and not large["compact"] and large["scope"] == ""
+    assert small["compact"] and not small["action"]
+    assert (large["href"], large["title"], large["reasons"]) == (small["href"], small["title"], small["reasons"])
+    assert small["h"] < large["h"], (small["h"], large["h"])
+
+
+def test_many_alerts_keep_every_deadline_and_fold_only_non_filing(browser, base, workspace):
+    ws = workspace("many")
+    for width in WIDTHS:
+        stays = _read(browser, base, ws, "/reservations", width, shot="many-stays")
+        settings = _read(browser, base, ws, "/settings", width, shot="many-settings")
+        # Stays page: the guest link alert is a line of its own, nothing is folded.
+        assert any("Guest link" in row["title"] for row in stays["rows"]), stays["rows"]
+        # Settings: the guest link alert folds into the one dashboard line; the 3 deadlines stay.
+        assert not any("Guest link" in row["title"] for row in settings["rows"]), settings["rows"]
+        assert settings["summary"] and settings["summaryHref"] == "/#needs-action", settings
+        assert set(_filing(settings, ws)) == ws["expected"]
+        assert all(row["compact"] and not row["action"] for row in settings["rows"])
+        stays_h = {row["href"]: row["h"] for row in stays["rows"]}
+        for row in settings["rows"]:
+            assert row["h"] < stays_h[row["href"]], (width, row["href"], row["h"], stays_h[row["href"]])
+        assert settings["overflow"] <= 1 and stays["overflow"] <= 1
+
+
+def test_filtered_property_labels_alerts_of_other_properties(browser, base, workspace):
+    ws = workspace("filter")
+    for width in WIDTHS:
+        data = _read(
+            browser, base, ws, f"/reservations?apartment={ws['karlin']}", width, shot="filtered-karlin"
+        )
+        mine = [r for r in data["rows"] if "Karlin" in r["title"]]
+        other = [r for r in data["rows"] if "Vinohrady" in r["title"]]
+        assert len(mine) == 2 and len(other) == 1, data["rows"]
+        for row in mine:
+            assert row["scope"] == "" and not row["compact"] and row["action"] and row["label"] == ""
+        for row in other:
+            assert row["scope"] == "workspace" and row["compact"] and not row["action"]
+            assert "Workspace alert" in row["label"], row
+            assert row["reasons"] and row["href"].startswith("/reservations/") and row["dismiss"]
+        # The other property's non-filing alert folds into the dashboard line; its deadline does not.
+        assert not any("Guest link" in r["title"] for r in data["rows"])
+        assert data["summary"] and data["summaryHref"] == "/#needs-action"
+        assert set(_filing(data, ws)) == ws["expected"]
+        assert data["overflow"] <= 1
+    unfiltered = _read(browser, base, ws, "/reservations", 1280)
+    assert all(row["scope"] == "" for row in unfiltered["rows"])
+    # Filtered by the other property, the first property's alerts are the workspace ones.
+    elsewhere = _read(browser, base, ws, f"/reservations?apartment={ws['vinohrady']}", 1280, shot="filtered-vinohrady")
+    assert len([r for r in elsewhere["rows"] if r["scope"] == "workspace"]) == 2
+    assert set(_filing(elsewhere, ws)) == ws["expected"]
+
+
+def test_dismissal_and_return_navigation_keep_the_filter_and_the_rest(browser, base, workspace):
+    ws = workspace("dismiss")
+    path = f"/reservations?apartment={ws['karlin']}"
+    context, page, errors = _visit(browser, base, ws, path, 390)
+    try:
+        before = page.evaluate(READ_JS)
+        mine = [r for r in before["rows"] if "Karlin" in r["title"] and r["dismiss"]]
+        assert mine, before["rows"]
+        gone = mine[0]
+        page.locator(f'[data-alert-id="{gone["id"]}"] [data-notification-dismiss] button').click()
+        page.wait_for_selector(f'[data-alert-id="{gone["id"]}"]', state="detached")
+        page.reload()
+        page.wait_for_load_state("networkidle")
+        assert f"apartment={ws['karlin']}" in page.url
+        after = page.evaluate(READ_JS)
+        left = {r["id"] for r in after["rows"]}
+        assert gone["id"] not in left
+        assert left == {r["id"] for r in before["rows"]} - {gone["id"]}
+        assert db.query_one("SELECT user_dismissed FROM alert WHERE id = ?", (int(gone["id"]),))["user_dismissed"] == 1
+        # Leave for Settings and come back: same filter, same remaining alerts, label still there.
+        page.goto(f"{base}/settings?lang=en")
+        page.wait_for_load_state("networkidle")
+        page.go_back()
+        page.wait_for_load_state("networkidle")
+        assert f"apartment={ws['karlin']}" in page.url
+        back = page.evaluate(READ_JS)
+        assert {r["id"] for r in back["rows"]} == left
+        assert any(r["scope"] == "workspace" and "Workspace alert" in r["label"] for r in back["rows"])
+        assert not errors, errors
+    finally:
+        context.close()
PATCH_B_END
git status --short | tail -5
```
Expected: only `App/tests/test_host_alert_stack_browser.py` is new. Then, from `App/`:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b11 .venv/bin/python -m pytest tests/test_host_alert_stack_browser.py -k "same_filing or zero_alerts" -q -rs --tb=short -x 2>&1 | tail -30
```
Expected: 2 passed (this is the BEFORE record: the same 3 stay links, titles and deadline texts on 6 pages and 3 widths, with the old template). Then run the whole file once, `-k "not (same_filing or zero_alerts)"`: expected 4 failed (the new behaviour, not yet built); do not fix them. Note the counts for the report. Commit: `git add App/tests/test_host_alert_stack_browser.py && git commit -m "0969 step 1"`.

### Step 2: apply the template and copy patch

From `/tmp/ubyhost-b11-worktree`:

```bash
git apply <<'PATCH_A_END'
diff --git a/App/app/host_i18n.py b/App/app/host_i18n.py
index b265a7d7..097df8fc 100644
--- a/App/app/host_i18n.py
+++ b/App/app/host_i18n.py
@@ -9280,11 +9280,13 @@ _SUMMARY_0280_STRINGS = {
         "notification.summary.count": "%(n)s alerts need you",
         "notification.summary.more": "%(n)s more alerts",
         "notification.summary.open": "Open the dashboard",
+        "notification.workspace.label": "Workspace alert, another property",
     },
     "cs": {
         "notification.summary.count": "Upozornění k vyřízení: %(n)s",
         "notification.summary.more": "Další upozornění: %(n)s",
         "notification.summary.open": "Otevřít přehled",
+        "notification.workspace.label": "Upozornění pracovního prostoru, jiné ubytování",
     },
 }
 for _lang, _strings in _SUMMARY_0280_STRINGS.items():
diff --git a/App/app/host_vi_i18n.py b/App/app/host_vi_i18n.py
index 28f23a46..7db2d1d5 100644
--- a/App/app/host_vi_i18n.py
+++ b/App/app/host_vi_i18n.py
@@ -4026,6 +4026,7 @@ STRINGS.update({
     "notification.summary.count": "%(n)s cảnh báo cần bạn xử lý",
     "notification.summary.more": "Thêm %(n)s cảnh báo",
     "notification.summary.open": "Mở trang tổng quan",
+    "notification.workspace.label": "Cảnh báo chung của không gian làm việc, chỗ ở khác",
 })
 
 # 0282: the locked signature and its signing dialog.
diff --git a/App/app/templates/_host_alerts.html b/App/app/templates/_host_alerts.html
index 82e43243..b5851626 100644
--- a/App/app/templates/_host_alerts.html
+++ b/App/app/templates/_host_alerts.html
@@ -1,21 +1,38 @@
 {#- 0280: off the dashboard, only red alerts get a line of their own, each one
     short line plus the link to its fix. Everything else is one line that opens
-    the dashboard's "What needs you" card. -#}
+    the dashboard's "What needs you" card.
+    0969: presentation only. Pages that are not about stays (settings, archive,
+    entities...) show every alert as a compact line (no action line, the whole
+    line still links to the fix) and fold alerts that are not about filing into
+    the one dashboard line. On /reservations?apartment=N an alert of another
+    property is a compact line labelled as a workspace alert. A filing alert is
+    never folded or hidden. -#}
 {% if open_alerts %}
-{% set red = open_alerts | selectattr('level', 'equalto', 'critical') | list %}
-{% set rest = open_alerts | rejectattr('level', 'equalto', 'critical') | list %}
+{% set path = request.url.path if request is defined and request else '' %}
+{% set scope = (request.query_params.get('apartment', '') if path == '/reservations' else '') | string %}
+{% set compact_page = not (alerts_expanded | default(false)) and path != '/' and path != '/reservations' and not path.startswith('/reservations/') and not path.startswith('/apartments/') %}
+{% set foldable_kinds = ['guest_pin_rotated', 'guest_pin_abuse', 'guest_pin_locked_out', 'guest_pin_challenged', 'guest_question', 'ttlock_budget'] %}
+{% set held = namespace(outside=[], shown=[], folded=[]) %}
+{% for item in open_alerts %}
+  {% if scope and item.apartment_id and (item.apartment_id | string) != scope %}{% set _ = held.outside.append(item.id) %}{% endif %}
+  {% if (compact_page or item.id in held.outside) and item.kind in foldable_kinds %}{% set _ = held.folded.append(item) %}{% else %}{% set _ = held.shown.append(item) %}{% endif %}
+{% endfor %}
+{% set red = held.shown | selectattr('level', 'equalto', 'critical') | list %}
+{% set rest = held.shown | rejectattr('level', 'equalto', 'critical') | list %}
 {% set rest_pin = rest | selectattr('kind', 'equalto', 'guest_pin_rotated') | list %}
-{% set rest_count = (rest | rejectattr('kind', 'equalto', 'guest_pin_rotated') | list | length) + (1 if rest_pin else 0) %}
-{% set lines = red + (rest if (rest_count == 1 or alerts_expanded | default(false)) else []) %}
+{% set rest_count = (rest | rejectattr('kind', 'equalto', 'guest_pin_rotated') | list | length) + (1 if rest_pin else 0) + (held.folded | length) %}
+{% set rest_inline = alerts_expanded | default(false) or (rest_count == 1 and not held.folded) %}
+{% set lines = red + (rest if rest_inline else []) %}
 <aside class="notification-stack{{ ' ph-hide' if ph_hide_pin | default(false) and (lines | rejectattr('kind', 'equalto', 'guest_pin_rotated') | list | length == 0) else '' }}" data-host-alerts aria-label="{{ t('a11y.notifications') }}" aria-live="polite">
   {% for alert in lines if alert.kind != 'guest_pin_rotated' or alert.id == (rest_pin[0].id if rest_pin else alert.id) %}
-    <article class="notification-bubble {{ alert.level }}{{ ' ph-hide' if ph_hide_pin | default(false) and alert.kind == 'guest_pin_rotated' else '' }}" data-notification>
+    <article class="notification-bubble {{ alert.level }}{{ ' ph-hide' if ph_hide_pin | default(false) and alert.kind == 'guest_pin_rotated' else '' }}" data-alert-id="{{ alert.id }}"{% if alert.id in held.outside %} data-alert-scope="workspace"{% endif %}{% if compact_page or alert.id in held.outside %} data-alert-compact{% endif %} data-notification>
       {% if alert.action_href %}<a class="notification-link" href="{{ alert.action_href }}">{% else %}<div class="notification-link">{% endif %}
         <span class="notification-icon" aria-hidden="true">!</span>
         <span class="grow">
           <strong>{{ alert.display_title or alert.message }}</strong>
           {% if alert.display_reason %}<small>{{ alert.display_reason }}</small>{% endif %}
-          {% if alert.action_label_key %}<small class="notification-action">{{ t(alert.action_label_key) }}</small>{% endif %}
+          {% if alert.id in held.outside %}<small class="notification-scope" data-workspace-label>{{ t('notification.workspace.label') }}</small>{% endif %}
+          {% if alert.action_label_key and not (compact_page or alert.id in held.outside) %}<small class="notification-action">{{ t(alert.action_label_key) }}</small>{% endif %}
         </span>
       {% if alert.action_href %}</a>{% else %}</div>{% endif %}
       {% if alert.kind != 'dates_changed_resign' %}
@@ -25,8 +42,8 @@
       {% endif %}
     </article>
   {% endfor %}
-  {% if rest_count > 1 and not (alerts_expanded | default(false)) %}
-    <article class="notification-bubble {{ rest[0].level }}" data-notification-summary>
+  {% if rest_count > 0 and not rest_inline %}
+    <article class="notification-bubble {{ (held.folded + rest)[0].level }}" data-notification-summary>
       <a class="notification-link" href="/#needs-action">
         <span class="notification-icon" aria-hidden="true">!</span>
         <span class="grow">
PATCH_A_END
git diff --stat | tail -5
```
Expected: 3 files, `_host_alerts.html` about 35 lines changed, `host_i18n.py` 2 insertions, `host_vi_i18n.py` 1 insertion. If `git apply` fails, STOP. Commit: `git add -A App/app && git commit -m "0969 step 2"`.

### Step 3: run the tests (from `App/`, each command exactly)

```bash
export UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b11
.venv/bin/python -m pytest tests/test_host_alert_stack_browser.py -q -rs --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_design_alerts_phone.py tests/test_needs_you_dashboard_0241.py tests/test_alert_language.py tests/test_claim_checkin_alerts.py tests/test_deadlines.py tests/test_deadline_after_reporting.py -q -rs --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest $(ls tests/test_host_*browser*.py) tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_dashboard_phone_browser.py tests/test_0252_touch_sweep_browser.py -q -rs --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest $(ls tests/test_host_*.py | grep -v browser) tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_static_versions.py -q -rs --tb=short -x 2>&1 | tail -30
```
Expected: all green, `0 skipped` in each browser run. Use a tool timeout of 600000 ms; if one command times out, STOP and report which (do not rerun the full suite). If `test_static_versions.py` fails only for `static_versions.json`, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`, then rerun it, and commit `0969 step 3`. A test fails twice: STOP.

### Step 4: look at the screenshots (do not retake)

The test writes them to `/tmp/ubyhost-b11` only: `zero-stays-390.png`, `one-stays-390.png`, `one-settings-390.png`, and for 390, 768 and 1280: `many-stays-W.png`, `many-settings-W.png`, `filtered-karlin-W.png`, `filtered-vinohrady-W.png` (the last one is written at 1280 only). Open each with the Read tool and give each one line in the report: what is above the page title, whether the deadline text and link are readable, whether the workspace label shows only on the other property's rows, no clipping or horizontal scroll. Expected: zero has no stack; one-stays has a large card with an action line; one-settings has the same title and deadline text without the action line; many-settings has 3 compact deadline lines plus one "1 more alerts" line to the dashboard; filtered-karlin has 2 large Karlin lines and 1 compact Vinohrady line labelled "Workspace alert, another property" plus the summary line. A screenshot that does not match: STOP and describe it. Never write screenshots anywhere else (no `docs/`, no `App/.screenshots`).

## 5. Do not touch

`host_page.html`, any CSS or JS, `alerts.py`, `reporting.py`, `deadlines.py`, `claim.py`, the `/alerts/<id>/dismiss` route, alert dedupe or persistence, send-readiness and retry rules, `docs/` other than the report. Hard rules 1, 3, 4, 6 and 9 of AGENTS.md. If a change beyond presentation seems needed (for example: alerts need a property name the row does not carry, or a filing alert would have to move), STOP and write it in the report as a separate brief; do not broaden this one.

## 6. Commands

Exactly those in section 4 steps 1 to 3, in that order, with their expected results. Never the full suite. Do not push, open a PR or merge; leave the branch committed and hand over to the owner.

## 7. Acceptance

- [ ] Step 1 baseline: 2 passed on the old template (before), recorded in the report.
- [ ] Step 3: new file 6 passed; the existing alert, deadline, host, geometry, guardrails, i18n and static-version commands green, `0 skipped` for browser runs.
- [ ] Chromium decisions, each pass or fail with the page seen: zero alerts (no stack); one alert (large on Stays, compact in Settings, same title and deadline text); many alerts (3 deadlines everywhere, only non-filing kinds folded); filtered property with another property's alert (labelled workspace, deadline kept, nothing looks like a failed filter); 390, 768, 1280 (no horizontal overflow, rows inside the viewport); dismissal and return navigation (dismissed alert gone, filter kept after reload and after Settings and back, the others unchanged, DB row `user_dismissed = 1`).
- [ ] Before/after: the same 3 (stay link, title, deadline text) keys on `/reservations`, both filtered views, `/settings`, `/settings/archived`, `/entities` at all 3 widths (the test asserts set equality).
- [ ] `git diff 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 --stat` lists only the files in section 3.
- [ ] Screenshots exist only under `/tmp/ubyhost-b11` and each has a one-line description in the report.

## 8. Stop and ask

Stop, and write the report, if: an anchor or `git apply` does not match; a test fails twice; 25 tool calls or about 50k tokens (report as `blocked`, `Done: steps 1 to k. Left: steps k+1 to 4.`); a file outside section 3 needs a change; section 5 would be touched; a filing alert would have to be hidden, folded, or reordered; a step is unclear; push, merge, secrets or deploy is needed.

## 9. Report

Write `docs/tasks/0969-report.md` (600 tokens at most): files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked, one line per screenshot, Deviations, Questions, owner steps left. Set `Status: review` in this brief. Commit `0969 report`.

## Risk list (for the reviewer)

- `_host_alerts.html`: the rewritten head (folding and `rest_inline`/`rest_count` arithmetic must equal the old behaviour when nothing is outside or folded, e.g. on the dashboard and `/reservations`) and the summary condition `rest_count > 0 and not rest_inline`.
- The `foldable_kinds` list: confirm none is a filing kind.
- `request.query_params.get('apartment')` is the filter name used by `reservations.html` (`view_query`).
- Not done on purpose: `/apartments/<id>` pages keep large lines and no scope (a later brief may scope them); no CSS, so a compact line is shorter by its action line only.

## Owner steps

1. Open the PR from branch `codex/0969-b11-alerts` after the reviewer accepts the report.
2. Merge only with `scripts/merge-pr-on-green.sh`; deploy stays manual.
