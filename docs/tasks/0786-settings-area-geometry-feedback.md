# 0786 brief: Josef's geometry feedback on the v2 settings area (2026-11-02 12:34)

Status: todo
Executor: Haiku 5.5, alone, on branch `claude/project-thread-vov8xp`. Run after 0785 (browser failures). Josef sees 390 and 1280 screenshots again before merge.

## 1. Objective

Josef's review of the 0780-0784 screenshots (390 px phone), fixed everywhere the same pattern occurs on the settings area pages (`/settings`, `/entities`, `/privacy-requests`, `/settings/archived`), not only where he pointed:

1. **Help `?` sits on its own line under a heading** (Archive, Data protection, Guest form access, and the rest). Put the 24 px round `?` inline, right after the heading text, on the same line (`display:inline-flex`, `vertical-align:middle`, 6-8 px gap). Every `.help-tip` that follows a heading or label.
2. **Text too close to a button.** Data protection: the note after "Delete 0 expired records" starts right beside the button and wraps under it. The note goes on its own line under the button, with a 8-12 px gap. Same for any button followed by inline text.
3. **Text at the card edge.** Activity log: the intro sentence and "Recent activity (1 events)" heading and the filter chips have no side padding, while the rows above have 20-24 px. Give every block inside a `.card` the same side padding as its rows. Check every `details` body and every card section.
4. **Help button label.** The accessible/visible text "Open help" is enough as "Help" ("Nápověda" in Czech); the `?` already says what it is. Change the i18n strings only.
5. **Společnosti (entities) row actions.** Phone card: Edit and Invoice settings buttons and the `⋮` menu are not on one line or not vertically centred; desktop row: `⋮` sits lower than the two buttons. All three on one row, same 36 px height (44 px tap area below 1024), centred on one axis; `⋮` is a 36 px round ghost button.

## 2. Context

CSS rules go in the existing `/* 0780 … */`, `/* 0781 … */` blocks of `App/app/static/app2.css`; generic `.help-tip` placement in `/* v2 ports of shared ui-* classes */`. Tips inside closed `details` stay plain text (0543 rule, `test_help_tip_target_size_and_no_js_reachability`); do not break the help popover rules from 2f54815. Tablet layout: no phone-only rules at 768.

## 3. Files

`App/app/static/app2.css`, `App/app/templates/settings.html`, `entities.html`, `privacy_requests.html`, `settings_archived.html`, `_components.html` (help-tip macro placement only), the i18n file holding the help label, `App/app/templates/base.html` + `App/tests/static_versions.json` (cache key `20261102-0786a`), and a new geometry check in `App/tests/test_0710_v2_mockup_match_browser.py` or a new `App/tests/test_0786_settings_geometry_browser.py`.

## 4. Steps

1. Add a browser test first (red), at 390 and 1280, en and cs, on the four pages: (a) every visible `.help-tip-btn` that follows a heading has its box top within the heading's line box (same line); (b) every visible text block inside a `.card` has left edge >= card left + 16 px; (c) a button's box and the next text block do not share a line (text top >= button bottom + 8); (d) in each entities row the action buttons and `⋮` have centres within 1 px vertically.
2. Fix items 1-5 until the test passes. One commit per item.
3. Cache key bump, `tests/test_static_versions.py --write`.

## 5. Do not touch

`App/app/static/app.js`, Python routes, other pages, mockups.

## 6. Commands

From `App/`: the new test, then
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_help_browser.py tests/test_design_settings.py tests/test_settings_technical.py tests/test_operator_naming.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30`
and the 0783 brief's 0710 and screenshot commands. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5`, `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

All pass, 0 skipped; screenshots at 390 and 1280 for the four pages.

## 8. Stop and ask

A Python or app.js change needed; another test fails; 30 tool calls.

## 9. Report

`docs/tasks/0786-report.md`: commits, counts, screenshot paths.
