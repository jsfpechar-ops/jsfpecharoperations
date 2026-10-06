# 0002: Login e-mail on every account

Status: review
Depends on: none | Base commit: main @ pull | Branch: task/0002-account-emails
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective
Add a required login e-mail to every host account, with admin set/change (reason, audit, notices) and a “missing e-mail” banner on Users. This unblocks e-mail link login in task 0003.

## 2. Context
Follow AGENTS.md (auth row: SECURITY, rules secrets). Plan patches: docs/docs/plans/magic-link-passkeys/HANDOFF.md “Cursor prompt: task 0002”. Apply only patch `0001-0002-login-e-mail-on-every-account.patch` via `git am` — do not rewrite.

## 3. Files
Only paths changed by the patch, plus `docs/tasks/0002-report.md`, `docs/context/status.md`, and this brief.

## 4. Steps
1. `git checkout main && git pull --ff-only origin main`
2. `git checkout -b task/0002-account-emails`
3. `git am docs/docs/plans/magic-link-passkeys/0001-0002-login-e-mail-on-every-account.patch` — if it fails, STOP (§8).
4. `pip install --require-hashes -r App/requirements.lock`
5. From `App/`: `.venv/bin/python -m pytest tests -q`
6. Repo root: `python3 scripts/context_lint.py`
7. UI changed: run `test_host_geometry` with **0 skipped**; screenshots of `/admin/users` at 360, 390, 1280 px (attach in report).
8. Write report (§9), update status.md (5 lines max in Now/Next), open one PR. Never `git add -A`; never push to `main`.

## 5. Do not touch
Anything outside the patch except one minimal fix per failing test (each listed in report). No new dependencies. No tasks 0003–0005.

## 6. Commands
As in §4; pytest must pass; geometry/browser 0 skipped where run.

## 7. Acceptance
- [ ] Patch applied cleanly
- [ ] Full pytest green; context lint OK
- [ ] test_host_geometry 0 skipped; admin Users screenshots at three widths
- [ ] PR open on `task/0002-account-emails`

## 8. Stop and ask
Patch does not apply; any test fail/skip; third-party network request (Turnstile excepted); need change outside patch scope.

## 9. Report
Per TEMPLATE §9: diff stat, command tails, §7 ticks, deviations, owner merge step only.

Risks: admin Users UI; mail notices on e-mail change.
Owner steps: merge on green, deploy, fill all account e-mails (including admin) before starting 0003.
