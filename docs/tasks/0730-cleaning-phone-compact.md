# 0730: Úklid phone, compact list ("Show N more")
Status: todo
Depends on: 0549b (same branch, pushed) | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

## 1. Objective
Owner 2026-11-01 18:56: "we have to be much more compact with phone". Shared rule (Overview thread): below 1024 px a page shows only what its phone mockup screen shows; the rest stays reachable behind "Show N more". The phone mockup Úklid screen shows "Dnes" and three "Tento týden" rows. So on phone, `/cleaning` shows all of today, the first 3 rows of "This week", and everything else (remaining week rows and the whole "Later" section) inside one closed `<details>` "Show N more" (N = number of hidden cleanings). Desktop (1024 px and up) is unchanged.

## 2. Context
- Phone markup: the `.cleaning-phone` block of `App/app/templates/_cleaning_table.html` (`sections` = list of `(key, items)`, keys `today`, `week`, `later`).
- Existing pattern to copy: `App/app/templates/dashboard.html` line 89, `<details class="needs-you-more ov-section"><summary>{{ tp('needs_you.more', count) }}</summary>` (plural copy `needs_you.more`, `.one`, `.few` in `App/app/host_i18n.py`). Reuse `tp('needs_you.more', n)` if `tp` is available in the cleaning context (grep `_context` in `App/app/routes/cleaning.py` and `cleaning.html` imports); otherwise add cleaning keys `more` cs "Zobrazit další (%(count)s)", en "Show %(count)s more", vi "Xem thêm %(count)s" at the END of the cleaning word lists and format with `|format(count=n)`.
- No JavaScript: `<details>` opens natively.
- The shared `.ph-hide` utility (brief 0722, Overview thread) is not on this branch yet; you do not need it here.

## 3. Files
`App/app/templates/_cleaning_table.html` (phone block only), `App/app/cleaning_i18n.py` + `App/app/host_vi_i18n.py` (only if a new key is needed), the `/* cleaning (0542) */` block at the end of `App/app/static/app2.css` (only for the summary style; + `?v=` key in `base.html`, `tests/static_versions.json` via `--write`), `App/tests/test_0540_cleaning_tables.py` (one new test). Screenshot `docs/tasks/screenshots-0730/`. Report `docs/tasks/0730-report.md`.

## 4. Steps
1. **Markup.** In the phone block: today as now; week: first 3 items as now in `.list`; if more cleanings remain (week items after 3, plus all later items), add `<details class="cleaning-more"><summary class="btn ghost">…Show N more…</summary>` containing the remaining week rows in a `.list`, then the "Later" `.grp` and its `.list`. Without remaining items, no details. Keep row markup identical. Commit `0730 step 1`.
2. **Style.** Summary: full width, min-height 44px, centered, no marker (`list-style:none`, `::-webkit-details-marker{display:none}`), margin-top 8px; if `.btn.ghost` already looks right, add nothing. Only in the cleaning block, below 1024 px. Bump the key, `--write`. Commit `0730 step 2`.
3. **Test.** In `test_0540_cleaning_tables.py` add a test: host with 6 cleanings this week + 1 later → the phone block has exactly 3 `.row` before `<details class="cleaning-more"`, and the summary contains "4" (in cs). Then run `.venv/bin/python -m pytest tests/test_0540_cleaning_tables.py tests/test_cleaning.py tests/test_design_cleaning.py tests/test_static_versions.py -q --tb=line 2>&1 | tail -10` and `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_cleaning_browser.py -k cleaning -q --tb=line 2>&1 | tail -15` (must stay green). Commit `0730 step 3`.
4. **Screenshot.** `UBYHOST_SHOTS_V2=1 UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q 2>&1 | tail -3`, copy `cleaning-390.png` to `docs/tasks/screenshots-0730/`, then `git checkout -- docs/tasks/screenshots-0710 && git clean -fq docs/tasks/screenshots-0710`. Commit `0730 step 4`.

## 5. Do not touch
Shared rules above the cleaning block, desktop tables, `cleaning.html`, the cleaner's shared view (`cleaning_shared.html`, `_cleaning_list.html`), JS, routes, mockups, `v2_mockup.py`. Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` only. Do not push.

## 6. Commands
From `App/` with `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`; then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3`.

## 7. Acceptance
Steps 3 sets green, lint OK, screenshot shows today + 3 week rows + one "Show N more" button above the share bar.

## 8. Stop and ask
Stop if a fix needs a shared rule, JavaScript, or a file outside section 3.

## 9. Report
`docs/tasks/0730-report.md`: Status, tails, screenshot path.
