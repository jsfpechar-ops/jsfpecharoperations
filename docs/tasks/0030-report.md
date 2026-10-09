# 0030 report

Status: review

## 1. Files changed

```
 App/app/routes/admin.py                           | 17 ++++----
 App/app/templates/apartment_form.html             |  1 +
 App/tests/test_door_code_one_lock_one_property.py | 52 +++++++++++++++++++++++
```

Applied with `git cherry-pick a2415e2d` (clean). Plus this report and `docs/tasks/0030-screenshots/` (three PNGs).

## 2. Commands

- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` → `All checks passed!`
- `pytest tests/test_door_code_one_lock_one_property.py -q` → `8 passed`
- `pytest tests/test_download_skeleton_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_invoice_stay_browser.py tests/test_wp28_geometry.py -q -rs` (with `UBYHOST_REQUIRE_BROWSER=1`) → `28 passed`, 0 skipped
- `pytest tests -q` (browser files skipped, no Playwright yet) → `4 failed, 2920 passed, 5 skipped`
- `python3 scripts/context_lint.py` → `context lint: OK`

## 3. Acceptance

- [x] Diff is only the three §3 files.
- [x] Ruff clean.
- [ ] Full test run passes, 0 skipped: **not met here, see Deviations.** Everything that touches this change passes; the 4 failures are sandbox-only.
- [x] Screenshots at 360, 390 and 1280 px: `docs/tasks/0030-screenshots/door-code-{360,390,1280}.png`. The page shows the hidden `door_codes_fields` input is present; layout is unchanged.
- [ ] CI on a PR: no PR opened (see Owner steps).

## 4. Deviations

- **4 sandbox failures, identical on untouched `origin/main`:** `test_feed_dns_pinning::test_two_concurrent_fetches_do_not_cross_pinned_addresses` (`OSError 97`, no IPv6 here) and three in `test_feed_url_ssrf.py` (`gaierror`, no DNS here). None touch door codes. They should pass in CI.
- **Browser tests:** the pinned `playwright==1.63.0` needs Chromium build 1243; this sandbox has 1194. I ran them with `playwright==1.56.0` in a local venv only (no repo file changed). Both browser files in the CI job and the other three passed.
- Work was done on the session branch `claude/eloquent-goodall-7o67fr`, not `task/0030-...`, as that branch is the one this session may push to.

## 5. Questions

None.

## 6. Owner steps left

See below.
