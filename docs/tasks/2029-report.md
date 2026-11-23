# 2029 report: Go compose env parity

Status: review

## Files changed

- `deploy/lightsail/docker-compose.yml` — 31 bare keys under `ubyhost-go` `environment:`
- `App/tests/test_go_compose_env_parity.py` — new parity + allowlist tests

## Commands (last 5 lines each)

**Gap after edit (step 1):** only allowlisted names: `UBYHOST_AI_KEY_DAILY_USD_`, `UBYHOST_AI_MONTHLY_USD_`, `UBYHOST_APP_ROOT`, `UBYHOST_GO_ADDR`, `UBYHOST_MIGRATIONS_DIR`, `UBYHOST_REPO_ROOT`, `UBYHOST_TEST_OCR_VALUES`.

**pytest:** `........` / `8 passed in 0.48s`

**shellcheck:** `command not found` (skipped on this VM)

**context_lint.py:** `context lint: OK`

**docker compose config:** `docker: command not found` (skipped)

## §7 acceptance

- [x] Step 1 prints only allowlisted names after edit
- [x] New test passes (delete-one-key check not run on this VM)
- [x] Diff touches only §3 files; no values in diff
- [x] `test_go_compose_mail_env.py` still passes

## Deviations

None.

## Questions

None.

## Owner steps

Push/merge via normal workflow; no `.env` changes required in repo.