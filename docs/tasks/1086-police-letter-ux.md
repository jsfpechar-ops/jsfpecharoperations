# 1086: G6 police letter, part 3 of 3: browser tests, the discard warning, screenshots and the UX gate

Status: todo
Tier: A | Depends on: 1085 (work on top of `claude/1085-police-letter-flow` after its executor commits; merge it in first), which depends on 1088 | Base commit: 71448224 | Branch: claude/1086-police-letter-ux
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: an extremely strict fresh Fable diff review (owner's words) before the PR opens, on UX, the no-JavaScript flow and filing safety in the browser.
Report: docs/tasks/1086-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) G6, part 3. This brief proves in a real browser that the 1085 flow works and looks right at 390, 768 and 1280 px, with and without JavaScript, under Turbo 8. It also:

- tests the discard warning that 1085 built (moved here from 1085, which has no browser test)
- takes the screenshots
- passes the UX gate (AGENTS rule 10), which 1085's draft PR waits for

It writes tests and screenshots. The only code changes allowed are layout fixes in `host.css`, `_property_editor.html` and `_police_letter_figure.html` for what the layout lint or the screenshots find. The flow logic, the routes, the copy and the parser stay untouched.

## 2. Context

### What 1085 builds (read `docs/tasks/1085-police-letter-flow.md` section 2 only if a detail below is unclear)

- **In the card `#ubyport`:**
  - `details.police-letter-find`: the SVG figure with the real labels and fake values (`Přihlašovací jméno: UBY-WS_ABCDE`, `Přístupové heslo: ••••••••`, `IDUB: 000000000000`), a numbered legend, and the short-name note
  - `details.police-letter-paste`: a textarea `letter_text` with `form="police-letter-form"`, and a "Read the letter" button
  - the check-answers card, shown only on the paste reply. Each filled value has its exact source in `<code>`, "Check this against your letter.", and a `required` box `letter_ok_<field>`. The password row says "Type it yourself".
  - `#police-letter-form` (only `_csrf`) sits after the big form. On the check-answers page `#property-settings-form` has `data-dirty-start="1"`.
- **Routes:**
  - `POST /apartments/{id}/police-letter` answers **422** with `Cache-Control: no-store`, for check-answers and for the `empty`, `too_long` and `failed` states. It stores nothing.
  - A save (`POST /apartments/{id}`, or `/test-connection`) with an unticked letter value answers **400**, and saves nothing.
  - `apartment_update` runs the read-only connection test automatically **only** at its final success exit, **only** when `letter_fields` is posted together with a password, and **never** with `setup_step`. The flashes are `letter_test_ok`, `letter_test_failed` (auth), `letter_test_unreachable` (transport) and `letter_saved_untested` (no password).
  - `/test-connection` with a new letter login and no password saves, but skips the test (`letter_new_login_no_password`).
- **Discard warning (JavaScript):** on submit of `#police-letter-form`, if `#property-settings-form` is dirty or `#uby_ws_password` has a value, `window.confirm(data-discard-warning)` runs. Cancel keeps the page. `app.js` and `host.css` keys are `20261110-1085`.
- **Turbo 8** (`base.html:44`) renders a 4xx reply to a form POST in place. The tests must show the card really appears with Turbo on and with JavaScript off.

### Other context

- **Mock UbyPort:** use what the existing e2e tests use: `UBYHOST_MOCK_URL` (`config.py:304`), or the monkeypatch pattern in `test_endtoend.py` (grep `test-connection` there and read 40 lines). Never the real police endpoint.
- **UX gate (rule 10):** run `test_layout_lint_browser.py` green, open the 390, 768 and 1280 shots of each touched page, and write per page what you saw. The touched page is the property settings page, at Reporting & fees, in two states: closed and with the check-answers card. Never ask the owner, never silence a finding.
- **Design system:** [design-system](../design/design-system.md):
  - rule 2: tokens only
  - rule 3: 12 px minimum between neighbours
  - rules 4 and 5: one Save per form, no lone button
  - rule 7: help under "?"
  - rule 8: no truncated label
  - rule 9: coral only as a signal
  - rule 10: no sideways scroll
  The section 5 checklist goes, ticked, into the report and the PR.
- **Test letters:** the fake `SAMPLE_*` values (`App/app/ubyport_sample_pdf.py:26-44`). Never real data; the screenshots are public.

### Anchors (re-check each with `grep -nF` after the merge)

1. `App/app/templates/_property_editor.html`: `police-letter-find`, `police-letter-paste`, `id="police-letter-form"`, `data-discard-warning`, `letter_ok_` (from 1085). If any is missing: STOP.
2. `App/app/static/app.js`: `police-letter-form` and `window.confirm` (from 1085).
3. `App/app/templates/_police_letter_figure.html` exists.
4. `App/tests/test_0833_property_editor_browser.py:7` `from tests.browser_support import chromium_launch_kwargs, settle_motion`, the model for imports and fixtures (read its first 60 lines only).
5. `App/tests/test_layout_lint_browser.py:52` `ALLOW: dict[tuple[str, str], str] = {}`. No new `ALLOW` entry.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_host_police_letter_browser.py` | create | flow, Turbo, no-JS and geometry tests (step 2) |
| `App/tests/test_host_police_letter_guard_browser.py` | create | the discard warning test (step 3), moved here from 1085 |
| `App/app/static/host.css` | edit, only if step 4 finds something | layout fixes, tokens only; key `20261110-1086`, then regenerate `static_versions.json` |
| `App/app/templates/base.html` | edit, only with a `host.css` change | the `host.css` key |
| `App/tests/static_versions.json` | regenerate, only with a `host.css` change | `tests/test_static_versions.py --write` |
| `docs/tasks/screenshots-1086/` | create | the PNGs (steps 2f and 4) |
| `docs/tasks/1086-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1086 step k`)

1. Merge `claude/1085-police-letter-flow` (or main, if 1085 has merged). Confirm anchors 1 to 5; if one is missing, STOP.
2. `test_host_police_letter_browser.py`, with `@pytest.mark.parametrize("width", [390, 768, 1280])`:
   a. **Find card:** open the property settings at Reporting & fees and open "Where do I find these?". The SVG is visible and inside the panel. `document.documentElement.scrollWidth <= innerWidth`. The three numbered lines and the legend are readable (no element narrower than its text).
   b. **Paste with Turbo on:** paste the official-layout letter (the title, `Přihlašovací jméno:`, `Přístupové heslo:`, `IDUB:`, with the `SAMPLE_*` values) and click "Read the letter" (no unsaved edits, so no dialog).
      - The check-answers card is visible.
      - The IDUB and login inputs hold the values; the short name holds `SAMPLE_ZKRATKA` with the "Taken from the login" line.
      - Each filled row shows its source in `<code>` and "Check this against your letter.". The password input is empty.
      - `page.content()` does not contain `SAMPLE_WS_PASSWORD`.
      - Back returns to the property page.
   c. **Confirm:**
      - Click Save with no tick: the browser blocks it (`required`).
      - Click "Save and test connection" with no tick (`formnovalidate`): 400, the card stays with the error under the box, and the saved row is unchanged (read it with the app's db helper).
      - Tick all, type a password, and Save against the mock: the flash reads "Saved. The login and password work.", and the mock records one test.
      - Paste again, tick all, Save with **no** password: the `letter_saved_untested` flash, and the mock records no call.
   d. **No JavaScript** (`java_script_enabled=False`, the pattern of `test_guest_form_input_browser.py`'s no-JavaScript test): the same paste works, the card renders from the 422 reply, and the 400 refusal and a confirmed save both work.
   e. **Geometry** at each width:
      - 12 px or more between the two `details`, the card and the first field; no overlap
      - the textarea fills the column below 768 px
      - every checkbox and button has a 44 px touch target on the phone
      - the focus ring shows on a checkbox after Tab
      - no label is cut off (`scrollWidth <= clientWidth`)
      - each `<code>` source wraps inside the card, with no sideways scroll
   f. **Screenshots** into `docs/tasks/screenshots-1086/`: `find-{390,768,1280}.png` (the figure open) and `check-{390,768,1280}.png` (the check-answers card). Look at each once, and write one line per file in the report.
3. `test_host_police_letter_guard_browser.py` (0 skipped; same imports and fixtures; width 1280), moved from 1085:
   - Type into the facility name, click "Read the letter" and dismiss the dialog: the page stays and the typed value is kept.
   - Accept it: the check-answers page loads.
   - With only a typed password, the dialog shows too. With no edits, there is no dialog.
   - On the check-answers page `#property-settings-form` has `data-dirty-start="1"`, and leaving the page (`beforeunload`) warns.
   - After an accepted dialog, `beforeunload` does not warn a second time.
4. **UX gate (rule 10):** run `test_layout_lint_browser.py` green, with no new `ALLOW`. Open its 390, 768 and 1280 shots of the property settings page with Reporting open. Save shots of the same page with the check-answers card at the three widths as `lint-check-{390,768,1280}.png`. Write per width what you saw for both states. A finding is fixed in `host.css` or the two templates (layout only), never silenced. Paste and tick the design-system section 5 checklist in the report.
5. Run section 6, then write the report.

## 5. Do not touch

`police_letter.py`, `routes/*`, `app.js`, the flow parts of the templates (the names, hidden inputs, `required`, `form` and `data-*` attributes), all i18n files, `validation.py`, `reporting.py`, `ubyport/*`, `db.py`, migrations, any dependency, and `ALLOW` in `test_layout_lint_browser.py`. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`, browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_police_letter_browser.py tests/test_host_police_letter_guard_browser.py tests/test_0833_property_editor_browser.py tests/test_property_navigation_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`. Then: `.venv/bin/python -m pytest tests/test_police_letter_flow.py tests/test_police_letter_parser.py tests/test_static_versions.py tests/test_host_i18n.py -q --tb=short -x`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The paste, the check-answers card (source and "Check this against your letter" per value), the 400 refusal and a confirmed save all work with Turbo on and with JavaScript off, at 390, 768 and 1280.
- [ ] With no password posted, the mock records no call. With one, it records exactly one test, with a plain-words flash.
- [ ] The discard warning shows for unsaved edits or a typed password, cancel keeps the page, and the check-answers page starts dirty.
- [ ] The password and the pasted text never show in the page beyond the source slices.
- [ ] Geometry green. Layout lint green with no new `ALLOW`. Nine screenshots, and one line per width per state in the report. The design-system checklist is ticked.
- [ ] Browser tests 0 skipped. `git diff --stat` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a fix needs a route, flow, copy, JavaScript or parser change (that goes back to 1085 or 1088); the card does not render under Turbo; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1086-report.md`, 600 tokens at most: files, each command with its last 5 lines, section 7 ticked, one line per screenshot, the layout-lint result per width and state, the design-system checklist, deviations and questions. Set this brief `Status: review`. After the strict fresh Fable review, open one PR. Body:
- the UX-gate lines per width and state
- the ticked checklist
- a link to 1085's PR
- this line: "1085 adds a new automatic outbound trigger (rule 2): the read-only connection test after a confirmed letter save with a typed password"

The orchestrator then marks 1085 ready, merges it, and merges this one after a rebase. Merge only with `scripts/merge-pr-on-green.sh`.
