# 1086: G6 police letter, part 3 of 3: browser tests, screenshots and the UX gate

Status: todo
Tier: A | Depends on: 1085 (work on top of `claude/1085-police-letter-flow` after its executor commits; rebase this branch on it first) | Base commit: f1ca4288 | Branch: claude/1086-police-letter-ux
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: an extremely strict fresh Fable diff review (owner's words) before the PR opens, on UX, the no-JavaScript flow and filing safety in the browser.
Report: docs/tasks/1086-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) G6, part 3. This brief proves in a real browser that the 1085 flow works and looks right at 390, 768 and 1280 px, with and without JavaScript and under Turbo 8. It takes the screenshots and passes the UX gate (AGENTS rule 10), which 1085's draft PR waits for.

It writes tests and screenshots. The only code changes allowed are fixes in `host.css` and in `_property_editor.html` / `_police_letter_figure.html` for what the layout lint or the screenshots find. The flow logic and the parser stay untouched.

## 2. Context

- **What 1085 built**, in the property editor card `#ubyport`:
  - two folded blocks, `details.police-letter-find` (the SVG figure) and `details.police-letter-paste` (a textarea with `form="police-letter-form"` and a "Read the letter" button)
  - a check-answers card, with a `letter_ok_<field>` box per filled field
  - the paste route `POST /apartments/{id}/police-letter`, which answers 422 with `no-store`
  - refused unconfirmed saves answer 400
  - the automatic test after a save, only when a password was posted
- **Turbo 8** (`base.html:44`) renders a 4xx reply to a form POST in place and ignores a 200. The browser test must check that the check-answers card really appears with JavaScript on (Turbo) and with it off.
- **Mock UbyPort:** use what the existing e2e tests use (`UBYHOST_MOCK_URL`, `config.py:304`, or the monkeypatch pattern in `test_endtoend.py`; grep `test-connection` there and read 40 lines). Never the real police endpoint.
- **Design system:** [design-system](../design/design-system.md) rules 2 (tokens only), 3 (12 px), 4 and 5 (one Save, no lone button), 7 (help under "?"), 8 (no truncated label) and 9 (coral only as a signal). The section 5 checklist goes into the report and the PR.
- **Test letters:** the fake `SAMPLE_*` values from `App/app/ubyport_sample_pdf.py:26-44`. Never real data; screenshots are public.

### Anchors (re-check each with `grep -nF` after the rebase)

1. `App/app/templates/_property_editor.html`: `police-letter-find`, `police-letter-paste`, `id="police-letter-form"` and `letter_ok_` (from 1085). If any is missing: STOP.
2. `App/app/templates/_police_letter_figure.html` exists.
3. `App/tests/test_0833_property_editor_browser.py:7` `from tests.browser_support import chromium_launch_kwargs, settle_motion`, the model for imports and fixtures (read its first 60 lines only).
4. `App/tests/test_layout_lint_browser.py:52` `ALLOW: dict[tuple[str, str], str] = {}`. No new `ALLOW` entry may be added.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_host_police_letter_browser.py` | create | browser, no-JS and geometry tests (step 2) |
| `App/app/static/host.css` | edit, only if step 3 finds something | layout fixes, tokens only; bump the cache key and regenerate `static_versions.json` as in 1085 step 3 |
| `App/app/templates/base.html` | edit, only with a `host.css` change | cache key `?v=20261110-1086` |
| `App/tests/static_versions.json` | regenerate, only with a `host.css` change | `tests/test_static_versions.py --write` |
| `docs/tasks/screenshots-1086/` | create | six PNGs (step 2f) |
| `docs/tasks/1086-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1086 step k`)

1. Rebase on `claude/1085-police-letter-flow` (or on main, if 1085 has merged). Confirm anchors 1 to 4; if one is missing, STOP.
2. Write `test_host_police_letter_browser.py` with `@pytest.mark.parametrize("width", [390, 768, 1280])`:
   a. **Find card:** open the property settings at Reporting & fees and open "Where do I find these?". The SVG is visible and inside the panel, `document.documentElement.scrollWidth <= innerWidth`, and the three numbered lines and the legend are readable (no element narrower than its text).
   b. **Paste with Turbo on:** paste the official-layout letter (title, `Přihlašovací jméno:`, `Přístupové heslo:`, `IDUB:` with the `SAMPLE_*` values) and click "Read the letter". The check-answers card is visible, the IDUB and login inputs hold the values, the short name holds `SAMPLE_ZKRATKA` with the "From the login" line, and the password input is empty. `page.content()` does not contain `SAMPLE_WS_PASSWORD`. The URL and the history stay sane: Back returns to the property page.
   c. **Confirm:** click Save with no tick, and the browser blocks it (`required`). Click "Save and test connection" with no tick (`formnovalidate`): the server answers 400, the card is still there with the error under the box, and the saved row is unchanged (read it through the app's db helper in the test). Tick all, type a password, and Save against the mock UbyPort: the flash reads `letter_test_ok` in words. Save again with all ticks but **no** password: the flash `letter_saved_untested`, and the mock records no call.
   d. **No JavaScript** (`java_script_enabled=False`, as `test_guest_form_input_browser.py:87`): the same paste, the 400 refusal and a confirmed save all work, and the card renders from the 422 reply.
   e. **Geometry** at each width:
      - 12 px or more between the two `details`, the card and the first field
      - no overlap
      - the textarea fills the column below 768 px
      - every checkbox and button has a 44 px touch target on the phone
      - the focus ring is visible on the checkbox after Tab
      - no label is cut off (`scrollWidth <= clientWidth` on each label)
   f. **Screenshots** into `docs/tasks/screenshots-1086/`: `find-{390,768,1280}.png` (the figure open) and `check-{390,768,1280}.png` (the check-answers card). Look at each once, and write one line per file in the report.
3. **UX gate (rule 10):** run `test_layout_lint_browser.py` green, with no new `ALLOW`. Open its 390, 768 and 1280 shots of the property settings page with Reporting open, and write per width what you saw. A finding is fixed in `host.css` or in the two templates (layout only, no flow or copy change), never silenced. Tick the design-system section 5 checklist in the report.
4. Run section 6, then write the report.

## 5. Do not touch

`police_letter.py`, `routes/*`, the flow logic in the templates (the names, hidden inputs, `required` and the `form` attributes), all i18n files, `validation.py`, `reporting.py`, `ubyport/*`, `db.py`, migrations, any dependency, and `test_layout_lint_browser.py`'s `ALLOW`. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`, browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_police_letter_browser.py tests/test_0833_property_editor_browser.py tests/test_property_navigation_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`. Then: `.venv/bin/python -m pytest tests/test_police_letter_flow.py tests/test_police_letter_parser.py tests/test_static_versions.py tests/test_host_i18n.py -q --tb=short -x`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The paste, the check-answers card, the refusal and a confirmed save work with Turbo on and with JavaScript off, at 390, 768 and 1280.
- [ ] With no password posted, the mock records no call. With one, it records exactly one test, with a plain-words flash.
- [ ] The password and the pasted text never show in the page.
- [ ] Geometry green, layout lint green, no new `ALLOW`, six screenshots, the design-system checklist ticked, and one line per width in the report.
- [ ] Browser tests 0 skipped. `git diff --stat` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a fix needs a route, flow, copy or parser change (that goes back to 1085 or 1083); the card does not render under Turbo; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1086-report.md`, 600 tokens at most: files, each command with its last 5 lines, section 7 ticked, one line per screenshot, the layout-lint result per width, the design-system checklist, deviations and questions. Set this brief `Status: review`. After the strict fresh Fable review, open one PR. Body: the UX-gate lines per page and width, the ticked checklist, and a link to 1085's PR. The orchestrator then marks 1085 ready, merges it, and merges this one after a rebase. Merge only with `scripts/merge-pr-on-green.sh`.
