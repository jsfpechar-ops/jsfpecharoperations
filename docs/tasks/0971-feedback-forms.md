# 0971: One success pattern and independent cleaning save forms (batch B13: X02, C07)

Status: todo
Depends on: none | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0971-b13-feedback
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Inline success notices (the new `success_notice` macro, the property-editor section notice, the cleaning list notice) and the success toast get one compact look: check mark, readable text, one optional next action, the same 44 px dismiss button. The copy-link button loses its badge overlay and keeps its size and label. On the cleaning property page the instructions form and the manual-code form become two separate cards with equal primary Save buttons ("Save instructions", "Save manual code"); each Save submits only its own form.

## 2. Context

Rules that apply: AGENTS.md rules 2 (no new outbound request, none added), 6 (light mode, forms work without JavaScript: the macro is server-rendered, JS only adds the dismiss button), 7 (screenshots), 9 (copy). No new dependency, no migration, no new personal data.

Facts found by reading (already verified; the patch in step 2 implements them):

- v2 host pages (cleaning, property editor) load `app2.css` only, never `host.css`. All new CSS therefore goes to the end of `App/app/static/app2.css`.
- `base.html` holds the `?v=` keys for `app2.css` and `app.js`. Bumping them there is required by `tests/test_static_versions.py`. This is the only edit outside the owner's file list and it is two lines.
- Existing keys reused: `a11y.dismiss_notification` (en, cs, vi in `host_i18n.py` / `host_vi_i18n.py`), `common.copied`. New keys exist only in `cleaning_i18n.py` (cleaning pages are en and cs only): `save_instructions`, `save_manual_code`.
- Announcements: the macro uses `role="status"`; the toast rail is `aria-live="off"` and announces through the single `[data-feedback-live]` region, so nothing is announced twice. The patch adds no new live region.
- Static success toasts already get a check icon from app.js (`feedback-card-icon`, around line 1029). The patch only styles it on v2.
- `app.js` `prepareCopyControl` no longer creates the `[data-copy-state-icon]` badge (it covered the label corner). The label already swaps to "Copied" in place inside a stacked span, so size is unchanged.
- Cleaning forms become cards the same way `cleaning_edit.html` does it: wrapper class `cl-v2-edit`, panels class `card`.

Anchors (grep each with `grep -nF`; all must be found BEFORE you apply the patch, else STOP):

- `App/app/templates/_components.html`: `{% macro copy_icon() %}`
- `App/app/templates/cleaning_settings.html`: `{% from "_components.html" import help_tip with context %}`, `<p role="status">{{ ct('saved') }}</p>`, `<div class="cleaning-page cleaning-form-page settings-lane">`, `{% if code.value or code.pending %}<details class="cleaning-remove">`
- `App/app/static/app.js`: `icon.className = "copy-state-icon";`, `  function initPage() {`, `    initSectionNotice();`
- `App/app/cleaning_i18n.py`: `    "cancel": [`
- `App/app/templates/base.html`: `app2.css?v=20261105-0961a`, `app.js?v=20261104-0955g`
- `App/tests/test_cleaning_browser.py`, `App/tests/test_host_feedback_browser.py` (append only)

Callers of the shared component (the reviewer checks these; you do not edit them):

- `success_notice` macro: `cleaning_settings.html` only (new).
- Section notice `.section-notice.ok` (macro `section_notice` in `_section_notice.html`): `_property_editor.html` sections basics, archive, messages, police, fee, calendars, lock. This is the property save result.
- `p.cleaning-notice`: `_cleaning_screen.html` (cleaning created, saved, removed on `/cleaning`).
- Success toast `.toast[data-toast-kind="success"]`: `base.html` flash (stay save and others), celebration toast.
- app.js `initSuccessNotices` runs from `initPage` on every host page.
- Copy buttons (badge removal): `_components.html` (`copy_button`, `copy_inline`), `_havel_card.html`, `_property_calendars.html`, `_property_editor.html`, `_smart_lock_share.html`, `_smart_locks_panel.html`, `apartment_form.html`, `apartments.html`, `booking_site_setup.html`, `dashboard.html`, `payments_share.html`, `reservation_detail.html`, `reservations.html`, `setup_wizard/_layout.html`, `setup_wizard/guest_link.html`, `stay_fee_detail.html`, `stay_fees.html`, `submission_detail.html`, `two_factor_recovery.html`, `two_factor_setup.html`.

Smoke pages this brief checks (all named; the tests in section 6 load them):

1. `/cleaning/properties/{id}?lang=en|cs` at 390, 768, 1280 (macro notice, two forms, injected section notice, injected cleaning notice, injected success toast, injected "Copy link" button).
2. `/cleaning?lang=en&notice=saved` at 390 and 1280 (cleaning list notice, the cleaning-creation redirect target).
3. `/settings?lang=en` at 390 (legacy shell copy button, no stacked feedback).
4. Every page in `test_host_*browser.py`, `test_host_geometry.py`, `test_design_guardrails_browser.py` (they render the shared base and copy buttons).
Not smoked here (named for the reviewer): the real property-editor save banner and the real stay-save toast are checked through injected markup of the same classes, not through a real save.

Safety: the tests only submit the instructions form and the manual-code form on the test workspace (`cleaning_codes.save_manual` writes locally and calls no lock service). They never click "Create permanent TTLock code" (`/code/ttlock`), which would queue provisioning. No mail is sent.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_components.html | edit | add macro `success_notice(text, next_href='', next_label='')` before `copy_icon` |
| App/app/static/app.js | edit | `initSuccessNotices` (dismiss button), hook in `initPage`, drop the copy badge in `prepareCopyControl` |
| App/app/static/app2.css | edit | append the success pattern block |
| App/app/templates/cleaning_settings.html | edit | macro notice, two card forms, labelled Saves |
| App/app/cleaning_i18n.py | edit | keys `save_instructions`, `save_manual_code` (en, cs) |
| App/app/templates/base.html | edit | bump the `?v=` keys of `app2.css` and `app.js` only |
| App/tests/test_cleaning_browser.py | append | 0971 tests |
| App/tests/test_host_feedback_browser.py | append | 0971 test |
| App/tests/static_versions.json | regenerate | by script, not by hand |

No other file may change.

## 4. Steps

Work from the worktree `/tmp/ubyhost-b13-worktree` (already exists, branch `codex/0971-b13-feedback`, clean). Do not create another.

1. Link the venv and check the anchors:
   `ln -s /tmp/ubyhost-0958-worktree/App/.venv /tmp/ubyhost-b13-worktree/App/.venv` (skip if it exists), then the `grep -nF` of every anchor in section 2. Any miss: STOP.
2. Save the patch below to `/tmp/ubyhost-b13/0971.patch` (create the folder), run from the repo root `git apply --check /tmp/ubyhost-b13/0971.patch 2>&1 | tail -30`, then `git apply /tmp/ubyhost-b13/0971.patch`. The check fails: STOP. Commit `git add -A && git commit -m "0971 step 1"` (not `.venv`; it is ignored).
3. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`. Commit `0971 step 2`.
4. Run section 6 commands. Commit nothing from /tmp.

The patch (apply exactly; do not edit it):

```diff
diff --git a/App/app/cleaning_i18n.py b/App/app/cleaning_i18n.py
index 0823e15b..d86b6425 100644
--- a/App/app/cleaning_i18n.py
+++ b/App/app/cleaning_i18n.py
@@ -89,6 +89,14 @@ WORDS = {
         "Save",
         "Uložit"
     ],
+    "save_instructions": [
+        "Save instructions",
+        "Uložit pokyny"
+    ],
+    "save_manual_code": [
+        "Save manual code",
+        "Uložit ruční kód"
+    ],
     "cancel": [
         "Cancel",
         "Zrušit"
diff --git a/App/app/static/app.js b/App/app/static/app.js
index 746e50cb..ea518d8c 100644
--- a/App/app/static/app.js
+++ b/App/app/static/app.js
@@ -369,12 +369,7 @@ if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches
         button.appendChild(stack);
       }
     }
-    var icon = document.createElement("span");
-    icon.className = "copy-state-icon";
-    icon.setAttribute("data-copy-state-icon", "");
-    icon.setAttribute("aria-hidden", "true");
-    icon.innerHTML = '<svg viewBox="0 0 24 24" focusable="false"><path d="m5 12 4 4L19 6"/></svg>';
-    button.appendChild(icon);
+    // 0971: no badge over the button; the label swaps to "Copied" in place and keeps the button's size.
   }
 
   function initCopy() {
@@ -2405,6 +2400,34 @@ if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches
     n.focus({ preventScroll: true });
   }
 
+  // 0971: one dismiss control on every inline success notice (success_notice macro, section notice, cleaning notice).
+  function initSuccessNotices() {
+    if (!document.body.classList.contains("host-workspace")) return;
+    var root = feedbackRoot();
+    var label = (root && root.getAttribute("data-dismiss-label")) || "Dismiss notification";
+    Array.prototype.forEach.call(document.querySelectorAll("[data-success-notice], .section-notice.ok, p.cleaning-notice"), function (notice) {
+      if (!claimNode(notice, "initSuccessNotices")) return;
+      var close = notice.querySelector("[data-success-dismiss]");
+      if (!close) {
+        close = document.createElement("button");
+        close.type = "button";
+        close.className = "success-notice-close";
+        close.setAttribute("data-success-dismiss", "");
+        close.setAttribute("aria-label", label);
+        close.textContent = "\u00d7";
+        notice.appendChild(close);
+      }
+      close.addEventListener("click", function () {
+        var section = notice.closest("section");
+        var heading = (section && section.querySelector("h2")) || document.querySelector("main h1, h1");
+        notice.remove();
+        if (!heading) return;
+        if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
+        heading.focus({ preventScroll: true });
+      });
+    });
+  }
+
   function initPage() {
     initPhoneDefaultClosed();
     initPropSectionLinks();
@@ -2416,6 +2439,7 @@ if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches
     initUnsavedForms();
     initUnsavedDialog();
     initSectionNotice();
+    initSuccessNotices();
     initHelpTips();
     initBirthDateInputs();
     initRowMenus();
diff --git a/App/app/static/app2.css b/App/app/static/app2.css
index 66fbf0f5..8a217105 100644
--- a/App/app/static/app2.css
+++ b/App/app/static/app2.css
@@ -2589,3 +2589,70 @@ body.v2 form.property-settings-form .btn,body.v2 form.property-settings-form .ui
   body.v2 .ui-body-detail:has(> aside.preview) > aside.preview{grid-column:2;grid-row:1;align-self:start;position:sticky;top:24px;z-index:1}
 }
 @media (max-width:1023px){body.v2 .ui-body-detail:has(> aside.preview) > aside.preview{position:static}}
+
+/* 0971: one compact success pattern (v2 pages load app2.css only): success_notice macro, inline section notice, cleaning notice, success toast. */
+body.v2 :is(.success-notice, .section-notice.ok, p.cleaning-notice, .toast-stack .toast[data-toast-kind="success"]) {
+  display: flex;
+  flex-wrap: wrap;
+  align-items: center;
+  gap: 4px 10px;
+  box-sizing: border-box;
+  width: 100%;
+  max-width: 100%;
+  min-width: 0;
+  min-height: 44px;
+  margin: 0 0 var(--space-4, 16px);
+  padding: 4px 4px 4px 12px;
+  border: 1px solid #b9dcc8;
+  border-left: 4px solid #147a4a;
+  border-radius: 12px;
+  background: #f3faf6;
+  color: var(--ink);
+  font-size: 15px;
+  line-height: 1.4;
+  overflow-wrap: anywhere;
+}
+body.v2 :is(.success-notice, .section-notice.ok, p.cleaning-notice)::before,
+body.v2 .toast-stack .toast[data-toast-kind="success"] .feedback-card-icon {
+  flex: 0 0 24px;
+  display: inline-grid;
+  place-items: center;
+  width: 24px;
+  height: 24px;
+  margin: 0;
+  border-radius: 50%;
+  background: #edf7f1;
+  color: #147a4a;
+  font-size: 14px;
+  font-weight: 800;
+}
+body.v2 :is(.success-notice, .section-notice.ok, p.cleaning-notice, .toast-stack .toast[data-toast-kind="success"]) :is(.success-notice-text, .grow, .feedback-card-body) { flex: 1 1 160px; min-width: 0; }
+body.v2 :is(.success-notice, .section-notice.ok, p.cleaning-notice)::before { content: "\2713"; }
+body.v2 .success-notice-next {
+  flex: none;
+  display: inline-flex;
+  align-items: center;
+  min-height: 44px;
+  padding: 0 8px;
+  font-weight: 600;
+}
+body.v2 :is(.success-notice-close, .toast-stack .toast[data-toast-kind="success"] > [data-toast-close]) {
+  flex: 0 0 44px;
+  display: inline-grid;
+  place-items: center;
+  width: 44px;
+  height: 44px;
+  min-width: 44px;
+  min-height: 44px;
+  margin: 0 0 0 auto;
+  padding: 0;
+  border: 0;
+  border-radius: 8px;
+  background: transparent;
+  color: var(--ink-secondary, #5b5a55);
+  font-size: 24px;
+  line-height: 1;
+  cursor: pointer;
+}
+body.v2 :is(.success-notice-close, .toast-stack .toast[data-toast-kind="success"] > [data-toast-close]):hover { background: var(--surface-hover, #f1f0ec); color: var(--ink); }
+body.v2 :is(.success-notice-close, .toast-stack .toast[data-toast-kind="success"] > [data-toast-close]):focus-visible { outline: 2px solid #d0452d; outline-offset: 2px; }
diff --git a/App/app/templates/_components.html b/App/app/templates/_components.html
index c4288baf..0fa30b4f 100644
--- a/App/app/templates/_components.html
+++ b/App/app/templates/_components.html
@@ -301,6 +301,15 @@
   </span>
 {% endmacro %}
 
+{# 0971: the one compact success notice. role=status announces it; the dismiss button is the same on every page; one optional next action. #}
+{% macro success_notice(text, next_href='', next_label='') %}
+<div class="success-notice" role="status" data-success-notice>
+  <span class="success-notice-text">{{ text }}</span>
+  {% if next_href and next_label %}<a class="success-notice-next" href="{{ next_href }}">{{ next_label }}</a>{% endif %}
+  <button type="button" class="success-notice-close" data-success-dismiss aria-label="{{ t('a11y.dismiss_notification') }}">&times;</button>
+</div>
+{% endmacro %}
+
 {% macro copy_icon() %}
 <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
   <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
diff --git a/App/app/templates/base.html b/App/app/templates/base.html
index 45ca7693..f51a7289 100644
--- a/App/app/templates/base.html
+++ b/App/app/templates/base.html
@@ -19,7 +19,7 @@
   <link rel="preload" href="/static/fonts/Manrope-latin.woff2?v=20261101-0495" as="font" type="font/woff2" crossorigin>
   {% if v2 | default(false) %}
   <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261103-0920">
-  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261105-0961a">
+  <link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261105-0971b">
   {% if show_nav | default(true) %}<link rel="stylesheet" data-turbo-track="reload" href="/static/command.css?v=20261103-0935">{% endif %}
   {% else %}
   <link rel="stylesheet" data-turbo-track="reload" href="/static/tokens.css?v=20261103-0920">
@@ -41,7 +41,7 @@
   {% if show_nav | default(true) %}<script src="/static/vendor/turbo-8.0.13.js?v=8.0.13" defer data-turbo-track="reload"></script><meta name="turbo-cache-control" content="no-cache"><meta name="view-transition" content="same-origin"><meta name="turbo-prefetch" content="true">{% endif %}
   <script src="/static/csrf.js?v=20260915a" defer data-turbo-track="reload"></script>
   <script src="/static/skeleton.js?v=20261102-0509" defer data-turbo-track="reload"></script>
-  <script src="/static/app.js?v=20261104-0955g" defer data-turbo-track="reload"></script>
+  <script src="/static/app.js?v=20261105-0971a" defer data-turbo-track="reload"></script>
   {% if show_nav | default(true) %}<script src="/static/host.js?v=20261102-0507" defer data-turbo-track="reload"></script>{% endif %}
   <noscript><link rel="stylesheet" href="/static/app-nojs.css?v=20261104-1210"></noscript>
   {% if show_nav | default(true) %}<script src="/static/guide.js?v=20261104-0916" defer data-turbo-track="reload"></script>{% endif %}
diff --git a/App/app/templates/cleaning_settings.html b/App/app/templates/cleaning_settings.html
index a63be169..da029e6b 100644
--- a/App/app/templates/cleaning_settings.html
+++ b/App/app/templates/cleaning_settings.html
@@ -1,6 +1,6 @@
 {% extends "host_page.html" %}
 {% set v2 = true %}
-{% from "_components.html" import help_tip with context %}
+{% from "_components.html" import help_tip, success_notice with context %}
 {% set body_kind = 'form' %}
 {% block title %}{{ home.internal_name }} · {{ ct('title') }}{% endblock %}
 {% block page_title %}{% endblock %}
@@ -8,24 +8,25 @@
 {% block back_label %}{% endblock %}
 {% block body %}
 {% with href='/cleaning/properties', title=home.internal_name %}{% include "partials/settings_back_header.html" %}{% endwith %}
-<div class="cleaning-page cleaning-form-page settings-lane">
+<div class="cleaning-page cleaning-form-page settings-lane cl-v2-edit">
 {% if error %}<p class="cleaning-warning" role="alert">{{ ct(error ~ '_error') if error in ('notes','property','code') else ct(error) }}</p>{% endif %}
-{% if request.query_params.get('notice') == 'saved' %}<p role="status">{{ ct('saved') }}</p>{% endif %}
-<form class="cleaning-panel cleaning-form" method="post" action="/cleaning/properties/{{ home.id }}">
+{% if request.query_params.get('notice') == 'saved' %}{{ success_notice(ct('saved')) }}{% endif %}
+<form class="cleaning-panel cleaning-form card" aria-label="{{ ct('instructions') }}" method="post" action="/cleaning/properties/{{ home.id }}">
 <input type="hidden" name="_csrf" value="{{ csrf_token }}">
 <div class="ui-field"><label for="property-instructions">{{ ct('instructions') }}</label>{{ help_tip('property-instructions-hint', ct('notes_hint')) }}<textarea id="property-instructions" name="instructions" rows="8" maxlength="10000" aria-describedby="property-instructions-hint">{{ prop.cleaning_instructions or '' }}</textarea></div>
 <section class="cleaning-subsection" aria-labelledby="cleaning-property-times"><h2 id="cleaning-property-times">{{ ct('property_times') }}</h2>{{ help_tip('property-times-hint', ct('property_times_hint')) }}<p>{{ ct('checkout') }}: <strong>{{ prop.effective_checkout_time or '—' }}</strong> · {{ ct('arrival') }}: <strong>{{ prop.effective_checkin_time or '—' }}</strong></p><a class="ui-btn ui-btn-quiet" href="/apartments/{{ home.id }}?view=settings&amp;section=property#arrival-departure">{{ ct('edit_property_times') }}</a></section>
-<div class="cleaning-actions"><button class="ui-btn ui-btn-primary" type="submit">{{ ct('save') }}</button></div></form>
-<section class="cleaning-panel cleaning-form"><h2>{{ ct('code') }}</h2>{{ help_tip('code-hint', ct('code_hint')) }}
+<div class="cleaning-actions"><button class="ui-btn ui-btn-primary" type="submit">{{ ct('save_instructions') }}</button></div></form>
+<section class="cleaning-panel cleaning-form card"><h2>{{ ct('code') }}</h2>{{ help_tip('code-hint', ct('code_hint')) }}
 {% if codes_disabled %}<p class="cleaning-warning" role="status">{{ ct('login_required') }}</p>{% endif %}
 {% if code.value %}<strong class="cleaning-pin" translate="no">{{ code.value }}{{ '#' if code.source == 'ttlock' else '' }}</strong>{{ help_tip('code-source-hint', ct('permanent_code') if code.source == 'ttlock' else ct('manual_code')) }}{% endif %}
 {% if code.pending %}<p class="cleaning-warning" role="status">{{ ct('code_failed') if code.pending == 'failed' else ct('code_pending') }}</p>{% endif %}
 {% if failed_revoke %}<p class="cleaning-warning" role="alert">{{ ct('revocation_failed') }}</p>{% endif %}
 <form class="cleaning-actions" method="post" action="/cleaning/properties/{{ home.id }}/code/ttlock"><input type="hidden" name="_csrf" value="{{ csrf_token }}"><button class="ui-btn ui-btn-secondary" type="submit">{{ ct('create_code') }}</button></form>
 <div class="cleaning-actions"><a class="ui-btn ui-btn-quiet" href="/apartments/{{ home.id }}?view=settings&amp;section=lock#lock">{{ ct('lock_link') }}</a></div>
+</section>
+<form class="cleaning-panel cleaning-form card" aria-label="{{ ct('manual_code') }}" method="post" action="/cleaning/properties/{{ home.id }}/code/manual"{% if code.source == 'ttlock' and code.value %} data-confirm data-confirm-message="{{ ct('manual_replaces') }}"{% endif %}><input type="hidden" name="_csrf" value="{{ csrf_token }}">
 {% if code.source == 'ttlock' and code.value %}<p>{{ ct('manual_replaces') }}</p>{% endif %}
-<form class="cleaning-form" method="post" action="/cleaning/properties/{{ home.id }}/code/manual"{% if code.source == 'ttlock' and code.value %} data-confirm data-confirm-message="{{ ct('manual_replaces') }}"{% endif %}><input type="hidden" name="_csrf" value="{{ csrf_token }}">
-<div class="ui-field"><label for="manual-code">{{ ct('manual_code') }}</label>{{ help_tip('manual-code-hint', ct('manual_hint')) }}<input id="manual-code" name="code" type="text" maxlength="32" autocomplete="off" spellcheck="false" required aria-describedby="manual-code-hint"></div><div class="cleaning-actions"><button class="ui-btn ui-btn-secondary" type="submit">{{ ct('save') }}</button></div></form>
-{% if code.value or code.pending %}<details class="cleaning-remove"><summary>{{ ct('remove_code') }}</summary><p>{{ ct('remove_code_hint') }}</p><form action="/cleaning/properties/{{ home.id }}/code/remove" method="post" data-confirm data-confirm-message="{{ ct('remove_code_hint') }}"><input type="hidden" name="_csrf" value="{{ csrf_token }}"><button class="ui-btn ui-btn-danger" type="submit">{{ ct('remove_code') }}</button></form></details>{% endif %}
-</section></div>
+<div class="ui-field"><label for="manual-code">{{ ct('manual_code') }}</label>{{ help_tip('manual-code-hint', ct('manual_hint')) }}<input id="manual-code" name="code" type="text" maxlength="32" autocomplete="off" spellcheck="false" required aria-describedby="manual-code-hint"></div><div class="cleaning-actions"><button class="ui-btn ui-btn-primary" type="submit">{{ ct('save_manual_code') }}</button></div></form>
+{% if code.value or code.pending %}<details class="cleaning-panel cleaning-remove"><summary>{{ ct('remove_code') }}</summary><p>{{ ct('remove_code_hint') }}</p><form action="/cleaning/properties/{{ home.id }}/code/remove" method="post" data-confirm data-confirm-message="{{ ct('remove_code_hint') }}"><input type="hidden" name="_csrf" value="{{ csrf_token }}"><button class="ui-btn ui-btn-danger" type="submit">{{ ct('remove_code') }}</button></form></details>{% endif %}
+</div>
 {% endblock %}
diff --git a/App/tests/test_cleaning_browser.py b/App/tests/test_cleaning_browser.py
index 93c9a809..c8312eaf 100644
--- a/App/tests/test_cleaning_browser.py
+++ b/App/tests/test_cleaning_browser.py
@@ -958,3 +958,186 @@ def test_0891_cleaning_airbnb_month(workspace, origin, width):
             page.screenshot(path=str(SHOTS_0891 / f"cleaning-{width}.png"), full_page=False)
         context.close()
         browser.close()
+
+
+# ---- 0971: one success pattern, independent cleaning save forms ----
+
+_NOTICE_FIXTURE = """
+document.addEventListener('readystatechange', () => {
+  if (document.readyState !== 'interactive') return;
+  const main = document.querySelector('main') || document.body;
+  const long = 'Averyveryveryveryverylongunbrokensuccesstext'.repeat(6);
+  main.insertAdjacentHTML('afterbegin',
+    '<div id="fx-section" class="banner ok section-notice" role="status" tabindex="-1" data-section-notice><span class="grow">' + long + '</span></div>' +
+    '<p id="fx-cleaning" class="cleaning-notice" role="status">Saved.</p>');
+  const rail = document.querySelector('[data-feedback-rail]');
+  if (rail) rail.insertAdjacentHTML('beforeend',
+    '<div id="fx-toast" class="toast" data-toast data-toast-kind="success"><span class="grow">Saved.</span>' +
+    '<button type="button" data-toast-close aria-label="Dismiss">\\u00d7</button></div>');
+  const src = document.createElement('input');
+  src.id = 'fx-copy-source'; src.className = 'sr-only'; src.value = 'synthetic-link'; src.readOnly = true;
+  const btn = document.createElement('button');
+  btn.id = 'fx-copy'; btn.type = 'button'; btn.className = 'btn small'; btn.dataset.copy = 'fx-copy-source';
+  btn.dataset.copyLabel = 'Copy link'; btn.dataset.copiedLabel = document.documentElement.lang === 'cs' ? 'Zkopírováno' : 'Copied';
+  btn.textContent = 'Copy link';
+  main.append(src, btn);
+});
+"""
+
+
+def _saved_state(ws):
+    prop = cleaning.properties(ws["owner"], [ws["home"]])[0]
+    return prop["cleaning_instructions"], cleaning._code(prop)["value"]
+
+
+@pytest.mark.parametrize("width", [390, 768, 1280])
+@pytest.mark.parametrize("lang", ["en", "cs"])
+def test_0971_each_cleaning_save_commits_only_its_own_form(workspace, origin, width, lang):
+    ws = workspace
+    url = f"{origin}/cleaning/properties/{ws['home']}?lang={lang}"
+    with sync_api.sync_playwright() as playwright:
+        browser, context = browser_context(playwright, ws, origin, width=width)
+        try:
+            page = context.new_page()
+            page.goto(url)
+            page.wait_for_selector("form[aria-label]")
+            forms = page.locator("form.cleaning-panel[aria-label]")
+            assert forms.count() == 2
+            geometry = page.evaluate("""() => {
+              const [a, b] = Array.from(document.querySelectorAll('form.cleaning-panel[aria-label]'));
+              const ba = a.querySelector('button[type=submit]'), bb = b.querySelector('button[type=submit]');
+              const ra = ba.getBoundingClientRect(), rb = bb.getBoundingClientRect();
+              return { nested: a.contains(b) || b.contains(a), submits: [a.querySelectorAll('button[type=submit]').length, b.querySelectorAll('button[type=submit]').length],
+                sameClass: ba.className === bb.className, sameHeight: Math.abs(ra.height - rb.height) < 1,
+                boxed: [a, b].map((f) => getComputedStyle(f).borderTopWidth !== '0px' || getComputedStyle(f).boxShadow !== 'none'),
+                overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
+                actions: [a.getAttribute('action'), b.getAttribute('action')] };
+            }""")
+            assert not geometry["nested"] and geometry["submits"] == [1, 1], geometry
+            assert geometry["sameClass"] and geometry["sameHeight"], geometry
+            assert geometry["boxed"] == [True, True] and not geometry["overflow"], geometry
+            shot(page, f"0971-settings-{lang}-{width}")
+            before_text, before_code = _saved_state(ws)
+            # Save instructions with an unsaved manual code typed in the other form.
+            page.fill("#property-instructions", "0971 instructions only")
+            page.fill("#manual-code", "UNSAVED-1")
+            page.locator("form[aria-label] button[type=submit]").first.click()
+            page.wait_for_url("**notice=saved**")
+            text, code = _saved_state(ws)
+            assert text == "0971 instructions only" and code == before_code, (text, code, before_code)
+            # Save the manual code with an unsaved instruction edit typed in the other form.
+            page.fill("#property-instructions", "UNSAVED instructions")
+            page.fill("#manual-code", "7710")
+            page.locator("form[aria-label] button[type=submit]").nth(1).click()
+            page.wait_for_url("**notice=saved**")
+            text, code = _saved_state(ws)
+            assert text == "0971 instructions only" and code == "7710", (text, code)
+            assert page.locator("[data-success-notice]").count() == 1
+            assert page.locator("[data-success-notice] [role=button], [data-success-notice] button").count() == 1
+        finally:
+            browser.close()
+
+
+@pytest.mark.parametrize("width", [390, 768, 1280])
+@pytest.mark.parametrize("lang", ["en", "cs"])
+def test_0971_success_notices_share_one_pattern_and_dismiss(workspace, origin, width, lang):
+    ws = workspace
+    with sync_api.sync_playwright() as playwright:
+        browser, context = browser_context(playwright, ws, origin, width=width)
+        try:
+            context.add_init_script(_NOTICE_FIXTURE)
+            page = context.new_page()
+            page.goto(f"{origin}/cleaning/properties/{ws['home']}?lang={lang}&notice=saved")
+            page.wait_for_selector("[data-success-notice]")
+            page.wait_for_selector("#fx-section [data-success-dismiss]", state="attached")
+            page.wait_for_selector("#fx-cleaning [data-success-dismiss]", state="attached")
+            look = page.evaluate("""() => {
+              const pick = (el) => { const s = getComputedStyle(el); const r = el.getBoundingClientRect();
+                const b = el.querySelector('[data-success-dismiss]').getBoundingClientRect();
+                return { border: s.borderLeftWidth + s.borderLeftColor, radius: s.borderTopLeftRadius, bg: s.backgroundColor, size: s.fontSize,
+                  mark: getComputedStyle(el, '::before').content, inside: r.left >= 0 && r.right <= innerWidth + 0.5 && b.right <= r.right + 0.5 && b.left >= r.left,
+                  close: [Math.round(b.width), Math.round(b.height)] }; };
+              return { macro: pick(document.querySelector('[data-success-notice]')), section: pick(document.querySelector('#fx-section')),
+                cleaning: pick(document.querySelector('#fx-cleaning')),
+                toast: (() => { const i = document.querySelector('#fx-toast .feedback-card-icon'); return i ? [i.textContent, Math.round(i.getBoundingClientRect().width)] : null; })(),
+                overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
+                live: document.querySelectorAll('[data-feedback-live]').length };
+            }""")
+            for key in ("section", "cleaning"):
+                for field in ("border", "radius", "bg", "size", "mark"):
+                    assert look[key][field] == look["macro"][field], (key, field, look)
+            for key in ("macro", "section", "cleaning"):
+                assert look[key]["inside"] and look[key]["close"] == [44, 44], (key, look)
+            assert look["toast"] == ["✓", 24], look
+            assert not look["overflow"] and look["live"] == 1, look
+            assert page.locator("[role=status][data-success-notice]").count() == 1
+            shot(page, f"0971-notices-{lang}-{width}")
+            # Pointer dismiss.
+            page.locator("#fx-section [data-success-dismiss]").click()
+            assert page.locator("#fx-section").count() == 0
+            # Keyboard dismiss: Tab to the macro notice's button, press Enter; focus lands on a heading.
+            page.locator("[data-success-notice] [data-success-dismiss]").focus()
+            page.keyboard.press("Enter")
+            assert page.locator("[data-success-notice]").count() == 0
+            assert page.evaluate("document.activeElement && /^H[12]$/.test(document.activeElement.tagName)")
+            page.locator("#fx-cleaning [data-success-dismiss]").focus()
+            page.keyboard.press("Space")
+            assert page.locator("#fx-cleaning").count() == 0
+        finally:
+            browser.close()
+
+
+@pytest.mark.parametrize("width", [390, 768, 1280])
+@pytest.mark.parametrize("lang", ["en", "cs"])
+def test_0971_copy_link_keeps_size_and_label_and_does_not_stack(workspace, origin, width, lang):
+    ws = workspace
+    with sync_api.sync_playwright() as playwright:
+        browser, context = browser_context(playwright, ws, origin, width=width)
+        try:
+            context.add_init_script("""Object.defineProperty(navigator, 'clipboard', { configurable: true,
+              value: { writeText: () => Promise.resolve() } });""" + _NOTICE_FIXTURE)
+            page = context.new_page()
+            page.goto(f"{origin}/cleaning/properties/{ws['home']}?lang={lang}")
+            page.wait_for_selector("#fx-copy")
+            button = page.locator("#fx-copy")
+            before = button.bounding_box()
+            copied = "Zkopírováno" if lang == "cs" else "Copied"
+            for _ in range(3):
+                button.click()
+                page.wait_for_function("(c) => document.querySelector('#fx-copy').getAttribute('aria-label') === c", arg=copied)
+            after = button.bounding_box()
+            assert after["width"] == pytest.approx(before["width"], abs=0.5)
+            assert after["height"] == pytest.approx(before["height"], abs=0.5)
+            state = page.evaluate("""() => ({ icons: document.querySelectorAll('[data-copy-state-icon]').length,
+              toasts: document.querySelectorAll('[data-feedback-rail] [data-toast]:not(#fx-toast)').length,
+              live: document.querySelector('[data-feedback-live]').textContent,
+              visible: Array.from(document.querySelectorAll('#fx-copy .copy-label-default, #fx-copy .copy-label-confirmed')).map(
+                (n) => getComputedStyle(n).visibility + ':' + n.textContent.trim()) })""")
+            assert state["icons"] == 0 and state["toasts"] == 0, state
+            page.wait_for_timeout(100)
+            assert page.evaluate("document.querySelector('[data-feedback-live]').textContent") == copied
+            assert any(item == f"visible:{copied}" for item in state["visible"]), state
+            shot(page, f"0971-copy-{lang}-{width}")
+            page.wait_for_function("() => !document.querySelector('#fx-copy').classList.contains('is-copy-confirmed')", timeout=4000)
+            assert "Copy link" in button.inner_text()
+        finally:
+            browser.close()
+
+
+@pytest.mark.parametrize("width", [390, 1280])
+def test_0971_cleaning_list_notice_is_one_dismissible_success_notice(workspace, origin, width):
+    ws = workspace
+    with sync_api.sync_playwright() as playwright:
+        browser, context = browser_context(playwright, ws, origin, width=width)
+        try:
+            page = context.new_page()
+            page.goto(f"{origin}/cleaning?lang=en&notice=saved")
+            page.wait_for_selector("p.cleaning-notice [data-success-dismiss]")
+            assert page.locator("p.cleaning-notice").count() == 1
+            assert page.locator("p.cleaning-notice [data-success-dismiss]").count() == 1
+            assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
+            shot(page, f"0971-list-notice-{width}")
+            page.locator("p.cleaning-notice [data-success-dismiss]").click()
+            assert page.locator("p.cleaning-notice").count() == 0
+        finally:
+            browser.close()
diff --git a/App/tests/test_host_feedback_browser.py b/App/tests/test_host_feedback_browser.py
index 7e88b47c..5b6d24f5 100644
--- a/App/tests/test_host_feedback_browser.py
+++ b/App/tests/test_host_feedback_browser.py
@@ -329,3 +329,42 @@ def test_host_copy_feedback_truth_and_geometry(base):
         assert no_js_page.locator("[data-feedback-rail]").get_attribute("aria-live") == "off"
         no_js.close()
         browser.close()
+
+
+def test_0971_repeated_copy_has_no_badge_and_no_stacked_feedback(base):
+    username = f"feedback{secrets.token_hex(4)}"
+    auth.create_account(f"{username}@example.test", "Feedback QA", role="host", username=username)
+    session = _session_cookie(username)
+    fixture = """
+      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.resolve() } });
+      document.addEventListener('DOMContentLoaded', () => {
+        const main = document.querySelector('main') || document.body;
+        const src = document.createElement('input'); src.id = 'c971-src'; src.className = 'sr-only'; src.value = 'x'; src.readOnly = true;
+        const b = document.createElement('button'); b.id = 'c971'; b.type = 'button'; b.dataset.copy = 'c971-src';
+        b.dataset.copiedLabel = 'Copied'; b.textContent = 'Copy link'; main.append(src, b);
+      });
+    """
+    with sync_api.sync_playwright() as playwright:
+        try:
+            browser = playwright.chromium.launch(**chromium_launch_kwargs())
+        except Exception as exc:
+            if REQUIRE_BROWSER:
+                raise
+            pytest.skip(f"Chromium is not available: {exc}")
+        context = browser.new_context(viewport={"width": 390, "height": 844})
+        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
+        context.add_init_script(fixture)
+        page = context.new_page()
+        page.goto(f"{base}/settings?lang=en")
+        page.wait_for_selector("#c971")
+        button = page.locator("#c971")
+        before = button.bounding_box()
+        for _ in range(3):
+            button.click()
+        after = button.bounding_box()
+        assert after["width"] == pytest.approx(before["width"], abs=0.5)
+        assert page.locator("[data-copy-state-icon]").count() == 0
+        assert page.locator("[data-feedback-rail] [data-toast]").count() == 0
+        page.wait_for_timeout(100)
+        assert page.locator("[data-feedback-live]").inner_text() == "Copied"
+        browser.close()
```

## 5. Do not touch

`host.css`, `app.css`, `cleaning.css`, `_section_notice.html`, `_cleaning_screen.html`, any route, any migration, `main`, secrets, servers, deploy. Rule 8: no push, no merge. Never click or post to `/cleaning/properties/{id}/code/ttlock`.

## 6. Commands

From `App/`, `export UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b13`. Run each; every one ends in `2>&1 | tail -30`. Browser runs: 0 skipped (`-rs`).

a. New tests, expect `20 passed` for the cleaning -k run and all green for the feedback file (it holds one new test):
`.venv/bin/python -m pytest tests/test_cleaning_browser.py -k 0971 -q --tb=short -x -rs 2>&1 | tail -30`
`.venv/bin/python -m pytest tests/test_host_feedback_browser.py -q --tb=short -x -rs 2>&1 | tail -30`

b. Cleaning row plus copy and notices, expect about 150 passed (about 3 minutes). One known flake: `test_fractional_checkout_and_same_day_cleaning_geometry[1280-cs]` can fail once with "Gantt slot or cleaning marker has no box"; rerun that single test once; it passed on retry and on the base commit.
`.venv/bin/python -m pytest tests/test_cleaning*.py tests/test_0300_copy_button.py tests/test_host_flash_outcomes.py tests/test_property_notices_0957.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_cleaning.py -q --tb=short -rs 2>&1 | tail -30`

c. Host and design-guardrail rows, takes about 10 minutes, so run in the background and poll (the tool limit is 10 minutes): 
`nohup .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_host_geometry.py $(ls tests/test_host_*browser.py) -q --tb=short -rs -p no:cacheprovider > /tmp/ubyhost-b13/host-row.log 2>&1 &` then `tail -5 /tmp/ubyhost-b13/host-row.log` until it ends. Expect `88 passed`.

d. Static rows: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short 2>&1 | tail -30`

e. Known failures on the base commit, not yours (do not fix, do not report as regressions): `test_host_fee_navigation.py::test_frozen_report_order_and_forms` and four tests in `test_host_ux_acceptance.py`. Run them only if you want to confirm; the rest of `test_host_*.py` passed (304).

## 7. Acceptance

Chromium UX checks. Decide pass or fail for each and write one line each in the report; a fail needs the fix or a STOP:

- [ ] Property save: injected `.section-notice.ok` has the same border, radius, background, font size and check mark as the macro notice, wraps a 270-character unbroken string without horizontal scroll, close button 44 x 44 inside the notice at 390, 768, 1280, en and cs.
- [ ] Stay save: injected success toast shows one 24 px check icon and the same 44 px close; no second check.
- [ ] Cleaning creation and save: `/cleaning?notice=saved` shows one `p.cleaning-notice` with one dismiss button; click removes it.
- [ ] Copy link: three clicks keep width and height (0.5 px), `[data-copy-state-icon]` count 0, no new toast, `[data-feedback-live]` reads exactly the localized "Copied" once, label is back to "Copy link" after about 2 s; en and cs, 390, 768, 1280.
- [ ] Dismiss by pointer and by keyboard (Enter, Space) works; focus lands on a heading after dismissal.
- [ ] Repeated success does not stack: one `[role=status][data-success-notice]` on the settings page, one live region.
- [ ] Cleaning property page: two forms, two cards, equal Save buttons (same class, same height), Save instructions changes only the instructions (an unsaved manual code typed beside it is not saved), Save manual code changes only the code (an unsaved instruction edit is not saved); reads from the database, not from the page.
- [ ] 0 skipped in every browser run; commands a to d green except the known failures in 6e.
- [ ] Screenshots exist under `/tmp/ubyhost-b13` (names below). Open these three and write what you saw in the report, one line each: `cleaning-0971-settings-en-390.png` (two separate cards, two red Save buttons labelled "Save instructions" and "Save manual code", no overlap with the bottom tab bar content), `cleaning-0971-notices-en-390.png` (four notices with the same check circle, border and X; the long text wraps inside its box), `cleaning-0971-list-notice-390.png` (one compact "Saved." row above the calendar). Others written by the tests: `cleaning-0971-settings-{en,cs}-{390,768,1280}.png`, `cleaning-0971-notices-{en,cs}-{390,768,1280}.png`, `cleaning-0971-copy-{en,cs}-{390,768,1280}.png`, `cleaning-0971-list-notice-{390,1280}.png`.
- [ ] Rule 10 note for the PR: touched host pages are the cleaning property page and the cleaning list; the reviewer, not the owner, ticks the design-system checklist.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; `git apply --check` fails; a test fails twice (the known flake and 6e excepted); 25 tool calls or about 50k tokens (report as `blocked`, "Done: steps 1 to k. Left: steps k+1 to n."); a new dependency, a file outside section 3, or a section 5 path seems needed; a step is unclear; anything needs push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0971-report.md` (600 tokens at most): `git diff --stat`; each command with its last 5 lines; section 7 ticked with the pass/fail lines and the three screenshot descriptions; deviations; questions; owner steps left. Set `Status: review` and open one PR only if the owner asked; otherwise leave the branch local.

## Risk list (for the reviewer)

- `App/app/static/app2.css` appended block: the `:is(...)` selector reaches specificity (0,4,1), so it overrides `body.v2 .section-notice` and `.cleaning-notice` on purpose; check no other `.section-notice.ok` page regresses.
- `App/app/static/app.js` `initSuccessNotices` adds a button to every `.section-notice.ok` and `p.cleaning-notice` on host pages; removing the notice moves focus to the section `h2` or the page `h1`.
- `App/app/templates/cleaning_settings.html`: the manual-code form is now outside the former wrapping `<section>`; the `data-confirm` for replacing a TTLock code is kept on the manual form.
- Scope gap: `_section_notice.html`, `_cleaning_screen.html` and `base.html` markup are unchanged by design (outside the allowed list); they get the shared pattern by CSS and JS. If the owner wants the macro used there, that is a follow-up brief. Legacy non-v2 pages (`host.css`) keep their old toast look.
- Evidence limit: real property-save and stay-save flows are covered by injected markup, not by a real save.

## Owner steps

1. Open the PR when the report says `review` and merge only with `scripts/merge-pr-on-green.sh`.
2. Deploy is yours: after deploy, open Cleaning, Properties, one property, and press Save instructions, then Save manual code, and confirm each shows one "Saved." row with an X.
