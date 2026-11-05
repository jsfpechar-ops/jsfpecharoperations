# 0961: Host shell on the manual guest form and the detailed invoice form (B03, X01)

Status: todo
Depends on: B02 | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0961-b03-host-shell
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Stay detail > Add guest and Generate invoice > detailed form must show the same sidebar, font and content lane as the neighbouring host pages. Root cause is verified below; the fix is NOT a one-line flag, so this brief is a gate plus a split. Do not write a CSS override.

## 2. Context (verified by reading, base 7b0355c4)

- `App/app/templates/base.html` line 20 `{% if v2 | default(false) %}` loads tokens.css + app2.css + command.css, adds `v2` to `<body>` (line 53) and includes `_shell_v2.html` (line 59). Without the flag it loads app.css, components.css, host.css, host2.css etc. and includes `_shell_sidebar.html`. The flag alone decides sidebar/rail and typography.
- Neighbours set the flag: `reservation_detail.html` line 3, `reservations.html` line 2, `invoices.html`, `invoice_stay_picker.html`, `apartment_form.html` line 4: `{% set v2 = true %}`.
- The two forms do not set it:
  - `guest_form_admin.html` lines 1-3: `{% extends "host_page.html" %}` / `{% set nav = 'reservations' %}` / `{% set body_kind = 'form' %}`
  - `invoice_form.html` lines 1-3: `{% extends "host_page.html" %}` / `{% set nav = 'invoices' %}` / `{% set body_kind = 'form' %}`
  - `host_page.html` needs no change (it only sets `body_kind` and `wrap_class`).
- Existing tests (`test_design_guest_admin.py`, `test_design_invoices.py`) say "v2 form shell" but only match markup, so they pass on the old shell. No test asserts `body.v2` on these two pages.
- Adding the flag would drop styles, because v2 pages load only app2.css and these classes exist only in v1 sheets (checked with grep against app2.css):
  - guest_form_admin: `signature-pad`, `signature-pad-bar`, `passport-preview`, `passport-preview-pdf-link`, `verify-panel` (app.css, host.css), `signature-saved`, `signature-saved-note` (host.css), `muted`.
  - invoice_form: `invoice-form` (host.css, host2.css), `invoice-more`, `invoice-more-body`, `invoice-actions`, `invoice-paid-choice`, `invoice-supplier-name`, `input-qty`, `input-unit`, `input-vat`, `banner-list`, `warn-text`, `opt` (app.css), `invoice-stay-context` (host.css), `invoice-lookup-guest`, `invoice-lookup-ico`, `invoice-other-description-field`, `invoice-supplier-edit`, `invoice-supplier-picker`, `ui-toolbar` (host2.css).
- app2.css, a static file, is outside this brief's file list, and the port is roughly 40 rule lines.

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/tasks/0961-report.md | create | the report |

No other file may change in this brief.

## 4. Steps

1. Gate. From the repo root run:
   `grep -nF "set v2 = true" App/app/templates/guest_form_admin.html App/app/templates/invoice_form.html 2>&1 | tail -30`
   Expected: no output. Output present: STOP (already changed, report).
2. From `App/` run:
   `for c in signature-pad passport-preview verify-panel invoice-more input-qty invoice-form; do echo "$c: $(grep -c -- "\.$c\b" app/static/app2.css)"; done 2>&1 | tail -30`
   Expected: every count is 0. Any count above 0 for all six: STOP and ask (the premise changed).
3. Both gates match, so STOP per §8. Write `docs/tasks/0961-report.md` with: root cause (missing `{% set v2 = true %}`), the missing-class lists from §2, and the split below. Set `Status: blocked`. Commit nothing else.

### Split to propose (the orchestrator writes these briefs; the executor does not)

- 0961a, guest form: add the flag after line 1 of guest_form_admin.html, port the guest-form classes above into `App/app/static/app2.css` scoped under `.ui-page` (copy the existing rules, tokens only, light mode), bump the app2.css version in `base.html` and `App/tests/static_versions.json`.
- 0961b, invoice form: same for invoice_form.html and its classes.
- Both: append one browser test, files per `test-map`: host pages row, v2 row (`test_0710_v2_mockup_match_browser.py`), `test_design_guest_admin.py` / `test_design_invoices.py` / `test_invoice_*.py`, `test_design_guardrails_browser.py`.

Flag patch (reserved for 0961a/0961b, DO NOT APPLY in this brief; it applies cleanly to the base commit):

```diff
--- a/App/app/templates/guest_form_admin.html
+++ b/App/app/templates/guest_form_admin.html
@@ -1,4 +1,5 @@
 {% extends "host_page.html" %}
+{% set v2 = true %}
 {% set nav = 'reservations' %}
 {% set body_kind = 'form' %}
 {% set editing = editing | default(guest is not none) %}
--- a/App/app/templates/invoice_form.html
+++ b/App/app/templates/invoice_form.html
@@ -1,4 +1,5 @@
 {% extends "host_page.html" %}
+{% set v2 = true %}
 {% set nav = 'invoices' %}
 {% set body_kind = 'form' %}
 {% from "_components.html" import field_label, help_tip, choice_card with context %}
```

Test to append (reserved, same rule), end of `App/tests/test_host_stay_detail_layout_browser.py`, reusing its fixtures:

```python
def test_add_guest_and_invoice_forms_keep_the_v2_host_shell(stay_actions_host, stay_actions_base):
    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    stay = stay_actions_host["ids"]["ready"]
    urls = {"stay": f"/reservations/{stay}", "guest": f"/reservations/{stay}/guests/new",
            "invoice": f"/invoices/new?reservation_id={stay}"}
    probe = """(() => ({v2: document.body.classList.contains('v2'),
        sidebar: !!document.querySelector('.ui-sidebar'),
        font: getComputedStyle(document.body).fontFamily,
        left: Math.round(document.querySelector('#main-content').getBoundingClientRect().left),
        path: location.pathname}))()"""
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
        page = context.new_page()
        for locale in ("en", "cs"):
            for width in (390, 768, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                seen = {}
                for key, url in urls.items():
                    page.goto(f"{stay_actions_base}{url}{'&' if '?' in url else '?'}lang={locale}")
                    page.wait_for_load_state("networkidle")
                    seen[key] = page.evaluate(probe)
                    assert seen[key]["path"] == url.split("?")[0], (key, width, seen[key])  # no redirect
                    assert seen[key]["v2"] and seen[key]["sidebar"], (key, width, locale)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (key, width)
                for key in ("guest", "invoice"):
                    assert seen[key]["font"] == seen["stay"]["font"], (key, width)
                    assert seen[key]["left"] == seen["stay"]["left"], (key, width)
        browser.close()
```

## 5. Do not touch

Any template, CSS, JS, test or static_versions file. Filed-guest identity reveal/edit locks, invoice issuance, `host_page.html`, `base.html`. AGENTS.md hard rules 7 and 10 apply to 0961a/b, not here.

## 6. Commands

From `App/`, after `ln -s /tmp/ubyhost-0958-worktree/App/.venv /tmp/ubyhost-b03-worktree/App/.venv` (skip if present). Steps 1 and 2 are the only commands in this brief. For 0961a/b (reference, not to run here), `export UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b03`, then `.venv/bin/python -m pytest <files> -rs -q --tb=short -x 2>&1 | tail -30` with:
`tests/test_host_stay_detail_layout_browser.py tests/test_host_geometry.py tests/test_shell_lane_browser.py tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_design_guest_admin.py tests/test_host_guest_form.py tests/test_design_invoices.py tests/test_0293_invoice_form.py tests/test_host_invoice_navigation.py tests/test_invoice_ux.py tests/test_invoice_stay_browser.py` (0 skipped).
Chromium checks for 0961a/b, each in EN and CS at 390, 768 and 1280, screenshots only under /tmp/ubyhost-b03, one described line each: stay detail > Add guest, and Generate invoice > detailed form must show the same sidebar or rail, font family and content lane as the neighbouring page; direct load and back/forward identical; required fields and typed values still work; signature pad, passport preview and invoice item rows keep their layout.

## 7. Acceptance (this brief)

- [ ] Both gate commands run and match the expected output.
- [ ] No file other than docs/tasks/0961-report.md changed.
- [ ] Report lists root cause, both class lists, the split, `Status: blocked`.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a new dependency seems needed; you need push, merge, secrets or deploy; a step is unclear. Step 3 is an expected stop.

## 9. Report

`docs/tasks/0961-report.md`, 600 tokens at most: gate outputs (last 5 lines each), root cause, split, Deviations, owner steps (none).
