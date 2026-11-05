# 0958: Correct the calendar record-type appearance

Status: in-progress
Depends on: none (independent B02a) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0958-calendar-type-state
Executor: Haiku 5.5 | Fits one session: 30 tool calls, checkpoint 60k tokens

## 1. Objective

Correct review finding C01: the inactive Stay/Cleaning option looks like the coral primary action, while the active option is pale. Keep the existing correct pressed state and record-creation behaviour; give inactive options a quiet normal/hover appearance.

This is only B02a of the UX plan. G01 guest draft preservation remains high priority and unimplemented. C04/C05/C06, layout changes and every other UX finding stay outside this brief.

## 2. Context

Confirmed in Chromium on the base commit: Add stay had Stay selected semantically, but Cleaning coral; Add cleaning showed the reverse. Existing JS correctly sets aria-pressed and field groups. Do not invert JS state to match the wrong colour.

Exact anchor, App/app/static/dashboard-calendar.css:
```css
.cal-create-types { display:flex; gap:6px; margin:0 0 14px; }
.cal-create-types .btn { min-height:42px; }
.cal-create-types .btn[aria-pressed="true"] { border-color:var(--brand-ink); background:var(--brand-soft); color:var(--ink); font-weight:750; }
```
The approved patch adds only token-based rules for aria-pressed=false. Existing lines 624–626 are inside @media (max-width:767px) and have stronger specificity. They keep the phone switch transparent/white; the added false-state rules address the desktop inactive coral style and do not change the selected rule. Verify 390/768/1280 in Chromium rather than assuming this cascade proves the outcome. No !important or broad override is authorized.

Exact anchor, App/app/templates/_dashboard_calendar.html:
```html
<link rel="stylesheet" href="/static/dashboard-calendar.css?v=20261105-0956e">
```

Exact end-of-file anchor, App/tests/test_dashboard_calendar_browser.py:
```python
        assert not found["touching"], (width, found["touching"][:8])
        context.close()
        browser.close()
```
The supplied patch contains the complete regression test. It uses the existing synthetic calendar fixture, opens both Dashboard and Cleaning, switches types by keyboard, checks semantics/fields/computed appearance and closes without creating a record. It checks 390/768/1280 and EN/CS, saving ten unique reference screenshots. No new dependency.

Pasted rules: use one primary action; preserve visible focus and disabled states; styles use existing tokens. Browser/geometry checks have zero skips; inspect changed-page screenshots yourself. No real customers, messages, payments, filings, provider actions, credentials, production or deletion. No full suite. Do not ask the owner to perform the UX check.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/dashboard-calendar.css | edit | Apply the two rules in the supplied patch only |
| App/app/templates/_dashboard_calendar.html | edit | Bump only this stylesheet's cache key |
| App/tests/test_dashboard_calendar_browser.py | edit | Append the complete supplied test |
| App/tests/static_versions.json | regenerate | Only dashboard-calendar.css version/hash entry changes |
| docs/tasks/0958-calendar-type-state.md | copy/status | This brief; update its status only |
| docs/tasks/0958-calendar-type-state.patch | copy/read | Exact approved implementation patch; do not alter |
| docs/tasks/0958-report.md | create | Executor report, max 600 tokens |

Environment-only: App/.venv may be created from the existing approved dependency files as described below; never stage it. Screenshots go under /tmp/ubyhost-0958, never the public repo. No other files may change.

Also permitted to read: AGENTS.md, docs/context/status.md, docs/context/executor.md, docs/context/test-map.md, App/tests/test_static_versions.py, App/requirements.lock, App/requirements-dev.txt, .github/workflows/ci.yml (dependency/browser setup ranges only), and the four modifiable App files above. The exact brief carries the required design context; do not audit the repo or read the master plan as an extra implementation scope.

## 4. Steps

1. Use your current repository, not any macOS path from the earlier prompt. The upload must contain this brief and 0958-calendar-type-state.patch. Copy only those two files into the current repository's docs/tasks/ if needed; this is permitted bootstrap work, not an App edit. Verify the named base exists and create an isolated worktree there. Preserve current HEAD and all unrelated work.
```sh
git cat-file -t 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 2>&1 | tail -30
git worktree add -b codex/0958-calendar-type-state /tmp/ubyhost-0958-worktree 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 2>&1 | tail -30
cp docs/tasks/0958-calendar-type-state.md docs/tasks/0958-calendar-type-state.patch /tmp/ubyhost-0958-worktree/docs/tasks/ 2>&1 | tail -30
```
Expected: commit type, clean isolated worktree and two delivered files. If branch/path exists, stop rather than deleting or resetting it. Use /tmp/ubyhost-0958-worktree for remaining work; set the copied brief to in-progress. No original checkout is needed.

2. Verify the anchors, then check and apply the supplied exact patch from the new repository root.
```sh
git apply --check docs/tasks/0958-calendar-type-state.patch 2>&1 | tail -30
git apply docs/tasks/0958-calendar-type-state.patch 2>&1 | tail -30
git diff --check 2>&1 | tail -30
```
Expected: patch applies without fuzz/errors and whitespace check is clean. Never substitute a guessed selector or broad CSS fix. Commit only these source/test changes and the copied brief/patch using message `0958 step 1`, ending with `Co-authored-by: Codex <noreply@openai.com>`.

3. From the isolated worktree's App directory, reuse its .venv if present. Otherwise create an isolated environment and install the repository's existing approved dependencies using the CI recipe. These are environment setup commands, not permission to add/change dependencies or lockfiles. Python 3.12 is the CI version; use the available compatible Python and report its version. If installation fails, report the concrete blocker; do not alter pins or invent another package source.
```sh
python3 --version 2>&1 | tail -30
python3 -m venv .venv 2>&1 | tail -30
.venv/bin/python -m pip install --require-hashes -r requirements.lock 2>&1 | tail -30
.venv/bin/python -m pip install -r requirements-dev.txt playwright==1.63.0 2>&1 | tail -30
.venv/bin/python -m playwright install chromium 2>&1 | tail -30
```
Run creation/install only when the needed environment is absent. If Chromium reports missing OS libraries, use the repository/CI-supported Playwright install-deps chromium only if the environment permits it; otherwise report that limitation. Do not bypass permissions or change system settings. No speculative packages are authorized. Regenerate the manifest after the cache-key bump and confirm its diff concerns only dashboard-calendar.css.

```sh
.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30
git diff -- tests/static_versions.json 2>&1 | tail -30
```
Expected: only the CSS version/hash record changes. Commit the manifest as `0958 step 2`, with the Codex trailer.

4. Run section 6's scoped checks. Inspect the saved screenshots for both changed surfaces and types; report actual appearance at each width. In Chromium, also confirm the selected cue, inactive hover, visible keyboard focus and Escape cancellation. No live integration is needed. Do not retake reference screenshots repeatedly or change the unrelated Cancel/label/dialog layout problems.

5. Write the report, mark review if checks passed or blocked with the reason otherwise, and commit only the brief/report status. No push, merge or deployment. Hand branch, report, screenshots and exact owner publication commands to the owner; do not promise a PR exists if you could not create one within executor permissions.

## 5. Do not touch

Do not change dashboard-calendar.js, field values, submit labels, record type/state, endpoints, dates, occupancy, booking spans, cleaning logic, guest draft logic, filing, fee/payment behaviour, auth, legal text, dependencies or any other page style. No production, sharing or irreversible actions. G01 is not resolved by this task.

## 6. Commands

Run from App, with UBYHOST_REQUIRE_BROWSER=1 and UBYHOST_SHOTS_DIR=/tmp/ubyhost-0958. The following are the affected test-map rows, not the full suite. Keep the environment variables on each browser invocation. If any glob has no matches, report it; do not guess replacement tests.
```sh
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-0958 .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_feed_*.py tests/test_dashboard_calendar*.py tests/test_calendar_*.py tests/test_sample_calendar.py -q --tb=short -x -rs 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-0958 .venv/bin/python -m pytest tests/test_cleaning*.py -q --tb=short -x -rs 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-0958 .venv/bin/python -m pytest tests/test_host_*.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30
```
Expected: relevant checks pass; browser/geometry checks show zero skipped, host layout lint zero findings. The new regression must run, not skip. Inspect calendar-0958-* images and layout-lint Dashboard/Cleaning images at 390/768/1280. Describe what you saw; no WCAG/contrast compliance claim without measurement.

From repository root:
```sh
python3 scripts/context_lint.py | tail -30
git diff --check 2>&1 | tail -30
git diff --name-only 2>&1 | tail -30
```
Expected: no new context errors; clean whitespace; only allowlisted files. Existing unrelated context warnings must be identified as such.

## 7. Acceptance

- [ ] In both launch contexts, the chosen type is visually selected and aria-pressed=true; the inactive type is quiet and not styled like Create.
- [ ] Both directions work by keyboard and pointer; fields and selected semantics agree.
- [ ] Inactive hover, focus-visible and disabled styling remain usable.
- [ ] EN/CS and 390/768/1280 regression cases pass; both type states have visual references, including one 390 px image per changed page.
- [ ] Escape cancels; the new test submits nothing. Existing record-creation regressions still pass.
- [ ] Browser/geometry checks have zero skips; required host layout lint has zero findings.
- [ ] Only the named files changed; no JS/state/record/production changes; manifest matches the new CSS key.
- [ ] Report states G01 and the rest of B02 remain queued, with no claim that the whole UX plan is complete.

## 8. Stop and ask

Stop and report if an anchor or base is missing, a selector/fixture no longer applies, the patch does not apply, an extra file/changed patch/dependency is needed, the environment cannot run required browser checks, the same check fails twice, or the checkpoint is reached. Do not make independent fixes. At 25 calls or about 50k tokens, finish only the current step, commit it and report blocked with Done/Left steps; hard stop at 30 calls/100k.

## 9. Report

Write docs/tasks/0958-report.md, at most 600 tokens: status; branch/base; changed files; each command with its last five lines and explicit pass/fail/skip count; acceptance checklist; Dashboard and Cleaning screenshot observations at 390/768/1280; deviations; synthetic-data/reset status; Done/Left steps; owner actions.

State that G01 and C04/C05/C06 remain queued. Keep screenshots and synthetic links outside the public repo. If all checks pass, set this brief to review and hand over the branch/report; otherwise set blocked with the concrete reason. No push, merge, production action or claim of a completed PR without evidence.

Ordering: this patch is anchored after the changes already present at the named base. Do not run alongside another brief changing the CSS, partial or browser test. If another task changes an anchor first, stop for a refreshed brief rather than resolving overlaps independently.
