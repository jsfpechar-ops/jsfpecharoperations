# 0735 report: phone v2 Menu (Airbnb style)

Status: blocked (WIP commit; steps 8-10 not done, one mockup style test fails)

## Changed files
- App/app/routes/admin.py (menu_view: month summary, no apartments)
- App/app/templates/menu.html (rewritten to the mockup menu screen)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (menu.sub.* removed, menu.tile.*, menu.add_property_sub, menu.help added)
- App/app/static/app2.css (0719/0728 menu rules removed, 0735 block appended)
- App/app/templates/base.html (css key 20261101-0735b), App/tests/static_versions.json
- App/tests/v2_mockup.py (menu entry: phone_mockup, phone_selectors, missing_ok; BOX_OVERRIDES .card.me, .card.me@320 and .big removed)

## Command tails
- Menu mockup test (brief step 7): `6 failed, 32 passed` for the full brief set; first failure:
  `menu at 320 px: 1 style differences` then `menu at 390 px: 4 style differences`:
  `.mh .big width` app 79.36 px vs mockup 75.94 px (same Manrope 800, 30 px, -.02em on both sides; cause not found).
- Full brief set (test_0710, test_0728, test_0718, test_0729, test_static_versions, test_0252): 6 failed.
  test_0728 still uses the old 0728 selectors (`getBoundingClientRect` on null, not yet rewritten, step 8).
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: All checks passed!
- `scripts/design_lint.py`: design lint: OK
- `scripts/context_lint.py`: context lint: OK

## Overrides added (BOX_OVERRIDES, text-dependent comment, 0735)
- `.promo@320`: height 80px
- `.promo b@320`: width 143.25px
- `.tile .v@320`: margin-top 29px

## Deviations
- Extra CSS fixes so the mockup style test can match: `body.v2 .tile` gets `border:0`; `body.v2 .tile b` gets `margin-top:0`; `body.v2 .tile .v` gets `color:var(--ink)`. The global `.tile` rules (app2.css lines 25-26, 56) otherwise apply.
- The first css key 20261101-0735 was refused by the static-version check after the CSS changed again; the key is 20261101-0735b.
- `nav.payments` has no Vietnamese entry in host_vi_i18n.py (it is already used by the old menu).
- In v2_mockup.py the comment above `.card.me@320` was removed with that key.
- Steps 8 (rewrite test_0728 geometry), 9 (test_0718 update) and 10 (screenshots) are not done.
- Commit trailer uses Claude Haiku 5.5 (the harness attribution); the handover said Opus 5.5.
- Branch in the worktree is phone-v2 (brief says claude/project-thread-50hyv5).

## Owner question
- The `.mh .big` width on /menu differs from the mockup. Either accept the app width (keep the override `.mh .big@320` with a reason) or the owner says which weight/copy the mockup should use.

## Owner steps left
- Decide the `.mh .big` width question, then the executor (or next run) does steps 8-10.
