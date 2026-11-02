# 0736 brief: Menu card "Add stay" instead of "Add a property"

Status: todo
Executor: Haiku 5.5, worktree /tmp/wt0729 (branch phone-v2).

## 1. Objective
Josef (2026-11-01 22:23): the Menu's soft card should add a stay, not a property (the Properties tab already has "Add property"). Today keeps no add button.

## 2. Context
Mockup copy `docs/design/mockup/ubyhost-phone-v2.html` already updated by the orchestrator ("Add stay" / "For bookings made directly with you").

## 3. Files
`App/app/templates/menu.html`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/tests/test_0718_menu_page.py` (only if it asserts the old link), `docs/tasks/0736-menu-add-stay-report.md` (new).

## 4. Steps
1. `App/app/templates/menu.html`: in the `<a class="promo" ...>` line change `href="/apartments/new"` to `href="/reservations?new=1"`, `{{ t('apartments.add') }}` to `{{ t('stays.add_stay') }}`, and `{{ t('menu.add_property_sub') }}` to `{{ t('menu.add_stay_sub') }}`.
2. i18n: replace the key line `"menu.add_property_sub": ...` in each dict:
   - English: `"menu.add_stay_sub": "For bookings made directly with you",`
   - Czech: `"menu.add_stay_sub": "Pro rezervace přímo u vás",`
   - Vietnamese (host_vi_i18n.py): `"menu.add_stay_sub": "Cho đặt phòng trực tiếp với bạn",`
   Then `grep -rn "add_property_sub" App/` must print nothing.
3. If `App/tests/test_0718_menu_page.py` asserts `/apartments/new` on /menu, change it to `/reservations?new=1`.

## 5. Do not touch
CSS, other templates, the mockup.

## 6. Commands
From App/: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0718_menu_page.py tests/test_0728_menu_geometry_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs -k "menu" 2>&1 | tail -15`. Repo root: `python3 scripts/context_lint.py | tail -2`.

## 7. Acceptance
- [ ] /menu card reads "Add stay" and opens the add-stay form; tests pass, 0 skipped.

## 8. Stop and ask
A box-size failure on `.promo small` / `.promo b`: update only that BOX_OVERRIDES height/width entry with the app value (text-dependent) and say so; anything else, stop.

## 9. Report
`docs/tasks/0736-menu-add-stay-report.md`: Status, files, test tail. Commit "0736: Menu card adds a stay" with the usual trailers, then `git push origin phone-v2:claude/project-thread-50hyv5`.
