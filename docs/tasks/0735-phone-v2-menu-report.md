# 0735 report: phone v2 Menu (Airbnb style)

Status: review

## Changed files
- App/app/routes/admin.py (menu_view: month summary, no apartments), App/app/templates/menu.html (mockup menu screen)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (menu.sub.* removed; menu.tile.*, menu.add_property_sub, menu.help added)
- App/app/static/app2.css (0719/0728 menu rules removed, 0735 block appended), App/app/templates/base.html (css key 20261101-0735b), App/tests/static_versions.json
- App/tests/v2_mockup.py (menu entry, BOX_OVERRIDES)
- App/tests/test_0728_menu_geometry_browser.py (rewritten for the new Menu; 4 widths)
- App/tests/test_0718_menu_page.py: unchanged (already passing)
- docs/tasks/screenshots-0735/menu-390.png, docs/tasks/screenshots-0735/menu-320.png

## Command tails
- Brief §6 set (from App/): `38 passed in 77.97s` (0 skipped, `-rs` shows none).
- `ruff check app tests --select E9,F63,F7,F82,F401,F841`: `All checks passed!`
- `scripts/design_lint.py`: `design lint: OK`
- `scripts/context_lint.py`: `context lint: OK` (WARN lines are open-brief notices, not failures)

## Overrides added (BOX_OVERRIDES, text-dependent comment, 0735)
- `.mh .big@320` and `.mh .big@390`: width 79.3594px (app value; Manrope in app, system-ui in mockup copy; brief §10.1)
- `.promo@390`: height 80px (app value; the 390 run also failed, same cause)
- `.promo b@390`: width 143.25px (app value)
- `.tile .v@390`: margin-top 29px (app value)
- Earlier WIP overrides kept: `.promo@320` height 80px, `.promo b@320` width 143.25px, `.tile .v@320` margin-top 29px.

## Deviations
- Brief §10.1 named only `.mh .big`; the 390 run also failed on `.promo`, `.promo b` and `.tile .v`, so the same text-dependent overrides were added at 390.
- Commit trailer: Co-Authored-By Claude Opus 5.5 as instructed for this run (the WIP commit used Haiku).
- Branch in the worktree is phone-v2 (brief names claude/project-thread-50hyv5).
- Screenshot run writes `docs/tasks/screenshots-0710` and also `mockup-None-*.png` files (a naming quirk of the existing test). Tracked PNGs were restored and the new untracked PNGs removed, so none were committed.

## Owner steps left
- Review the screenshots and the text-dependent overrides, then merge via `scripts/merge-pr-on-green.sh`. Nothing is pushed.
