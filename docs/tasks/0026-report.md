# 0026 report: a host cannot add the same calendar link to two of their properties

Status: review
Branch: `task/0026-one-calendar-link-per-user`, cut from `main` at `8e89924`.

## Steps

1. Done. Added `_feed_already_added` directly above the `add_feed` route in `App/app/routes/admin.py`. It checks only the same owner's properties, through `db.null_safe_eq`.
2. Done. In `add_feed`, the duplicate check runs after URL validation and before `db.insert`. It returns the `flash.error.feed_duplicate` message naming the property.
3. Done. `flash.error.feed_duplicate` added once to the English block and once to the Czech block of `App/app/host_i18n.py`.
4. Done. `App/tests/test_feed_no_duplicate_per_user.py` created with the four tests from the brief.
5. Skipped (nothing to delete). The brief says to delete the `K-F20` row from `docs/context/known-issues.md`. There is no `K-F20` row on `main`, and no other mention of it anywhere in the repo. The file is unchanged. The brief's acceptance check (`grep -c 'K-F20'` prints 0) holds.
6. Done. Ran §6 (below).

## Commands

`.venv/bin/python -m pytest tests/test_feed_no_duplicate_per_user.py -q`, last lines:

```
.... [100%]
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
4 passed, 1 warning in 1.02s
```

`.venv/bin/python -m pytest tests/test_endtoend.py -q`, last line: `28 passed, 1 warning in 2.73s`

`.venv/bin/python -m pytest tests -q`, last lines:

```
FAILED tests/test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses
FAILED tests/test_feed_url_ssrf.py::test_redirects_are_revalidated_not_followed_blindly
FAILED tests/test_feed_url_ssrf.py::test_a_redirect_that_drops_https_is_refused
FAILED tests/test_feed_url_ssrf.py::test_allows_public_https_calendar - app.f...
4 failed, 2963 passed, 7 warnings in 322.85s (0:05:22)
```

The four are the DNS tests from brief 0023 §2.

`python3 scripts/context_lint.py`: `context lint: OK`

## Section 7

- [x] `4 passed` for the new file.
- [x] `grep -c '"flash.error.feed_duplicate"' App/app/host_i18n.py` prints `2`.
- [x] `grep -c 'K-F20' docs/context/known-issues.md` prints `0` (the row was never there).
- [x] `git diff --stat main` lists only §3 files (`admin.py`, `host_i18n.py`, the new test file, this report; `known-issues.md` not changed).
- [x] `context lint: OK`.

## Deviations

- Step 5: no `K-F20` row exists on `main`, so nothing was deleted.

## Questions

- The duplicate-link bug the brief describes (K-F20) is not in known-issues. Should it be added as a fixed entry, or is it tracked somewhere else?

## Owner steps left

Nothing beyond merge and deploy. A link that differs in any character (for example a newly exported Airbnb link) counts as a different link.
