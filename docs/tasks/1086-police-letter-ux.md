# 1086: G6 police letter, part 3 of 3: browser tests, the discard warning, screenshots and the UX gate

Status: review
Tier: A | Depends on: 1085 (merged to main as PR #882, `a166812a`; merge `origin/main` into this branch first) | Base commit: a166812a | Branch: claude/1086-police-letter-ux
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: an extremely strict fresh Fable diff review (owner's words) before the PR opens, on UX, the no-JavaScript flow and filing safety in the browser.
Report: docs/tasks/1086-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) G6, part 3. This brief proves in a real browser that the 1085 flow works and looks right at 390, 768 and 1280 px, with and without JavaScript, under Turbo 8. It also:

- tests the discard warning that 1085 built (1085 pins it only in the source, not in a browser)
- takes the screenshots
- passes the UX gate (AGENTS rules 7 and 10) for the whole flow

1085 is merged and live. It passed its own UX gate over four fix rounds and has one browser test (section 2). This brief adds the full-flow browser files; it does not redo or change what 1085 settled.

It writes tests and screenshots. The only code changes allowed are layout fixes in `App/app/static/app2.css` (under `body.v2`), `_property_editor.html` and `_police_letter_figure.html` for what the layout lint or the screenshots find. The flow logic, the routes, the copy, the parser, `app.js` and `host.css` stay untouched.

## 2. Context

### What 1085 built (it is on main; read `docs/tasks/1085-report.md` "Attempt 2" to "Attempt 4" only if a detail below is unclear)

- **In the card `#ubyport`:**
  - `details.police-letter-find`: the SVG figure with the real labels and fake values (`Přihlašovací jméno: UBY-WS_ABCDE`, `Přístupové heslo: ••••••••`, `IDUB: 000000000000`), a numbered legend, and the short-name note
  - `details.police-letter-paste`: a textarea `letter_text` with `form="police-letter-form"`, and a "Read the letter" button
  - the check-answers block `#police-letter-check`, shown on the paste reply and on a refused save. One `.police-letter-row` per field (IDUB, login, short name; there is **no** password row). Each filled value has its exact source in `<code>` and a `required` tick `letter_ok_<field>` in a `div.checkline`, with the label "Matches my letter" and a `req-star`. The sentence "Check this against your letter." no longer exists.
  - `#police-letter-form` (only `_csrf`) sits after the big form (line 474). On the check-answers page `#property-settings-form` has `data-dirty-start="1"`.
- **Routes:**
  - `POST /apartments/{id}/police-letter` answers **422** with `Cache-Control: no-store`, for check-answers and for the `empty`, `too_long` and `failed` states. It stores nothing.
  - A save (`POST /apartments/{id}`, or `/test-connection`) with an unticked letter value answers **400**, and saves nothing.
  - `apartment_update` runs the read-only connection test automatically **only** at its final success exit, **only** when `letter_fields` is posted together with a password, and **never** with `setup_step`. The flashes are `letter_test_ok`, `letter_test_failed` (auth), `letter_test_unreachable` (transport) and `letter_saved_untested` (no password).
  - `/test-connection` with a new letter login and no password saves, but skips the test (`letter_new_login_no_password`).
- **Discard warning (JavaScript):** on submit of `#police-letter-form`, if `#property-settings-form` is dirty or `#uby_ws_password` has a value, `window.confirm(data-discard-warning)` runs. Cancel keeps the page (`initPoliceLetterForm`, `app.js:2285`).
- **Turbo 8** (`base.html:44`) renders a 4xx reply to a form POST in place. The tests must show the block really appears with Turbo on and with JavaScript off.

### What 1085's fix rounds settled (do not undo any of it)

- Every helper rule lives in `App/app/static/app2.css` under `body.v2` (lines 3435-3470; the editor is a v2 page). `host.css` has no police-letter rule.
- The two `details` are plain disclosure rows: no box, no gap between them, a 1 px `--line` rule, summaries 44 px high, flush with their content.
- `letter_text` has `form="police-letter-form"`, so Save never sends it.
- The legend note and the "Saved now" line use `police-letter-note` (`--ink-secondary`, for contrast). Never `muted`.
- After "Read the letter", `initPoliceLetterForm` scrolls `#police-letter-check` or `#letter_text-error` into view. With no JavaScript the first unticked box (or the textarea, on an error) has `autofocus`. After a paste the editor starts on `sec-police` (`data-start-section`).
- The tick label has `margin:0`; the 20 x 20 box and its text are centred within 2 px.
- Keys on main: `app2.css?v=20261110-1085i` (`base.html:23`), `app.js?v=20261110-1085b` (`base.html:47`), `host.css?v=20261108-1010a` (unchanged by 1085).
- **1085's browser test** `test_the_letter_helper_is_styled_in_the_browser` (`App/tests/test_police_letter_flow.py:916`) already asserts the figure styling, the disclosure rows, the 422 and 400 replies, the landing in the viewport and the tick alignment at 390, 768 and 1280. It is the model for the server thread, the session cookie and the page URL (read lines 916-965 only). Do not copy its assertions and do not edit it.

### Other context

- **Mock UbyPort:** the `fake_client` and `no_client` fixtures in `App/tests/test_police_letter_flow.py:190-214`. They monkeypatch `reporting.client_for`; the browser test runs the app in a thread of the same process, so they apply. `fake_client["made"]` lists the clients built, each with its `.calls`. Never the real police endpoint.
- **UX gate (rules 7 and 10, [steps](../context/workflow.md#ux-gate)):** run `test_layout_lint_browser.py` green with 0 skipped, open the 390, 768 and 1280 shots of each touched page, and write per page what you saw. The touched page is the property settings page, at Reporting & fees, in two states: closed and with the check-answers block. Never ask the owner, never silence a finding.
- **Design system:** [design-system](../design/design-system.md):
  - rule 2: tokens only
  - rule 3: 12 px minimum between neighbours
  - rules 4 and 5: one Save per form, no lone button
  - rule 7: help under "?"
  - rule 8: no truncated label
  - rule 9: coral only as a signal
  - rule 10: no sideways scroll
  The section 5 checklist goes, ticked, into the report and the PR.
- **Test letters:** `LETTER` in `App/tests/test_police_letter_flow.py:38`, built from the fake `SAMPLE_*` values (`App/app/ubyport_sample_pdf.py:26-44`). Never real data; the screenshots are public.

### Anchors (re-check each with `grep -nF` after the merge)

1. `App/app/templates/_property_editor.html`: `police-letter-find` (312), `police-letter-paste` (316), `id="letter_text"` with `form="police-letter-form"` (320), `id="police-letter-check"` (328), `letter_ok_` (343), `formaction="{{ base_url }}/test-connection"` (382), and `id="police-letter-form"` with `data-discard-warning` (474). If any is missing: STOP.
2. `App/app/static/app.js:2285` `function initPoliceLetterForm`, with `window.confirm(letterForm.dataset.discardWarning)` below it.
3. `App/app/templates/_police_letter_figure.html` exists.
4. `App/tests/test_police_letter_flow.py`: `LETTER = (` (38), `def host` (153), `def fake_client` (191), `def no_client` (205) and `def test_the_letter_helper_is_styled_in_the_browser` (916). Import `LETTER` and the three fixtures from there (`from tests.test_police_letter_flow import ...  # noqa: F401`, as `test_0833_property_editor_browser.py:8` does for its fixtures).
5. `App/tests/test_layout_lint_browser.py:53` `ALLOW: dict[tuple[str, str], str] = {}`. Two old entries follow on lines 55-56. No new `ALLOW` entry.
6. `App/app/static/app2.css:3435` `body.v2 details.police-letter-find,` and `App/app/templates/base.html:23` `app2.css?v=20261110-1085i`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_host_police_letter_browser.py` | create | flow, Turbo, no-JS and geometry tests (step 2) |
| `App/tests/test_host_police_letter_guard_browser.py` | create | the discard warning test (step 3) |
| `App/app/static/app2.css` | edit, only if step 2 or 4 finds something | layout fixes in the `body.v2 .police-letter-*` block (3435-3470), tokens only, every selector under `body.v2` |
| `App/app/templates/_property_editor.html`, `App/app/templates/_police_letter_figure.html` | edit, only if step 2 or 4 finds something | layout only (a class or a wrapper) |
| `App/app/templates/base.html` | edit, only with an `app2.css` change | line 23: `app2.css?v=20261110-1085i` becomes `app2.css?v=20261110-1086a` (a second change: `1086b`). No other key changes. |
| `App/tests/static_versions.json` | regenerate, only with an `app2.css` change | from `App/`: `.venv/bin/python tests/test_static_versions.py --write` |
| `docs/tasks/screenshots-1086/` | create | the PNGs (steps 2f and 4) |
| `docs/tasks/1086-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1086 step k`)

1. `git fetch origin main`, then `git merge origin/main` into this branch (1085 is in main). Confirm anchors 1 to 6; if one is missing, STOP.
2. `test_host_police_letter_browser.py`, with `@pytest.mark.parametrize("width", [390, 768, 1280])`. Import playwright as the model test does (a plain import when `UBYHOST_REQUIRE_BROWSER=1`, else `importorskip`). Page URL: `/apartments/{id}?view=settings&section=reporting#ubyport`.
   a. **Find card:** open the property settings at Reporting & fees and open "Where do I find these?". The SVG is visible and inside the panel. `document.documentElement.scrollWidth <= innerWidth`. The three numbered lines and the legend are readable (no element narrower than its text).
   b. **Paste with Turbo on:** paste `LETTER` (the official layout with the `SAMPLE_*` values) and click "Read the letter" (no unsaved edits, so no dialog).
      - The check-answers block `#police-letter-check` is visible and inside the viewport.
      - The IDUB and login inputs hold the values; the short name holds `SAMPLE_ZKRATKA` with the "Taken from the login on line ..." line (`police_letter.source_login`).
      - Each filled row shows its source in `<code>` and its "Matches my letter" tick with a `req-star`. There is no password row, and `#uby_ws_password` is empty.
      - `page.content()` does not contain `SAMPLE_WS_PASSWORD`.
      - Back returns to the property page.
   c. **Confirm:**
      - Click Save with no tick: the browser blocks it (`required`).
      - Click "Save and test connection" with no tick (`formnovalidate`): 400, the block stays with one error under each unticked box, and the saved row is unchanged (read it with the app's db helper).
      - Tick all, type a password, and Save with `fake_client`: the flash reads "Saved. The login and password work.", and `fake_client["made"]` holds exactly one client, with read-only calls only.
      - Paste again, tick all, Save with **no** password: the `flash.apartments.letter_saved_untested` text, and no further client was built.
   d. **No JavaScript** (`java_script_enabled=False`, as `test_guest_form_input_browser.py:91`): the same paste works, the block renders from the 422 reply with the focus on the first unticked box (`autofocus`), and the 400 refusal and a confirmed save both work.
   e. **Geometry** at each width:
      - 12 px or more between the "Read the letter" button and what follows it, and between the check block and the first field (`#uby_idub`); no overlap. The two `details` stay flush rows (1085): do not add a gap between them.
      - the textarea fills the column below 768 px
      - every tick row (the `.checkline` label), summary and button has a 44 px touch target on the phone (the box itself is 20 x 20 by design)
      - the focus ring shows on a checkbox after Tab
      - no label is cut off (`scrollWidth <= clientWidth`)
      - each `<code>` source wraps inside the block, with no sideways scroll
   f. **Screenshots** into `docs/tasks/screenshots-1086/`: `find-{390,768,1280}.png` (the figure open) and `check-{390,768,1280}.png` (the check-answers block), taken as the model test's `shot` helper does (`page.locator("#ubyport").screenshot`). Look at each once, and write one line per file in the report.
3. `test_host_police_letter_guard_browser.py` (0 skipped; same imports and fixtures; width 1280). Handle the dialog with `page.on("dialog", ...)`:
   - Type into the facility name, click "Read the letter" and dismiss the dialog: the page stays and the typed value is kept.
   - Accept it: the check-answers page loads.
   - With only a typed password, the dialog shows too. With no edits, there is no dialog.
   - On the check-answers page `#property-settings-form` has `data-dirty-start="1"`, and leaving the page (`beforeunload`) warns.
   - After an accepted dialog, `beforeunload` does not warn a second time.
4. **UX gate (rules 7 and 10):** from `App/` run `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`: green, 0 skipped, no new `ALLOW`. Then `ls /tmp/shots/layout-lint | grep -i propert | head -50` and open the 390, 768 and 1280 shots of the property settings page, plain and `+open` (in `+open` the two `details` are open). The lint does not reach the check-answers state, so save full-page shots of it at the three widths from your own test as `docs/tasks/screenshots-1086/lint-check-{390,768,1280}.png`. Write per width what you saw for both states. A finding is fixed in `app2.css` or the two templates (layout only), never silenced, and never by undoing a point of "What 1085's fix rounds settled". Paste and tick the design-system section 5 checklist in the report.
5. Run section 6, then write the report.

## 5. Do not touch

`police_letter.py`, `routes/*`, `app.js` and its key, `host.css`, `App/tests/test_police_letter_flow.py`, the flow parts of the templates (the names, hidden inputs, `required`, `autofocus`, `form` and `data-*` attributes), the `req-star` and `police-letter-note` classes, all i18n files, `validation.py`, `reporting.py`, `ubyport/*`, `db.py`, migrations, any dependency, and `ALLOW` in `test_layout_lint_browser.py`. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

No full suite. From `App/`:

1. Browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_host_police_letter_browser.py tests/test_host_police_letter_guard_browser.py tests/test_police_letter_flow.py tests/test_0833_property_editor_browser.py tests/test_property_navigation_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_required_stars.py -q --tb=short -rs`.
2. `.venv/bin/python -m pytest tests/test_police_letter_parser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_host_i18n.py -q --tb=short -x`.
3. Only with an `app2.css` or template change (the v2 row of the [test-map](../context/test-map.md)): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs`.

Repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`.

CI runs the rest of the host pages row. Two failures are known on clean main and are not yours: `test_host_ux_acceptance.py` (guide page, `cs`, 390 px, a `help-tip-btn`) and `test_reporting_help_0097.py` (a fee help button). Do not fix them; name them in the report if you see them.

## 7. Acceptance

- [ ] The paste, the check-answers block (source and a required "Matches my letter" tick per value), the 400 refusal and a confirmed save all work with Turbo on and with JavaScript off, at 390, 768 and 1280.
- [ ] With no password posted, no police client is built. With one, exactly one is built and it makes read-only calls only, with a plain-words flash.
- [ ] The discard warning shows for unsaved edits or a typed password, cancel keeps the page, and the check-answers page starts dirty.
- [ ] The password and the pasted text never show in the page beyond the source slices.
- [ ] Geometry green. Layout lint green with no new `ALLOW`. Nine screenshots, and one line per width per state in the report. The design-system checklist is ticked.
- [ ] Nothing in "What 1085's fix rounds settled" changed; `test_police_letter_flow.py` is untouched and green.
- [ ] Browser tests 0 skipped. `git diff --stat origin/main` touches only section 3 files. The `app2.css` key is bumped if, and only if, the file changed.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a fix needs a route, flow, copy, JavaScript, `host.css` or parser change, or would undo a point of "What 1085's fix rounds settled" (that goes back to the orchestrator as a new brief); the block does not render under Turbo; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1086-report.md`, 600 tokens at most: files, each command with its last 5 lines, section 7 ticked, one line per screenshot, the layout-lint result per width and state, the design-system checklist, deviations and questions. Set this brief `Status: review`. After the strict fresh Fable review, open one PR. Body:
- the UX-gate lines per width and state
- the ticked checklist
- a link to PR #882 (1085, merged)
- this line: "No new outbound request. 1085 (merged) added the automatic read-only connection test after a confirmed letter save with a typed password; this PR only tests it against a fake client."

Keep the PR a draft until the orchestrator has reviewed it. Merge only with `scripts/merge-pr-on-green.sh`.
