# 1061: Icons for status marks and close buttons (replace ✓ ✗ ×)

Status: todo

Owner: Josef, 2026-11-09. Executor: Haiku 5.5. Branch `claude/icons-1061`. Independent of 1060, 1062 and 1063 (different files). Do not touch `_icons.html`; `check`, `x`, `triangle-alert`, `info` already exist in it.

## 1. Objective
Text glyphs `✓ ✗ ×` (and the toast's `!` / `i` letters) used as icons become Lucide SVG: `icon('check', N)` / `icon('x', N)` in templates, a small inline-SVG helper in `app.js`. Size 16 inside buttons, 12 to 14 in small marks, 20 in the big setup-wizard badge. Keep `aria-hidden` and every existing `aria-label`.

## 2. Context
`icon(name, size, cls)` renders `<svg class="ui-icon" aria-hidden="true" stroke="currentColor">`, so colours set by existing CSS (`.readiness-mark`, `.fee-stepper-dot`, ...) keep working. Add `{% from "_icons.html" import icon with context %}` as the first line of any partial that lacks it (`grep -c "_icons.html" <file>` shows 0). Files that extend a layout: put the import after the `{% extends %}` line.

## 3. Files (exactly these; paths under `App/app/templates/` unless noted)
`_property_editor.html`, `setup_wizard/done.html`, `leon_setup/done.html`, `setup_wizard/try_it.html`, `setup_wizard/_layout.html`, `_components.html`, `_workflow.html`, `stay_fees.html`, `_smart_locks_panel.html`, `auth_base.html`, `_dashboard_calendar.html`; `static/app.js`; sizing-only CSS if a screenshot needs it in `static/app.css`, `static/app2.css`, `static/host.css`; tests `App/tests/test_icons_marks_1061.py`, `test_cleaning_browser.py`, `test_host_feedback_browser.py` (only the assertions on the toast glyph); cache keys in `templates/base.html` lines for `app.js`, `app2.css`, `app.css`, `host.css` (bump only files you edited) and `tests/static_versions.json`.
NOT in this brief (owned elsewhere): `landing.html`, `guest/stay.html`, `public_guide.html`, `pricing.html`, `product.html` (1063); `base.html` close buttons, `property_page_review.html` (1062, except the cache-key lines above, which are separate hunks). `dashboard.html` line 26 and `_host_alerts.html` line 40 keep their `×`: app2.css (`font-size:0; color:transparent` plus a drawn `:before` X) already hides the glyph, so it is not a visible text icon. Say so in the report.

## 4. Steps
Each step: `grep -nF` the anchor; not found = STOP. Commit `1061 step k`.
1. `_property_editor.html` lines 97 and 113: replace `{{ '✓' if item.done else '✗' }}` with `{{ icon('check' if item.done else 'x', 14) }}` (both lines). Add the import. If `.readiness-mark` needs `display:inline-flex;align-items:center` for centring, add it to the rule in `static/app.css` line ~529.
2. `setup_wizard/done.html`: line 10 `{{ '!' if missing_row else '✓' }}` becomes `{{ icon('triangle-alert' if missing_row else 'check', 20) }}`; line 31 `<span aria-hidden="true">✓</span>` becomes `<span aria-hidden="true">{{ icon('check', 14) }}</span>`. `leon_setup/done.html` line 5 `✓` becomes `{{ icon('check', 20) }}` (add the import). `setup_wizard/try_it.html` line 16 `{% if real %}✓{% else %}` becomes `{% if real %}{{ icon('check', 14) }}{% else %}`. `setup_wizard/_layout.html` line 22 `✓</span>` becomes `{{ icon('check', 14) }}</span>` (add the import).
3. `_components.html` (already imports `icon`): line 431 `{% if step.done %}✓{% else %}` becomes `{% if step.done %}{{ icon('check', 16) }}{% else %}`; line 309 `data-success-dismiss aria-label="{{ t('a11y.dismiss_notification') }}">&times;</button>` becomes `...">{{ icon('x', 16) }}</button>`. `_workflow.html` line 32 `{% if step.state == 'done' %}✓{% else %}` becomes `{% if step.state == 'done' %}{{ icon('check', 14) }}{% else %}` (add the import).
4. `stay_fees.html` (imports `icon`) line 62 `{% if n < period.step %}✓{% else %}` becomes `{% if n < period.step %}{{ icon('check', 14) }}{% else %}`. `_smart_locks_panel.html` line 38 `<p class="ui-sub">✓ {{ t(` becomes `<p class="ui-sub">{{ icon('check', 14) }} {{ t(` (add the import).
5. `auth_base.html` lines 80, 84, 88: `<em>✓</em>` becomes `<em>{{ icon('check', 14) }}</em>`; `<em>UbyPort ✓</em>` becomes `<em>UbyPort {{ icon('check', 14) }}</em>`; `{{ t('landing.demo.queue.ready') }} ✓</span>` becomes `{{ t('landing.demo.queue.ready') }} {{ icon('check', 14) }}</span>`. Add the import at the top. If the marks sit low, add `vertical-align: -2px` to `.ui-icon` inside `.auth-float em` only in the CSS file that styles `.auth-float` (`grep -n "auth-float" static/*.css`); that is allowed.
6. `_dashboard_calendar.html` lines 43, 68, 74, 80: in each `... class="btn soft cal-close" data-cal-close aria-label="{{ t('calendar.close') }}">×</button>` replace `×` with `{{ icon('x', 16) }}` (four places; add the import). `static/dashboard-calendar.css` is not in scope: if the X looks wrong at 390 px, STOP and report.
7. `static/app.js`. Find the first lines of the file with `grep -nm3 "use strict" static/app.js` and insert right after the first `"use strict";` (inside the outer function) this helper:
   ```js
   var ICON_MARKUP = {
     check: '<path d="M20 6 9 17l-5-5"/>',
     x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
     "triangle-alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
     info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'
   };
   function iconSvg(name, size) {
     var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
     svg.setAttribute("class", "ui-icon");
     svg.setAttribute("width", String(size));
     svg.setAttribute("height", String(size));
     svg.setAttribute("viewBox", "0 0 24 24");
     svg.setAttribute("fill", "none");
     svg.setAttribute("stroke", "currentColor");
     svg.setAttribute("stroke-width", "2");
     svg.setAttribute("stroke-linecap", "round");
     svg.setAttribute("stroke-linejoin", "round");
     svg.setAttribute("aria-hidden", "true");
     svg.innerHTML = ICON_MARKUP[name];
     return svg;
   }
   function feedbackIconName(kind) {
     return kind === "success" ? "check" : kind === "error" || kind === "warning" || kind === "partial" ? "triangle-alert" : "info";
   }
   ```
   (The strings are constants, no user data goes into `innerHTML`.) Then replace line ~220 and line ~1033, the line `icon.textContent = kind === "success" ? "✓" : kind === "error" || kind === "warning" || kind === "partial" ? "!" : "i";` (two places, different indentation) with `icon.appendChild(iconSvg(feedbackIconName(kind), 16));`, and line ~235 `close.textContent = "×";` with `close.appendChild(iconSvg("x", 16));`. If `iconSvg` is not in scope at line 1033 (`node --check static/app.js` is fine but a browser test fails), move the helper to the outermost scope. Check: `node --check static/app.js 2>&1 | tail -30` and `grep -nF '"×"' static/app.js` prints nothing.
8. Tests: new `App/tests/test_icons_marks_1061.py`:
   ```python
   from pathlib import Path

   APP = Path(__file__).resolve().parents[1] / "app"
   TEMPLATES = [
       "_property_editor.html", "setup_wizard/done.html", "leon_setup/done.html", "setup_wizard/try_it.html",
       "setup_wizard/_layout.html", "_components.html", "_workflow.html", "stay_fees.html",
       "_smart_locks_panel.html", "auth_base.html", "_dashboard_calendar.html",
   ]


   def test_no_check_cross_times_glyphs_in_templates():
       for name in TEMPLATES:
           text = (APP / "templates" / name).read_text(encoding="utf-8")
           assert not [g for g in "✓✗×" if g in text] and "&times;" not in text, name


   def test_app_js_builds_svg_icons_not_glyph_text():
       js = (APP / "static" / "app.js").read_text(encoding="utf-8")
       assert 'textContent = "×"' not in js and '"✓"' not in js
   ```
   `_components.html` may legitimately keep `×` inside prose; if the first test fails only for a non-icon `×`, STOP and report which line. Existing tests that assert the old glyph text (`grep -n '✓' tests/test_cleaning_browser.py tests/test_host_feedback_browser.py`, expected `test_cleaning_browser.py` line ~1096 `look["toast"] == ["✓", 24]`): change them to assert the toast icon contains an `svg` child and keep the size 24 check. Change nothing else in them.
9. Cache keys: bump `?v=` to `20261109-1061a` for each static file you edited (`grep -n "app.js\|app2.css\|app.css\|host.css" templates/base.html`), then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`.
10. Screenshots and report (section 7).

## 5. Do not touch
`_icons.html`, files owned by 1060, 1062, 1063, filing logic, i18n keys, `dashboard.html`/`_host_alerts.html` (see section 3), typographic glyphs (— – · • ••• ⌘), dependencies, outbound requests, personal data.

## 6. Commands (from `App/`, each ending `-q --tb=short -x 2>&1 | tail -30`)
- Host pages row: `tests/test_host_*.py tests/test_host_geometry.py` (0 skipped; includes `test_host_feedback_browser.py`).
- Onboarding, properties row: `tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py`.
- Invoices, stay fee row: `tests/test_invoice_*.py tests/test_stay_fee*.py`.
- Calendar row: `tests/test_dashboard_calendar*.py tests/test_calendar_*.py`; Cleaning row: `tests/test_cleaning*.py` (browser 0 skipped).
- Door codes row: `tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py`.
- Login row: `tests/test_login_*.py tests/test_auth_*.py`; Public pages row: `tests/test_public_*.py tests/test_landing_*.py`.
- Static row: `tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`; new `tests/test_icons_marks_1061.py`; `tests/test_design_icons.py`.
- `tests/test_design_guardrails_browser.py` (0 skipped).
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30`.

## 7. Acceptance
All commands green, 0 skipped. Screenshots 390/768/1280, EN and CS, of: property editor readiness list, setup wizard done and try-it, onboarding steps (overview), stay fees stepper, smart locks panel, login page demo, dashboard calendar dialog with close X, and a triggered success toast plus an error toast (close X). Read each; PR body per page "390: ...; 768: ...; 1280: ..." (mark centred in its circle, same colour as before, X not clipped). Tick the design-system checklist. Never silence a finding.

## 8. Stop and ask
Anchor missing; a mark off-centre that needs a file outside section 3; a test fails twice; `iconSvg` scope problem you cannot fix by moving the helper.

## 9. Report
`docs/tasks/1061-report.md`, 600 tokens at most.
