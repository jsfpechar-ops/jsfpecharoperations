# 0964: Connection states for the Smart lock and Calendars sections

Status: blocked
Depends on: B05 (queue order only; no file overlap expected) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0964-b06-connection-states
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The Smart lock section, when no lock is connected, shows its state (same source as the top pill), one reason and one next action, or the workspace limitation. Calendar rows keep name, sync state and actions visible; the feed URL becomes a secondary value behind a labelled disclosure with a Copy link control. Findings P07, P08 (batch B06).

## 2. Context

Worktree: /tmp/ubyhost-b06-worktree (already created on the base commit). Work only there.

Current anchors (each must be found with `grep -nF`; not found means STOP, section 8):

- `App/app/templates/_property_editor.html`: the lock state block ends `      </form>` / `    </div>` / `    {% endif %}` / `    {% if door_code %}` / `    {% include "_door_code_window.html" %}`. The no-lock fallback is `    <p class="ui-sub">{{ t('smart_locks.lede') }}</p>` followed by `    {% endif %}` and `    {% if door_code and lock_panel and lock_panel.smart_locks_enabled %}`.
- Status source: `door_code.state` (`off|times|offline|on`), built in `_door_code_context` (App/app/routes/admin.py). The top pill is `<a class="sc" ... data-strip="door" data-state="{{ {'on': 'ok', 'off': 'off'}.get(door_code.state, 'bad') if door_code else 'off' }}">`. Do not change either.
- `App/app/templates/_property_calendars.html`: `<td class="small mono truncate" data-label="{{ t('apartment.form.feed.url') }}">{{ feed.url }}</td>` (the width constraint).
- `App/app/static/app2.css` holds `.lock-state` rules (`/* 0954 ttlock */`) and `body.v2 .feed-table` rules. `App/app/templates/base.html` links `app2.css?v=20261105-0961a`.
- Existing i18n keys are reused; no new key (host_i18n.py is out of scope): `smart_locks.state_*`, `apartment.form.door_code.connect_first`, `smart_locks.setup`, `wizard.door_lock.unavailable` (the wizard uses it for the same condition), `common.copy_link`, `apartment.form.feed.url`.
- Rules: light mode only; no new dependency; no new outbound request; no personal data; no JS added (native `<details>`; the existing `copy_button` macro does the copy).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_property_editor.html | edit | lock-off/unavailable state blocks |
| App/app/templates/_property_calendars.html | edit | URL cell becomes details plus Copy link |
| App/app/static/app2.css | edit | scoped 0964 rules appended |
| App/app/templates/base.html | edit | bump `app2.css?v=` key only (required by test_static_versions; outside the original file list; flagged by the orchestrator, needed for the cache key) |
| App/tests/test_host_property_controls_browser.py | append | four browser tests |
| App/tests/static_versions.json | regenerate | via `--write` |
| docs/tasks/0964-report.md | create | report |

No other file may change. No change to lock provisioning, door-code logic, calendar sync, feed validation, routes or i18n.

## 4. Steps

Setup (one command, no commit): `cd /tmp/ubyhost-b06-worktree/App && ln -s /tmp/ubyhost-0958-worktree/App/.venv .venv && git status --short | tail -5`. The symlink must stay untracked; if `git status` lists it, add `.venv` to nothing, just never `git add` it (use `git add <paths>` below).

### Step 1: templates and CSS

Write the patch to /tmp/ubyhost-b06/src.patch (`mkdir -p /tmp/ubyhost-b06`) with the heredoc below, then `cd /tmp/ubyhost-b06-worktree && git apply --check /tmp/ubyhost-b06/src.patch && git apply /tmp/ubyhost-b06/src.patch && git diff --stat | tail -8`. If `--check` fails: STOP.

Commit: `git add App/app/templates App/app/static/app2.css && git commit -m "0964 step 1"`.

````
diff --git a/App/app/static/app2.css b/App/app/static/app2.css
index 66fbf0f5..dc2c6ac1 100644
--- a/App/app/static/app2.css
+++ b/App/app/static/app2.css
@@ -2589,3 +2589,11 @@ body.v2 form.property-settings-form .btn,body.v2 form.property-settings-form .ui
   body.v2 .ui-body-detail:has(> aside.preview) > aside.preview{grid-column:2;grid-row:1;align-self:start;position:sticky;top:24px;z-index:1}
 }
 @media (max-width:1023px){body.v2 .ui-body-detail:has(> aside.preview) > aside.preview{position:static}}
+/* 0964 connection states: a lock row without a lock, and calendar rows whose URL never sets the width */
+.lock-state > .ui-btn{margin-left:auto}
+.lock-state small{color:var(--ink3)}
+body.v2 .feed-table td.feed-url{min-width:0;max-width:none;white-space:normal}
+body.v2 .feed-table td.feed-url::before{display:none}
+body.v2 .feed-url-details{min-width:0;margin-bottom:8px}
+body.v2 .feed-url-details summary{cursor:pointer;min-height:44px;display:inline-flex;align-items:center}
+body.v2 .feed-url-value{display:block;max-width:100%;overflow-wrap:anywhere;word-break:break-all;white-space:normal}
diff --git a/App/app/templates/_property_calendars.html b/App/app/templates/_property_calendars.html
index 7783d670..81977ee6 100644
--- a/App/app/templates/_property_calendars.html
+++ b/App/app/templates/_property_calendars.html
@@ -45,7 +45,13 @@
               {% if checked_at %}<div class="ui-sub">{{ checked_at | datetime_local }}</div>{% endif %}
               {% if feed.last_error %}<div class="small err-text">{{ feed.last_error }}</div>{% endif %}
             </td>
-            <td class="small mono truncate" data-label="{{ t('apartment.form.feed.url') }}">{{ feed.url }}</td>
+            <td class="small feed-url" data-label="{{ t('apartment.form.feed.url') }}">
+              <details class="feed-url-details">
+                <summary>{{ t('apartment.form.feed.url') }}</summary>
+                <span class="mono feed-url-value" id="feed-url-{{ feed.id }}">{{ feed.url }}</span>
+              </details>
+              {{ copy_button('feed-url-' ~ feed.id, t('common.copy_link')) }}
+            </td>
             <td class="row-actions" data-label="">
               <form method="post" action="/feeds/{{ feed.id }}/delete" class="inline"
                     data-confirm data-confirm-message="{{ t('confirm.disconnect_feed') }}">
diff --git a/App/app/templates/_property_editor.html b/App/app/templates/_property_editor.html
index c3b23826..cb5c4365 100644
--- a/App/app/templates/_property_editor.html
+++ b/App/app/templates/_property_editor.html
@@ -380,6 +380,14 @@
         <button class="ui-btn {{ 'ui-btn-primary' if door_code.state == 'off' else 'ui-btn-secondary' }}" type="submit">{{ t('smart_locks.turn_on') if door_code.state == 'off' else t('smart_locks.turn_off') }}</button>
       </form>
     </div>
+    {% elif door_code %}
+    {#- 0964: no lock connected yet. Same state source as the top pill (door_code.state); one next action, or the workspace limitation. -#}
+    <div class="lock-state" id="lock-setup-state" data-state="{{ door_code.state }}" role="status">
+      <i class="sd" aria-hidden="true"></i>
+      <div class="lock-state-text"><b>{{ t({'off': 'smart_locks.state_off', 'times': 'smart_locks.state_times', 'offline': 'smart_locks.state_offline'}.get(door_code.state, 'smart_locks.state_on')) }}</b>
+        <small>{% if lock_panel and lock_panel.smart_locks_enabled %}{{ t('apartment.form.door_code.connect_first') }}{% else %}{{ t('wizard.door_lock.unavailable') }}{% endif %}</small></div>
+      {% if lock_panel and lock_panel.smart_locks_enabled %}<a class="ui-btn ui-btn-primary" href="#door-code">{{ t('smart_locks.setup') }}</a>{% endif %}
+    </div>
     {% endif %}
     {% if door_code %}
     {% include "_door_code_window.html" %}
@@ -413,6 +421,10 @@
     <input form="property-settings-form" type="hidden" name="door_code_section" value="1">
     {% else %}
     <p class="ui-sub">{{ t('smart_locks.lede') }}</p>
+    <div class="lock-state" id="lock-unavailable" data-state="off" role="status">
+      <i class="sd" aria-hidden="true"></i>
+      <div class="lock-state-text"><b>{{ t('smart_locks.state_off') }}</b><small>{{ t('wizard.door_lock.unavailable') }}</small></div>
+    </div>
     {% endif %}
     {% if door_code and lock_panel and lock_panel.smart_locks_enabled %}
   <section class="panel property-section ui-section" id="{% if door_code.account and door_code.locks %}smart-locks{% else %}door-code{% endif %}">
diff --git a/App/app/templates/base.html b/App/app/templates/base.html
index 45ca7693..eb216937 100644
--- a/App/app/templates/base.html
+++ b/App/app/templates/base.html
@@ -19,7 +19,7 @@
   <link rel="preload" href="/static/fonts/Manrope-latin.woff2?v=20261101-0495" as="font" type="font/woff2" crossorigin>
   {% if v2 | default(false) %}
   <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261103-0920">
-  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261105-0961a">
+  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261105-0964a">
   {% if show_nav | default(true) %}<link rel="stylesheet" data-turbo-track="reload" href="/static/command.css?v=20261103-0935">{% endif %}
   {% else %}
   <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261103-0920">

````

(Heredoc: `cat > /tmp/ubyhost-b06/src.patch <<'PATCH_EOF'` ... `PATCH_EOF`, with the content of the block above, verbatim, including the trailing newline.)

### Step 2: browser tests

Same method with /tmp/ubyhost-b06/tests.patch, then `git apply --check` and `git apply`. Commit: `git add App/tests/test_host_property_controls_browser.py && git commit -m "0964 step 2"`.

````
diff --git a/App/tests/test_host_property_controls_browser.py b/App/tests/test_host_property_controls_browser.py
index 12b572e2..b17d83c1 100644
--- a/App/tests/test_host_property_controls_browser.py
+++ b/App/tests/test_host_property_controls_browser.py
@@ -555,3 +555,166 @@ def test_guest_links_and_message_settings_geometry(host, base):
                 tip_top = page.evaluate(_TIP_JS, "ocr_scan")
                 assert tip_top is not None and abs(tip_top[0] - cb["y"]) <= 6, tip_top
         browser.close()
+
+
+# --- 0964: connection states (smart lock off/on/unavailable, calendar rows) ----
+
+_SHOT_DIR_0964 = os.environ.get("UBYHOST_SHOTS_DIR")
+_PILL_0964 = {"on": "ok", "off": "off"}
+_LONG_URL_0964 = "https://example.invalid/ical/" + "synthetic-token-" * 20 + ".ics"
+_NO_SIDEWAYS_0964 = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
+_IN_VIEW_0964 = """(selector) => {
+  const vw = document.documentElement.clientWidth;
+  const nodes = [...document.querySelectorAll(selector)];
+  return {count: nodes.length, vw, bad: nodes.filter(el => {
+    const r = el.getBoundingClientRect();
+    return !r.width || !r.height || r.left < -1 || r.right > vw + 1;
+  }).map(el => el.id || el.className)};
+}"""
+
+
+def _shot_0964(page, name):
+    if _SHOT_DIR_0964:
+        Path(_SHOT_DIR_0964).mkdir(parents=True, exist_ok=True)
+        page.screenshot(path=str(Path(_SHOT_DIR_0964) / f"0964-{name}.png"), full_page=True)
+
+
+def _lock_page_0964(playwright, base, host, width, lang="en"):
+    browser = playwright.chromium.launch(**chromium_launch_kwargs())
+    context = browser.new_context(viewport={"width": width, "height": 900})
+    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _session_cookie(host), "url": base + "/"}])
+    page = context.new_page()
+    page.goto(f"{base}/apartments/{host['apartment']}?view=settings&lang={lang}")
+    page.evaluate("() => { document.getElementById('sec-lock').open = true; }")
+    return browser, page
+
+
+def _lock_env_0964(monkeypatch, allowed):
+    from app import config, ttlock
+
+    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
+    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
+    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
+    monkeypatch.setattr(ttlock, "allowed_for", lambda owner_user_id: allowed)
+
+
+def _assert_lock_state_matches_pill_0964(page, state_selector, expected_state):
+    pill = page.get_attribute(".prop-strip .sc[data-strip='door']", "data-state")
+    block = page.locator(state_selector)
+    assert block.is_visible()
+    assert block.get_attribute("data-state") == expected_state
+    assert pill == _PILL_0964.get(expected_state, "bad"), (pill, expected_state)
+    return block
+
+
+def test_0964_lock_off_explains_and_offers_one_action(host, base, monkeypatch):
+    _lock_env_0964(monkeypatch, True)
+    db.execute("UPDATE apartment SET lock_provider = NULL, lock_id = NULL WHERE id = ?", (host["apartment"],))
+    with sync_api.sync_playwright() as playwright:
+        for width in (390, 768, 1280):
+            browser, page = _lock_page_0964(playwright, base, host, width)
+            try:
+                block = _assert_lock_state_matches_pill_0964(page, "#lock-setup-state", "off")
+                assert "Turned off" in block.inner_text()
+                assert "TTLock" in block.inner_text()
+                action = block.locator("a.ui-btn[href='#door-code']")
+                assert action.count() == 1 and action.is_visible()
+                assert block.locator("form, input, button").count() == 0  # no lock command, no credential edit here
+                fit = page.evaluate(_IN_VIEW_0964, "#lock-setup-state, #lock-setup-state a")
+                assert fit["count"] == 2 and not fit["bad"], fit
+                assert page.evaluate(_NO_SIDEWAYS_0964) <= 1, width
+                _shot_0964(page, f"lock-off-{width}")
+            finally:
+                browser.close()
+
+
+def test_0964_lock_on_with_mock_fixture_keeps_its_controls(host, base, monkeypatch):
+    import json
+
+    from tests.property_host_fixture import LOCK
+
+    _lock_env_0964(monkeypatch, True)
+    db.insert("lock_account", {"owner_user_id": host["owner"], "provider": "ttlock", "username": "synthetic_0964",
+                               "status": "ok", "locks_json": json.dumps([LOCK]),
+                               "created_at": db.utcnow(), "updated_at": db.utcnow()})
+    db.execute("UPDATE apartment SET lock_provider = 'ttlock', lock_id = ?, checkin_hour = 15, checkout_hour = 10 WHERE id = ?",
+               (LOCK["lock_id"], host["apartment"]))
+    try:
+        with sync_api.sync_playwright() as playwright:
+            for width in (390, 768, 1280):
+                browser, page = _lock_page_0964(playwright, base, host, width)
+                try:
+                    block = _assert_lock_state_matches_pill_0964(page, ".lock-state[data-state='on']", "on")
+                    assert page.locator("#lock-setup-state, #lock-unavailable").count() == 0
+                    assert block.locator(".lock-state-form button").is_visible()
+                    assert page.evaluate(_NO_SIDEWAYS_0964) <= 1, width
+                    _shot_0964(page, f"lock-on-{width}")
+                finally:
+                    browser.close()
+    finally:
+        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (host["owner"],))
+        db.execute("UPDATE apartment SET lock_provider = NULL, lock_id = NULL, checkin_hour = NULL, checkout_hour = NULL WHERE id = ?",
+                   (host["apartment"],))
+
+
+def test_0964_lock_unavailable_states_the_workspace_limitation(host, base, monkeypatch):
+    _lock_env_0964(monkeypatch, False)
+    with sync_api.sync_playwright() as playwright:
+        for width in (390, 768, 1280):
+            browser, page = _lock_page_0964(playwright, base, host, width)
+            try:
+                block = _assert_lock_state_matches_pill_0964(page, "#lock-unavailable", "off")
+                assert "Door codes are not enabled on this deployment." in block.inner_text()
+                assert block.locator("form, input, button, a").count() == 0
+                assert page.evaluate(_NO_SIDEWAYS_0964) <= 1, width
+                _shot_0964(page, f"lock-unavailable-{width}")
+            finally:
+                browser.close()
+
+
+def test_0964_calendar_rows_keep_state_and_actions_with_a_long_url(host, base):
+    apartment = host["apartment"]
+    now = db.utcnow()
+    healthy = db.insert("ical_feed", {
+        "apartment_id": apartment, "url": _LONG_URL_0964, "label": "booking", "own_name": "",
+        "active": 1, "last_status": "ok", "last_sync_at": now, "created_at": now,
+    })
+    failed = db.insert("ical_feed", {
+        "apartment_id": apartment, "url": "https://example.invalid/failed.ics", "label": "airbnb", "own_name": "",
+        "active": 1, "last_status": "error", "last_error": "Synthetic feed unreachable", "created_at": now,
+    })
+    try:
+        with sync_api.sync_playwright() as playwright:
+            browser = playwright.chromium.launch(**chromium_launch_kwargs())
+            context = browser.new_context(viewport={"width": 1280, "height": 900})
+            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _session_cookie(host), "url": base + "/"}])
+            page = context.new_page()
+            for width in (390, 768, 1280):
+                page.set_viewport_size({"width": width, "height": 900})
+                page.goto(f"{base}/apartments/{apartment}?view=bookings&lang=en")
+                assert page.locator("#sec-calendars[open]").count() == 1
+                rows = page.locator(".feed-table tbody tr")
+                assert rows.count() == 2
+                assert page.locator(".feed-table td[data-label='Last sync'] [data-tone='red']").is_visible()
+                assert page.locator(".feed-table td[data-label='Last sync'] [data-tone='green']").is_visible()
+                assert "Synthetic feed unreachable" in page.locator(".feed-table").inner_text()
+                # Name, state, URL control, copy and Remove are all in view while the URL is collapsed.
+                fit = page.evaluate(_IN_VIEW_0964, ".feed-table td strong, .feed-table [data-tone], .feed-table summary, .feed-table .copy-btn, .feed-table .row-actions .ui-btn")
+                assert fit["count"] >= 10 and not fit["bad"], (width, fit)
+                assert page.locator(".feed-url-details[open]").count() == 0
+                assert not page.locator(f"#feed-url-{healthy}").is_visible()
+                assert page.get_attribute(f".feed-table .copy-btn[data-copy='feed-url-{healthy}']", "data-copy")
+                assert page.evaluate(_NO_SIDEWAYS_0964) <= 1, width
+                _shot_0964(page, f"calendars-collapsed-{width}")
+                # Opening the long URL wraps it inside its cell and never pushes an action out of view.
+                page.locator(".feed-table summary").first.click()
+                assert page.locator(f"#feed-url-{healthy}").is_visible()
+                fit = page.evaluate(_IN_VIEW_0964, ".feed-table .row-actions .ui-btn, .feed-table .copy-btn, .feed-url-value")
+                assert not fit["bad"], (width, fit)
+                assert page.evaluate(_NO_SIDEWAYS_0964) <= 1, width
+                wrap = page.evaluate("() => { const w = document.querySelector('.feed-table').closest('.scroll-x'); return w.scrollWidth - w.clientWidth; }")
+                assert wrap <= 1, (width, wrap)
+                _shot_0964(page, f"calendars-open-{width}")
+            browser.close()
+    finally:
+        db.execute("DELETE FROM ical_feed WHERE id IN (?, ?)", (healthy, failed))

````

### Step 3: static version manifest

From App/: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`, then `git diff --stat App/tests/static_versions.json | tail -3` (only the `app2.css` entry changes). Commit: `git add App/tests/static_versions.json && git commit -m "0964 step 3"`.

### Step 4: run the tests

From App/, each command ends `2>&1 | tail -30`; add `-rs` to browser runs and require 0 skipped. Set once per command: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b06`.

1. New tests: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b06 .venv/bin/python -m pytest tests/test_host_property_controls_browser.py -k 0964 -q -rs --tb=short -x 2>&1 | tail -30` (expect 4 passed).
2. Host row: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b06 .venv/bin/python -m pytest tests/test_host_property_controls_browser.py tests/test_host_geometry.py tests/test_wp28_geometry.py tests/test_wp28_ui_sweep.py tests/test_0952_lock_section.py tests/test_0952_lock_section_browser.py tests/test_0534_property_page_v2.py -q -rs --tb=short -x 2>&1 | tail -30`.
3. Smart-lock and door-code row: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30`.
4. Calendar row: `.venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_feed_*.py tests/test_dashboard_calendar*.py tests/test_calendar_*.py tests/test_sample_calendar.py -q --tb=short -x 2>&1 | tail -30`.
5. Static and design: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30`.
6. Lint: `cd /tmp/ubyhost-b06-worktree && python3 scripts/context_lint.py 2>&1 | tail -10`.

A test fails: read the last 30 lines, fix once (only inside section 3 files), rerun; fails again: STOP. If a pre-existing test that asserts the old `truncate` URL cell fails, that is a stop condition, not a licence to edit that test.

### Step 5: Chromium UX check (decide pass or fail per line)

Screenshots land in /tmp/ubyhost-b06 (named `0964-lock-off-390.png`, `lock-on`, `lock-unavailable`, `calendars-collapsed`, `calendars-open`, each at 390, 768, 1280). Open each once with Read and write one sentence per image in the report: what you saw, then PASS or FAIL.

- Lock Off (390/768/1280): state label "Automatic door codes: Turned off", one sentence explaining a lock must be connected, one primary "Connect my lock" link; nothing clipped; the status dot colour matches the top "Smart lock" pill.
- Lock On (mock lock account): green state row with the Turn off button, unchanged from before.
- Unavailable: state label plus "Door codes are not enabled on this deployment."; no button.
- Calendars healthy and failed: name, sync badge (green, red with error text), "URL" disclosure, Copy link and Remove all visible without horizontal scroll at 390, 768 and 1280, collapsed and with the long URL open.
Any FAIL: STOP with the report as `blocked`; do not adjust CSS beyond one fix of section 3 files.
Tick the design-system checklist items that apply (docs/design/design-system.md) in the report as a one-line list.

## 5. Do not touch

Lock provisioning (`ttlock.py`), `door_codes.py`, `routes/admin.py`, calendar sync (`icalsync.py`, `feed_fetch.py`, `feed_url.py`), i18n files, `_smart_locks_panel.html`, `_door_code_window.html`, any existing test. Never push, merge, open a PR, or deploy; leave that to the orchestrator. No live sync, no lock command, no credential edit; the Remove button keeps its confirm flow and is never clicked in tests.

## 6. Commands

See step 4. Expected: 4 passed for the new tests; every other row green with 0 skipped on browser files.

## 7. Acceptance

- [ ] Lock Off: `#lock-setup-state` shows the same state as the top pill, with one action `a[href="#door-code"]`.
- [ ] Lock unavailable: `#lock-unavailable` shows the limitation, no controls.
- [ ] Lock On unchanged.
- [ ] Calendar rows: name, badge, URL disclosure, Copy link, Remove inside the viewport at 390, 768, 1280; no horizontal scroll.
- [ ] 4 new tests pass; rows in step 4 pass; 0 skipped.
- [ ] Screenshots viewed and described in the report.
- [ ] Only the files in section 3 changed (`git diff --stat 7b0355c | tail`).

## 8. Stop and ask

Stop, and write the report (Status: blocked), if:

- an anchor or the patch does not apply;
- a test fails twice, or a pre-existing test fails because of the new markup;
- the view needs new provider or backend behaviour (for example telling a missing plan from a missing deployment setting, or a new i18n key): do NOT add it; report it so it becomes a separate brief;
- a file outside section 3 needs a change;
- 25 tool calls or about 50k tokens;
- push, merge, secrets or deploy would be needed.

## 9. Report

Write `docs/tasks/0964-report.md` (600 tokens at most): files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked, one sentence per screenshot with PASS/FAIL, deviations, questions, owner steps left (none expected). Set `Status: review` in this brief, then `git add docs/tasks/0964-report.md docs/tasks/0964-connection-states.md && git commit -m "0964 report"`. Do not push or open a PR.

## Risk list (for the reviewer)

`_property_editor.html` (new `elif door_code` and `else` blocks), `_property_calendars.html` (URL cell), the 0964 block in `app2.css`. Known limit: when the account has no plan for door codes, the limitation sentence says "not enabled on this deployment" (same string the setup wizard uses); a plan-specific reason needs a backend flag and a new i18n key, so it is a separate brief.

## Owner steps

None for this brief. The orchestrator reviews the report and the screenshots before any PR.
