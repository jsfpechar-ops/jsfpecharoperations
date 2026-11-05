# 0963: Remove redundant property wrappers and headings (batch B05: P04, P05, P06, P09)

Status: todo
Depends on: B04 (merge order only; this brief is built on base 7b0355c and touches no B04 hunk) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0963-b05-property-wrappers
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the property page: one Stay fee heading (the accordion title), the police section with one title and three subsections (Connection to UbyPort, Accommodation facility, When to send to UbyPort), a direct secondary "Archive property" button instead of the Archive accordion, and a copy-property chooser on the rounded common dialog surface. No change to fees, exports, police credentials or archive semantics.

## 2. Context

Hard rules that apply: AGENTS.md 5 (no new SQL), 6 (light mode), 7 (template/CSS change: browser tests 0 skipped + 390 px screenshot per changed page), 9 (copy: no sentence the button already says), 10 (UX gate is done by the orchestrator, not you). Work in the worktree /tmp/ubyhost-b05-worktree. All paths below are from its root.

Findings from the review (what was seen):
- P04: expanded Stay fee shows the accordion title, then `Stay fee (poplatek z pobytu)` again.
- P05: Foreigner police shows an inner `Police reporting` heading, then `When to send to UbyPort`.
- P06: Archive is an accordion hiding one button, wording repeated three times.
- P09: on `/apartments/new` the copy chooser is a square dialog with a dark UA border. Cause (verified): v2 pages load only tokens.css, app2.css and command.css, so the `.host-workspace .ui-dialog` rules in host2.css never apply. The fix is CSS in app2.css scoped to `.copy-settings-dialog`; `_copy_settings_dialog.html` needs NO change (markup already follows the `ui_dialog_begin` macro).

Current anchors (all must be found, else STOP, section 8):

```
grep -nF '<details class="prop-sec" id="sec-archive"' App/app/templates/_property_editor.html
grep -nF "<div class=\"field-label-row\"><h2 class=\"property-section-title\">{{ t('apartment.form.stay_fee.heading') }}" App/app/templates/_property_editor.html
grep -nF "{{ t('host.reporting') }}{{ help_tip('ubyport-help'" App/app/templates/_property_editor.html
grep -nF "{{ text_field('uby_mark'," App/app/templates/_property_editor.html
grep -nF '"property_page.sec.archive.sub": "Hide the property from the list",' App/app/host_i18n.py
grep -nF '"property_page.sec.archive.sub": "Skrýt nemovitost ze seznamu",' App/app/host_i18n.py
grep -nF 'app2.css?v=20261105-0961a' App/app/templates/base.html
grep -nF 'assert names == ["basics", "archive", "messages", "police", "fee", "calendars", "lock"]' App/tests/test_0534_property_page_v2.py
grep -nF 'assert visible == ["basics", "police", "calendars", "messages", "lock", "fee", "archive"]' App/tests/test_0534_property_page_v2.py
```

Why these two extra files are in section 3 (owner-approved scope exceptions, needed or the suite breaks): `base.html` holds the only `?v=` cache key of app2.css (rule: a changed static file needs a new key; `test_static_versions.py`), and `test_0534_property_page_v2.py` asserts Archive is a `<details>` section.

Kept on purpose (tests depend on them): `id="sec-archive"` (now a div, CSS `body.v2 #sec-archive{order:7}` still orders it last), `id="archive"` before the savebar, `id="ubyport"`, `id="automation"`, `id="stay-fee-settings"`, `.police-section-head`, `#police-sample-link` before the IDUB field, the first `.property-section-title` inside `#ubyport`.

Known: the stay-fee lede help tip (`apartment.form.stay_fee.lede`, "Optional. Only for your report... Guests never see it.") was attached to the removed duplicate heading and is dropped with it. Do not re-add it; the orchestrator decides. Archive proceed label in the shared confirm dialog and its square look are existing behaviour; do not touch.

Known pre-existing failure on the base commit (verified): `tests/test_reporting_help_0097.py::test_reporting_and_fee_list_geometry_and_tips_in_the_browser` times out on a hidden tap target. It fails identically without this patch. Do not run it, do not fix it, mention it in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_property_editor.html | edit | fee heading removed; police subsections; Archive row |
| App/app/host_i18n.py | edit | 3 keys x EN and CS: `property_page.archive.button`, `property_page.police.connection`, `property_page.police.facility` |
| App/app/static/app2.css | edit (append) | archive row + copy dialog rules, v2 only |
| App/app/templates/base.html | edit | app2.css `?v=` key to `20261105-0963a` |
| App/tests/static_versions.json | regenerate | by the script in step 4, never by hand |
| App/tests/test_0534_property_page_v2.py | edit | two asserts: archive is no longer a details section |
| App/tests/test_host_property_controls_browser.py | append | 2 browser tests, EN+CS, 390/768/1280 |
| docs/tasks/0963-report.md | create | report |

`App/app/templates/_copy_settings_dialog.html` is allowed but needs no change. No other file may change. No new dependency, no SQL, no migration.

## 4. Steps

Setup (once): `ln -s /tmp/ubyhost-0958-worktree/App/.venv App/.venv` (if the link exists, skip). Then `mkdir -p /tmp/ubyhost-b05`. Commit after each step with message `0963 step k`.

Each patch is saved with a heredoc and applied from the worktree root. Check first with `--check`. A failed check is a STOP (the file drifted).

### Step 1: templates and copy keys

```
cat > /tmp/ubyhost-b05/1.patch <<'PATCH_EOF'
diff --git a/App/app/templates/_property_editor.html b/App/app/templates/_property_editor.html
index c3b23826..363a5ac6 100644
--- a/App/app/templates/_property_editor.html
+++ b/App/app/templates/_property_editor.html
@@ -123,32 +123,20 @@
 
   </div>
   </details>
-<details class="prop-sec" id="sec-archive"{% if inline_flash_section == 'archive' %} open{% endif %}><summary><span class="dot {{ 'n' }}" aria-hidden="true"></span><div><b>{{ t('property_page.sec.archive.title') }}</b></div><small class="sec-state">{{ t('property_page.sec.archive.sub') }}</small></summary>
-  <div class="fields-wrap">
+<div class="prop-archive-row" id="sec-archive">
   {{ section_notice('archive') }}
-    <section class="panel property-section ui-section property-archive" id="archive">
-      {% if apartment.archived_at %}
-      <div class="setup-item">
-        <div class="grow">
-          <strong>{{ t('apartments.archived.when') }} {{ apartment.archived_at | date_cz }}</strong>
-          <div class="ui-sub">{{ t('apartment.form.archived_help') }}</div>
-        </div>
-        <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit" formmethod="post" formnovalidate
-                formaction="{{ base_url }}/unarchive">{{ t('common.restore') }}</button>
-      </div>
-      {% else %}
-      <div class="setup-item">
-        <div class="grow">
-          <strong>{{ t('apartment.form.archive_title') }}</strong> {{ help_tip('archive-help', t('apartment.form.archive_help')) }}
-        </div>
-        <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit" formmethod="post" formnovalidate
-                formaction="{{ base_url }}/archive"
-                data-confirm data-confirm-message="{{ t('host.delete_to_archived.confirm') }}">{{ t('common.archive') }}</button>
-      </div>
-      {% endif %}
-    </section>
+  <div class="prop-archive-actions" id="archive">
+    {% if apartment.archived_at %}
+    <p class="prop-archive-note"><strong>{{ t('apartments.archived.when') }} {{ apartment.archived_at | date_cz }}</strong> <span class="ui-sub">{{ t('apartment.form.archived_help') }}</span></p>
+    <button class="ui-btn ui-btn-secondary" type="submit" formmethod="post" formnovalidate
+            formaction="{{ base_url }}/unarchive">{{ t('common.restore') }}</button>
+    {% else %}
+    <button class="ui-btn ui-btn-secondary" type="submit" formmethod="post" formnovalidate
+            formaction="{{ base_url }}/archive"
+            data-confirm data-confirm-message="{{ t('host.delete_to_archived.confirm') }}">{{ t('property_page.archive.button') }}</button>{{ help_tip('archive-help', t('apartment.form.archive_help')) }}
+    {% endif %}
   </div>
-  </details>
+</div>
 
   {# ---- Guest experience ---------------------------------------------- #}
 <details class="prop-sec" id="sec-messages"{% if inline_flash_section == 'messages' %} open{% endif %}{% if settings_section == 'guests' %} open{% endif %}><summary><span class="dot {{ 'n' }}" aria-hidden="true"></span><div><b>{{ t('property_page.sec.messages.title') }}</b></div><small class="sec-state">{{ t('property_page.sec.messages.sub') }}</small></summary>
@@ -232,7 +220,7 @@
   <div class="fields-wrap">
   {{ section_notice('police') }}
     <section class="panel property-section ui-section" id="ubyport">
-      <div class="field-label-row police-section-head"><h2 class="property-section-title">{{ t('host.reporting') }}{{ help_tip('ubyport-help', t('apartment.form.ubyport.credentials_help_heading'), '/guide#ubyport-credentials') }}</h2>
+      <div class="field-label-row police-section-head"><h2 class="property-section-title">{{ t('property_page.police.connection') }}{{ help_tip('ubyport-help', t('apartment.form.ubyport.credentials_help_heading'), '/guide#ubyport-credentials') }}</h2>
         <a class="ui-btn ui-btn-secondary ui-btn-compact police-sample-link" id="police-sample-link" href="/static/docs/ubyport-ws-credential-sample.pdf?v=20261004a" target="_blank" rel="noopener">{{ t('apartment.form.ubyport.sample_link') }}</a></div>
       <p class="ui-sub">{{ t('why.police') }}</p>
       <p class="ui-sub"><a href="{{ base_url }}?view=settings&amp;section=automation#automation">{{ t('automation.timing_title') }} </a></p>
@@ -256,6 +244,7 @@
       </div>
       <p class="small muted police-no-credentials">{{ t('apartment.form.ubyport.no_credentials') }}
         <a href="https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/jake-jsou-moznosti-zasilani-dat-aplikaci-ubyport" target="_blank" rel="noopener">{{ t('apartment.form.ubyport.no_credentials_link') }}</a></p>
+      <div class="field-label-row"><h2 class="property-section-title">{{ t('property_page.police.facility') }}</h2></div>
       <div class="grid">
         {{ text_field('uby_mark', t('apartment.form.ubyport.mark_label'), apartment.uby_mark, t('apartment.form.ubyport.mark_hint'), false, 6) }}
       </div>
@@ -308,7 +297,6 @@
   <div class="fields-wrap">
   {{ section_notice('fee') }}
     <section class="panel property-section ui-section" id="stay-fee-settings">
-      <div class="field-label-row"><h2 class="property-section-title">{{ t('apartment.form.stay_fee.heading') }}{{ help_tip('stay-fee-help', t('apartment.form.stay_fee.lede')) }}</h2></div>
       <p class="ui-sub">{{ t('why.stay_fee') }}</p>
       {% if fee_return_to %}
       <p class="small fee-return-note"><a href="{{ fee_return_to }}"> {{ t('stay_fees.setup.back_to_report') }}</a></p>
PATCH_EOF
git apply --check /tmp/ubyhost-b05/1.patch && git apply /tmp/ubyhost-b05/1.patch
cat > /tmp/ubyhost-b05/2.patch <<'PATCH_EOF'
diff --git a/App/app/host_i18n.py b/App/app/host_i18n.py
index b265a7d7..cf0f99d3 100644
--- a/App/app/host_i18n.py
+++ b/App/app/host_i18n.py
@@ -7816,6 +7816,9 @@ _PROPERTY_NAV_0094_STRINGS = {
         "property_page.strip.operator_missing": "Operator missing",
 
         "property_page.sec.archive.sub": "Hide the property from the list",
+        "property_page.archive.button": "Archive property",
+        "property_page.police.connection": "Connection to UbyPort",
+        "property_page.police.facility": "Accommodation facility",
         "property_page.sec.calendars.title": "Calendars",
         "property_page.sec.calendars.sub": "Airbnb and Booking",
         "property_nav.group.property": "Property information",
@@ -7854,6 +7857,9 @@ _PROPERTY_NAV_0094_STRINGS = {
         "property_page.strip.operator_missing": "Chybí provozovatel",
 
         "property_page.sec.archive.sub": "Skrýt nemovitost ze seznamu",
+        "property_page.archive.button": "Archivovat nemovitost",
+        "property_page.police.connection": "Připojení k UbyPortu",
+        "property_page.police.facility": "Ubytovací zařízení",
         "property_page.sec.calendars.title": "Kalendáře",
         "property_page.sec.calendars.sub": "Airbnb a Booking",
         "property_nav.group.property": "Údaje o ubytování",
PATCH_EOF
git apply --check /tmp/ubyhost-b05/2.patch && git apply /tmp/ubyhost-b05/2.patch
git add -A App && git commit -q -m "0963 step 1" 2>&1 | tail -3
```

### Step 2: stylesheet and cache key

```
cat > /tmp/ubyhost-b05/3.patch <<'PATCH_EOF'
diff --git a/App/app/static/app2.css b/App/app/static/app2.css
index 66fbf0f5..5a475106 100644
--- a/App/app/static/app2.css
+++ b/App/app/static/app2.css
@@ -2589,3 +2589,28 @@ body.v2 form.property-settings-form .btn,body.v2 form.property-settings-form .ui
   body.v2 .ui-body-detail:has(> aside.preview) > aside.preview{grid-column:2;grid-row:1;align-self:start;position:sticky;top:24px;z-index:1}
 }
 @media (max-width:1023px){body.v2 .ui-body-detail:has(> aside.preview) > aside.preview{position:static}}
+
+/* 0963: the direct Archive property row, and the copy-property chooser on the common dialog surface (v2 pages do not load host2.css) */
+body.v2 .prop-archive-row{padding:4px 0 8px}
+body.v2 .prop-archive-actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
+body.v2 .prop-archive-actions .ui-btn{min-height:44px}
+body.v2 .prop-archive-note{margin:0;flex:1 1 240px;min-width:0}
+body.v2 .ui-dialog.copy-settings-dialog{border:0;padding:0;background:transparent;max-width:none;width:min(var(--dialog-w),calc(100vw - var(--space-8)))}
+body.v2 .ui-dialog.copy-settings-dialog::backdrop{background:var(--scrim)}
+body.v2 .copy-settings-dialog .ui-sheet{background:var(--surface);border-radius:var(--sheet-radius);padding:var(--space-6);box-shadow:var(--shadow-3);max-height:calc(100dvh - var(--space-8));overflow:auto;box-sizing:border-box}
+body.v2 .copy-settings-dialog .ui-sheet-handle{display:none}
+body.v2 .copy-settings-dialog h2{margin:0 0 var(--space-3);font-size:var(--size-18);font-weight:var(--control-weight)}
+body.v2 .copy-settings-dialog h3{margin:var(--space-4) 0 var(--space-2);font-size:var(--size-14);font-weight:var(--control-weight)}
+body.v2 .copy-settings-dialog select{width:100%;min-width:0}
+body.v2 .copy-settings-list{margin:0;padding-left:1.25rem}
+body.v2 .copy-settings-list li+li{margin-top:var(--space-1)}
+body.v2 .copy-settings-never{margin:0}
+body.v2 .copy-settings-dialog .ui-sub{margin:var(--space-3) 0 0}
+body.v2 .copy-settings-dialog .copy-settings-actions{display:flex;flex-wrap:wrap;gap:var(--space-3);margin-top:var(--space-5)}
+body.v2 .copy-settings-dialog .copy-settings-actions .ui-btn{min-height:44px}
+@media (max-width:767px){
+  body.v2 .ui-dialog.copy-settings-dialog{width:100vw;max-width:100vw;margin:0;position:fixed;inset:auto 0 0 0}
+  body.v2 .copy-settings-dialog .ui-sheet{border-radius:var(--sheet-radius) var(--sheet-radius) 0 0;max-height:85dvh;padding:var(--space-2) var(--space-4) calc(var(--space-6) + env(safe-area-inset-bottom))}
+  body.v2 .copy-settings-dialog .ui-sheet-handle{display:block;width:var(--space-8);height:var(--space-1);border-radius:var(--radius-pill);background:var(--line-strong);margin:var(--space-1) auto var(--space-4)}
+  body.v2 .copy-settings-dialog .copy-settings-actions .ui-btn{flex:1 1 0}
+}
PATCH_EOF
git apply --check /tmp/ubyhost-b05/3.patch && git apply /tmp/ubyhost-b05/3.patch
cat > /tmp/ubyhost-b05/4.patch <<'PATCH_EOF'
diff --git a/App/app/templates/base.html b/App/app/templates/base.html
index 45ca7693..076078d2 100644
--- a/App/app/templates/base.html
+++ b/App/app/templates/base.html
@@ -19,7 +19,7 @@
   <link rel="preload" href="/static/fonts/Manrope-latin.woff2?v=20261101-0495" as="font" type="font/woff2" crossorigin>
   {% if v2 | default(false) %}
   <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261103-0920">
-  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261105-0961a">
+  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261105-0963a">
   {% if show_nav | default(true) %}<link rel="stylesheet" data-turbo-track="reload" href="/static/command.css?v=20261103-0935">{% endif %}
   {% else %}
   <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261103-0920">
PATCH_EOF
git apply --check /tmp/ubyhost-b05/4.patch && git apply /tmp/ubyhost-b05/4.patch
cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3 && cd ..
git add -A App && git commit -q -m "0963 step 2" 2>&1 | tail -3
```

If B04 has already merged and `git apply --check` on 4.patch fails because the key differs, STOP and report (do not guess a key).

### Step 3: tests

```
cat > /tmp/ubyhost-b05/5.patch <<'PATCH_EOF'
diff --git a/App/tests/test_0534_property_page_v2.py b/App/tests/test_0534_property_page_v2.py
index 896ccab1..006dd71e 100644
--- a/App/tests/test_0534_property_page_v2.py
+++ b/App/tests/test_0534_property_page_v2.py
@@ -43,7 +43,8 @@ def test_sections_are_details_in_order(host):
     # 0536: the fixture has no door codes, but the lock section is always rendered
     # (connect text only). DOM order; v2 CSS puts them in mockup order (0952: the one lock
     # section sits after the property form, so it is last in the DOM).
-    assert names == ["basics", "archive", "messages", "police", "fee", "calendars", "lock"]
+    # 0963: archive is a direct button row (id sec-archive), no longer a details section.
+    assert names == ["basics", "messages", "police", "fee", "calendars", "lock"]
 
 
 def test_0536_setup_continue_is_the_first_aside_card(host):
@@ -143,7 +144,7 @@ def test_rendered_sections_show_in_mockup_order(host):
     client, apartment_id = host
     names = [name for name, _ in _sections(_page(client, apartment_id))]
     visible = sorted(names, key=lambda name: MOCKUP_ORDER[name])
-    assert visible == ["basics", "police", "calendars", "messages", "lock", "fee", "archive"]
+    assert visible == ["basics", "police", "calendars", "messages", "lock", "fee"]
 
 
 def test_aside_has_cards_and_links_to_each_section(host):
PATCH_EOF
git apply --check /tmp/ubyhost-b05/5.patch && git apply /tmp/ubyhost-b05/5.patch
cat > /tmp/ubyhost-b05/6.patch <<'PATCH_EOF'
diff --git a/App/tests/test_host_property_controls_browser.py b/App/tests/test_host_property_controls_browser.py
index 12b572e2..0484993e 100644
--- a/App/tests/test_host_property_controls_browser.py
+++ b/App/tests/test_host_property_controls_browser.py
@@ -555,3 +555,131 @@ def test_guest_links_and_message_settings_geometry(host, base):
                 tip_top = page.evaluate(_TIP_JS, "ocr_scan")
                 assert tip_top is not None and abs(tip_top[0] - cb["y"]) <= 6, tip_top
         browser.close()
+
+
+# --- 0963: one Stay fee heading, one police title, direct Archive, copy chooser on the common dialog ---
+
+SHOTS_0963 = Path(os.environ.get("UBYHOST_SHOTS_DIR", "/tmp/ubyhost-b05"))
+
+
+def _shot_0963(page, name):
+    SHOTS_0963.mkdir(parents=True, exist_ok=True)
+    page.screenshot(path=str(SHOTS_0963 / f"{name}.png"), full_page=False)
+
+
+def _open_page_0963(browser, base, host, path, width):
+    context = browser.new_context(viewport={"width": width, "height": 900}, has_touch=width < 700)
+    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _session_cookie(host), "url": base}])
+    page = context.new_page()
+    page.goto(f"{base}{path}")
+    page.wait_for_load_state("networkidle")
+    return context, page
+
+
+def test_0963_fee_and_police_headings_and_archive_button(host, base):
+    apartment = host["apartment"]
+    with sync_api.sync_playwright() as playwright:
+        browser = playwright.chromium.launch(**chromium_launch_kwargs())
+        try:
+            for lang, fee_title, police_title, connection, facility, archive_label in (
+                ("en", "Stay fee", "Foreigner police", "Connection to UbyPort", "Accommodation facility", "Archive property"),
+                ("cs", "Poplatek z pobytu", "Cizinecká policie", "Připojení k UbyPortu", "Ubytovací zařízení", "Archivovat nemovitost"),
+            ):
+                for width in (390, 768, 1280):
+                    context, page = _open_page_0963(browser, base, host, f"/apartments/{apartment}?lang={lang}", width)
+                    try:
+                        label = (lang, width)
+                        # Stay fee: the accordion title once, no inner duplicate; opens and closes.
+                        fee = page.locator("#sec-fee")
+                        fee.locator("> summary").click()
+                        assert fee.evaluate("e => e.open") is True, label
+                        assert fee_title in fee.locator("> summary b").inner_text(), label
+                        inner = [" ".join(h.split()).lower() for h in fee.locator("h2, h3").all_text_contents()]
+                        assert not any(h.startswith(fee_title.lower()) for h in inner), (label, inner)
+                        assert fee.locator("h2.property-section-title").count() == 0, label
+                        assert fee.locator("#stay-fee-settings").count() == 1, label
+                        fee.locator("> summary").click()
+                        assert fee.evaluate("e => e.open") is False, label
+                        # Police: one title, three meaningful subsections, no synonym heading.
+                        police = page.locator("#sec-police")
+                        police.locator("> summary").click()
+                        assert police.evaluate("e => e.open") is True, label
+                        assert police_title in police.locator("> summary b").inner_text(), label
+                        heads = [" ".join(h.split()) for h in police.locator("h2.property-section-title").all_text_contents()]
+                        assert len(heads) == 3, (label, heads)
+                        assert heads[0].startswith(connection) and heads[1].startswith(facility), (label, heads)
+                        assert not any(h.startswith(("Police reporting", "Hlášení policii")) for h in heads), (label, heads)
+                        assert police.locator("#police-sample-link").count() == 1, label
+                        if width == 390:
+                            _shot_0963(page, f"police-open-{lang}-390")
+                        police.locator("> summary").click()
+                        assert police.evaluate("e => e.open") is False, label
+                        # Archive: a direct secondary button, no accordion, not clipped.
+                        assert page.locator("details#sec-archive").count() == 0, label
+                        button = page.locator("#archive button[formaction$='/archive']")
+                        assert button.count() == 1 and button.inner_text().strip() == archive_label, label
+                        assert "ui-btn-secondary" in button.get_attribute("class"), label
+                        button.scroll_into_view_if_needed()
+                        box = button.bounding_box()
+                        assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1 and box["height"] >= 40, (label, box)
+                        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"), label
+                        page.evaluate("document.activeElement && document.activeElement.blur()")
+                        assert not page.locator("#archive-help").is_visible(), label  # the tip stays closed until asked
+                        if lang == "en":
+                            _shot_0963(page, f"archive-{width}")
+                            # Click -> existing confirmation -> Cancel changes nothing.
+                            url_before = page.url
+                            button.click()
+                            dialog = page.locator("#confirm-dialog")
+                            dialog.wait_for(state="visible")
+                            assert dialog.locator("[data-confirm-cancel]").is_visible(), label
+                            if width == 390:
+                                _shot_0963(page, "archive-confirm-390")
+                            dialog.locator("[data-confirm-cancel]").click()
+                            dialog.wait_for(state="hidden")
+                            assert page.url == url_before, label
+                            row = db.query_one("SELECT archived_at, active FROM apartment WHERE id = ?", (apartment,))
+                            assert row["archived_at"] is None and row["active"] == 1, label
+                    finally:
+                        context.close()
+        finally:
+            browser.close()
+
+
+def test_0963_copy_chooser_uses_the_common_dialog_and_cancel_keeps_form_data(host, base):
+    with sync_api.sync_playwright() as playwright:
+        browser = playwright.chromium.launch(**chromium_launch_kwargs())
+        try:
+            for lang in ("en", "cs"):
+                for width in (390, 768, 1280):
+                    context, page = _open_page_0963(browser, base, host, f"/apartments/new?lang={lang}", width)
+                    try:
+                        label = (lang, width)
+                        name = page.locator("input[name='internal_name']").first
+                        name.fill("Keep me 0963")
+                        page.locator(".airbnb-actions .copy-settings-open").first.click()
+                        dialog = page.locator("#copy-settings")
+                        dialog.wait_for(state="visible")
+                        page.wait_for_timeout(500)
+                        style = dialog.evaluate(
+                            """d => { const s = d.querySelector('.ui-sheet'); const c = getComputedStyle(d), k = getComputedStyle(s);
+                                      const r = d.getBoundingClientRect(); const q = s.getBoundingClientRect();
+                                      return {border: c.borderTopWidth, radius: k.borderTopLeftRadius, bg: k.backgroundColor,
+                                              left: r.left, right: r.right, top: q.top, bottom: q.bottom,
+                                              vw: document.documentElement.clientWidth, vh: innerHeight}; }""")
+                        assert style["border"] == "0px", (label, style)
+                        assert style["radius"] != "0px" and style["bg"] == "rgb(255, 255, 255)", (label, style)
+                        assert style["left"] >= -1 and style["right"] <= style["vw"] + 1, (label, style)
+                        assert style["top"] >= -1 and style["bottom"] <= style["vh"] + 1, (label, style)
+                        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"), label
+                        select = dialog.locator("select#copy_from")
+                        select.select_option(index=0)
+                        assert select.input_value(), label
+                        _shot_0963(page, f"copy-dialog-{lang}-{width}")
+                        dialog.locator("[data-sheet-close]").click()
+                        dialog.wait_for(state="hidden")
+                        assert name.input_value() == "Keep me 0963", label
+                    finally:
+                        context.close()
+        finally:
+            browser.close()
PATCH_EOF
git apply --check /tmp/ubyhost-b05/6.patch && git apply /tmp/ubyhost-b05/6.patch
git add -A App && git commit -q -m "0963 step 3" 2>&1 | tail -3
```

### Step 4: run the commands in section 6, then screenshots, then the report (section 9).

## 5. Do not touch

Fee logic and `_stay_fee_fields.html`, exports, police credentials and their validation, archive/unarchive routes and the confirmation text (`host.delete_to_archived.confirm`), `app.js`, `host.css`, `host2.css`, any other template, any other i18n file (host_vi_i18n.py has no entry for the 3 new keys by design; see section 8). Never push, merge or open a PR; the owner does that.

## 6. Commands

Run from `App/`. Always with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b05`. Browser tests: add `-rs`; 0 skipped.

```
cd /tmp/ubyhost-b05-worktree/App
export UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b05
# 1. the new tests (expect 2 passed)
.venv/bin/python -m pytest tests/test_host_property_controls_browser.py -k 0963 -q -rs --tb=short -x 2>&1 | tail -30
# 2. static and property rows (expect all passed)
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_0534_property_page_v2.py tests/test_property_navigation_browser.py tests/test_ubyport_sample_pdf.py tests/test_copy_property_settings.py tests/test_0913_property_stay_fee.py -q -rs --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_property_*.py tests/test_onboarding*.py tests/test_first_*.py -q -rs --tb=short -x 2>&1 | tail -30
# 3. copy row
.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30
# 4. host row (0 skipped) and design guardrails, layout lint
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30
# 5. v2 row
.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -rs --tb=short -x 2>&1 | tail -30
```

Each of 2 to 5 may exceed the 120 s tool timeout: run it with run_in_background and read the output file. A command that has a failing test: read the last 30 lines, fix once, rerun; second failure is a STOP. If `-x` stops on a test that also fails on base (check with `git stash`, run, `git stash pop`), write it in Deviations and continue with `--deselect` for that one test.

Side effect: some host tests rewrite tracked PNGs under `docs/tasks/*-evidence/`. After the last test run do `git status --short | grep -v '^ M App' | head` and restore them with `git checkout -- docs/tasks/<the evidence folder>`; never stage them. Commit only the files in section 3 (`git add -A App` and the brief and report by name).

Expected: the orchestrator ran rows 1, 2 and the i18n row on this exact patch (all green except the pre-existing 0097 test). Rows 4 and 5 were not run by the orchestrator.

## 7. Acceptance (tick in the report)

Chromium, EN and CS, at 390, 768 and 1280 (the new tests assert these; describe the screenshots from them):
- [ ] Stay fee: opens and closes; only the accordion title says "Stay fee" / "Poplatek z pobytu"; first content is the numbered settings (no duplicated heading).
- [ ] Foreigner police: opens and closes; one title; three subsection headings (Connection to UbyPort, Accommodation facility, When to send to UbyPort); no "Police reporting" heading; example-letter link still beside the first subsection heading.
- [ ] Archive: no accordion; one secondary "Archive property" button (CS "Archivovat nemovitost") in the lower area after Stay fee, not clipped, no horizontal scroll; click opens the existing confirmation; Cancel closes it, URL unchanged, `archived_at` still NULL.
- [ ] Copy chooser on `/apartments/new`: opens, shows rounded white surface (not square, no dark border), selecting works, Cancel closes it and the typed property name is still in the form. At 390 it is a bottom sheet fully inside the viewport.
- [ ] No nested forms (`test_property_navigation_browser.py` passes), no duplicate ids.
- [ ] 0 skipped in every browser file. `git diff --stat 7b0355c..HEAD` lists only the files in section 3.
- [ ] Screenshots in /tmp/ubyhost-b05 (written by the tests): `archive-390.png`, `archive-768.png`, `archive-1280.png`, `archive-confirm-390.png`, `police-open-en-390.png`, `copy-dialog-en-390.png`, `copy-dialog-cs-390.png`, `copy-dialog-en-768.png`, `copy-dialog-en-1280.png`. Open each once and write one sentence per file saying what you see (heading count, button fully visible, dialog corners, overflow). A screenshot you did not open is not evidence.

## 8. Stop and ask

Stop and write the report (Status: blocked) if: an anchor in section 2 is not found; `git apply --check` fails; a test fails twice; a test outside the list fails and also fails on base only if you cannot show that with `git stash`; you reach 25 tool calls or about 50k tokens; a file outside section 3 needs a change; `host_vi_i18n.py` or a parity test demands the 3 new keys (do not edit it, report the test name); you need push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/0963-report.md` (600 tokens at most): files changed (`git diff --stat 7b0355c..HEAD`), each command with its last 5 lines, section 7 ticked with one sentence per screenshot, Deviations (include the pre-existing 0097 failure), Questions, owner steps left. Set `Status: review` at the top of this brief. Commit both as `0963 report`. Do not push or open a PR.

## Risk list (for the reviewer)

- `_property_editor.html`: Archive button stays inside `#property-settings-form` (formaction submit, same as before); a second form must not appear. `id="archive"` and `id="sec-archive"` kept.
- `app2.css` append: v2-only rules; `.copy-settings-dialog` scoped, no other dialog touched.
- Lost help tip: stay-fee lede (see section 2).

## Owner steps

None for the executor. After review the owner merges with `scripts/merge-pr-on-green.sh` after B04.
