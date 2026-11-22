# 2029: Pass every env var Go reads to the ubyhost-go container (AUD-06)

Status: todo
Depends on: none | Base commit: current main | Branch: task/2029-go-compose-env-parity
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the `UBYHOST_*` variables that `go/` reads but `deploy/lightsail/docker-compose.yml` does not pass to `ubyhost-go`, and add a test that fails when the two drift apart again. Today editing `.env` for these has no effect: the guest PIN cannot be turned off, lifecycle mail never sends, the mail heartbeat never fires, retention auto-purge cannot be enabled.

Source: AUD-06 in `docs/reports/go-cutover-parity-audit.md` (branch `origin/docs/go-cutover-parity-audit`, commit `15f92f28a`, PR #1260; not on main yet). Verified on current main by the orchestrator: the claim still holds (115 distinct `"UBYHOST_*"` literals in non-test `go/`, 83 in the `ubyhost-go` env block, 42 differ; after the exclusions below, 34 remain to add).

## 2. Context

Compose rule, pasted from the comment above the block: "A bare key is passed through from .env only when it is set there; do not write NAME: ${NAME:-}, an empty string is not the same as unset. A new variable read in go/ must be added here." Exception: keys that already use `${NAME:-default}` stay as they are.

Existing pattern to copy: `App/tests/test_go_compose_mail_env.py` has `_go_env_block()` (slices from `"\n  ubyhost-go:\n"` to `"\n  mock-ubyport:"`, then `environment:` to `volumes:`). Reuse that approach in a new test file.

Add these 34 bare keys under `environment:` of `ubyhost-go`, in the existing alphabetical-ish order (insert, do not reorder others):

```
UBYHOST_ADMIN_EMAIL
UBYHOST_ADMIN_USERNAME
UBYHOST_ADS_CONVERSION_NAME
UBYHOST_AI_MAX_INPUT_TOKENS
UBYHOST_AI_MAX_TOKENS
UBYHOST_AI_MODEL
UBYHOST_ALERT_RETENTION_DAYS
UBYHOST_AUDIT_RETENTION_DAYS
UBYHOST_DEMO_ENABLED
UBYHOST_GO_RETENTION_APPLY
UBYHOST_GUEST_LANGS
UBYHOST_GUEST_NOTICE_VERSION
UBYHOST_GUEST_PIN
UBYHOST_GUIDE_PHOTOS_DIR
UBYHOST_HAVEL_MONTHLY
UBYHOST_HAVEL_WEEKLY
UBYHOST_HEADCOUNT_LEAD_LIVE
UBYHOST_HEARTBEAT_MAIL_URL
UBYHOST_LEGAL_EFFECTIVE_DATE
UBYHOST_LIFECYCLE_MAIL
UBYHOST_MAIL_ENABLED
UBYHOST_OPERATOR_REGISTRY_URL
UBYHOST_RATE_LIMIT_RETENTION_HOURS
UBYHOST_RETENTION_AUTOPURGE
UBYHOST_RETENTION_NOTICE_DAYS
UBYHOST_RUIAN_URL
UBYHOST_SECRET
UBYHOST_SECURE_COOKIES
UBYHOST_SMTP_HOST
UBYHOST_STAGING_LOGIN_PASSWORD
UBYHOST_TTLOCK_API_BASE
```
That is 31 lines; before editing, re-run step 1 and add any other key it lists that is not in the exclusion list below (expected total 34; stop and ask if the count differs by more than 3).

Do NOT pass (the test allowlists these with a reason):
- `UBYHOST_GO_ADDR`, `UBYHOST_MIGRATIONS_DIR`, `UBYHOST_APP_ROOT`: set by `ENV` in `go/Dockerfile:15`.
- `UBYHOST_TEST_OCR_VALUES`, `UBYHOST_REPO_ROOT`: test/dev only (`draft_scan.go:427`, `demo_seed_mock.go:56`); must never reach production.
- `UBYHOST_AI_KEY_DAILY_USD_`, `UBYHOST_AI_MONTHLY_USD_`: prefixes; the per-key variables are already listed.
- Non-`UBYHOST_` names (`AWS_SES_REGION`, `POSTHOG_*`, `TURNSTILE_*`) are out of scope.

Privacy/secrets: names only. Never print values from `.env`. `UBYHOST_SECRET`, `UBYHOST_STAGING_LOGIN_PASSWORD`, `UBYHOST_SMTP_HOST` are sensitive or legacy: they are passed through bare like the SES keys; no value goes in the repo.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/docker-compose.yml` | edit | add the bare keys to `ubyhost-go` `environment:` only |
| `App/tests/test_go_compose_env_parity.py` | create | compose list vs keys read in `go/` |
| `docs/ENVIRONMENT.md` | edit | only if it says the Go container gets a fixed list; one sentence, grep first |

No other file may change.

## 4. Steps

1. Print the gap (names only):
```
cd /agent/repos/jsfpecharoperations
grep -rhoE '"UBYHOST_[A-Z0-9_]+"' go --include=*.go --exclude=*_test.go | tr -d '"' | sort -u > /tmp/go.txt
awk '/^  ubyhost-go:/{f=1;next} /^  [a-z]/{f=0} f' deploy/lightsail/docker-compose.yml | grep -oE 'UBYHOST_[A-Z0-9_]+' | sort -u > /tmp/c.txt
comm -23 /tmp/go.txt /tmp/c.txt | tail -50
```
2. Edit the compose file: insert the bare keys (6-space indent, trailing colon, no value) into the `ubyhost-go` block. Do not touch other services.
3. Create `App/tests/test_go_compose_env_parity.py`: copy `_go_env_block()` from `test_go_compose_mail_env.py`; read every non-`_test.go` file under `go/` with `Path.rglob("*.go")`; collect `re.findall(r'"(UBYHOST_[A-Z0-9_]+)"', text)`; passed = keys of the env block lines (`ln.strip().split(":")[0]`). Constant `NOT_PASSED = {...}` holds the four exclusions above plus the two prefixes, each with a comment giving the reason. Assert `read - passed - NOT_PASSED == set()` with a message listing the missing names, and assert every `NOT_PASSED` entry is still read in `go/` (so the allowlist cannot rot). Add one test that no env line in the block has a value other than the existing `${...}`/`/data` forms for these new keys (they stay bare).
4. Run the tests (§6). Fix only the new file or compose.
5. Grep `docs/ENVIRONMENT.md` for `ubyhost-go` and `Go container`; adjust one sentence only if wrong.

## 5. Do not touch

`go/`, `App/app/`, `.env*`, other compose services, Caddyfiles, `UBYHOST_GO_PATHS`, `docs/context/status.md`, `decisions.md`. Hard rules 3 (no secrets) and 4 (no dependency) apply.

## 6. Commands

```
cd App && .venv/bin/python -m pytest tests/test_go_compose_env_parity.py tests/test_go_compose_mail_env.py -q --tb=short -x 2>&1 | tail -30
cd .. && shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
docker compose -f deploy/lightsail/docker-compose.yml --profile go config -q 2>&1 | tail -10
```
Expected: tests pass, no shellcheck output, lint OK, compose config silent (skip the last if docker is missing, say so in the report).

Test-map row: "Deploy scripts, Caddyfile, compose" (`shellcheck -S error deploy/lightsail/scripts/*.sh`; CI job `caddy`; `test_pg_*script*.py`) plus the mail-env test above. No browser tests: no template or CSS change.

## 7. Acceptance

- [ ] Step 1 command prints nothing after the edit except the allowlisted names.
- [ ] New test passes, and fails if one key is deleted from compose (check once locally, then restore).
- [ ] Diff touches only the §3 files; no value for any key appears in the diff.
- [ ] `test_go_compose_mail_env.py` still passes.

## 8. Stop and ask

Stop, and write the report, if: the gap differs from 34 by more than 3; a key in the list is no longer read in `go/`; a test fails twice; a file outside §3 needs a change; 25 tool calls or about 50k tokens are reached; you need push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/2029-report.md` (600 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`deploy/lightsail/docker-compose.yml` (a bare key with an empty `.env` entry is passed as empty: check `UBYHOST_DEMO_ENABLED`, whose Go code treats empty as on, and `UBYHOST_SECURE_COOKIES`, `UBYHOST_MAIL_ENABLED`); the allowlist in the new test.

## Owner steps

After the PR is green and merged (merge auto-deploys):
1. On the server, open the `.env` beside `deploy/lightsail/docker-compose.yml`.
2. Decide per variable whether to set it. Nothing changes until you do, because bare keys pass only what `.env` sets. Likely wanted now: `UBYHOST_GUEST_PIN`, `UBYHOST_LIFECYCLE_MAIL`, `UBYHOST_HEARTBEAT_MAIL_URL`, `UBYHOST_RETENTION_AUTOPURGE`, `UBYHOST_GO_RETENTION_APPLY`, `UBYHOST_ADMIN_EMAIL`, `UBYHOST_ADMIN_USERNAME`.
3. Setting any of these changes live behaviour (mail starts sending, purge starts deleting). Set one at a time, then run `docker compose --profile go up -d ubyhost-go` and check `/healthz`.
4. Do not paste values into chat or the repo.
