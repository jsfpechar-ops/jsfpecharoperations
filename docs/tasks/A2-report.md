# A2 report

Status: review

## Done
- Copy (en, cs, vi): the connection-test and letter-test messages say the login was accepted and that the test files nothing, so it does not prove filing works. "Connection works" is gone.
- Go log line `ubyport_submission_failed` now carries apartment_id, owner_user_id, submission_id, env, endpoint, guest_ids, error_type and cause. No message text, login or password. Reuses the existing `ubyportEnv` (default mock); `batchTransport` gained `guestIDs`.
- New tests: `App/tests/test_ubyport_test_copy.py`, `go/internal/ubyport/submit_log_test.go`.
- `App/tests/test_flash_next_step.py` tuples at :226-227 updated to the new en/cs copy (approved by orchestrator).

## Tests
- Python: test_ubyport_test_copy, test_police_letter_flow, test_host_i18n, test_go_host_i18n, test_flash_literals, test_no_em_dashes, test_flash_next_step: 99 passed, 0 skipped.
- Go: `go test ./internal/ubyport/... ./internal/hostweb/...` against local Postgres 16 (port 5433, database ubyhost_test): 272 PASS, 0 SKIP.
- gofmt and go vet on ubyport: clean.
- `App/scripts/go_host_i18n.py --check`: exit 0.
- `python3 scripts/context_lint.py`: OK.

## Deviations
- known-issues entry NOT added: the file is about 2656 tokens against a 2500 cap (lint ERROR). The entry text is in brief section 4 step 8. It needs a compaction first.
- golangci-lint not run: the installed binary (Go 1.25) cannot load the config (Go 1.26.0).
- Anchors drifted: cs copy at host_i18n.py :2975 and :2979; submit.go log :275, batchTransport :251, call :113.
- Commit trailer: Claude Sonnet 5.5, per orchestrator decision. The harness reminder said Haiku 5.5.
- No template or CSS change: no screenshots.

## Owner steps
- Merge after review with `scripts/merge-pr-on-green.sh`.
