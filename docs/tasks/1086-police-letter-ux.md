# 1086: G6 police letter, part 3 of 3: browser tests, screenshots and the UX gate

Status: todo
Tier: A | Depends on: 1085 (merged to main as PR #882, `a166812a`; merge `origin/main` into this branch first) | Base commit: a166812a | Branch: claude/1086-police-letter-ux
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: an extremely strict fresh Fable diff review (owner's words) before the PR opens, on UX, the no-JavaScript flow and filing safety in the browser.
Report: docs/tasks/1086-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) G6, part 3. This brief proves in a real browser that the 1085 flow works and looks right at 390, 768 and 1280 px, with and without JavaScript and under Turbo 8. It takes the screenshots and passes the UX gate (AGENTS rules 7 and 10) for the whole flow.

1085 is merged and live. It already passed its own UX gate over four fix rounds and has one browser test (context below). This brief adds the full-flow browser file; it does not redo or change what 1085 settled.

It writes tests and screenshots. The only code changes allowed are layout fixes in `App/app/static/app2.css` (under `body.v2`) and in `_property_editor.html` / `_police_letter_figure.html` for what the layout lint or the screenshots find. The flow logic, the parser, `app.js` and `host.css` stay untouched.

## 2. Context

- **What 1085 built**, in the property editor card `#ubyport`:
  - two folded blocks, `details.police-letter-find` (the SVG figure) and `details.police-letter-paste` (a textarea with `form="police-letter-form"` and a "Read the letter" button)
  - a check-answers block `#police-letter-check`: one `.police-letter-row` per field, and per filled field a `required` tick `letter_ok_<field>` in a `div.checkline` whose label carries the `req-star`
  - the paste route `POST /apartments/{id}/police-letter`, which answers 422 with `no-store`
  - refused unconfirmed saves answer 400 (Save, and the "Test connection" button, which posts to `/test-connection` with `formnovalidate`)
  - the automatic test after a save, only when a password was posted
- **What 1085's fix rounds settled. Do not undo any of it:**
  - Every helper rule lives in `App/app/static/app2.css` under `body.v2` (lines 3435-3470; the editor is a v2 page). `host.css` has no police-letter rule.
  - The two `details` are plain disclosure rows: no box, no gap between them, a 1 px `--line` rule, summaries 44 px high, flush with their content.
  - `letter_text` has `form="police-letter-form"`, so Save never sends it.
  - The legend note and the "Saved now" line use `police-letter-note` (`--ink-secondary`, for contrast). Never `muted`.
  - After "Read the letter", `initPoliceLetterForm` (`app.js:2286`) scrolls `#police-letter-check` or `#letter_text-error` into view; with no JavaScript the first unticked box (or the textarea, on an error) has `autofocus`. After a paste the editor starts on `sec-police` (`data-start-section`).
  - The tick label has `margin:0`; box and text are centred within 2 px.
  - Keys on main: `app2.css?v=20261110-1085i`, `app.js?v=20261110-1085b`.
- **1085's browser test** `test_the_letter_helper_is_styled_in_the_browser` (`App/tests/test_police_letter_flow.py:916`) already asserts the figure styling, the disclosure rows, the 422 and 400 replies, the landing in the viewport and the tick alignment at 390, 768 and 1280. It is the model for the server thread, the session cookie and the page URL (read lines 916-965 only). Do not copy its assertions and do not edit it.
- **Turbo 8** (`base.html:44`) renders a 4xx reply to a form POST in place and ignores a 200. The browser test must check that the check-answers block really appears with JavaScript on (Turbo) and with it off.
- **Mock UbyPort:** the `fake_client` and `no_client` fixtures in `App/tests/test_police_letter_flow.py:190-214` (they monkeypatch `reporting.client_for`; the browser test runs the app in a thread of the same process, so they apply). `fake_client["made"]` lists the clients built and each client's `.calls`. Never the real police endpoint.
- **Design system:** [design-system](../design/design-system.md) rules 2 (tokens only), 3 (12 px), 4 and 5 (one Save, no lone button), 7 (help under "?"), 8 (no truncated label) and 9 (coral only as a signal). The section 5 checklist goes into the report and the PR.
- **Test letters:** `LETTER` in `App/tests/test_police_letter_flow.py:38`, built from the fake `SAMPLE_*` values in `App/app/ubyport_sample_pdf.py:26-44`. Never real data; screenshots are public.

### Anchors (re-check each with `grep -nF` after merging `origin/main`)

1. `App/app/templates/_property_editor.html`: `police-letter-find` (312), `police-letter-paste` (316), `id="letter_text"` with `form="police-letter-form"` (320), `id="police-letter-check"` (328), `letter_ok_` (343), `formaction="{{ base_url }}/test-connection"` (382) and `id="police-letter-form"` (474). If any is missing: STOP.
2. `App/app/templates/_police_letter_figure.html` exists.
3. `App/tests/test_police_letter_flow.py`: `def host` (153), `def fake_client` (191), `def no_client` (205), `LETTER = (` (38) and `def test_the_letter_helper_is_styled_in_the_browser` (916). Import the three fixtures and `LETTER` from there (`from tests.test_police_letter_flow import ...  # noqa: F401`, as `test_0833_property_editor_browser.py:8` does for its fixtures).
4. `App/tests/test_layout_lint_browser.py:53` `ALLOW: dict[tuple[str, str], str] = {}`. Two old entries follow on lines 55-56. No new `ALLOW` entry may be added.
5. `App/app/static/app2.css:3435` `body.v2 details.police-letter-find,` and `App/app/templates/base.html:23` `app2.css?v=20261110-1085i`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_host_police_letter_browser.py` | create | browser, no-JS and geometry tests (step 2) |
| `App/app/static/app2.css` | edit, only if step 2 or 3 finds something | layout fixes in the `body.v2 .police-letter-*` block (3435-3470), tokens only, every selector under `body.v2` |
| `App/app/templates/_property_editor.html`, `App/app/templates/_police_letter_figure.html` | edit, only if step 2 or 3 finds something | layout only (a class or a wrapper); no name, `required`, `form`, `autofocus`, hidden input or copy change |
| `App/app/templates/base.html` | edit, only with an `app2.css` change | line 23: `app2.css?v=20261110-1085i` becomes `app2.css?v=20261110-1086a` (a second change: `1086b`). No other key changes. |
| `App/tests/static_versions.json` | regenerate, only with an `app2.css` change | from `App/`: `.venv/bin/python tests/test_static_versions.py --write` |
| `docs/tasks/screenshots-1086/` | create | six PNGs (step 2f) |
| `docs/tasks/1086-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1086 step k`)

1. `git fetch origin main` and `git merge origin/main` into this branch (1085 is in main). Confirm anchors 1 to 5; if one is missing, STOP.
2. Write `test_host_police_letter_browser.py` with `@pytest.mark.parametrize("width", [390, 768, 1280])`. Import playwright as the model test does (plain import when `UBYHOST_REQUIRE_BROWSER=1`, else `importorskip`). Page URL: `/apartments/{id}?view=settings&section=reporting#ubyport`.
   a. **Find card:** open the property settings at Reporting & fees and open "Where do I find these?". The SVG is visible and inside the panel, `document.documentElement.scrollWidth <= innerWidth`, and the three numbered lines and the legend are readable (no element narrower than its text).
   b. **Paste with Turbo on:** paste the official-layout letter (title, `Přihlašovací jméno:`, `Přístupové heslo:`, `IDUB:` with the `SAMPLE_*` values) and click "Read the letter". The check-answers block `#police-letter-check` is visible and inside the viewport, the IDUB and login inputs hold the values, the short name holds `SAMPLE_ZKRATKA` with the "From the login" line, and the password input is empty. `page.content()` does not contain `SAMPLE_WS_PASSWORD`. The URL and the history stay sane: Back returns to the property page.
   c. **Confirm:** click Save with no tick, and the browser blocks it (`required`). Click "Test connection" (`formaction=".../test-connection"`, `formnovalidate`) with no tick: the server answers 400, the block is still there with one error under each unticked box, and the saved row is unchanged (read it through the app's db helper in the test). Tick all, type a password, and Save with `fake_client`: the flash is the `flash.apartments.letter_test_ok` text, and `fake_client["made"]` holds exactly one client. Paste again, tick all and Save with **no** password: the flash is the `flash.apartments.letter_saved_untested` text, and no further client was built.
   d. **No JavaScript** (`java_script_enabled=False`, as `test_guest_form_input_browser.py:91`): the same paste, the 400 refusal and a confirmed save all work, the block renders from the 422 reply, and the first unticked box has the focus (`autofocus`).
   e. **Geometry** at each width:
      - 12 px or more between the "Read the letter" button and what follows it, and between the check block and the first field (`#uby_idub`). The two `details` themselves stay flush rows (1085); do not add a gap between them.
      - no overlap
      - the textarea fills the column below 768 px
      - every tick row (`.checkline` label), summary and button has a 44 px touch target on the phone (the box itself is 20 x 20 by design)
      - the focus ring is visible on the checkbox after Tab
      - no label is cut off (`scrollWidth <= clientWidth` on each label)
   f. **Screenshots** into `docs/tasks/screenshots-1086/`: `find-{390,768,1280}.png` (the figure open) and `check-{390,768,1280}.png` (the check-answers block). Take them as the model test's `shot` helper does (`page.locator("#ubyport").screenshot`). Look at each once, and write one line per file in the report.
3. **UX gate (rules 7 and 10, [steps](../context/workflow.md#ux-gate)):** from `App/` run `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`: green, 0 skipped, no new `ALLOW`. Then `ls /tmp/shots/layout-lint | grep -i propert | head -50` and open the 390, 768 and 1280 shots of the property settings page, plain and `+open` (the `+open` shots have the two `details` open). Write per width what you saw. A finding is fixed in `app2.css` or in the two templates (layout only, no flow or copy change), never silenced, and never by undoing a 1085 point from section 2. Tick the design-system section 5 checklist in the report.
4. Run section 6, then write the report.

## 5. Do not touch

`police_letter.py`, `routes/*`, `App/app/static/app.js` and its key, `host.css`, `App/tests/test_police_letter_flow.py`, the flow logic in the templates (the names, hidden inputs, `required`, `autofocus`, the `form` attributes and `data-start-section`), the `req-star` and `police-letter-note` classes, all i18n files, `validation.py`, `reporting.py`, `ubyport/*`, `db.py`, migrations, any dependency, and `test_layout_lint_browser.py`'s `ALLOW`. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

No full suite. From `App/`:

1. Browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_host_police_letter_browser.py tests/test_police_letter_flow.py tests/test_0833_property_editor_browser.py tests/test_property_navigation_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_required_stars.py -q --tb=short -rs`.
2. `.venv/bin/python -m pytest tests/test_police_letter_parser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_host_i18n.py -q --tb=short -x`.
3. Only with an `app2.css` or template change (v2 row of the [test-map](../context/test-map.md)): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs`.

Repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`.

CI runs the rest of the host pages row. Two failures are known on clean main and are not yours: `test_host_ux_acceptance.py` (guide page, `cs`, 390 px, a `help-tip-btn`) and `test_reporting_help_0097.py` (a fee help button). Do not fix them; name them in the report if you see them.

## 7. Acceptance

- [ ] The paste, the check-answers block, the refusal and a confirmed save work with Turbo on and with JavaScript off, at 390, 768 and 1280.
- [ ] With no password posted, no police client is built. With one, exactly one is built and it calls only read-only methods, with a plain-words flash.
- [ ] The password and the pasted text never show in the page.
- [ ] Geometry green, layout lint green, no new `ALLOW`, six screenshots, the design-system checklist ticked, and one line per width in the report.
- [ ] Nothing from section 2 "What 1085's fix rounds settled" changed; `test_police_letter_flow.py` is untouched and green.
- [ ] Browser tests 0 skipped. `git diff --stat origin/main` touches only section 3 files. `app2.css` key bumped if, and only if, the file changed.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a fix needs a route, flow, copy, parser, `app.js` or `host.css` change, or would undo a 1085 point from section 2 (that goes back to the orchestrator as a new brief); the block does not render under Turbo; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1086-report.md`, 600 tokens at most: files, each command with its last 5 lines, section 7 ticked, one line per screenshot, the layout-lint result per width, the design-system checklist, deviations and questions. Set this brief `Status: review`. After the strict fresh Fable review, open one PR. Body: the UX-gate lines per page and width ("390: ...; 768: ...; 1280: ..."), the ticked checklist, the six screenshots, and a link to PR #882 (1085, merged). Keep it a draft until the orchestrator has reviewed it. Merge only with `scripts/merge-pr-on-green.sh`.
