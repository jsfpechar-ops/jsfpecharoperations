# 0253 report (round 2)

Status: review. Branch claude/project-thread-kpgr9d, not pushed, no PR.

## Files changed in round 2
- App/app/static/host-design0123.css: on phone `.stay-command-main { padding-left:0; padding-right:0 }` (§10 A).
- App/tests/test_host_invoice_items_browser.py: stale `width >= 1280` table block replaced with stacked-layout checks (§10 invoice).
- App/tests/test_0199_phone_geometry_browser.py: A measures the content edge of .stay-command-main; new An check for the note text (step 9, orchestrator decision).
- App/app/templates/base.html, App/tests/static_versions.json: see Deviations.

## Test result (§6 command, last 5 lines)
```
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
18 passed, 1 warning in 153.00s (0:02:33)
EXIT 0
```
18 passed, 0 skipped.

## Deviations
1. Static key: host-design0123.css changed after round 1, so test_static_versions needs a new key. It is now 20261022-0253b in base.html. host2.css keeps 20261022-0253.
2. A measurement: the eyebrow pill's own 9 px padding (app.css:2710) is no longer counted. A now measures the content edge of .stay-command-main, and An checks the note text against Guests text (orchestrator decision, no CSS change for the pill).
3. Step 3 scratch check: lines() on a 120 px wrapped button returns 2, a single line returns 1. Run on a probe element, since the stay page's only [data-copy] is a hidden menu item. Scratch files deleted.
4. The stay test rewrites checkpoint-6/mobile/*.png on each run. The copied stay screenshots are from the final run.

## Screenshots (/mnt/project-files/red-tests-safari/after/)
stay-incomplete-en-390.png, stay-failed-en-390.png, stay-ready-cs-390.png, stay-incomplete-vi-360.png (stay); invoice-items-en-390.png (invoice, one "other" row).
