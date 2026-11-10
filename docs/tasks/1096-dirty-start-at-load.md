# 1096: a form that starts dirty shows the Save row and the leave warning at load

Status: todo
Tier: C | Depends on: 1086 (merged in #892, `30a2ef45`) | Base: origin/main | Branch: claude/1096-dirty-start
Executor: Sonnet (Tier C, effort medium) | Attempts: 3 at most | Fits one session: stop at 30 tool calls (section 8); reads stay at 150 lines or fewer
Review: the orchestrator checks the diff and the screenshots before the PR opens.
Report: docs/tasks/1096-report.md

## 1. Objective

Found in the review of PR #892. `initUnsavedForms` in `App/app/static/app.js` sets `form._ubyBase` but never calls `recomputeDirty`, which runs only on `input` and `change`. A form rendered with `data-dirty-start="1"` therefore shows no Save row and gives no leave warning until the first input event. The police letter check-answers page is the case that matters: the host must tick "Matches my letter", but nothing says the page holds unsaved work until they do.

The fix is one line: call `recomputeDirty(form);` right after `form._ubyBase = formSnapshot(form);`. `initUnsavedDialog` runs later (`initUnsavedForms();` is called at about line 2829, the dialog init after it) and syncs the Save bar from `data-dirty`. Nothing else in app.js changes.

## 2. Context

- `recomputeDirty` (app.js ~2230) returns early while `_ubyBase` is unset, then sets `data-dirty="1"` when `data-dirty-start="1"` is present or the snapshot differs. The `beforeunload` handler (~2271) warns when any `form[data-unsaved-guard]` has `data-dirty="1"`.
- **Every `data-dirty-start` user** (grep of `App/app/templates` on origin/main; re-check with `grep -rn 'data-dirty-start' App/app/templates`):
  1. `App/app/templates/_property_editor.html:139`, `#property-settings-form`: `{% if operator_error or letter_check %} data-dirty-start="1"{% endif %}`. It covers two states:
     - `letter_check`: the police letter check-answers page (the target of this fix).
     - `operator_error`: a refused save from `admin.py` (`_property_operator_error`, for example `flash.error.no_such_controller`) and the onboarding wizard refusal (`refuse_setup_save`). The page holds the posted values, so it must also start dirty. This is the same intent, so the fix must show the Save row there too, with no regression: the "Cancel" link reloads the saved page (app.js ~2495 sets `_ubySubmitting` for `data-dirty-start`), and `discard` (~2466) keeps `_ubyBase` for these forms.
  2. No other template sets it. The two other app.js lines that read the attribute (~2466, ~2495) are the Cancel handling above.
- Forms with `data-unsaved-guard` and no `data-dirty-start` are unaffected: the new call runs in the same synchronous tick as the line that sets `_ubyBase`, so the two `formSnapshot` results are equal (autofill or a widget cannot run between them), and `recomputeDirty` removes `data-dirty` (already absent). The call sits after the `claimNode` return, so a second `initPage` does not repeat it.
- **Two wanted side effects on a `data-dirty-start` page, with no input** (both read `data-dirty`; do not "fix" them, name them in the report and the PR body):
  1. `initPoliceLetterForm` (app.js ~2299): "Read the letter" pressed again on the check-answers page now asks `police_letter.discard_warning` first.
  2. `initUnsavedDialog`: an in-app link asks before leaving, and `syncResetButtons` adds `is-dirty` to the Save row (`app2.css` ~2807 hides `.savebar[data-for="property-settings-form"]:not(.is-dirty)`).
  If an existing test fails only because of one of these (it reads the letter twice, or follows a link from a refused-save page, with no input): STOP and report; do not edit that test.
- Out of scope: a refused save that sets no `operator_error` (an address or time error alone) does not get `data-dirty-start`; leave it.
- The existing test `test_the_check_answers_page_starts_dirty_and_warns_on_leaving` (`App/tests/test_host_police_letter_guard_browser.py:88`) ticks a box first, which is why it never caught this. Do not edit it.

### Anchors (re-check each with `grep -nF`; if one is missing: STOP)

1. `App/app/static/app.js`: `form._ubyBase = formSnapshot(form);` inside `initUnsavedForms` (about line 2241), and `function recomputeDirty` (about 2230).
2. `App/app/templates/base.html` line 47: `app.js?v=20261110-1085b`.
3. `App/tests/test_host_police_letter_guard_browser.py`: imports `READ_BUTTON, en, live` from `tests.test_host_police_letter_browser` and `LETTER, fake_client, host, no_client` from `tests.test_police_letter_flow`; helper `_open(live, answers)` at line 23.
4. `App/tests/test_static_versions.py` (`--write` regenerates `App/tests/static_versions.json`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app.js` | edit | add `recomputeDirty(form);` after `form._ubyBase = formSnapshot(form);` (anchor 1). Nothing else. |
| `App/app/templates/base.html` | edit | line 47: `app.js?v=20261110-1085b` becomes `app.js?v=20261110-1096a`. No other key changes. |
| `App/tests/static_versions.json` | regenerate | from `App/`: `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_host_police_letter_guard_browser.py` | edit | add the test of step 2 (append; keep the existing tests) |
| `docs/tasks/screenshots-1096/` | create | the six PNGs of step 4 |
| `docs/tasks/1096-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1096 step k`)

1. `git fetch origin main`, `git merge origin/main` if behind. Confirm anchors 1 to 4. Write the test of step 2 **first** and run it once (`UBYHOST_REQUIRE_BROWSER=1`, that one test): it must fail on the `data-dirty` wait. Paste that failure line in the report. Then make the app.js edit, bump the key in base.html, and regenerate the json (bump first: `--write` refuses a changed file under an unchanged key).
2. Add `test_the_check_answers_page_shows_the_save_row_and_warns_with_no_input` to the guard test file (width 1280, `live`, `no_client`, same imports):
   - Reuse `_open(live, [False])`, click `READ_BUTTON` and wait for `#police-letter-check`, exactly as the existing test does.
   - Do **not** tick, type or focus anything. Assert at once: `#property-settings-form` has `data-dirty="1"` (use `page.wait_for_function`, not a fixed sleep), and the Save row `.savebar[data-for='property-settings-form']` is visible (`is_visible()`).
   - Chromium only shows the `beforeunload` prompt on a page the user has touched (the existing test says so), so after the two asserts above do one click on text that is not a control: `page.locator("#police-letter-check .police-letter-check-title").click()` (the `h3`; not a label, link or field, and not `page.mouse.click(5, 5)`, which can hit the header). Assert `data-dirty` is still `"1"` and no dialog was recorded.
   - Then `with page.expect_event("dialog"): page.close(run_before_unload=True)` (`_open(live, [False])` so the prompt is dismissed), and assert the recorded dialog kinds are `["beforeunload"]` and the page is still open.
   - Also assert a clean page stays clean: open the editor with no letter read (`live.url`), and `data-dirty` is absent and the Save row is hidden.
3. `operator_error` check (no new brief needed, a short test in the same file or in `test_host_unsaved_changes_browser.py`, your choice): trigger a refused save that sets `operator_error` (grep `no_such_controller` in `App/tests` for an existing way to post it), and assert on the rendered page with no input: `data-dirty-start="1"`, `data-dirty="1"`, Save row visible, and the Cancel link reloads the saved page without a leave dialog (`_ubySubmitting`). If posting the refusal in a browser test takes more than 5 tool calls, drop it, run `test_0833_property_editor_browser.py` and `test_host_unsaved_changes_browser.py`, and say in the report that the `operator_error` path is covered by those only.
4. **UX gate (AGENTS rules 7 and 10; steps in [workflow](../context/workflow.md#ux-gate)):**
   - From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30`: green, 0 skipped, zero findings on host pages, no new `ALLOW`.
   - Open the lint's own property-editor screenshots, `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` (`ls /tmp/shots/layout-lint | grep -i prop | head -50`): they show the clean page, so the Save row must **not** be there.
   - Take `docs/tasks/screenshots-1096/check-{390,768,1280}.png` of the page at load in the check-answers state (the Save row now visible, nothing touched), full page, from your new test or a throwaway script. Open each once.
   - In the report and the PR body, one line per page in the form "390: ...; 768: ...; 1280: ...": what you saw (Save row visible and not covering the first unticked box or a field; no sideways scroll; touch targets 44 px on the phone). If the new Save row overlaps content at load, STOP and report (a layout fix is a new brief).
   - Tick the [design-system checklist](../design/design-system.md) in the report.
5. Run section 6, write the report, set this brief `Status: review`.

## 5. Do not touch

Any other line of `app.js`, `host.css`, `app2.css`, templates other than the `base.html` key, routes, i18n, the existing tests, `ALLOW` in `test_layout_lint_browser.py`, any dependency, `main`.

## 6. Commands (each ends `2>&1 | tail -30`; from `App/`; no full suite)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_police_letter_guard_browser.py tests/test_host_police_letter_browser.py tests/test_0833_property_editor_browser.py tests/test_host_unsaved_changes_browser.py tests/test_0851_savebar_browser.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py tests/test_host_geometry.py -q --tb=short -rs`: 0 skipped.
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x`.
3. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

(test-map rows used: static files and cache keys; host pages geometry; any host template, CSS or JS.) CI runs the rest. Two failures are known on clean main and are not yours: `test_host_ux_acceptance.py` (guide page, `cs`, 390 px, a `help-tip-btn`) and `test_reporting_help_0097.py`.

## 7. Acceptance

- [ ] At load of the check-answers page, with no input, `data-dirty="1"`, the Save row is visible and `beforeunload` warns (new test green, and seen red before the app.js edit).
- [ ] A page with no letter read is still clean at load (no Save row, no warning).
- [ ] `operator_error` pages still start dirty, Cancel still reloads the saved page, and the other `data-unsaved-guard` forms are unchanged (named suites green).
- [ ] `app.js?v=20261110-1096a`, `static_versions.json` regenerated, `test_static_versions.py` and `test_wp07_cache_heartbeats.py` green.
- [ ] Browser tests 0 skipped, layout lint green with no new `ALLOW`, three screenshots with one line each in the report, checklist ticked.
- [ ] `git diff --stat origin/main` shows only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the fix needs more than the one line; the Save row at load overlaps content; a browser test skips; a test fails twice on the same cause; 30 tool calls (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1096-report.md`, 400 tokens at most: files, each command with its last 5 lines, section 7 ticked, one line per screenshot, the design-system checklist, deviations. PR body: the UX-gate lines per width, the ticked checklist, a link to PR #892, and this line: "No new outbound request, no new personal data." Keep the PR a draft until the orchestrator has reviewed it. Merge only with `scripts/merge-pr-on-green.sh`.
