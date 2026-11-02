# 0728 report: phone Menu lines and log-out row

Status: review

## Changes
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`: `menu.sub.*` keys (en, cs, vi). Placeholders are `%(today)s` and `%(week)s`, the style these files already use.
- `App/app/routes/admin.py` (`menu_view`): counts cleaning events for today and the next 7 days; wrapped in try/except so the menu never fails.
- `App/app/templates/menu.html`: second line on every row; Cleaning shows live counts, badge when today > 0; log-out is a `.list` row with a grey icon.
- `App/app/static/app2.css`: log-out rules (phone block); `.menu-list .row .t small` one line with ellipsis (see Deviations).
- `App/app/templates/base.html`: css key `20261101-0728c`; `App/tests/static_versions.json` rewritten.
- `App/tests/test_0728_menu_geometry_browser.py`: new, widths 320, 360, 390, 768.
- Screenshot: `docs/tasks/screenshots-0728/menu-390.png`.

## Commands (last lines)
- `pytest tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py tests/test_0718_menu_page.py tests/test_0728_menu_geometry_browser.py -q -rs`: `32 passed in 33.77s`, no skips.
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: `All checks passed!`
- `scripts/design_lint.py`: `design lint: OK`
- `scripts/context_lint.py`: `context lint: OK`

## Brief section 7
- [x] Every row has a second line
- [x] Cleaning shows live counts (shows "0 today, 4 this week" in the test data)
- [x] Log out is a row in its own card with a grey icon
- [x] Tests and lints pass, 0 skipped

## Deviations
- Steps 2 and 3 share `menu.html` and `app2.css`, so they are one commit (`1709e6d`), not two.
- Step 4 commit is `34e122b`; the css key bump was amended into it.
- Added `.menu-list .row .t small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}`. Reason: the 0710 desktop check flagged the default small size (11.67 px), and "Company, notifications, plan, privacy" wrapped to two lines at 320 and 360 px.
- Commits carry `Co-Authored-By: Claude Haiku 5.5`, per the attribution reminder, not Opus 5.5 as the launch message asked.
- `App/tests/v2_mockup.py` still has the `missing_ok` entry for `.row .t small` on menu. It is now harmless and was left as is.
- Cleaning event keys: I did not print them separately. The code uses `kind == "cleaning"` and `start[:10]`, and the live count renders. Today's count of 0 is not independently checked.

## Owner steps left
1. Decide the Settings subtitle at 320 and 360 px: keep the ellipsis, or shorten the copy in `menu.sub.settings`.
2. Look at `docs/tasks/screenshots-0728/menu-390.png`.
3. Review and open the PR. Nothing was pushed and no PR was opened.
