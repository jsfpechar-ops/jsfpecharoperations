# 0253 report (round 2)

Status: blocked. Branch claude/project-thread-kpgr9d, not pushed, no PR.

## Files changed in round 2
- App/app/static/host-design0123.css: added `.stay-command-main { padding-left:0; padding-right:0 }` on phone (§10 A).
- App/tests/test_host_invoice_items_browser.py: replaced the `width >= 1280` table block with stacked-layout checks (§10 invoice).
- App/app/templates/base.html and App/tests/static_versions.json: see Deviations.
- docs/tasks/0253-report.md.

## Test result (§6 command, last 5 lines)
```

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_0199_phone_geometry_browser.py::test_stay - AssertionError:...
1 failed, 17 passed, 1 warning in 155.67s (0:02:35)
```
Invoice test: passes. Static versions: 3 passed. Only test_0199 test_stay fails.

## Open failure: stay A, offset 9 px at all 18 stay shots
The Next step eyebrow is a pill: app.css:2710 `.eyebrow { padding: 4px 9px }`. Probe at 390 px: panel main left 33, eyebrow box 33, eyebrow text 42, Guests text 33. The 9 px is the pill padding, which §10 did not account for.
Owner decision needed. Options:
1. (recommended) Hang the pill on phone: `.stay-command-main .eyebrow { margin-left:-9px }`. Text lands at 33, pill edge at 24.
2. Remove the pill's left padding on phone (`padding-left:0`). Text at 33, pill loses its inset.
3. Not allowed: changing test A to measure the eyebrow box loosens the test.
Not applied: it changes the look of the chip, so it is the owner's call.

## Deviations
1. Static key: changing host-design0123.css after round 1 requires a new `?v=` (test_static_versions). It is now `20261022-0253b` in base.html. host2.css keeps `20261022-0253`, unchanged since round 1.
2. Step 3 scratch check: lines() on a 120 px wrapped button returns 2, single line returns 1. The stay page's only [data-copy] is a hidden menu item, so the check ran on a probe element. Scratch files deleted.
3. Screenshots: the stay test rewrites checkpoint-6/mobile/*.png on every run, so the four copied files are fresh renders (they show the eyebrow inset). Copied to /mnt/project-files/red-tests-safari/after/: stay-incomplete-en-390.png, stay-failed-en-390.png, stay-ready-cs-390.png, stay-incomplete-vi-360.png. Plus invoice-items-en-390.png (test shot, one "other" row).

## Owner steps left
Choose option 1 or 2 above. Then the executor re-runs §6 and opens the PR.
