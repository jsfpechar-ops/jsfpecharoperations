# 1092: close the party count hole (one count writer, floor, lock, full-group check in /save)

Status: todo
Tier: A | Depends on: none | Base commit: 39962ad7 | Branch: claude/1092-party-count-hole
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a strict fresh Fable diff review before the PR opens, on filing safety and the lock.
Report: docs/tasks/1092-report.md

## 1. Objective

Close the live filing hole found by the Fable review of the head-count-change plan (owner project files `plans/head-count-change.md`, not in the repo; sections 1 and 3, the H1 parts that need no new feature). It ships now, with no feature flag:

1. Every write of `reservation.declared_guests` by a guest goes through one function. It never sets a number below the stay's live guest rows (registered or started, the floor, never below 1) or above 60 (the ceiling). It runs under `db.lock_key(cur, "reservation", id)` inside `db.immediate()`, and writes one audit row per write.
2. `claim.start_claim` no longer writes the count before the e-mail is confirmed. The typed number waits on the claim row and is applied, with the same floor, by `claim.confirm`.
3. `/save` refuses a NEW guest row when the group is full, under the same lock, with the reservation read fresh inside the lock.

**Tier A, filing HIGH RISK:** today a claimed lead (or, with mail off, anyone with link and PIN) can post `party_size=1` with 3 people registered. `_set_declared_guests` then calls `submit_stay_if_complete`, which in `immediate` mode files the stay at once with people missing. After this brief that post is refused. When in doubt, refuse the write and keep the old number.

No UI, no template, no copy, no Go change, no migration.

## 2. Context

Verified on 39962ad7 (the lines the source plan gives are older; use these):

| Where | What |
|---|---|
| `App/app/routes/guest.py:1186-1198` | `_set_declared_guests`: skips when `expected_guests_override` is set; checks only 1-60; `db.update`; then `reporting.submit_stay_if_complete`. No floor, no lock, no audit |
| `guest.py:1604-1714` | `POST /l/{token}/{id}/party`. Mail off: 1624-1641 writes with link and PIN only. E-mail given, or not claimed: 1646-1697 calls `claim.start_claim`. Claimed with session: 1699-1714 |
| `guest.py:1717-1746` | `POST /another`: `_set_declared_guests(reservation, min(current + 1, 60))` (called outside the threadpool) |
| `guest.py:1885-1892` | `GET /new`: "full" when `filled >= expected` (`filled` = complete forms, `reporting.py:453`) |
| `guest.py:2145` `/save`; 2238-2240, 2317-2318 | first form with no count: checks and writes `party_size`, using the `reservation` read at request start |
| `guest.py:2369-2382` | the new-row path DOES re-check `filled >= expected` (correction of the review), but with no transaction or lock, on the stale `reservation`, then `db.insert("guest")`. Two phones still both pass |
| `guest.py:2401-2408` | after a save: `submit_stay_if_complete`, `door_codes.on_registration_complete`, `maybe_notify_completion` |
| `App/app/claim.py:226-336` | `start_claim`: 279-294 writes `reservation_claim.declared_guests`; 296-301 writes `reservation.declared_guests` before confirmation. Also reachable on a CLAIMED stay by anyone who types the lead's e-mail (resend path, `guest.py:1646`, no claim session needed) |
| `claim.py:339-369` | `resend_to_verified_email` (host button) passes `_declared_count` back into `start_claim` |
| `claim.py:654-695` | `confirm`: the UPDATE's `rowcount == 1` means this call spent the link |
| `App/app/reporting.py:350-354`, 395-453, 1025 | `expected_guest_count`; `reservation_progress`; `submit_stay_if_complete` |
| `App/app/routes/admin.py:3920-3951` | host "remove empty slot": floor = live guest rows (`archived_at IS NULL`). Do not change; copy its floor |
| `App/app/db.py:951-965`, 868-875, 1978-1995, 2087-2093, 2138 | `immediate`, `lock_key` (used for `guest` and `submit_apartment`, never `reservation`); a nested block on the same thread opens a new connection and on SQLite waits for the outer write lock, so `db.insert` and `db.audit` inside an `immediate()` block deadlock; `insert`; `update_in`; `audit` |

Choice for `start_claim` (owner rule 1, filing first): **apply at confirm**, not "same floor before confirm". A floor alone still lets someone with no e-mail proof move the count inside `[floor, 60]`, and lowering to the registered number files at once in `immediate` mode. With mail on, `/save` already needs a claim session, so nobody registers before confirm and nothing is lost by waiting.

[UBYPORT_CORE](../UBYPORT_CORE.md#features-that-must-stay-aligned-with-filing): no UbyPort call inside `db.immediate()`. All submit and mail calls run after the block commits.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/headcount.py` | create | `MAX_GUESTS = 60`; `live_guest_rows(cur, reservation_id)`; `apply_declared_in(cur, reservation_id, count) -> (code, old)`; `set_declared_guests(reservation_id, count, *, source, owner_user_id) -> str` |
| `App/app/db.py` | edit | `insert_in(cur, table, values) -> Optional[int]`, `insert()` on a cursor from `cursor()`/`immediate()` (same `_write_values`, `RETURNING id`, `fetchall`) |
| `App/app/routes/guest.py` | edit | `_set_declared_guests` and its four callers; `/new` full check; `/save` new-row path |
| `App/app/claim.py` | edit | `start_claim` stops writing `reservation`; `confirm` applies the pending count |
| `App/tests/test_party_count_1092.py` | create | section 4 step 4 |
| `docs/tasks/1092-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1092 step k`)

1. Confirm with `grep -nF` the anchors `def _set_declared_guests`, `"/l/{token}/{reservation_id}/party"`, `{"declared_guests": party_size, "updated_at": now}`, `return cur.rowcount == 1`, `fresh = reporting.reservation_progress(reservation)`, `def lock_key`. One missing: STOP. Run the section 6 rows: green before you start.
2. **`headcount.py` and `db.insert_in`.** `apply_declared_in` on an open `immediate()` cursor: `db.lock_key(cur, "reservation", id)`; read `status, archived_at, expected_guests_override, declared_guests` fresh; return, in this order, `stay_gone` (not active or archived), `host_set` (override set; no write, as today), `out_of_range` (count < 1), `above_ceiling` (> 60), `below_floor` (count < max(1, live rows)), `unchanged`, else `db.update_in` and `saved`. Live rows = `guest` rows with `archived_at IS NULL`, the admin floor. `set_declared_guests` opens `db.immediate()`, calls it, and after commit: on `saved` or `below_floor` writes `db.audit("reservation_declared_guests_set" or "..._refused", f"id={id} from={old} to={count} source={source}", actor="guest", owner_user_id=...)` (numbers only, no personal data); on `saved` calls `reporting.submit_stay_if_complete` as today. No other call (door code, bill) is added.
3. **Wire it.**
   - `_set_declared_guests` becomes a thin wrapper over `set_declared_guests` returning the code. `/party` mail-off and claimed branches: any code other than `saved`, `unchanged`, `host_set` redirects with the existing `&party_error=1`. `/another`: source `another`, through `run_in_threadpool`.
   - `start_claim`: delete the `reservation` write (296-301). On a first claim (state not CLAIMED) the typed `party_size` stays in `reservation_claim.declared_guests`; on a CLAIMED stay (resend, host resend) store NULL there, so a resend link never changes the count. `confirm`: only when `rowcount == 1` and the claim row's pending count is set, call `set_declared_guests(..., source="claim_confirm")` after the UPDATE's block, then set the pending column to NULL. `below_floor` keeps the old count.
   - `/save` new-row path: one `db.immediate()` block: `lock_key`; re-read the reservation; on a first form with no count, `apply_declared_in(party_size)`, any refusal returns the existing redirect to the stay page; then "full" when `expected is not None and live rows >= expected` returns the same redirect; else `db.insert_in(cur, "guest", payload)`. Audit, passport photo, submit, door code and mail calls stay after the block, in today's order. Existing-row edits are unchanged.
   - `GET /new` (1885-1892): use the same "full" rule (live rows), so the page and the save agree.
4. **Tests** in `test_party_count_1092.py` (fixtures as in `test_claim_resend_complete.py` and `test_endtoend.py`):
   - Floor: 3 live rows (2 complete, 1 started), claimed `/party` with 2 and with 1: refused, count unchanged, one `_refused` audit row. With 3: saved, one `_set` audit row whose detail holds only numbers.
   - Ceiling: 61 and 0 refused; 60 saved; `/another` at 60 stays 60. Host override set: no write, no audit.
   - Mail off: the same floor on the open `/party`.
   - Unconfirmed claim: `start_claim` with 1 leaves `reservation.declared_guests` unchanged; after `confirm` it is 1 when no rows exist; with 2 rows it stays as it was. A CLAIMED stay: `/party` with the lead's e-mail and a new count, no claim session: count unchanged, also after that link is confirmed.
   - Never filed below the floor: `immediate` apartment, 2 complete rows, declared 3, `/party` with 1: refused and no submission or claim row is created. Run `submit_stay_if_complete` afterwards: still nothing filed.
   - Two phones: phone A opens `/new` with one free slot, phone B saves the last person, phone A saves: redirected, no new row, live rows == count. A spy on `db.lock_key` sees `("reservation", id)` in `/save`, `/party`, `/another` and `confirm`. If `test_db_postgres.py`'s environment is present, add a threaded race there (two saves, one slot: exactly one row).
   - Lowered then saved: declared 3, lowered to 2 with 2 rows, a third `/save`: refused.
   An old test that now fails on purpose (for example one that relied on the pre-confirm count or on `filled` in `/new`): change it only if the failure is this brief's rule, and name it in the report.
5. Run section 6, then write the report.

## 5. Do not touch

Templates, CSS, i18n and copy; `go/`; migrations and `pg_schema.py`; `reporting.py` (call it, do not change it); `routes/admin.py`; `stays_export.py`; `retention.py` (no new personal data: audit details hold numbers only); any dependency. No feature flag. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`, the [test-map](../context/test-map.md) rows "Filing, UbyPort, worker, claim", "Database, migrations", and the non-browser part of "Guest pages":
- `.venv/bin/python -m pytest tests/test_party_count_1092.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py tests/test_overview_headcount.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x --ignore-glob='*browser*'`

Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. No template changed, so the guest browser and geometry tests and the 390 px shots are not needed (rule 7); CI runs them.

## 7. Acceptance

- [ ] `grep -n '"declared_guests"' App/app --include=*.py -r` shows writes only in `headcount.py` (plus `demo.py` and schema).
- [ ] No guest post can set the count below the live rows or above 60; every write and refusal has one audit row with numbers only.
- [ ] `start_claim` never writes `reservation`; only a confirmed first claim applies its count, under the floor.
- [ ] `/save` inserts a new row only inside the locked block after the fresh full check; `/new` uses the same rule.
- [ ] No UbyPort, mail or door-code call inside `db.immediate()`.
- [ ] All section 6 rows green. `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the fix needs a migration, a template or a Go change; an existing test needs the old pre-confirm count for a reason that is not this brief's rule; the SQLite suite deadlocks in the new block; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1092-report.md`, 400 tokens at most: files, each command with its last 5 lines, section 7 ticked, tests added and old tests changed, deviations and questions. Set this brief `Status: review`. After the strict fresh Fable review, open one PR. Body: server only, no UI, no new request, no new personal data; the filing hole it closes. Merge only with `scripts/merge-pr-on-green.sh`.
