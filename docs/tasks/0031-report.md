# 0031 report

Status: review

## 1. Files changed

```
 App/tests/test_door_codes_view.py | 262 +++++++++++++++++++++++++++
```

Taken from `refs/pull/316/head` (`abc38f4c`) with one edit: `from datetime import date, timedelta, timezone` became `from datetime import date, timedelta`. The first lines matched §2 exactly. `test_staging_password_login.py` was not brought over. Plus this report.

## 2. Commands

- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` → `All checks passed!`
- `pytest tests/test_door_codes_view.py -q` → `11 passed`
- `pytest tests -q` (Playwright 1.56 locally, `UBYHOST_REQUIRE_BROWSER=1`) → `4 failed, 2959 passed`, 0 skipped
- `python3 scripts/context_lint.py` → `context lint: OK`

## 3. Acceptance

- [x] Diff is only `App/tests/test_door_codes_view.py` and the report.
- [x] Ruff clean.
- [ ] Both pytest commands pass: the new file passes; the full run has 4 sandbox-only failures (see Deviations).
- [ ] CI on a PR: no PR opened (see Owner steps).

## 4. Deviations

- **4 sandbox failures, identical on untouched `origin/main`:** `test_feed_dns_pinning::test_two_concurrent_fetches_do_not_cross_pinned_addresses` (no IPv6 here) and three in `test_feed_url_ssrf.py` (no DNS here). None touch door codes.
- Playwright: pinned 1.63.0 needs Chromium 1243, this sandbox has 1194, so a local-venv-only `playwright==1.56.0` was used. No repo file changed.
- Done on the session branch `claude/eloquent-goodall-7o67fr` (it also carries 0030), not `task/0031-...`.
- Checked the new file for personal data: only synthetic labels ("Door host", "DC view", "Flat", `dc-view-` usernames); no emails, phones or guest identity fields.

## 5. Questions

None.

## 6. Owner steps left

Open a PR from the session branch (or ask for one), wait for CI, merge with `scripts/merge-pr-on-green.sh <pr-number>`.
