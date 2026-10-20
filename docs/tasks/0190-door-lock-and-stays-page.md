# 0190: Door lock account on Properties, stays list at 5 per page

Status: review
Depends on: none | Base commit: see git log | Branch: claude/project-thread-3xqb0b
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner request (Josef, 2026-10-20): the "Door lock account" tab on the Properties tab strip goes away. The lock account is a section on the Properties page itself. The stays list shows 5 stays per page instead of 15.

## 2. Context

- `App/app/templating.py`: the properties tab strip added `("lock", "/smart-locks", "properties.shared.lock")` when `ttlock.enabled()`; `nav == "smart_locks"` picked that tab.
- `App/app/routes/admin.py`: `/smart-locks` GET rendered `smart_locks.html`; POST routes (`/smart-locks/setup`, `/refresh`, `/remove`) redirect back through `_smart_locks_url`. `RESERVATION_PAGE_SIZE` sets the stays page size.
- The old page template `smart_locks.html` held the lock body. Its body now lives in `_smart_locks_panel.html`, included by `apartments.html`.
- Section ids kept: `smart-locks-how`, `smart-locks-setup`, `smart-locks-share`, `smart-locks-add-more`, `smart-locks-list`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templating.py | edit | remove the lock tab and the `smart_locks` tab branch |
| App/app/routes/admin.py | edit | `_smart_lock_panel_context()`; `/smart-locks` GET 303 to `/apartments#...`; `_smart_locks_url` returns `/apartments#anchor` (keeps `/smart-locks?return_to=/apartments/...` for property return paths); `RESERVATION_PAGE_SIZE = 5` |
| App/app/templates/apartments.html | edit | heading, lede and include of the panel, after the property list |
| App/app/templates/_smart_locks_panel.html | new (moved from smart_locks.html) | lock body, unchanged except the `cta` set |
| App/app/templates/smart_locks.html | delete | replaced by the partial |
| App/tests/test_design_admin.py, test_smart_locks_page.py, test_host_properties_navigation.py, test_host_list_page_layout_browser.py, test_lock_navigation_browser.py | edit | assert the Properties page and the new redirect targets |

No CSS, base.html or static_versions.json change (another executor owns them).

## 4. Steps

1. Create `_smart_locks_panel.html` from `smart_locks.html` lines 11-78 with `{% set cta = 'ui-btn ui-btn-primary' %}` first; delete `smart_locks.html`.
2. templating.py: remove the `ttlock` lock tab and the `nav == "smart_locks"` branch.
3. admin.py: add `_smart_lock_panel_context(request)` (returns `smart_locks_enabled: False` when TTLock is off); spread it into the `apartments.html` render; `/smart-locks` GET redirects 303 (anchor `smart-locks-list` with an account, else `smart-locks-how`); `_smart_locks_url` returns `/apartments#anchor` unless return_to starts with `/apartments/`; `RESERVATION_PAGE_SIZE = 5`.
4. apartments.html: after the `{% if rows %}` block, `{% if smart_locks_enabled %}` with `h2#smart-locks-title`, the lede, and `{% include "_smart_locks_panel.html" %}`.
5. Tests: update the assertions listed in §3.
6. Screenshots at 390 and 1280 of `/apartments` with TTLock enabled (fixture from `test_lock_navigation_browser.py`) to `/mnt/project-files/design-reset/checkpoint-4-shell-fixes/properties-doorlock-<width>.png`.

## 5. Do not touch

CSS files, `base.html`, `static_versions.json`, UbyPort code, lock API code (`ttlock.py`), guest pages.

## 6. Commands

- `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell .venv/bin/python -m pytest tests/test_smart_locks_page.py tests/test_design_admin.py tests/test_host_properties_navigation.py tests/test_lock_navigation_browser.py tests/test_archive_stays_on_page.py tests/test_design_shell_browser.py tests/test_design_properties.py tests/test_host_list_page_layout_browser.py tests/test_property_hub.py -q --tb=short -rfs 2>&1 | tail -30`
- `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] No "Door lock account" tab on Properties; `/smart-locks` answers 303 to `/apartments#...`.
- [ ] `/apartments` shows the lock panel only when TTLock is enabled.
- [ ] `RESERVATION_PAGE_SIZE` is 5; the stays pagination tests pass.
- [ ] 0 skipped in the command above.
- [ ] Screenshots at 390 and 1280 written.

Known open after this run (see the report): two browser tests in `test_lock_navigation_browser.py` that drive the old `/smart-locks` page flow (`test_lock_setup_flow_keeps_its_place`, `test_share_section_without_javascript_and_foreign_returns`), and one layout test (`test_list_pages_share_order_edges_and_rhythm`) failing on invoices and fees tab strips, which this change does not touch.

## 8. Stop and ask

An excerpt is not found, a test fails twice, a file outside §3 needs a change, 25 tool calls reached.

## 9. Report

`docs/tasks/0190-report.md` (600 tokens max), then `Status: review` or `blocked`. Commit on the current branch and push with `git pull --rebase origin claude/project-thread-3xqb0b` first. Never push to `main`.
