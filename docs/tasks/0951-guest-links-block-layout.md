# 0951: property page "Automatic messages": tidy the Guest links block and the settings below it
Status: todo
Depends on: 0948 (run AFTER it merges; it edits the top of the same template. This brief touches only lines 128-196 of `_property_editor.html`, section `sec-messages`) | Branch: new branch from `main`, name `claude/0951-guest-links-layout`
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens. Two chats: chat A = steps 1-3 (Guest links block), chat B = steps 4-7 (rest of section, tests, gate). One commit per step.

## 1. Objective
Owner screenshots of `/apartments/<id>`, section "Automatic messages": the Guest links block is "extremely ugly" and the settings below it are misaligned. Same controls and behaviour, less height, aligned, v2 design system ([design-system](../design/design-system.md) rules 3, 4, 7, 8 and the Buttons / Forms / Help rows):
1. Link and PIN: label above, then ONE row: input (fills the column) + compact Copy button of the same height as the input. Never wraps to a second row, also at 390 px.
2. Secondary actions (Preview as a guest, Open the guest guide, Generate a new PIN, Generate a new link): ONE quiet action row under the two values. All same size (compact secondary), same baseline, text vertically centred, no round blobs. Each regenerate button keeps its "?" tip directly after the button.
3. Settings below: aligned fields, ? directly after the label, hint under its own field, select text not cut, passport-scan checkbox a proper checkbox row.
4. No new text, no new i18n keys.

## 2. Context (verified)
- Template `App/app/templates/_property_editor.html`: block `<div class="guest-link-top">` lines 135-170; windows grid `<div class="grid guest-link-windows">` lines 173-195; OCR row lines 189-194 has inline `style=` (violates rule 2: remove).
- Shared macros in `App/app/templates/_components.html`: `copy_button` (line 311; v2 branch makes `<button class="btn sm ghost copy-btn" ...>` with icon + `copy-label-default` span; else `ui-btn ui-btn-secondary ui-btn-icon ui-btn-compact copy-btn`) and `copy_inline` (line 325). Do NOT change the macros' data attributes (`data-copy`, `data-copy-label`, `data-copied-label`, `data-copy-label-slot`); app.js depends on them.
- Existing CSS to replace for this block only: `App/app/static/app2.css` lines ~2341-2343 (`.guest-link-actions`, `.guest-link-action`), ~1037-1038 (`.fields-wrap .copyrow > .btn.sm{min-height:48px}`: the cause of the oversized Copy; scope-limit it, see step 2), ~1669 (`.field-label-row{... flex-wrap:nowrap}`), ~1900 (`.prop-sec input... margin-bottom:12px`), ~12 (checkbox 20px) and ~1030 (phone `min-height:44px` for `details.prop-sec` inputs, excluding checkbox). `App/app/static/host.css` lines 909-915 (`.guest-link-top ...`, `.guest-link-pin{max-width:320px}` = the half-width inputs) and ~928 (`.host-workspace .copy-btn` 40px square).
- `.copyrow` is also used at `_property_editor.html:351` and in `stay_fee_detail.html` (many): do NOT change `.copyrow` globally. Scope every new rule under `.guest-link-top`. Before editing run `grep -rn "guest-link-top\|guest-link-actions\|guest-link-action\|guest-link-pin\|guest-link-url\|guest-link-windows" App/app App/tests | cut -c1-150 | tail -30` (known: only `_property_editor.html`, `host.css`, `app2.css`). Also `grep -rn "copy_button\|permalink_pin" App/app/templates | cut -c1-120`: the setup wizard (`setup_wizard/guest_link.html`, `done.html`, `try_it.html`) and `apartment_form.html` may show the same link/PIN: if they use `copyrow` + `copy_button` for link or PIN, give them the same `guest-copy-row` class (step 1) so one rule fixes all; name each in the report. Do not restructure them otherwise.
- Tests that reference the old markup: `grep -rln "guest-link-\|permalink_pin\|ocr_scan\|link-window-note" App/tests` (list: test_onboarding, test_0531_property_page, test_calmer_forms, test_security, test_dashboard_order, ...). Most assert ids/names only (stay valid: keep ids `permalink`, `permalink_pin`, `ocr_scan`, `passport_photo_policy`, `permalink_window_days`, `permalink_reachback_days`, names, `data-copy`, `formaction`, `data-confirm`). Only update an assertion that names a class you remove.
- Browser tests for this page: `test_0833_property_editor_browser.py`, `test_host_property_controls_browser.py`, `test_0541_property_page_phone_browser.py`; add the new geometry test to `test_host_property_controls_browser.py` (read its helpers first with `grep -n "^def \|^@pytest" ...`).
- Test-map rows: "Onboarding, properties" (`test_property_*.py`) plus browser/geometry rows of the property page; run only the files named below.

## 3. Files
`App/app/templates/_property_editor.html` (lines 128-196 only), `App/app/static/app2.css`, `App/app/static/host.css`, `App/app/templates/base.html` (`?v=`), `App/tests/static_versions.json` (via `--write`), `App/tests/test_host_property_controls_browser.py`, tests found by grep that name removed classes, `docs/design/catalog.json` (only if it lists a removed class), `docs/design/pages/` property add-on (one line), `docs/context/decisions.md`, `docs/context/status.md`. Screenshots `docs/tasks/screenshots-0951/`. Report `docs/tasks/0951-report.md`.

## 4. Steps
1. Markup, Guest links block (replace lines 135-170, keep both `<form>` semantics: the regenerate buttons are submit buttons of the surrounding settings form with `formaction`; copy them character for character: `formmethod="post" formnovalidate formaction="{{ base_url }}/regenerate-pin"` / `/regenerate-link`, `data-confirm data-confirm-message=...`, and the two `help_tip(...)` calls). New structure:
```
<div class="guest-link-top">
  <div class="field guest-link-url">
    <label for="permalink">{{ t('property_nav.guest_link') }}</label>
    <div class="copyrow guest-copy-row">
      <input type="text" id="permalink" readonly value="{{ permalink }}">
      {{ copy_button('permalink') }}
    </div>
  </div>
  <div class="field guest-link-pin">
    {{ field_label('permalink_pin', t('guest_links.pin'), t('apartment.form.guest_link.pin_hint')) }}
    <div class="copyrow guest-copy-row pin-row"> ...same input as today... {{ copy_button('permalink_pin') }} </div>
  </div>
  <div class="guest-link-actions">
    <a class="ui-btn ui-btn-secondary ui-btn-compact" href="/l/{{ link_key }}" target="_blank" rel="noopener">{{ t('guest_links.preview') }}</a>
    <a class="ui-btn ui-btn-secondary ui-btn-compact" href="/apartments/{{ apartment.id }}/guide">{{ t('leon_page.guide_link') }}</a>
    <span class="guest-link-action"> regenerate-pin button (ui-btn ui-btn-secondary ui-btn-compact) + help_tip </span>
    <span class="guest-link-action"> regenerate-link button + help_tip </span>
  </div>
</div>
```
   All four actions use `ui-btn ui-btn-secondary ui-btn-compact` (the old `btn sm ghost` and `ui-btn-quiet` are removed, so sizes match). The guide link keeps its `href`. Commit `0951 step 1`.
2. CSS, Guest links block. In `host.css` delete lines 909-915 (the `.guest-link-*` rules) and add in `app2.css` (new block at the end, comment `/* 0951: guest links block */`), all under `body.v2`:
```
body.v2 .guest-link-top{display:grid;gap:16px;grid-template-columns:minmax(0,1fr);margin-bottom:16px}
body.v2 .guest-link-top .guest-copy-row{display:flex;flex-wrap:nowrap;align-items:center;gap:8px}
body.v2 .guest-link-top .guest-copy-row input{flex:1 1 auto;min-width:0;width:100%;max-width:none;height:40px;margin:0;text-overflow:ellipsis}
body.v2 .guest-link-top .guest-copy-row .copy-btn{flex:none;width:auto;min-width:40px;height:40px;min-height:40px;padding:0 12px;margin:0;display:inline-flex;align-items:center;justify-content:center;gap:6px;border-radius:var(--radius-md,8px)}
body.v2 .guest-link-top .guest-link-actions{display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;gap:12px;margin:0}
body.v2 .guest-link-top .guest-link-actions .ui-btn{height:40px;min-height:40px;padding:0 14px;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap}
body.v2 .guest-link-top .guest-link-action{display:inline-flex;align-items:center;gap:6px}
@media (max-width:1023px){body.v2 .guest-link-top .guest-copy-row :is(input,.copy-btn),body.v2 .guest-link-top .guest-link-actions .ui-btn{height:44px;min-height:44px}body.v2 .guest-link-top .guest-copy-row .copy-btn{min-width:44px}}
```
   Delete the old `.guest-link-actions`/`.guest-link-action` lines (~2341-2342 shared selector: remove only `.guest-link-actions,` from the `:is(...)` list, and delete line ~2342-2343). The `.fields-wrap .copyrow > .btn.sm{min-height:48px}` lines (~1037-1038) stay for other uses; the more specific selector above overrides them (specificity: `.guest-link-top .guest-copy-row .copy-btn` wins). Use existing tokens if `tokens.css` has `--radius-md` (it does, host.css uses it); no raw hex. Pin input must NOT be half width. Copy button label: if the v2 branch shows icon+text, keep it; it must not wrap (`white-space:nowrap`). Commit `0951 step 2`.
3. Quick check (no new test yet): `.venv/bin/python -m pytest tests/test_0531_property_page.py tests/test_calmer_forms.py -q --tb=short -x 2>&1 | tail -30`. Fix assertions that name removed classes only. Commit `0951 step 3`. (End of chat A.)
4. Rest of section "Automatic messages" (`_property_editor.html` 172-195). Rhythm: one vertical rhythm for the whole section: label 6 px above its field, 16 px between fields (use `gap:16px`; `margin-bottom:0` on inputs inside the section so the rhythm is the gap, not stacked margins). Markup changes:
   - Replace the OCR `<div class="feature-switch-row" style="...">` and its inline `style` attributes by `<div class="field passport-scan-row"><label class="checkline" for="ocr_scan"><input type="checkbox" id="ocr_scan" name="ocr_scan" value="1" {% if apartment.ocr_scan %}checked{% endif %} aria-describedby="ocr_scan-help"><span>{{ t('apartment.form.ocr_scan.label') }}</span></label>{{ help_tip('ocr_scan-help', t('apartment.form.ocr_scan.hint')) }}</div>` (the tip sits right after the label text, outside the `<label>` so a tap on ? does not toggle the box; keep the help_tip id `ocr_scan-help`).
   - Order inside `.guest-link-windows`: window days, reach-back days (two columns), then the passport select (full row), then the OCR row (full row, directly under the select). Keep the next-stay hint `<p class="ui-sub link-window-note">` inside the window-days field, unchanged text.
   CSS (app2.css, same 0951 block):
```
body.v2 .guest-link-windows{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 24px;align-items:start}
body.v2 .guest-link-windows .field{display:flex;flex-direction:column;gap:6px;min-width:0;margin:0}
body.v2 .guest-link-windows .field > input,body.v2 .guest-link-windows .field > select{width:100%;max-width:none;margin:0;box-sizing:border-box}
body.v2 .guest-link-windows .field-label-row{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-start;gap:6px;margin:0}
body.v2 .guest-link-windows .link-window-note{margin:0}
body.v2 .guest-link-windows .field:has(> select),body.v2 .guest-link-windows .passport-scan-row{grid-column:1/-1}
body.v2 .guest-link-windows select{text-overflow:clip;white-space:normal;height:auto;min-height:40px;padding-top:8px;padding-bottom:8px}
body.v2 .passport-scan-row{flex-direction:row;align-items:center;gap:8px;min-height:44px}
body.v2 .passport-scan-row .checkline{display:inline-flex;align-items:center;gap:12px;margin:0;min-height:44px;cursor:pointer}
body.v2 .passport-scan-row input[type=checkbox]{width:24px;height:24px;min-width:24px;min-height:24px;margin:0;flex:none}
@media (max-width:767px){body.v2 .guest-link-windows{grid-template-columns:minmax(0,1fr)}}
```
   If a long select option is still cut at 390 px (check in step 6), shorten with the existing short keys: `grep -n "passport_policy" App/app/host_i18n.py | head` and use an existing shorter key only if one exists; otherwise rely on the full-width select (`white-space:normal` is ignored by some browsers' closed select; then set `font-size` unchanged and rely on full width, which fits at 390 because the option text is under about 45 characters). Do not add i18n unless the test below still fails; in that case stop and ask. Commit `0951 step 4`.
5. Version bump. `grep -n "app2.css\|host.css" App/app/templates/base.html`: app2 `?v=20261104-0960m` becomes the next free letter (`0960n`; if 0949 already took it, `0960o`), host.css `20261102-0799` becomes `20261104-0800`. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5` (else `grep -n -- '--write' tests/test_static_versions.py`). Commit `0951 step 5`.
6. Browser geometry test. In `tests/test_host_property_controls_browser.py` add `test_guest_links_and_message_settings_geometry` following that file's login/page helpers, parametrised over widths 390, 768, 1280. Open the property page with `?section=guests` (or open `#sec-messages`; use whatever the file does for `settings_section`). Assert, via `page.evaluate` on bounding boxes:
   - `#permalink` and its `.copy-btn` (`[data-copy="permalink"]`): `abs(top diff) <= 4`, heights equal (±1), button right of input; same for `#permalink_pin` and `[data-copy="permalink_pin"]`.
   - every `.guest-link-top .ui-btn, .guest-link-top .copy-btn`: equal height (±1); at 390 each height >= 44.
   - `#permalink` width >= 60% of the `.guest-link-top` width (not half width).
   - `.guest-link-actions` at 1280 sits on at most 2 visual rows (distinct `top` values <= 2); each regenerate button's `.help-tip` is within 24 px right of the button.
   - `#permalink_window_days` and `#permalink_reachback_days`: same `top` (±1) at 768 and 1280; at 390 the second is below the first.
   - `#passport_photo_policy`: `scrollWidth <= clientWidth` and its `getBoundingClientRect().width` >= 90% of the `.guest-link-windows` width; select label `.help-tip` on the same row as the label text (tops within 6 px).
   - `#ocr_scan`: width and height between 20 and 26 px; its label text vertical centre within 3 px of the checkbox centre; the `.help-tip` of `ocr_scan-help` is on the same row (top diff <= 6) at 1280, and the box is below the select (top greater than select bottom).
   - `document.documentElement.scrollWidth <= innerWidth` at each width.
   Zero skips. Commit `0951 step 6`.
7. UX gate ([workflow](../context/workflow.md#ux-gate)). From `App/`: `export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/shots`, then `.venv/bin/python -m pytest tests/test_host_property_controls_browser.py tests/test_0833_property_editor_browser.py tests/test_0541_property_page_phone_browser.py tests/test_layout_lint_browser.py tests/test_static_versions.py -q --tb=short -rs -p no:cacheprovider 2>&1 | tail -30` (0 skipped; take screenshots of the opened "Automatic messages" section at 390/768/1280 into `/tmp/shots`, copy to `docs/tasks/screenshots-0951/`). Open each, write per width what you saw (Copy on the input row, one action row, equal buttons, select text whole, checkbox aligned). Never silence a lint finding. Tick the [design-system checklist](../design/design-system.md) in the report. Docs: one line in the property page add-on under `docs/design/pages/` (`grep -n "Guest" ` there, one range): `- Guest links: value + Copy on one row, one quiet action row, settings grid per 0951.`; append to `docs/context/decisions.md`: `- [property-page] 2026-11-04: guest link and PIN are one input+Copy row each, four secondary actions in one compact row; section settings share one 6/16 px rhythm. Source: brief 0951.`; status.md at most 5 lines. Then `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5` and from repo root `python3 scripts/context_lint.py | tail -30`. Write `docs/tasks/0951-report.md`. Commit `0951 step 7`.

## 5. Do not touch
Form actions, POST routes, CSRF, `data-confirm` messages, `copy_button` / `copy_inline` macros, `.copyrow` global rules, `stay_fee_detail.html`, the rest of `_property_editor.html` (0948 owns the top), JS files, guest pages, i18n files (unless step 4 says stop and ask). No new dependency, personal data or outbound request.

## 6. Commands
From `App/`, only the test files named in steps 3, 6, 7 (test-map rows "Onboarding, properties" and the property-page browser rows); browser tests skip silently without the env vars in step 7. No full suite.

## 7. Acceptance
Link and PIN each one row with Copy at the same height and top; one action row of equal buttons; regenerate buttons still confirm and post as before; two number fields aligned (one column on phone); select text not truncated; checkbox 24 px visual, centred with its label, ? inline, under the select; no horizontal overflow at 390/768/1280; listed tests pass with 0 skipped; no inline `style=` left in lines 128-196.

## 8. Stop and ask
Stop if an anchor is not found verbatim (0948 may have shifted lines: use grep for `guest-link-top`), if a test outside the listed ones fails, if the select still truncates without new i18n, or if the wizard markup cannot share `guest-copy-row` without larger changes (report instead).

## 9. Report
`docs/tasks/0951-report.md`: status, test tails, test assertions changed one by one, places sharing the component (names), per-width screenshot notes, deviations. Stage files by name, never `git add -A`, never `App/.venv`. Do not push. If you run out of calls: commit what passes, `Status: blocked`, `Done: steps 1 to k. Left: steps k+1 to 7.`
