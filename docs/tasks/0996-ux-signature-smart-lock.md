# 0996: Signature dialog and Smart lock section on v2 property page

Status: todo
Depends on: 0993, 0994, 0995 (all edit `app2.css` and `base.html`; run them first) | Base commit: 423d603 | Branch: task/0996-ux-signature-lock
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix two broken-looking areas of the v2 property page: the signature dialog (fills the whole screen, unstyled Draw/Type buttons, "Archive property" bleeds through at the bottom) and the Smart lock section (two "Connect my lock" buttons, a big empty area under "Digital door lock", the terms checkbox far from its button). Quick UX fixes.

## 2. Context

Rules: light mode only; copy rule 9 (a heading the button repeats is dropped, not reworded); host-page UX gate (AGENTS rule 10). Auth-form no-JS rule does not apply here.

Root causes (verified by the orchestrator):

- `base.html` loads only `tokens.css`, `app2.css`, `command.css` when `v2` is true. `host2.css` (the `.host-workspace .ui-dialog`, `.ui-sheet`, `.signature-dialog-pad` rules, lines 86 to 89 and 737 to 744) and `app.css` (`.checkline`, line 1068) are never loaded on v2 pages, so the `<dialog>` is a bare browser dialog and the tabs are default buttons.
- `app2.css` line 969 to 970 (media `min-width:1024px`): `.property-section` is a 2-column grid and only `h3,p,.hint,.grid,.field-label-row,.actions,.preview-hint` span both columns, so the `<h2>` "Digital door lock" sits in the left column and the next `.ui-section` ("How it works") in the right one, leaving the empty area.

Anchors (each verbatim, else STOP):

`App/app/static/app2.css`:
```
  body.v2 .property-section > :is(h3,p,.hint,.grid,.field-label-row,.actions,.preview-hint){grid-column:1/-1}
```
```
body.v2 .signature-dialog-pad{width:100%}
```
```
@media (max-width:599px){body.v2 .ui-dialog.signature-dialog{width:calc(100vw - 16px);max-width:none;padding:0}body.v2 .ui-dialog.signature-dialog .ui-sheet{padding:12px}}
```
`App/app/templates/_property_editor.html` (Smart lock section, no lock connected, about lines 445 to 456):
```
      {% if lock_panel and lock_panel.smart_locks_enabled %}<a class="ui-btn ui-btn-primary" href="#door-code">{{ t('smart_locks.setup') }}</a>{% endif %}
```
```
    <h2 class="property-section-title">{{ t('smart_locks.title') }}</h2>
    <p class="ui-sub">{{ t('smart_locks.lede') }}</p>
```
`App/app/templates/_smart_locks_panel.html` lines 13 to 21:
```
<section class="ui-section" id="smart-locks-setup">
  <h2>{{ t('smart_locks.setup_title') }}</h2>
  <form method="post" action="/smart-locks/setup">
    <input type="hidden" name="return_to" value="{{ return_to }}">
    <label class="checkline" for="terms"><input type="checkbox" id="terms" name="terms" value="1" required>
      <span>{{ t('smart_locks.terms') }} <a href="/guide#door-codes-terms">{{ t('smart_locks.terms_link') }}</a></span></label>
    <div class="action-group"><button class="{{ cta }}" type="submit">{{ t('smart_locks.setup') }}</button></div>
  </form>
```
`App/app/templates/base.html` line 22 (`/static/app2.css?v=...`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app2.css | edit | dialog, tabs, pad, checkline, full-width section children |
| App/app/templates/_property_editor.html | edit | drop the top duplicate button, hide the duplicate heading visually |
| App/app/templates/_smart_locks_panel.html | edit | hide the duplicate setup heading visually, checkbox and button on one row |
| App/app/templates/base.html | edit | bump `app2.css` key |

No other file may change.

## 4. Steps

1. `app2.css`: in the `@media (min-width:1024px)` block, replace the anchor line with `  body.v2 .property-section > :is(h2,h3,p,.hint,.grid,.field-label-row,.actions,.preview-hint,.ui-section,.lock-state){grid-column:1/-1}`.
2. `app2.css` append (mirrors host2.css, scoped to v2):
```
/* 0996: signature dialog and terms line on v2 pages (host2.css and app.css are not loaded there) */
body.v2 .ui-dialog.signature-dialog{border:0;padding:0;background:transparent;max-width:none;width:min(720px,calc(100vw - 32px));margin:auto}
body.v2 .ui-dialog.signature-dialog::backdrop{background:var(--scrim,rgba(32,32,30,.4))}
body.v2 .ui-dialog.signature-dialog .ui-sheet{background:var(--surface);border-radius:16px;padding:20px;box-shadow:0 12px 40px rgba(0,0,0,.18);max-height:calc(100dvh - 32px);overflow:auto}
body.v2 .signature-dialog .ui-sheet-handle{display:none}
body.v2 .signature-dialog h2{margin:0 0 12px;font-size:18px;font-weight:700}
body.v2 .signature-modes{display:flex;gap:8px;margin:0 0 12px}
body.v2 .signature-modes .ui-tab{min-height:44px;padding:0 16px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--ink);font:inherit;font-weight:600;cursor:pointer}
body.v2 .signature-modes .ui-tab[aria-selected="true"]{background:var(--ink);color:#fff;border-color:var(--ink)}
body.v2 .signature-dialog .signature-dialog-pad{display:block;width:100%;height:clamp(160px,32vh,260px);margin:12px 0;border:1px solid var(--line);border-radius:10px;background:#fff;touch-action:none}
body.v2 .signature-dialog .signature-typed-preview{touch-action:auto}
body.v2 .signature-dialog .action-group{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0}
body.v2 .signature-dialog-actions{justify-content:flex-end}
@media (max-width:599px){body.v2 .signature-dialog-actions{flex-direction:column;align-items:stretch}}
body.v2 .checkline{display:flex;gap:10px;align-items:flex-start;font-size:14px;margin:0 0 12px}
body.v2 .checkline input{width:auto;margin-top:3px;accent-color:var(--acc)}
body.v2 #smart-locks-setup form{display:grid;gap:4px;justify-items:start}
```
3. `_property_editor.html`: delete the whole line `{% if lock_panel and lock_panel.smart_locks_enabled %}<a class="ui-btn ui-btn-primary" href="#door-code">{{ t('smart_locks.setup') }}</a>{% endif %}` (the state box keeps its text; the one "Connect my lock" button lives under the terms). Change `<h2 class="property-section-title">{{ t('smart_locks.title') }}</h2>` to `<h2 class="property-section-title sr-only">{{ t('smart_locks.title') }}</h2>` (the section summary already says "Smart lock"; text kept for tests and screen readers).
4. `_smart_locks_panel.html` line 14: change `<h2>{{ t('smart_locks.setup_title') }}</h2>` to `<h2 class="sr-only">{{ t('smart_locks.setup_title') }}</h2>`. Nothing else in the file changes.
5. `base.html` line 22: set the value after `/static/app2.css?v=` to `20261107-0996`.
6. Check there is no stray reference: `grep -rn "smart_locks.setup\b" App/tests | tail -30`; if a test counts exactly one `href="#door-code"` button or two "Connect my lock" strings, update the expectation to one button (the form submit).

## 5. Do not touch

`signature.js`, `_entity_business_fields.html` markup, `host2.css`, `app.css`, the connected-lock branch of the section, `smart_locks.*` copy, door-code logic (UbyPort and TTLock rules in AGENTS stay). No new dependency.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` (browser 0 skipped, `UBYHOST_REQUIRE_BROWSER=1`).
- `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q -x 2>&1 | tail -30`. The lint does not open dialogs: also take, with Playwright, one 390 px and one 1280 px screenshot of the open signature dialog and the Smart lock section (open `#sec-lock`, then click the signature "Sign" button on `#sec-fee`) and read them.
- `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root.

## 7. Acceptance

- [ ] Signature dialog: a centred card at most 720 px wide, pill tabs Draw/Type, a 160 to 260 px pad, actions inside the card, page behind dimmed (no "Archive property" showing through at the bottom).
- [ ] Smart lock (no lock connected): state box without a button, no empty column under the title, "How it works" full width, checkbox directly above the single "Connect my lock" button.
- [ ] Layout lint zero findings, 0 skipped; 390 px screenshots (dialog and section) in the report; per page "390: ...; 768: ...; 1280: ..." in the PR; design-system checklist ticked.

## 8. Stop and ask

An excerpt is not found; a test fails twice; 25 tool calls; a file outside section 3 needs a change; the dialog is still full screen after step 2 (report the computed styles, do not add `!important`).

## 9. Report

`docs/tasks/0996-report.md` (600 tokens at most), `Status: review`: files changed, last 5 lines of each command, section 7 ticked, deviations.
