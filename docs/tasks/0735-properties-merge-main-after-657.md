# 0735: properties branch: finish the merge of main (after #657)
Status: todo
Depends on: main 273026f (#657 merged) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
`git merge origin/main` is in progress on this branch with 11 conflicted files. Resolve them, run the checks, and commit the merge. The branch owns the properties list (`apartments.html`) and the property page; main owns the Overview, the menu and the shared shell.

## 2. Rules per file (HEAD = ours, origin/main = theirs)
- `App/app/routes/admin.py`, `App/app/templates/menu.html`: take theirs (`git checkout --theirs <f>`).
- `App/tests/test_host_controls_browser.py`, `App/tests/test_host_wide_geometry_browser.py`: take ours (they measure our `/apartments` and property markup). Read the hunk first; if theirs changes something about another page, keep that part too.
- `scripts/design_lint.py`: ours (the multi-line set that also has `apartments.html`), plus any entry theirs adds.
- `docs/design/catalog.json`: keep every class from both sides, valid JSON (`python3 -m json.tool` it).
- `App/app/static/app2.css` (7 hunks): keep both sides in each hunk, ours first, and remove duplicate lines. Hunk at line ~283 (`.row .t small`): take theirs (it is ours plus the menu-logout rules). Hunk at ~5: ours, then theirs' `.app` gradient line, with `.app` and `.side` only once.
- `App/tests/v2_mockup.py`, `App/tests/test_0710_v2_mockup_match_browser.py` (7 hunks each): keep both sides. Our side adds the `properties` and `property` PAGES entries, overrides and phone checks; theirs adds the Overview ones. Keep each PAGES entry once, and one copy of any helper both sides define (take theirs for the Overview helper, ours for property).
- `App/app/templates/base.html`: app2.css key `?v=20261101-0735`; app.js key `?v=20261101-0735` (both sides changed app.js); host.js keep ours (`0547b`).
- `App/tests/static_versions.json`: take theirs, then regenerate with `.venv/bin/python tests/test_static_versions.py --write` from `App/` after base.html is done.
- After the merge, `grep -n 'initPropertyViews\|initInlineTiming' App/app/static/app.js` must return nothing (main's 0505 may have touched them; if one came back, remove it again and say so).

## 3. Do not touch
Anything that has no conflict. No new code, no new dependency.

## 4. Steps
1. Resolve per section 2. `grep -rn '^<<<<<<<\|^>>>>>>>' App scripts docs/design | head` returns nothing.
2. Run section 5. Fix only merge mistakes (a lost or doubled rule, a broken import).
3. `git add` the 11 files by name, `git commit --no-edit`.

## 5. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_0534_property_page_v2.py tests/test_0541_property_page_phone_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_0503_page_inits_once_browser.py tests/test_0504_mixed_inits_once_browser.py -k "not webkit" -q --tb=line -p no:cacheprovider 2>&1 | tail -12`. Ruff `--select E9,F63,F7,F82,F401,F841` on app tests. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -3`.

## 6. Acceptance
No conflict markers. The commands pass with 0 skipped, apart from failures that also fail on `origin/main` alone or on HEAD before the merge (list them with the failing line).

## 7. Stop and ask
Stop if a hunk changes the same rule in two different ways and neither side is clearly ours or theirs.

## 8. Report
Section "0735" at the end of `docs/tasks/0536-report.md`: per file what you kept, then the test lines. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. Hand back with SubagentHandback; never post to the user.
