# 0175: old Invoices icon and name, a border on every pill

Status: todo
Depends on: 0174 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Owner requests (verbatim): "i dont like the invoices logo, give it the old one, name it invoices and stay fee" and "give some borders to the pills, it looks really weird without one, actually all of the pills with this current open design look weird".

1. The sidebar and phone More-sheet entry for Invoices uses the icon it had before the redesign, and reads "Invoices and stay fees" (Czech: "Faktury a poplatky z pobytu").
2. Every pill/badge gets a 1 px border in its own tone colour.

## 2. Context

The entry is `('/invoices', 'receipt', t('nav.invoices'), ...)` in `App/app/templates/_shell_sidebar.html` line 18 and the More sheet in `_shell_tabbar.html` line 19. Icons are inline SVG paths in `App/app/templates/_icons.html` (`icon('name', size)`). The old icon: find the pre-redesign sidebar with `git log --format='%h %s' -S'href="/invoices"' -- App/app/templates | tail -5`, then `git show <oldest commit that has a sidebar>:<template path> | grep -n -i invoices | cut -c1-300` and read which icon or glyph it used for Invoices (it may be a different Lucide-style name such as `file-text`, `banknote`, or an emoji). If that name already exists in `_icons.html`, use it; if the old one was an inline SVG, add its paths to `_icons.html` under a new name. If you cannot find a pre-redesign icon after five attempts, stop and report the candidates you found.

Badges are `.ui-badge` in `App/app/static/host2.css` lines 53-59 (`ui-badge-action`, `-attention`, `-done`, `-neutral` with tokens `--st-<tone>-bg/-ink/-dot`; `-overdue` already has `border: 1px solid var(--st-action-dot)`). S1 lint forbids raw colours; S2 forbids bare px in margin, padding, gap and font-size (a `1px` border is fine, as the existing line does).

## 3. Files

`App/app/templates/_shell_sidebar.html`, `_shell_tabbar.html`, `_icons.html` (only if a new icon is needed), `App/app/host_i18n.py` (new key `nav.invoices_fees` in both language blocks, next to `nav.invoices`), `App/app/static/host2.css` (append), `App/app/templates/base.html` (host2.css key), `App/tests/static_versions.json`, tests that assert the sidebar label (`grep -rn "nav.invoices\|>Invoices<\|\"Invoices\"" App/tests/*.py | cut -c1-160 | head`), `docs/tasks/0175-*`.

## 4. Steps

1. Find the old icon (section 2) and note it in the report.
2. Add `"nav.invoices_fees": "Invoices and stay fees"` and the Czech `"Faktury a poplatky z pobytu"`. In `_shell_sidebar.html` line 18 and `_shell_tabbar.html` line 19 use the old icon and `t('nav.invoices_fees')`. Keep `nav.invoices` for the page titles and tabs. Check the label fits the sidebar at 1280 px open and the 1024 px auto-collapsed rail (the collapsed rail shows icons only; the label stays in the tooltip/aria-label).
3. Append to `host2.css`: `/* 0175 */ .host-workspace .ui-badge { border: 1px solid var(--ui-dot); }` plus, for each tone, make the border use the tone dot colour (the `--ui-dot` custom property is already set per tone). Keep `-overdue` as it is. Check the badge height still equals `--badge-h` (use `box-sizing: border-box`; if the height grows, reduce nothing, report it). Also give the neutral tone a border that is visible on its background (`var(--st-neutral-dot)`). Run `python3 scripts/design_lint.py 2>&1 | tail -2` from the repo root. Expected: OK.
4. Bump the host2.css key in `base.html` to one ending `-0175` and run from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
5. Fix any test that asserted the old sidebar label (edit only that string). From `App/` run the sidebar and shell tests: `.venv/bin/python -m pytest tests/test_design_shell.py tests/test_host_redesign.py tests/test_host_i18n.py -q --tb=short 2>&1 | tail -6`.
6. Browser tests (foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`): `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_host_controls_browser.py -q -rs 2>&1 | tail -8`. Then from the repo root: `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused). Expected: all passed, 0 skipped; the a11y contrast check must still pass with the borders.
7. One 390 px screenshot of `/reservations` and the open More sheet: run from `App/`: `.venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app $PWD --out docs/tasks/0175-screenshots --pages "/reservations,/invoices" --widths 390,1280 2>&1 | tail -3`.
8. Commit: `git add App docs/tasks/0175-* && git commit` with message "0175: old Invoices icon, name with stay fees, borders on pills" and the two trailers given by the orchestrator.

## 5. Do not touch

Page titles, tabs, any other i18n key; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Sidebar and More sheet show the old icon and "Invoices and stay fees"; all pills have a border; tests pass with 0 skipped.

## 8. Stop and ask

The old icon cannot be found, or a test fails twice.

## 9. Report

`docs/tasks/0175-report.md`, short; `Status: review`.
