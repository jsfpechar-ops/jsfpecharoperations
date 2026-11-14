# 1526: Smart-locks POST routes (setup, refresh, remove)

Status: blocked — no Go TTLock client exists; the three routes call the TTLock gateway
Depends on: see §2 | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: none until unblocked | Tier B (A where §2 says)

> **One big PR mode.** The owner wants one big pull request. You work on the current branch: commit `1526 step k` after each step that changes a file, never create a branch, never push, never open a PR. The orchestrator merges. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1526 step'` and `git show --stat` on those commits.

## 1. Objective

Port `POST /smart-locks/setup`, `POST /smart-locks/refresh` and `POST /smart-locks/remove` of `admin.py` (lines 729-856).

## 2. Context

Why blocked: the routes call `ttlock.create_account`, `ttlock.check_locks` and `ttlock.delete_account` (`App/app/ttlock.py`, 741 lines: OAuth token handling, encrypted credentials, monthly call budget, lock list parsing). Go has no such client (`grep -ri ttlock go/internal` finds only the palette and the cleaning/customers readers). Porting it means a new outbound client to `https://euapi.ttlock.com` with real credentials and a call budget, which is a port of its own (tier A, door codes are access to guests' homes). The task rule is: make no new outbound request and use no missing helper; so it is not written here.

What is done: `GET /smart-locks` (the redirect) is in brief 1520. Also needed later: `rate_limit.blocked("ttlock_setup", ...)` (5 an hour; the Go helper `rateBlocked` of brief 1523 fits), `db.audit("door_code_terms_accepted")`, `_default_on_first_lock` (admin.py 756-770).

Python for the later brief: `smart_locks_setup` 729-756, `smart_locks_refresh` 776-818, `smart_locks_remove` 820-856, helpers `_smart_locks_return_to`, `_smart_locks_url`, `_smart_locks_section`, `_lock_property_return` (admin.py 185-221).

**Paths.** `/smart-locks/setup`, `/smart-locks/refresh`, `/smart-locks/remove` stay on Python. Do not switch a `/smart-locks/*` prefix after 1520.

## 3. Files

None until unblocked.

## 4. Steps

None. Unblock by a plan for a Go TTLock package (owner decision on the outbound client, its credentials and the budget), then a brief for it, then this port.

## 5. Do not touch

Everything.

## 6. Commands

None.

## 7. Acceptance

None.

## 8. Stop and ask

Do not run this brief.

## 9. Report

None.

## Risk list (for the reviewer)

Not applicable.

## Owner steps

1. Decide whether door codes are ported to Go before Python is retired.
