# 0024 report: a code that fails is handed to the host within about a minute

Status: review
Branch: `task/0024-door-code-immediate-handover`, cut from `claude/staging-no-login` at `aded777` (PR #325 not merged yet, so the anchors exist only on that branch).
Brief: `docs/tasks/0024-door-code-immediate-handover.md` on `claude/charming-feynman-k7oear`, commit `e0d49f3`.

## Files changed

| File | Change |
|---|---|
| `App/app/door_codes.py` | `ISSUE_MAX_ATTEMPTS = 2`; `DELAY_MINUTES = 5`; both attempt checks use it; `DOOR_CODE_PROBLEM` log lines (issue x2, delayed x1); `first_use_by` in the issued view; delayed alert skips hosts without door codes and sends the host mail at once (`mail.drain`) |
| `App/app/mail_notify.py` | Failed notice carries the reason; delayed notice uses the failed texts; `build_door_code` takes `first_use_by` |
| `App/app/i18n.py` | `door_code_first_use` (5 languages) replaces `door_code_only_between`; `door_code_preparing` set to the owner's waiting copy; `door_code_delayed` deleted |
| `App/app/host_i18n.py` | Failed host texts (en, cs) replaced with the new copy; delayed texts deleted |
| `App/app/templates/guest/stay.html` | Issued shows the first-use deadline; the delayed branch is gone (a late code shows the waiting text) |
| `App/tests/test_door_code_handover.py` | New, 7 tests from brief step 14 |
| `App/tests/test_door_codes_safeguards.py` | One test replaced (step 15) |
| `App/tests/test_guest_mail.py` | One line added (step 16) |
| `docs/tasks/0024-report.md` | This file |

## Commands

Setup: `App/.venv` already existed from earlier. Installed `playwright==1.63.0` in it (as CI does). Symlinked the installed Chromium at the path Playwright 1.63 expects (`/opt/pw-browsers/chromium_headless_shell-1243/.../chrome-headless-shell`). This is environment only, not in the repo.

1. `.venv/bin/python -m pytest tests/test_door_code_handover.py tests/test_door_codes_safeguards.py tests/test_guest_mail.py -q`
   ```
   .......................................................................  [100%]
   71 passed, 1 warning in 1.12s
   ```
2. `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_wp28_geometry.py -q -rs`
   ```
   25 passed, 1 warning in 192.61s (0:03:12)
   ```
   No `SKIPPED` line. Before the symlink, 24 of these were skipped and one failed on the missing browser, not on code.
3. `.venv/bin/python -m pytest tests -q`
   ```
   FAILED tests/test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses
   FAILED tests/test_feed_url_ssrf.py::test_redirects_are_revalidated_not_followed_blindly
   FAILED tests/test_feed_url_ssrf.py::test_a_redirect_that_drops_https_is_refused
   FAILED tests/test_feed_url_ssrf.py::test_allows_public_https_calendar - app.f...
   4 failed, 2933 passed, 7 warnings in 320.19s (0:05:20)
   ```
   The four are the DNS tests named in brief 0023 §2.
4. `python3 scripts/context_lint.py` → `context lint: OK` (warnings only: open briefs that name the same files).

## Section 7

- [x] `grep -c '"door_code_first_use"' App/app/i18n.py` → 5
- [x] `grep -c 'DOOR_CODE_PROBLEM' App/app/door_codes.py` → 3
- [x] §6 commands pass as stated
- [x] Only §3 files changed (the `git diff --stat` above; `door_code_only_between` no longer appears in `App/app` source)

## Deviations

1. **Host texts (step 12).** The brief says to delete the `delayed` lines and then "Set" the en and cs texts without naming the keys. I read those texts as the new values of `mail.door_code_notice.failed.subject` and `.failed.body`, because the delayed notice now uses the failed keys (step 8).
2. **Test replaced (step 15).** `test_guests_are_not_shown_the_first_use_rule` is replaced, as the brief says. No other test in `test_door_codes_safeguards.py` changed.
3. **Brief status.** I did not change `Status:` in the 0024 brief on its branch, since §3 says no other file may change.

## Questions

1. Brief 0022 (replaced) and 0024 both describe the waiting copy. Only 0024 is run. The 0022 anchors no longer match, so it would stop at its first anchor anyway.
2. Old briefs 0005, 0008 to 0016, 0020 and 0021 are still `Status: todo`, and the new overlap warning lists them. Probably shipped. Owner or orchestrator should set each to `done` or `replaced`.

## Owner steps left

1. Merge PR #325 first (`scripts/merge-pr-on-green.sh 325`). This brief starts from its branch.
2. Open a PR for `task/0024-door-code-immediate-handover` when ready. Not opened from here, since no PR was asked for.
3. After merge and deploy: in Render, open the service, click **Logs**, search `DOOR_CODE_PROBLEM`. Every failed try, hand-over and late code shows up there.
4. Reviewer takes guest screenshots: the waiting card and the issued card, at 360, 390 and 1280 px.
