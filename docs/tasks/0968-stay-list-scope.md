# 0968: Stays list scope label and compact filter row

Status: blocked (command 4 fails on base 7b0355c4 too; see report)
Depends on: B09 (0958), not needed to run | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0968-b10-stay-list
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Read this brief in ranges of 150 lines (a hook blocks whole-file reads over 350 lines).

## 1. Objective

The default Stays tab "Upcoming & current" also lists ended stays that are not yet reported (overdue). Rename the tab to say so, explain it in one line, and make the desktop filter panel one compact row with Apply and Cancel only, while "Reset filters" moves under the scope line, away from Cancel. Query semantics and the overdue rule do not change; no stay is hidden.

## 2. Context

- Route `App/app/routes/admin.py` `reservations_list` (read only, do not edit): range `upcoming` shows `date_to >= today` plus `_overdue_unfinished_ids`. Order is `date_from ASC`, page size 5.
- The tab label key is `stays.chip.upcoming` in `App/app/host_i18n.py` (en at about line 1227, cs at about 3295) and `App/app/host_vi_i18n.py` (about line 1251). Supported host languages: en, cs, vi.
- Template `App/app/templates/reservations.html`: the filter form `#stays-filter-panel` has an action row with Apply, Cancel (`data-filter-cancel`) and a Reset link. The scope summary is `<p class="sub ph-hide" data-filter-summary>`. The filter panel exists on desktop only (1024 px and up); at 390 and 768 px the toggle is hidden by design, so there only the tab label and the note are checked.
- Anchors you will see in the patch (do not search for them yourself; `git apply --check` is the check):
  - `<p class="sub ph-hide" data-filter-summary>{{ stay_summary }}</p>`
  - `"stays.chip.upcoming": "Upcoming & current",`
  - `<h2 class="sec">{{ t(label_key) }}</h2>`
  - `app2.css?v=20261105-0961a` in `App/app/templates/base.html`
- Existing tests that assert the old strings and are fixed by the patch: `test_0285_rows_browser.py` (tab label) and `test_host_filter_panels_browser.py` (Reset link inside the panel).
- Copy rules: no em dashes, light mode only, no new dependency.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/reservations.html | edit | overdue note, Reset filters link under the scope line, Reset removed from action row, phone group heading |
| App/app/host_i18n.py | edit | en and cs: new tab label, 3 new keys |
| App/app/host_vi_i18n.py | edit | vi: new tab label, 3 new keys |
| App/app/static/app2.css | edit (append) | desktop one-row filter panel |
| App/app/templates/base.html | edit | bump the app2.css key to 20261105-0968a |
| App/tests/static_versions.json | edit | app2.css hash and key |
| App/tests/test_host_filter_panels_browser.py | edit | append 0968 tests; one assertion line changed |
| App/tests/test_0285_rows_browser.py | edit | one assertion line changed (new tab label) |
| docs/tasks/0968-report.md | create | report |

`app2.css` and `base.html` are beyond the original B10 file list. They are needed because the filter row cannot be made shorter by markup alone. Do not touch any other file.

## 4. Steps

Work in `/tmp/ubyhost-b10-worktree`. Branch already exists: `git branch --show-current` must print `codex/0968-b10-stay-list`, else STOP.

### Step 1: venv symlink and baseline

```
cd /tmp/ubyhost-b10-worktree/App && ln -s /tmp/ubyhost-0958-worktree/App/.venv .venv 2>&1 | tail -3; ls .venv/bin/python | tail -3
```
If the symlink target is missing, STOP. No commit for this step.

### Step 2: app patch

Write the patch below to `/tmp/b10-app.patch` exactly (heredoc with quoted delimiter), check, apply, commit.

```
cat > /tmp/b10-app.patch <<'PATCH'
diff --git a/App/app/host_i18n.py b/App/app/host_i18n.py
index b265a7d7..396af7a4 100644
--- a/App/app/host_i18n.py
+++ b/App/app/host_i18n.py
@@ -1224,7 +1224,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "stays.add_panel.label_ph": "Direct booking – Novák",
         "stays.add_panel.email": "Guest e-mail",
         "stays.add_panel.create": "Create stay",
-        "stays.chip.upcoming": "Upcoming & current",
+        "stays.chip.upcoming": "Upcoming, current & overdue",
         "stays.chip.past": "Past",
         "stays.chip.all": "All dates",
         "stays.chip.archive": "Archived",
@@ -1234,6 +1234,9 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "stays.grp.week": "This week",
         "stays.grp.later": "Later",
         "stays.grp.earlier": "Earlier",
+        "stays.grp.overdue": "Overdue, not reported",
+        "stays.scope.overdue_note": "Includes stays that have ended but are not yet reported to the police.",
+        "stays.filter.reset_scope": "Reset filters",
         "stays.housebook_hint": "CSV for checking",
         "stays.archive_note": "Archived stays are hidden from your daily work but kept for reference. Restore any entry you archived by mistake.",
         "stays.filter.apartment": "Property",
@@ -3292,7 +3295,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "stays.add_panel.label_ph": "Přímá rezervace – Novák",
         "stays.add_panel.email": "E-mail hosta",
         "stays.add_panel.create": "Vytvořit pobyt",
-        "stays.chip.upcoming": "Nadcházející",
+        "stays.chip.upcoming": "Nadcházející, aktuální a po termínu",
         "stays.chip.past": "Proběhlé",
         "stays.chip.all": "Všechna data",
         "stays.chip.archive": "Archivované",
@@ -3302,6 +3305,9 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "stays.grp.week": "Tento týden",
         "stays.grp.later": "Později",
         "stays.grp.earlier": "Dříve",
+        "stays.grp.overdue": "Po termínu, nenahlášeno",
+        "stays.scope.overdue_note": "Zahrnuje skončené pobyty, které ještě nejsou nahlášené cizinecké policii.",
+        "stays.filter.reset_scope": "Obnovit filtry",
         "stays.housebook_hint": "CSV pro kontrolu",
         "stays.archive_note": "Archivované pobyty jsou skryté z denní práce, ale zůstávají k dispozici. Chybné záznamy můžete obnovit.",
         "stays.filter.apartment": "Ubytování",
diff --git a/App/app/host_vi_i18n.py b/App/app/host_vi_i18n.py
index 28f23a46..0bf62f85 100644
--- a/App/app/host_vi_i18n.py
+++ b/App/app/host_vi_i18n.py
@@ -1248,7 +1248,7 @@ STRINGS: Dict[str, str] = {
     "stays.add_panel.label_ph": "Đặt trực tiếp – Novák",
     "stays.add_panel.email": "Email của khách",
     "stays.add_panel.create": "Tạo lượt lưu trú",
-    "stays.chip.upcoming": "Sắp tới và hiện tại",
+    "stays.chip.upcoming": "Sắp tới, hiện tại và quá hạn",
     "stays.chip.past": "Đã qua",
     "stays.chip.all": "Mọi ngày",
     "stays.chip.archive": "Đã lưu trữ",
@@ -1258,6 +1258,9 @@ STRINGS: Dict[str, str] = {
     "stays.grp.week": "Tuần này",
     "stays.grp.later": "Sau đó",
     "stays.grp.earlier": "Trước đó",
+    "stays.grp.overdue": "Quá hạn, chưa khai báo",
+    "stays.scope.overdue_note": "Gồm các lượt lưu trú đã kết thúc nhưng chưa được khai báo với cảnh sát.",
+    "stays.filter.reset_scope": "Đặt lại bộ lọc",
     "stays.housebook_hint": "CSV để kiểm tra",
     "stays.archive_note": "Lượt lưu trú đã lưu trữ được ẩn khỏi công việc hằng ngày nhưng vẫn được giữ để tham khảo. Hãy khôi phục mục bạn lỡ lưu trữ.",
     "stays.filter.apartment": "Chỗ ở",
diff --git a/App/app/static/app2.css b/App/app/static/app2.css
index 66fbf0f5..8bdbdb7a 100644
--- a/App/app/static/app2.css
+++ b/App/app/static/app2.css
@@ -2589,3 +2589,10 @@ body.v2 form.property-settings-form .btn,body.v2 form.property-settings-form .ui
   body.v2 .ui-body-detail:has(> aside.preview) > aside.preview{grid-column:2;grid-row:1;align-self:start;position:sticky;top:24px;z-index:1}
 }
 @media (max-width:1023px){body.v2 .ui-body-detail:has(> aside.preview) > aside.preview{position:static}}
+
+/* 0968: the stays filter panel on desktop is one row: the fields, then Apply and Cancel. Reset filters lives under the scope line. */
+@media (min-width:1024px){
+  body.v2 form.stays-filter:not(.is-collapsed){display:flex;align-items:flex-end;gap:16px;flex-wrap:nowrap}
+  body.v2 form.stays-filter .filter-fields{flex:1 1 auto;min-width:0}
+  body.v2 form.stays-filter .filter-panel-actions{flex:none;margin:0}
+}
diff --git a/App/app/templates/base.html b/App/app/templates/base.html
index 45ca7693..0114c0a5 100644
--- a/App/app/templates/base.html
+++ b/App/app/templates/base.html
@@ -19,7 +19,7 @@
   <link rel="preload" href="/static/fonts/Manrope-latin.woff2?v=20261101-0495" as="font" type="font/woff2" crossorigin>
   {% if v2 | default(false) %}
   <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261103-0920">
-  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261105-0961a">
+  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261105-0968a">
   {% if show_nav | default(true) %}<link rel="stylesheet" data-turbo-track="reload" href="/static/command.css?v=20261103-0935">{% endif %}
   {% else %}
   <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261103-0920">
diff --git a/App/app/templates/reservations.html b/App/app/templates/reservations.html
index b7feceb7..3a1697d5 100644
--- a/App/app/templates/reservations.html
+++ b/App/app/templates/reservations.html
@@ -98,6 +98,12 @@
 <div class="stays-pills">{% with wrap_on_phone=true %}{% include "partials/settings_pills.html" %}{% endwith %}</div>
 </div>
 <p class="sub ph-hide" data-filter-summary>{{ stay_summary }}</p>
+{% set overdue_scope = namespace(count=0) %}
+{% if date_range == 'upcoming' and not show_archive and not report %}
+  {% for row in rows %}{% set ended_on = parse_iso_date(row.reservation.date_to) %}{% if ended_on and ended_on < today() %}{% set overdue_scope.count = overdue_scope.count + 1 %}{% endif %}{% endfor %}
+{% endif %}
+{% if overdue_scope.count %}<p class="sub" data-stays-overdue-note>{{ t('stays.scope.overdue_note') }}</p>{% endif %}
+{% if apartment_id or status != 'active' or date_range == 'custom' %}<p class="sub ph-hide stays-scope-reset"><a data-stays-reset href="{{ '/reservations?range=archive' if show_archive else '/reservations?range=all' }}">{{ t('stays.filter.reset_scope') }}</a></p>{% endif %}
 <div class="saved-views" data-saved-views data-label="{{ t('stays.filter.saved_views') }}"></div>
 
 {% if show_archive %}
@@ -131,7 +137,6 @@
   <div class="filter-panel-actions">
     <button class="ui-btn ui-btn-primary filter-apply" type="submit" name="range" value="custom">{{ t('host.filter.apply_filters') }}</button>
     <button class="ui-btn ui-btn-quiet" type="button" data-filter-cancel hidden>{{ t('confirm.cancel') }}</button>
-    <a class="ui-btn ui-btn-quiet" href="{{ '/reservations?range=archive' if show_archive else '/reservations?range=all' }}">{{ t('host.filter.reset') }}</a>
   </div>
 </form>
 {% endif %}
@@ -152,7 +157,7 @@
   {% set group_rows = [] %}
   {% for row in rows if stay_group(row.reservation) | trim == key %}{% set _ = group_rows.append(row) %}{% endfor %}
   {% if group_rows %}
-  <h2 class="sec">{{ t(label_key) }}</h2>
+  <h2 class="sec">{{ t('stays.grp.overdue' if key == 'earlier' and date_range == 'upcoming' else label_key) }}</h2>
     {% for row in group_rows %}
       {% set reservation = row.reservation %}
       {% set progress = row.progress %}
diff --git a/App/tests/static_versions.json b/App/tests/static_versions.json
index b0642a2f..01ef2c3c 100644
--- a/App/tests/static_versions.json
+++ b/App/tests/static_versions.json
@@ -24,8 +24,8 @@
     "v": "20261104-0955g"
   },
   "app2.css": {
-    "sha256": "a8e8ad2f73bc500286699708512164cbf450b540f856bda609b5d1cc76b531bf",
-    "v": "20261105-0961a"
+    "sha256": "57d86cdead74221a45087f390a79be6f5b054b6a195b703c0a9e5469f2867d88",
+    "v": "20261105-0968a"
   },
   "apple-touch-icon.png": {
     "sha256": "8b487f53a3a7522a9620ed5c26ab1fd77ee6a08cae12fcd087cb9f7a0c03c250",
PATCH
cd /tmp/ubyhost-b10-worktree && git apply --check /tmp/b10-app.patch 2>&1 | tail -30
```
Check fails: STOP (anchor not found). Else:
```
cd /tmp/ubyhost-b10-worktree && git apply /tmp/b10-app.patch && cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3
cd /tmp/ubyhost-b10-worktree && git add -A App && git commit -q -m "0968 step 2" 2>&1 | tail -3
```
(`--write` rewrites the hash; if the hash already matches, git shows no change in that file, which is fine.)

### Step 3: test patch

```
cat > /tmp/b10-tests.patch <<'PATCH'
diff --git a/App/tests/test_0285_rows_browser.py b/App/tests/test_0285_rows_browser.py
index 8a918ea1..8fa3ee9c 100644
--- a/App/tests/test_0285_rows_browser.py
+++ b/App/tests/test_0285_rows_browser.py
@@ -30,7 +30,7 @@ def _client():
 def test_stays_open_on_upcoming_and_current():
     client = _client()
     page = client.get("/reservations?lang=en").text
-    assert 'aria-current="page">Upcoming &amp; current<' in page
+    assert 'aria-current="page">Upcoming, current &amp; overdue<' in page
     # v2 (0528): the mockup has no "All dates" chip, so no chip is current on range=all.
     page = client.get("/reservations?range=all&lang=en").text
     assert 'class="chip on"' not in page
diff --git a/App/tests/test_host_filter_panels_browser.py b/App/tests/test_host_filter_panels_browser.py
index 7a49945e..222f8c96 100644
--- a/App/tests/test_host_filter_panels_browser.py
+++ b/App/tests/test_host_filter_panels_browser.py
@@ -356,7 +356,7 @@ def test_filter_draft_calendar_and_month_grid_commit_once(host, base):
         assert "Filter Property Two" in page.locator("[data-filter-summary]").inner_text()
         page.goto(base + f"/reservations?range=custom&archive_scope=1&apartment={host['apartments'][1]}&status=cancelled&lang=en")
         assert "range=archive" in page.locator('.settings-pills .settings-pill.is-current').get_attribute("href")
-        assert page.locator('#stays-filter-panel a').filter(has_text="Reset").get_attribute("href") == "/reservations?range=archive"
+        assert page.locator("[data-stays-reset]").get_attribute("href") == "/reservations?range=archive"
         assert not page_errors, "browser script errors: " + " | ".join(page_errors)
 
         page.goto(base + f"/invoices?status=paid&q=Sample&apartment={host['apartments'][0]}&lang=en")
@@ -509,3 +509,220 @@ def test_filter_geometry_and_popovers_stay_inside_the_viewport_in_english_and_cz
                 _capture(page, f"invoices-selected-month-{lang}-{width}-month-grid")
         assert not page_errors, "browser script errors: " + " | ".join(page_errors)
         browser.close()
+
+
+# ---------------------------------------------------------------------------
+# 0968: the default Stays tab says it includes overdue stays; the filter panel
+# is one compact row; Reset filters sits under the scope line, away from Cancel.
+# ---------------------------------------------------------------------------
+from datetime import date, timedelta
+
+from app import deadlines, reporting
+
+SCOPE_LABEL = {"en": "Upcoming, current & overdue", "cs": "Nadcházející, aktuální a po termínu"}
+SCOPE_NOTE = {
+    "en": "Includes stays that have ended but are not yet reported to the police.",
+    "cs": "Zahrnuje skončené pobyty, které ještě nejsou nahlášené cizinecké policii.",
+}
+
+
+def _past_deadline_arrival():
+    now = deadlines.local_now()
+    for back in range(10, 21):
+        candidate = date.today() - timedelta(days=back)
+        if deadlines.reporting_deadline(candidate) < now:
+            return candidate
+    pytest.fail("no past-deadline arrival found")
+
+
+def _shots_dir() -> Path:
+    target = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b10")
+    target.mkdir(parents=True, exist_ok=True)
+    return target
+
+
+@pytest.fixture(scope="module")
+def scope_host():
+    db.init_db()
+    username = f"scope-{secrets.token_hex(4)}"
+    owner = auth.create_account(
+        f"{username}@example.test", "Scope Test", role="host", username=username
+    )
+    entity = db.insert("legal_entity", {
+        "name": "Scope Test s.r.o.", "owner_user_id": owner, "created_at": db.utcnow(),
+    })
+    apartments = []
+    for name in ("Scope Alpha", "Scope Beta"):
+        apartments.append(db.insert("apartment", {
+            "internal_name": name, "owner_user_id": owner, "legal_entity_id": entity,
+            "permalink_token": f"scope{secrets.token_hex(4)}", "automation_mode": "manual",
+            "active": 1, "created_at": db.utcnow(),
+        }))
+    alpha, beta = apartments
+    now = db.utcnow()
+    today = date.today()
+    ids = {}
+
+    def add(key, apartment_id, start, end, archived_at=None):
+        ids[key] = db.insert("reservation", {
+            "apartment_id": apartment_id, "source": "manual",
+            "uid": f"scope-{key}-{secrets.token_hex(3)}",
+            "date_from": start.isoformat(), "date_to": end.isoformat(),
+            "summary": f"Scope {key} stay", "status": "active",
+            "expected_guests_override": 1, "archived_at": archived_at,
+            "created_at": now, "updated_at": now,
+        })
+        return ids[key]
+
+    arrival = _past_deadline_arrival()
+    overdue = add("overdue", alpha, arrival, arrival + timedelta(days=3))
+    db.insert("guest", {
+        "reservation_id": overdue, "surname": "SCOPEOVERDUE", "first_name": "ANNA",
+        "birth_date": "01011990", "nationality": "DEU", "doc_number": "P9988772",
+        "res_street": "Hauptstrasse 5", "res_city": "Berlin", "res_country": "DEU",
+        "purpose": "10", "is_lead": 1, "entered_by": "guest", "signature_png": "imported",
+        "signed_at": now, "passport_photo_at": now, "identity_verified_at": now,
+        "stay_from": arrival.isoformat(), "stay_to": (arrival + timedelta(days=3)).isoformat(),
+        "submit_state": reporting.PENDING, "created_at": now, "updated_at": now,
+    })
+    add("current", alpha, today - timedelta(days=1), today + timedelta(days=2))
+    for index in range(5):
+        start = today + timedelta(days=10 + index * 4)
+        add(f"future{index}", alpha, start, start + timedelta(days=2))
+    add("beta", beta, today + timedelta(days=12), today + timedelta(days=14))
+    add("archived", alpha, today + timedelta(days=60), today + timedelta(days=62), archived_at=now)
+    client = TestClient(app)
+    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
+    assert response.status_code == 303, response.text
+    yield {"client": client, "owner": owner, "apartments": apartments, "ids": ids}
+    db.execute("DELETE FROM guest WHERE reservation_id IN (?)", (overdue,))
+    db.execute("DELETE FROM reservation WHERE apartment_id IN (?, ?)", apartments)
+    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
+    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
+    db.execute("DELETE FROM user_account WHERE id = ?", (owner,))
+
+
+def test_default_stays_tab_label_names_overdue_and_the_note_only_shows_there(scope_host):
+    client, ids = scope_host["client"], scope_host["ids"]
+    for lang in ("en", "cs"):
+        page = client.get(f"/reservations?lang={lang}").text
+        label = SCOPE_LABEL[lang].replace("&", "&amp;")
+        assert f'aria-current="page">{label}<' in page
+        assert "data-stays-overdue-note" in page and SCOPE_NOTE[lang] in page
+        assert f"/reservations/{ids['overdue']}" in page, "overdue stay must stay visible"
+        assert f"/reservations/{ids['current']}" in page
+        assert f"/reservations/{ids['archived']}" not in page
+    for url in ("/reservations?range=past&lang=en", "/reservations?range=all&lang=en",
+                "/reservations?range=archive&lang=en", "/reservations?range=current&lang=en"):
+        assert "data-stays-overdue-note" not in client.get(url).text, url
+    assert f"/reservations/{ids['archived']}" in client.get("/reservations?range=archive&lang=en").text
+
+
+def test_stays_filter_is_one_row_with_reset_apart_from_cancel_and_scope_survives_paging(scope_host, base):
+    apartments = scope_host["apartments"]
+    alpha, beta = apartments
+    shots = _shots_dir()
+    with sync_api.sync_playwright() as playwright:
+        browser, _context, page = _browser_context(playwright, scope_host, base, width=1280)
+        errors = []
+        page.on("pageerror", lambda error: errors.append(str(error)))
+        page.goto(base + "/reservations?lang=en")
+        page.locator("[data-filter-toggle]").click()
+        panel = page.locator("#stays-filter-panel")
+        settle_motion(page)
+        assert panel.is_visible()
+        # No link in the action row: Apply and Cancel only.
+        assert page.locator("#stays-filter-panel .filter-panel-actions a").count() == 0
+        apply_box = page.locator("#stays-filter-panel .filter-apply").bounding_box()
+        cancel_box = page.locator("#stays-filter-panel [data-filter-cancel]").bounding_box()
+        fields_box = page.locator("#stays-filter-panel .filter-fields").bounding_box()
+        actions_box = page.locator("#stays-filter-panel .filter-panel-actions").bounding_box()
+        panel_box = panel.bounding_box()
+        (shots / "heights.txt").write_text(f"panel_height_1280={round(panel_box['height'])}\n", encoding="utf-8")
+        assert abs(apply_box["y"] - cancel_box["y"]) <= 2, "Apply and Cancel share one row"
+        # Compact: the actions sit in the same row as the fields, not under them.
+        assert actions_box["y"] < fields_box["y"] + fields_box["height"] - 4, (actions_box, fields_box)
+        page.screenshot(path=str(shots / "filter-open-en-1280.png"), full_page=True)
+
+        # Cancel restores the draft and closes the panel without navigating.
+        before_url = page.url
+        page.locator('#stays-filter-panel [name="apartment"]').select_option(str(alpha))
+        page.locator("#stays-filter-panel [data-filter-cancel]").click()
+        assert not panel.is_visible()
+        assert page.url == before_url
+        assert page.locator('#stays-filter-panel [name="apartment"]').input_value() == ""
+
+        # Apply: scope stays visible, Reset filters is above the panel and far from Cancel.
+        page.locator("[data-filter-toggle]").click()
+        page.locator('#stays-filter-panel [name="apartment"]').select_option(str(alpha))
+        with page.expect_navigation():
+            page.locator("#stays-filter-panel .filter-apply").click()
+        assert f"apartment={alpha}" in page.url and "range=custom" in page.url
+        assert "Scope Alpha" in page.locator("[data-filter-summary]").inner_text()
+        reset = page.locator("[data-stays-reset]")
+        assert reset.is_visible() and reset.inner_text().strip() == "Reset filters"
+        page.locator("[data-filter-toggle]").click()
+        settle_motion(page)
+        reset_box = reset.bounding_box()
+        cancel_box = page.locator("#stays-filter-panel [data-filter-cancel]").bounding_box()
+        assert reset_box["y"] + reset_box["height"] <= panel.bounding_box()["y"] + 1
+        assert cancel_box["y"] - (reset_box["y"] + reset_box["height"]) >= 40, "Reset and Cancel are not adjacent"
+        page.screenshot(path=str(shots / "filter-applied-en-1280.png"), full_page=True)
+
+        # Pagination keeps the scope: page size is 5, Alpha has 7 stays in this view.
+        next_link = page.locator('a[rel="next"]').first
+        assert f"apartment={alpha}" in next_link.get_attribute("href")
+        assert "range=custom" in next_link.get_attribute("href")
+        assert page.locator(".stays-desk tbody tr").count() == 5
+        with page.expect_navigation():
+            next_link.click()
+        assert "page=2" in page.url and f"apartment={alpha}" in page.url
+        assert page.locator(".stays-desk tbody tr").count() == 2
+        assert "Scope Alpha" in page.locator("[data-filter-summary]").inner_text()
+        assert page.locator(f'a[href^="/reservations/{scope_host["ids"]["beta"]}?"]').count() == 0
+
+        # Reset filters leaves the scope and the link goes away.
+        with page.expect_navigation():
+            page.locator("[data-stays-reset]").click()
+        assert "range=all" in page.url and "apartment=" not in page.url
+        assert page.locator("[data-stays-reset]").count() == 0
+
+        # Empty filtered result keeps the way back.
+        page.goto(base + f"/reservations?range=custom&apartment={beta}&from=2000-01-01&to=2000-01-02&lang=en")
+        assert page.locator(".stays-desk tbody tr").count() == 0
+        assert page.get_by_text("No stay matches this filter.").first.is_visible()
+        assert page.locator("[data-stays-reset]").is_visible()
+        page.screenshot(path=str(shots / "filter-empty-en-1280.png"), full_page=True)
+        assert not errors, errors
+        browser.close()
+
+
+def test_stays_default_tab_label_is_not_clipped_at_phone_tablet_and_desktop_in_english_and_czech(scope_host, base):
+    shots = _shots_dir()
+    with sync_api.sync_playwright() as playwright:
+        browser, _context, page = _browser_context(playwright, scope_host, base, width=1280)
+        for width in (390, 768, 1280):
+            page.set_viewport_size({"width": width, "height": 1000})
+            for lang in ("en", "cs"):
+                page.goto(base + f"/reservations?lang={lang}")
+                current = page.locator(".stays-pills [aria-current=page]").first
+                assert " ".join(current.inner_text().split()) == SCOPE_LABEL[lang], f"{width}px {lang}"
+                geometry = page.evaluate(
+                    """() => {
+                      const root = document.documentElement;
+                      const pill = document.querySelector('.stays-pills [aria-current=page]');
+                      const note = document.querySelector('[data-stays-overdue-note]');
+                      const box = pill.getBoundingClientRect();
+                      const noteBox = note.getBoundingClientRect();
+                      return {
+                        pageOverflow: root.scrollWidth > root.clientWidth + 1,
+                        pillClipped: pill.scrollWidth > pill.clientWidth + 1 || box.left < -1 || box.right > root.clientWidth + 1,
+                        noteInside: noteBox.width > 0 && noteBox.left >= -1 && noteBox.right <= root.clientWidth + 1,
+                      };
+                    }"""
+                )
+                assert not geometry["pageOverflow"], f"{width}px {lang}: page overflow"
+                assert not geometry["pillClipped"], f"{width}px {lang}: tab label clipped"
+                assert geometry["noteInside"], f"{width}px {lang}: overdue note missing or outside"
+                page.screenshot(path=str(shots / f"stays-default-{lang}-{width}.png"), full_page=True)
+        browser.close()
PATCH
cd /tmp/ubyhost-b10-worktree && git apply --check /tmp/b10-tests.patch 2>&1 | tail -30
```
Check fails: STOP. Else:
```
cd /tmp/ubyhost-b10-worktree && git apply /tmp/b10-tests.patch && git add -A App && git commit -q -m "0968 step 3" 2>&1 | tail -3
```

### Step 4: run the tests (section 6), then look at the screenshots

## 5. Do not touch

`App/app/routes/admin.py`, any query, the overdue rule, `reporting.py`, `app.js`, `host.css`, other templates, other tests, `docs/` except the report. No secrets, no guest data in the report (the fixtures are fake). Never push, merge or open a PR beyond what the report step says; the owner merges.

## 6. Commands

From `/tmp/ubyhost-b10-worktree/App`. Each ends with `2>&1 | tail -30`. Use `-rs` so skips show; skipped means failed.

1. New and changed tests:
```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b10 .venv/bin/python -m pytest tests/test_host_filter_panels_browser.py tests/test_0285_rows_browser.py -q -rs --tb=short -x 2>&1 | tail -30
```
Expect all pass, 0 skipped.
2. Static keys: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30`
3. Host stay-list and layout row (test-map "Host pages" row plus design guardrails browser):
```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b10 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_0523_stays_list.py tests/test_wp33_gates.py tests/test_archive_stays_on_page.py tests/test_stays_empty_workspace.py tests/test_design_guardrails_browser.py tests/test_0766_phone_stays_browser.py -q -rs --tb=short -x 2>&1 | tail -30
```
4. Copy and translation row: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`
5. Layout lint (UX gate, AGENTS rule 10): `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b10 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs --tb=short 2>&1 | tail -30` (if that file does not exist, write "missing" in the report and stop; do not search).
6. Lint from the repo root: `cd /tmp/ubyhost-b10-worktree && python3 scripts/context_lint.py 2>&1 | tail -30`

A command fails: read the last 30 lines, fix once inside the files in section 3, rerun. Fails again: STOP.
`tests/test_0285_rows_browser.py` opens a demo-seeded host; a failure there that is not about the tab label: STOP and report, do not fix.

### Screenshots (look at each once; write what you saw per file)

In `/tmp/ubyhost-b10` after command 1 you should have: `stays-default-{en,cs}-{390,768,1280}.png` (6 files), `filter-open-en-1280.png`, `filter-applied-en-1280.png`, `filter-empty-en-1280.png`, `heights.txt`. Open each with the image reader and decide pass or fail:

- Default tab, all 6: the highlighted tab label reads "Upcoming, current & overdue" (cs: "Nadcházející, aktuální a po termínu"), the note line sits under the tabs, an ended stay with an overdue badge is in the list, nothing is clipped or overlapping, no horizontal scroll. At 390 px the pills may wrap onto a second line; that is fine, clipping is not. At 390 px the phone list heading above the ended stay reads "Overdue, not reported" (cs "Po termínu, nenahlášeno").
- filter-open 1280: the fields and the Apply and Cancel buttons are on one row; there is no Reset button in the panel.
- filter-applied 1280: the scope line names the property; the "Reset filters" link is above the panel, far from Cancel.
- filter-empty 1280: the empty message and the Reset filters link are visible.
- `heights.txt` has `panel_height_1280`. Copy the number into the report. The old panel was two rows (fields, then buttons); the new one is one row, which the test asserts.

## 7. Acceptance

- [ ] Tab label says overdue in en, cs, vi (keys in section 3 files); overdue stay still listed on the default tab; archived stay not.
- [ ] Note line shows only on the default (upcoming) tab and only when an ended stay is on the page.
- [ ] Filter panel: Apply and Cancel only; fields and buttons in one row at 1280 px; Reset filters link under the scope line, at least 40 px above Cancel.
- [ ] Apply keeps scope visible in the summary; page 2 link keeps apartment and range; Cancel closes without navigating; Reset filters clears the scope; empty filtered result still shows the empty state.
- [ ] Commands 1 to 6 pass, 0 skipped.
- [ ] One 390 px screenshot of the default tab viewed, and the 768 and 1280 ones, with a line per file in the report.
- [ ] Report written, Status set to `review`.

## 8. Stop and ask

Stop, write the report as `blocked`, and say which step you finished if:

- `git apply --check` fails for a patch (an anchor is missing);
- a test fails twice, or any test is skipped;
- the screenshot check fails (clipped label, overlap, Reset next to Cancel, panel still two rows at 1280). Say which and attach the file name; do not tune CSS beyond the appended rule without asking;
- you reach 25 tool calls or about 50k tokens (executor.md: write the report as `blocked`);
- a file outside section 3 needs a change, a new dependency is needed, or you need push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/0968-report.md` (600 tokens at most): files changed (`git diff --stat 7b0355c4`), each command with the last 5 lines, section 7 ticked, one line per screenshot (pass or fail and what you saw), `panel_height_1280`, deviations, questions, owner steps. Set `Status: review` in this brief, commit as `0968 report`, and stop. Do not push or open a PR: the orchestrator hands that to the owner.

## Risk list (for the reviewer)

- `App/app/templates/reservations.html`: the Reset link moved out of the form; `[data-stays-reset]` is the new hook.
- `App/app/static/app2.css`: the appended rule targets `form.stays-filter:not(.is-collapsed)` at 1024 px and up only; no-JS shows the form open and is covered by the same rule.
- Saved views use `[data-filter-summary]` text; the Reset link is deliberately outside that paragraph.

## Owner steps

1. Review the PR diff for the files in the Risk list.
2. Merge with `scripts/merge-pr-on-green.sh` once CI is green. Deploy is yours, as usual.
