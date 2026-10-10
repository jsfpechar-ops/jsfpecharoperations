# 0032 report: guide drops the form picture

Status: review. Implemented by the orchestrator on the owner's "implement it yourself" (2026-10-09). Commit `2889234` on `task/bundle-0025-0031` (PR #332).

## 1. Files changed

```
 App/app/guide_i18n.py                   |   2 --
 App/app/static/guide/ttlock-form.png    | Bin 98185 -> 0 bytes
 App/app/static/guide/ttlock-home.png    | Bin 140159 -> 136428 bytes
 App/app/templates/guide.html            |   4 ++--
 App/tests/test_ttlock_guide_pictures.py |  10 ++++++++--
```

## 2. Commands

- `.venv/bin/python -m pytest tests -q`: `4 failed, 2975 passed` (0 skipped). The 4 are `test_feed_dns_pinning.py` (1) and `test_feed_url_ssrf.py` (3); they fail the same way on `origin/main` in this sandbox (no DNS). CI has DNS.
- `ruff check` on the changed files: `All checks passed!`
- `python3 scripts/context_lint.py`: `context lint: OK`

## 3. Acceptance

- [x] `/guide#door-codes` shows pictures under steps 3 and 4 only (checked in Chromium at 360, 390, 1280 px; both images load).
- [x] Marker "1" is a badge on the Authorized Admin box; the old arrow at Remote is gone.
- [x] `git grep -n "shot_form\|ttlock-form"` returns only the new test line.
- [x] Screenshots in `0032-screenshots/`.

## 4. Deviations

Browser tests ran with Playwright 1.63 against the sandbox's Chromium 1194 (symlinked browser path, outside the repo). The section screenshots show the sticky top bar mid-image; that is the element-screenshot stitching, not the page.

## 5. Questions

None.

## 6. Owner steps left

1. Wait for CI on PR #332 to go green.
2. Merge: `scripts/merge-pr-on-green.sh 332`.
