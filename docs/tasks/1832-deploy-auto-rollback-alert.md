# 1832: Deploy safety 3: automatic rollback to the previous image when a check fails, plus an owner alert naming the failing step

Status: todo
Depends on: 1830 (slots) and 1831 (smoke step) | Base commit: current tip of the working branch | Branch: task/1832-deploy-auto-rollback-alert
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (deploy script; exact diffs only; fresh review of the full diff)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) section 6.

> **One PR mode.** Commit each step as `1832 step k`. Never push, merge or deploy.

## 1. Objective

Every failing deploy step (Caddy validate, Caddy reload, health wait, public check, smoke registration) ends in `rollback`, and the owner gets one alert that names the failed step.

## 2. Context

Hard rules: 1 filing correctness first (a rollback must never leave the worker and the web app on different code for long; see below); 2 a new outbound request needs its reason in the PR; 3 no secrets in the repo; 4 no new dependency.

**What exists in `deploy/lightsail/scripts/deploy.sh` (quote, verify with `grep -nF`):**
- Line 47: `# 0710: rollback target. .deployed-sha is written only when a deploy finished;` and `PREV_SHA="$(cat .deployed-sha ...`
- `public_ok()` at line 52, `rollback()` at line 65:
```
rollback() {
  echo "==> Rolling back to ${PREV_SHA:-the previous image and Caddyfile}" >&2
  ...
  if docker image inspect ubyhost:previous >/dev/null 2>&1; then
    docker tag ubyhost:previous ubyhost:local
  fi
  if docker image inspect ubyhost-go:previous >/dev/null 2>&1; then
    docker tag ubyhost-go:previous ubyhost-go:local
  fi
  docker compose up -d --no-build --remove-orphans || true
  docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile || true
```
- The images are kept at lines 215 to 221: `docker tag ubyhost:local ubyhost:previous` and `docker tag ubyhost-go:local ubyhost-go:previous`.
- Callers of `rollback`: after `caddy reload` fails (line 338), after the health wait (line 357, message `New release never became healthy.`), after `public_ok` fails (line 364). **Not covered today:** an invalid Caddyfile at line 122 (it restores `Caddyfile.previous` and exits; nothing was restarted, so no image rollback is needed, but the owner gets no alert) and a failed public smoke at line 461 (`ERROR: public smoke failed ...` then `exit 1` without rollback). This brief closes both.
- Not covered: after 1830, the Go image runs from slot tags (`ubyhost-go:slot-a` / `slot-b`), so `docker tag ubyhost-go:previous ubyhost-go:local` no longer changes what runs.

**Migrations.** Nothing is rolled back. A migration that already ran stays; this is safe only because migrations are add-only within a release, so the previous image keeps working on the new schema (`docs/context/rules.md` line 47). The rollback message must say so.

**Alert channel (open question 1).** The repo already pings healthchecks.io-style URLs (`UBYHOST_HEARTBEAT_*`, `deploy/lightsail/scripts/monitoring-watchdog.sh` lines 70 to 76: `curl -fsS -m 10 --retry 2 -o /dev/null "${heartbeat}/fail"`). This brief adds one more of the same kind, `UBYHOST_HEARTBEAT_DEPLOY_URL`: on failure `POST <url>/fail` with the body `deploy failed at step: <name>`, which healthchecks.io shows in the alert it sends. Reason for the PR (rule 2): the request goes to the owner's own monitoring URL, carries a step name and the short commit sha, no personal data. Second, free alert: the script exits non-zero, so the GitHub deploy workflow turns red and GitHub notifies the owner.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/scripts/deploy.sh` | edit | `alert_owner`, `FAILED_STEP`, rollback of the Go slot, new call sites |
| `deploy/lightsail/scripts/go-slot.sh` | edit | add `go_rollback_slots` (created by 1830) |
| `docs/ENVIRONMENT.md` | edit | one row `UBYHOST_HEARTBEAT_DEPLOY_URL` |
| `docs/tasks/1832-report.md` | create | the report |

No other file may change.

## 4. Steps

1. **`alert_owner`.** Insert directly above `rollback() {`:
```bash
# 1832: one alert per failed deploy, naming the step. Needs UBYHOST_HEARTBEAT_DEPLOY_URL
# (healthchecks.io semantics, same as the other heartbeats). Never fails the deploy.
alert_owner() {
  local step="$1" url="${UBYHOST_HEARTBEAT_DEPLOY_URL:-}"
  echo "ALERT: deploy failed at step: ${step}" >&2
  if [ -n "${url}" ]; then
    curl -fsS -m 10 --retry 2 -o /dev/null --data-raw "deploy failed at step: ${step} (commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown))" "${url%/}/fail" || true
  fi
}
```
2. **`rollback` takes the step.** Change `rollback() {` to `rollback() {` plus, as its first line, `alert_owner "${1:-unknown}"`. Then update every caller (grep `rollback$` and `rollback ` in the file): `caddy-reload`, `health-wait`, `public-check`. Example: the line `  rollback` after `New release never became healthy.` becomes `  rollback health-wait`.
3. **Cover the two gaps.** At the invalid-Caddyfile exit (line 122 to 127) add `alert_owner caddy-validate` before `exit 1`. At the public smoke failure (line 461) replace the `exit 1` with `rollback public-smoke` then `exit 1`. After the 1831 call `./scripts/smoke-registration.sh` make its failure branch `rollback smoke-registration` then `exit 1`.
4. **Go slots in `rollback`.** After the two `docker tag ... :previous ... :local` blocks and before `docker compose up -d --no-build --remove-orphans || true`, add `if [ -f ./scripts/go-slot.sh ]; then source ./scripts/go-slot.sh; go_rollback_slots || true; fi` (with `# shellcheck disable=SC1091`). Add to `go-slot.sh`:
```bash
# 1832: bring the other (old) slot back and stop the new one. The old slot's image
# tag was never moved, so this is the previous Go image.
go_rollback_slots() {
  local live idle
  live="$(go_live_slot)"
  idle="$(go_idle_slot)"
  docker compose --profile go up -d --no-build --no-deps "$(go_svc "${idle}")" || return 1
  go_wait_healthy "${idle}" 60 || return 1
  echo "${idle}" > .go-slot
  docker compose --profile go stop "$(go_svc "${live}")" || true
}
```
   Open question 2 says when this is wrong; the executor does not resolve it.
5. **Message.** Add to the end of the success branch of `rollback`'s `public_ok` check: `echo "Migrations that already ran were NOT undone; they are add-only, so the previous image works on them." >&2`.
6. **ENVIRONMENT.md** row: `UBYHOST_HEARTBEAT_DEPLOY_URL`, unset, "deploy.sh posts `<url>/fail` with the failing step when a deploy fails".

## 5. Do not touch

The `:previous` tagging (lines 215 to 221), `public_ok`, the 1830 rotation block, the Caddyfiles, any migration, `App/`, `go/`.

## 6. Commands

- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`
- `bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30`
- `cd App && .venv/bin/python -m pytest $(ls tests/test_pg_*script*.py) -q --tb=short -x 2>&1 | tail -30`
- `grep -cF 'rollback ' deploy/lightsail/scripts/deploy.sh | tail -30`: every call passes a step name (`grep -nE '^\s+rollback$' deploy/lightsail/scripts/deploy.sh` prints nothing).

## 7. Acceptance

- [ ] No bare `rollback` call remains; steps named: `caddy-validate`, `caddy-reload`, `health-wait`, `public-check`, `public-smoke`, `smoke-registration`.
- [ ] shellcheck and `bash -n` green; diff lists only §3 paths.
- [ ] The rollback text states that migrations are not undone.

## 8. Stop and ask

An anchor not found; `source` of `go-slot.sh` fails shellcheck at error level; a file outside §3; a test fails twice; 25 tool calls.

## 9. Report

`docs/tasks/1832-report.md`, 600 tokens at most.

## 10. Staging first, owner steps

1. Owner: create a healthchecks.io check (or the existing heartbeat service), put its URL in staging `.env` as `UBYHOST_HEARTBEAT_DEPLOY_URL`.
2. Deploy staging from this branch (green path): no alert.
3. Force each failure once on staging (mock only): (a) add a deliberate typo to `caddy/Caddyfile.active` source on a throwaway branch, expect `caddy-validate` alert; (b) point `UBYHOST_PUBLIC_BASE_URL` at a wrong host for one run, expect `public-check` alert and rollback to the previous image (`docker compose ps` shows the old image id). Each run: one alert naming the right step.
4. Production only after all of the above.

## Rollback

Revert the PR. The old `rollback()` returns.

## Open questions for the orchestrator

1. Alert channel: the heartbeat URL (chosen, no new vendor) or e-mail to `UBYHOST_OPERATOR_EMAIL` through SES from the server? The plan says "alert with the failing step" without a channel.
2. A failure after the Go slot switch but with a Python-only fault: `go_rollback_slots` then swaps Go back for no reason. Acceptable (both are the previous good release) or should rollback only touch Go when the failing step is Go-related? Not decidable from the files.
3. The worker (`worker` service) shares the Python image, so rolling back `ubyhost:local` also rolls the worker back at `up -d --no-build`. Confirm nothing about the worker needs its own step (not read here).
