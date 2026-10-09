# 0023 report: PR #325 fix-ups

Status: review
Branch: `claude/staging-no-login` (head `6a48383` before this commit)

## Files changed

| Path | Change |
|---|---|
| `docs/privacy/ROPA.md` | Support mailbox row: added the "door code not created" copy to the host (property, stay date, TTLock error; no guest name, no door code) |
| `docs/tasks/0022-guest-door-code-waiting-messages.md` | Status line: `blocked (superseded by 0024, owner decision 2026-10-09)` (see Deviations) |
| `docs/tasks/0023-report.md` | This file |

No file under `App/` changed. No test was edited. `docs/tasks/0023-pr325-fixups.md` was fetched from `claude/charming-feynman-k7oear` to read it and is not committed.

## Commands

**Setup.** `App/.venv` did not exist. Created it and installed `requirements-dev.txt` and `requirements.txt`. Both are declared in the repo.

**`App/`: `.venv/bin/python -m pytest tests -q`** (last 5 lines):

```
FAILED tests/test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses
FAILED tests/test_feed_url_ssrf.py::test_redirects_are_revalidated_not_followed_blindly
FAILED tests/test_feed_url_ssrf.py::test_a_redirect_that_drops_https_is_refused
FAILED tests/test_feed_url_ssrf.py::test_allows_public_https_calendar - app.f...
4 failed, 2900 passed, 4 skipped, 7 warnings in 131.13s (0:02:11)
```

**Root: `python3 scripts/context_lint.py`** (last 2 lines, exit 0):

```
next free: task 0024 | migration 0008
context lint: OK
```

## FAILED lines and what was done

All four are the §2 DNS tests. Each error is `Could not resolve calendar host` (`App/app/feed_url.py:102`), which matches the sandbox-without-DNS cause in §2. No code fix. I did not re-run these on `main`; §2 already records that they fail only without DNS.

## §7 acceptance

- [x] Every `FAILED` line listed above, with its outcome.
- [x] `grep -c 'door code not created' docs/privacy/ROPA.md` prints `1`.
- [x] `git diff --stat origin/claude/staging-no-login` lists only §3 files (2 edited, plus this report).
- [x] `context lint: OK`.

## Deviations

1. **Step 5 status text.** The brief says to write `Status: superseded by 0024 (owner decision 2026-10-09)`. `scripts/context_lint.py:49` allows only `todo, in-progress, review, done, blocked`, and CI runs the lint (`.github/workflows/ci.yml:186`). The literal text would have made a new check red. I used `Status: blocked (superseded by 0024, owner decision 2026-10-09)`. `blocked` is the only lint-valid status that keeps the reason. `done` would need `0022-report.md`, which §3 does not allow.
2. **Venv.** Created `App/.venv` (not in the repo) so the §6 command could run.

## Questions for the owner or orchestrator

1. Should `superseded` be a valid status in `scripts/context_lint.py` (`STATUSES`)? That is a one-line change outside §3, so I did not make it. If yes, 0022 can use the exact text from step 5.
2. Is `blocked` acceptable for 0022, or do you prefer another status?

## Owner steps left

1. Open PR #325 on GitHub and wait for `test` and the lint check to go green.
2. Ask the reviewer for the guest-page screenshots (door-code card: issued and "being prepared", at 360, 390 and 1280 px).
3. Merge with `scripts/merge-pr-on-green.sh 325`.
