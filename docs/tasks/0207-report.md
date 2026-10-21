# 0207 report: four critical push alerts

Status: review
Done: steps 1 to 6. Left: none.

## Files changed
- App/app/push.py: four helpers (filing_problem, deadline_at_risk, door_code_missing, cancelled_with_guests), 96 lines before `# --- retention ---`.
- App/app/reporting.py: import plus one hook after the rejected-branch submission_problem call.
- App/app/filing_watchdog.py: import plus hook before the try in notify_hosts.
- App/app/door_codes.py: import plus hook after door_code_delayed_notice.
- App/app/icalsync.py: import plus hook after cancelled_with_guests.
- App/tests/test_push_events.py: new, 6 tests.
- docs/tasks/0207-push-critical-events.md: Status set to review.
- docs/tasks/0207-report.md: this file.

Commits: bd43e9b c6b2393 4101252 c1fad7c 0436e26 758a605(one per step, 6 included; the report commit follows).
Diff stat of App/ and docs/ since step 1 base: 6 files changed, 209 insertions(+), 4 deletions(-)

## Commands (last lines)
1. `.venv/bin/python -m pytest tests/test_push_events.py tests/test_push.py -q --tb=short -x`
   `41 passed, 1 warning in 0.95s`
2. `.venv/bin/python -m pytest tests/test_filing_watchdog.py tests/test_submission_*.py tests/test_ubyport_*.py tests/test_stale_submission.py -q --tb=short -x`
   `133 passed, 3 warnings in 4.79s`
3. `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_icalsync.py tests/test_feed_*.py -q --tb=short`
   `1 failed, 162 passed, 1 warning in 8.17s`
   Failure: tests/test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses, `OSError: [Errno 97] Address family not supported by protocol` when the test helper opens an AF_INET6 server. A bare `socket.socket(AF_INET6)` call fails the same way in this container, so the container has no IPv6 sockets. The failure happens before any push code runs. Not a filing, door-code or calendar test. I did not check it against the base commit.
4. `python3 scripts/context_lint.py`
   `context lint: OK` (with WARN lines about other open briefs naming the same files, and a note about 50 commits touching App/ since the last status update; not caused by this brief).

Acceptance (§7): §6 commands 1, 2 and 4 pass. Command 3 has one failure from the IPv6 environment, so that box is not ticked. No browser or screenshot tests (no UI change).

## Deviations
- Step 6 fixture: added `"uid"` to the reservation insert, because `reservation.uid` is NOT NULL. Brief §4 step 6 allows this.
- Step 2: the brief's old block is six lines (`mail_notify.submission_problem(` to `)`); I matched exactly those lines, not the closing fence.
- Step 2 and the other hooks are inserted directly after the anchor line, with no blank line, as the brief writes them.
- executor.md asks for one PR. Per the owner's instruction for this run, no PR was opened and nothing was pushed.
- Known pre-existing failures in tests/test_host_i18n.py ("no such table: apartment") were not in §6 and were not run.

## Questions
- None on the code. Question for the owner or reviewer: the feed DNS-pinning IPv6 test needs an IPv6-enabled runner; CI should confirm it.

## Owner steps left
- None from the brief. Merge and deploy are the owner's, after review.
