# 0202: Vietnamese fits the phone layouts from 0196-0201

Status: done
Depends on: 0201, main's languages 0196 (vi host app) | Base commit: 19d6cab | Branch: claude/project-thread-xo8dql
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Vietnamese (`vi`) is now a host app language. Its labels are often longer than English and Czech. The phone rules from 0199/0200 use `white-space:nowrap` on the stay page action buttons and one-row scrolling chips. Prove the same geometry holds in `vi`, and fix only what breaks.

## 2. Context

- Language switch: `?lang=vi` (same as `en`/`cs`).
- Tests to extend: `App/tests/test_0199_phone_geometry_browser.py` (stay page, Door lock tab, cleaning; 360/390) and `App/tests/test_0201_tabbar_safe_area_browser.py` (tab bar). Add `"vi"` wherever they loop or parametrize over `en`/`cs`.
- Also check, at 360 and 390 in `vi`, the 0200 pages: property new, invoice new picker, invoice detail, operator add, properties list, submission detail, property settings save bar, setup calendar. Reuse the sweep approach from `docs/tasks/0200-phone-actions-site-wide.md` §4 step 3: no `scrollWidth > innerWidth`, every text `.ui-btn` inside the action rows fits its container, no button wider than the viewport.
- CSS: stay page = `App/app/static/host-design0123.css` (0199 phone block); shared = `App/app/static/host2.css` (0200 block); tab bar labels = `.ui-tabbar a` in host2.css (`font-size: var(--size-11)`).
- Rules: tokens only (design lint fails on bare px in gap/padding: run `python3 scripts/design_lint.py`), 44 px phone targets, one `?v=` bump per changed CSS file + `.venv/bin/python tests/test_static_versions.py --write`.

## 3. Files

The two test files above; CSS only if a fault is measured.

### Likely faults to look for

- A. Stay page `.stay-command-actions` buttons are `nowrap`: a long `vi` label may overflow its button or the row at 360. Fix: let the label wrap (`white-space:normal; text-align:center`) while keeping min-height 44 px, only if it overflows.
- B. Tab bar: five `vi` labels at 11 px may be wider than a 72 px column (360/5). Measure each label's `scrollWidth <= clientWidth`. If not, allow two lines centred (`white-space:normal; text-align:center; line-height:1.15`) without growing the bar beyond `--tabbar-h`, or report the labels that need a shorter translation (do not change copy).
- C. Any 0200 action row button whose text overflows.

## 4. Steps

1. Extend the two tests with `vi`. Run them (command in §6). Write a temporary sweep for the 0200 pages in `vi` (`App/tests/test_zz_vi_sweep_browser.py`, not committed; copy fixtures from `tests/test_host_wide_geometry_browser.py` or `tests/test_design_guardrails_browser.py`).
2. Fix only measured faults, in one `/* 0202 */` block per changed CSS file. Bump keys, regenerate manifest.
3. Save 390 `vi` screenshots of the stay page, Door lock tab, cleaning, dashboard (tab bar) to `/mnt/project-files/design-reset/checkpoint-6/mobile/vi/` (`mkdir -p`, trailing slash).
4. Delete the temporary sweep file when done.

## 5. Do not touch

Translations/copy, Python, templates other than `?v=` keys. No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/` with `PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/-home-user-jsfpecharoperations/32720230-0d1d-503f-bf86-113631eb131a/scratchpad/pw UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0` (and `unset UBYHOST_BROWSER_EXECUTABLE`):
`.venv/bin/python -m pytest tests/test_0199_phone_geometry_browser.py tests/test_0201_tabbar_safe_area_browser.py tests/test_static_versions.py tests/test_design_guardrails_browser.py -q --tb=line 2>&1 | grep -E "^E |FAILED|passed|failed" | tail -10`
Then from the repo root: `python3 scripts/design_lint.py | tail -2`.

## 7. Acceptance

- [ ] Tests above pass with `vi` added, 0 skipped; design lint OK.
- [ ] `vi` sweep of the 0200 pages at 360/390: no overflow; numbers in the report.

## 8. Stop and ask

If a fault can only be fixed by changing copy or markup, stop and list it. Do not commit.

## 9. Report

[0202-report.md](0202-report.md)
