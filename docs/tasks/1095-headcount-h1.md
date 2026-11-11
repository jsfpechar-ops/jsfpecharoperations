# 1095: head-count H1, the server count rule (lead reduction, one rule in Python and Go)

Status: review
Tier: A | Depends on: 1092 (merged), 1094 report (PR #893) | Base commit: 30a2ef45 | Branch: claude/1095-headcount-h1
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a strict fresh Fable diff review before the PR opens, on filing timing, the lock and Python and Go agreeing.
Report: docs/tasks/1095-report.md

## 1. Objective

Brief H1 of the owner's head-count change plan (owner project files `plans/head-count-change.md`, not in the repo: sections 2, 3, 6, 8, 9; owner answers 2026-11-10 18:01, Q12 allows a small Go change in this PR). The read-only H0 answers are `docs/tasks/1094-report.md` (PR #893). Where H0 corrects the plan, H0 wins.

Build the server rule only. The guest pages are H2a.

1. **Store a lead reduction apart from the host's number.** The new columns are `reservation.lead_reduced_guests`, `lead_reduced_from`, `lead_reduced_at` and `lead_reduced_changes`. The expected count is the lower of the base count (the host override when non-zero, else the declared count) and the reduction.
2. **One rule everywhere.** Python's `expected_guest_count` and every copy H0 lists (`claim.py:361`, `stays_export.py:56`, the admin SQL, the claim-form prefill, Go `recover.go` and `progress.go`) give the same number. One shared test table of (host count, lead count, reduction) to the expected number is read by the Python and the Go tests.
3. **One lead change function.** `headcount.change_by_lead` lowers or restores under `db.lock_key(cur, "reservation", id)`, with a floor, a ceiling, a cut-off, a cap on changes, a stale check, one audit row and, after the commit, the three completion calls. The function has one POST route and no template.
4. **Host edits clear the reduction.** The host's "remove empty slot" also runs the three completion calls (owner Q7).

**Feature flag.** `UBYHOST_HEADCOUNT_LEAD_LIVE`, default off, stays off until H3 merges. While it is off, the new route returns 404 and `change_by_lead` writes nothing. `/party` gets no cut-off, and the host's "remove empty slot" keeps today's single submit call. With the flag off, no stay can get a reduction. Every code path below must then act as it does today, byte for byte. The plan's hole-closing parts (the floor on `/party` and on `start_claim`) already shipped in 1092 (H0 (b): "closed by 1092"). This brief adds no code for them, only one pin test in step 9. The `/party` claim check when mail is off belongs to H2a (H0 "Needs a code change"), not here.

**UbyPort filing correctness beats every other goal here** (AGENTS rule 1, [UBYPORT_CORE](../UBYPORT_CORE.md)). The count never goes into the UbyPort payload. No guest row is written by a count change. An existing `registration_completed_at` never moves. A stay without a reduction must file at exactly the same moment, with exactly the same people, as on 30a2ef45. When in doubt, refuse the change and keep the old number.

The work has no new dependency, no new outbound request and no new personal data. The new columns hold numbers and one time. The only template edit is the value on `guest/claim.html:36`.

## 2. Context

Every anchor below was confirmed with grep on 30a2ef45:

| Where | What |
|---|---|
| `App/app/reporting.py:420-424` | `def expected_guest_count(reservation)`: `if reservation["expected_guests_override"]: return ...override`, else `declared_guests`. THE rule |
| `App/app/headcount.py` (120 lines, from 1092) | `MAX_GUESTS = 60`; codes `SAVED UNCHANGED HOST_SET STAY_GONE OUT_OF_RANGE ABOVE_CEILING BELOW_FLOOR`; `ACCEPTED`; `live_guest_rows(cur, id)`; `apply_declared_in(cur, id, count)` (lock, `SELECT status, archived_at, expected_guests_override, declared_guests FROM reservation WHERE id = ?`, checks, `db.update_in`); `record(...)`; `set_declared_guests(...)` (block, then `record`, then `submit_stay_if_complete`) |
| `App/app/claim.py:361-366` | `def _declared_count(reservation, row)`: override first, then `reservation_progress(...)["expected"]`, then `row["declared_guests"]`, then 1. Called at `claim.py:354` (host resend) |
| `App/app/claim.py:786` | `def maybe_notify_completion(reservation, apartment, *, force: bool = False)`: the bill, sent only when registered >= count |
| `App/app/door_codes.py:1248` | `def on_registration_complete(reservation_id: int)` |
| `App/app/stays_export.py:56` | `guests = row["expected_guests_override"] or row["declared_guests"]` (rows from `SELECT r.*, ...` at :27) |
| `App/app/routes/admin.py:4112-4142` | `reservation_remove_empty_slot`: `UPDATE ... AND COALESCE(NULLIF(expected_guests_override, 0), declared_guests) = ? ...` (:4133), then audit `reservation_headcount_corrected`, then only `submit_stay_if_complete` |
| `admin.py:4066-4090` `reservation_update`; `admin.py:4145-4163` `reservation_quick_edit` | host writes `payload["expected_guests_override"] = expected` (:4086, :4162). `admin.py:3871` is the INSERT of a new stay (no reduction exists yet: leave it) |
| `App/app/routes/guest.py:1243-1257` | `_require_claim_session`: mail off returns None; host owning the flat returns None; else claim cookie or 303 |
| `guest.py:726` | `def _host_owns_apartment(request, apartment)` |
| `guest.py:1490-1497` | claim-form prefill: `if claim_view.get("declared_guests") is None: claim_view["declared_guests"] = reservation["declared_guests"]` |
| `guest.py:1518-1522` | renders `guest/assigned.html` from the same context |
| `guest.py:1686-1702` | `/party` preamble: `_language`, `_open_link`, `_require_pin`, `_reservation_for_guest`, `_throttle_guest_post(request, token, "guest_party", lang)`, `await request.form()` |
| `guest.py:2590-2608` | `/save` of a NEW person (from 1092): `db.lock_key(cur, "reservation", reservation_id)`, then `refused = fresh["expected"] is not None and fresh["filled"] >= fresh["expected"]` from `reservation_progress(fresh_row)` (`SELECT *`). The plan's "count check in the save" is already there and reads the rule: do not add one. With a reduction it refuses a person above the reduced number, so raising back must always stay possible |
| `guest.py:1831-1845` | `/another`: no-op when the host set a count; else posts `progress["expected"] + 1` through `headcount.set_declared_guests` |
| `guest.py:2668-2675` | after a save: `submit_stay_if_complete`, `door_codes.on_registration_complete`, `claim.maybe_notify_completion(db.query_one("SELECT * FROM reservation WHERE id = ?", ...), apartment)` |
| `App/app/templates/guest/claim.html:36` | `value="{{ claim.declared_guests or reservation.expected_guests_override or 1 }}"` |
| `App/app/templates/guest/archive/ticket-wallet/claim.html:40` | an archived copy of the line above; no route renders it. Leave it |
| `App/app/templates/guest/assigned.html:33` | hidden `party_size` = `{{ claim.declared_guests or 1 }}` |
| `App/app/config.py:365` | `DOOR_CODES_LIVE = os.environ.get("UBYHOST_DOOR_CODES_LIVE", "0") in ("1", "true", "yes")`: the flag pattern |
| `docs/ENVIRONMENT.md:167` | the `UBYHOST_DOOR_CODES_LIVE` table row |
| `App/app/retention.py:91` | the comment line for `reservation_claim.fee_*` (non-personal columns): the pattern |
| `App/app/booking_site.py:23,220` | `PRAGUE = ZoneInfo("Europe/Prague")`; `datetime.combine(date.fromisoformat(check_in), time(int(checkin_hour)), PRAGUE)` |
| `App/app/migrations/0043_guest_signed_for.sql`, `App/migrations_pg/00014_guest_signed_for.sql` | last migrations. Next: SQLite `0044`, goose `00015` with `schema_migrations` version 44. Go tests apply the goose Up sections (`go/internal/jobs/queue_test.go:172`) |
| `go/internal/ubyport/recover.go:167-188` | `RefreshRegistrationCompletedAt`: `var override, declared *int64`; SELECT `... expected_guests_override, declared_guests FROM reservation WHERE id = $1`; `.Scan(&dateFrom, &dateTo, &existing, &override, &declared)`; `expected := declared; if override != nil && *override != 0 { expected = override }`. This decides the filing time |
| `go/internal/ubyport/recover_test.go:148,180` | `refreshFixture(t, pool, declared any, filed, blank int, updated string, existing any) int64`; `TestRefreshRegistrationCompletedAt` table (no override field) |
| `go/internal/calendar/progress.go:66-75,88-100` | `type stayRow` (`declared *int64`, `override *int64`); `func expectedCount(stay stayRow) *int` |
| `go/internal/calendar/handler.go:173,191-192` | SELECT `r.source, r.declared_guests, r.expected_guests_override, a.checkin_hour::text, ...`; `rows.Scan(... &s.source, &s.declared, &s.override, &s.checkinHour, &s.checkoutHour)` |
| `go/go.mod:1` | `module github.com/jsfpechar-ops/jsfpecharoperations/go` |

**Cut-off.** The lead may change the count until the flat's check-in time on arrival day, Europe/Prague. When `apartment.checkin_hour` is empty, the cut-off is midnight at the start of arrival day (plan section 2, the stricter reading). H0 (d) recommends 15:00 instead; that choice is with the owner (section 8). The hour lives in ONE constant, `headcount.NO_HOUR_CUTOFF_HOUR = 0`, read in one place (`lead_cutoff`), so the owner's answer is a one-number change. A cut-off only ever refuses a change. The cut-off and the change cap apply to lowering only: raising is never blocked by either, because `/save` refuses a new person above the count (`guest.py:2608`) and a blocked raise would keep a real person from being registered and filed. When the cut-off cannot be worked out (bad date or hour), lowering is refused and raising passes.

**Deploy order.** Production runs on SQLite (rules: database); the Go worker reads Postgres only. The app does not start while a goose file is pending, and 00015 is additive, so the old image keeps working on the new schema. Old rows get NULL, NULL, NULL and 0: the rule returns today's number for every one of them.

**Lock order and blocks** (as in 1092): a block takes `("reservation", id)` and no other `lock_key`. Inside `db.immediate()`, use only `cur` (`cur.execute`, `db.update_in`): no `db.query*`, `db.update`, `db.audit` or `reporting.*` that opens a connection. The audit, the submit, the door-code call and the mail all run after the block commits. No UbyPort call inside a block.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0044_lead_reduced_guests.sql` | create | step 2 |
| `App/migrations_pg/00015_lead_reduced_guests.sql` | create | step 2 |
| `App/app/config.py` | edit | `HEADCOUNT_LEAD_LIVE` after line 365 |
| `docs/ENVIRONMENT.md` | edit | one row after line 167 |
| `App/app/retention.py` | edit | one comment line after line 91 |
| `App/app/reporting.py` | edit | `expected_guest_count` only |
| `App/app/headcount.py` | edit | reduction handling in `apply_declared_in`; `lead_cutoff`; `change_by_lead_in`; `change_by_lead` |
| `App/app/claim.py` | edit | `_declared_count` only |
| `App/app/stays_export.py` | edit | line 56 only |
| `App/app/routes/admin.py` | edit | `reservation_remove_empty_slot`, `reservation_update`, `reservation_quick_edit` |
| `App/app/routes/guest.py` | edit | claim prefill (1495-1496); new `POST /l/{token}/{reservation_id}/count` |
| `App/app/templates/guest/claim.html` | edit | line 36 value only |
| `go/internal/headcount/headcount.go` | create | `Expected` |
| `go/internal/headcount/headcount_test.go` | create | reads the shared table |
| `go/internal/headcount/testdata/cases.json` | create | THE shared table |
| `go/internal/ubyport/recover.go` | edit | SELECT, Scan, the rule |
| `go/internal/ubyport/recover_test.go` | edit | reduction cases |
| `go/internal/calendar/progress.go`, `handler.go`, `calendar_test.go` | edit | `reduced` field, SELECT, Scan, `expectedCount`, one test |
| `App/tests/test_headcount_1095.py` | create | step 9 |
| `docs/tasks/1095-report.md` | create | the report, and set this brief `Status: review` |

Overlap (context lint): older open briefs that name `claim.py`, `config.py`, `retention.py`, `routes/admin.py`, `routes/guest.py` or `ENVIRONMENT.md` do not go first; this brief runs on 30a2ef45 and its anchors are the guard.

## 4. Steps (commit after each: `1095 step k`)

1. **Anchors.** Use `grep -nF` to confirm each of these strings on your base:
   - `def expected_guest_count(reservation)`
   - `def apply_declared_in(cur, reservation_id: int, count: int)`
   - `def _declared_count(reservation, row)`
   - `guests = row["expected_guests_override"] or row["declared_guests"]`
   - `AND COALESCE(NULLIF(expected_guests_override, 0), declared_guests) = ? `
   - `claim_view["declared_guests"] = reservation["declared_guests"]`
   - `claim.declared_guests or reservation.expected_guests_override or 1`
   - `expected := declared`
   - `func expectedCount(stay stayRow) *int`
   - `r.source, r.declared_guests, r.expected_guests_override`
   - `DOOR_CODES_LIVE = os.environ.get`

   If one is missing, STOP. Run section 6: it must be green before you start.
   Then run `grep -rn 'expected_guest_count(\|reservation_progress(' App/app --include=*.py | grep -v 'def ' | head -40`. List in the report every caller whose row comes from a SELECT that names columns instead of `*`. Add `lead_reduced_guests` to each such SELECT in step 3. Also run `grep -n 'def refresh_registration_completed_at' -A40 App/app/reporting.py | grep -n 'override\|declared' | head`. A copy of the rule there must change too; if it is not reachable through `expected_guest_count`, STOP.
2. **Migration.** `0044_lead_reduced_guests.sql`, in the 0043 style:
   ```sql
   -- Brief 1095: the lead guest's lower head count, kept apart from the host's number.
   -- Numbers and one timestamp, no personal data; deleted with the reservation row.
   ALTER TABLE reservation ADD COLUMN lead_reduced_guests INTEGER;
   ALTER TABLE reservation ADD COLUMN lead_reduced_from INTEGER;
   ALTER TABLE reservation ADD COLUMN lead_reduced_at TEXT;
   ALTER TABLE reservation ADD COLUMN lead_reduced_changes INTEGER NOT NULL DEFAULT 0;
   ```
   Write `00015_lead_reduced_guests.sql` as a copy of 00014's shape: `-- +goose Up`, the "Twin of ..." line, the same four columns with `ADD COLUMN IF NOT EXISTS` and the same types as above (`INTEGER`, `INTEGER`, `TEXT`, `INTEGER NOT NULL DEFAULT 0`), then `INSERT INTO schema_migrations (version, name, applied_at) VALUES (44, 'lead_reduced_guests', '2026-11-10T00:00:00+00:00') ON CONFLICT (version) DO NOTHING;`. Under `-- +goose Down`, delete version 44 and run `DROP COLUMN IF EXISTS` for each column. Leave `db.SCHEMA` and `db.ADDED_COLUMNS` unchanged (rules: database). No backfill, no UPDATE of old rows, no index, no change to an existing column. If `test_migrations.py` asks for a `db.SCHEMA` edit, STOP.
   Then add the flag. In `config.py` after line 365: `HEADCOUNT_LEAD_LIVE = os.environ.get("UBYHOST_HEADCOUNT_LEAD_LIVE", "0") in ("1", "true", "yes")`. Read it at call time as `config.HEADCOUNT_LEAD_LIVE`, so tests can monkeypatch it. In `ENVIRONMENT.md`, add this row after 167: `| UBYHOST_HEADCOUNT_LEAD_LIVE | 0 | 1, true or yes lets a lead guest lower the head count (brief 1095). Leave off until the host notice (H3) is live. |`, formatted with backticks like the row above it. In `retention.py`, add after line 91: `# reservation.lead_reduced_* (brief 1095) hold numbers and a timestamp, are not personal data and go with the reservation row.`, formatted like line 91.
   Command: `.venv/bin/python -m pytest tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`. Expected: green.
3. **The rule** in `reporting.py:420`. The base is what the function returns today. Read the reduction inside `try: reduced = reservation["lead_reduced_guests"]` / `except (KeyError, IndexError): reduced = None` (a dict raises the first, `sqlite3.Row` the second; a row from an old SELECT then acts as today). If the reduction is truthy and (the base is None or the reduction < the base), return the reduction; otherwise return the base. A reduction never raises the number and a 0 or NULL reduction is ignored. Write a docstring of one line. Add the column to the SELECTs found in step 1. Touch nothing else in `reporting.py`: `refresh_registration_completed_at` (:1031) and `submit_stay_if_complete` (:1098) read `SELECT *` and get the rule through `reservation_progress`.
4. **Copies.**
   - `claim.py:_declared_count`: the body becomes `expected = reporting.expected_guest_count(reservation)` and `return int(expected or row["declared_guests"] or 1)`. This is the same result for every stay without a reduction, because `expected_guest_count` already puts the override first.
   - `stays_export.py:56`: `guests = reporting.expected_guest_count(row)`. Import `reporting` if it is missing. If the import makes a cycle, STOP.
   - `guest.py:1495-1496`: when the claim row holds no count, the prefill becomes `reporting.expected_guest_count(reservation)` (a lead who claims again on a new phone keeps the reduction, plan section 8). `claim.html:36` becomes `value="{{ claim.declared_guests or 1 }}"`, the same precedence as `assigned.html:33`, which is not changed (it gets the same `claim_view`; check with `grep -n '"claim": claim_view' App/app/routes/guest.py`; if it is missing, STOP).
   - `admin.py:4133`: put this expression in place of `COALESCE(NULLIF(expected_guests_override, 0), declared_guests)`: `CASE WHEN lead_reduced_guests IS NOT NULL AND lead_reduced_guests > 0 AND lead_reduced_guests < COALESCE(NULLIF(expected_guests_override, 0), declared_guests) THEN lead_reduced_guests ELSE COALESCE(NULLIF(expected_guests_override, 0), declared_guests) END`. It is portable SQL with no `LEAST`. The SET also clears the reduction: `lead_reduced_guests = NULL, lead_reduced_from = NULL, lead_reduced_at = NULL`. After the existing submit call, and only when `config.HEADCOUNT_LEAD_LIVE` is on, run `door_codes.on_registration_complete` and `claim.maybe_notify_completion` (fresh row) in the threadpool, in the order of `guest.py:2668-2675` (owner Q7).
   - `reservation_update` and `reservation_quick_edit`: when the loaded reservation has a truthy `lead_reduced_guests`, compare the posted override with `reporting.expected_guest_count(reservation)`. If they are equal, remove `expected_guests_override` from the payload, because the host only re-saved the number shown and the reduction stays. If they differ, add the three `lead_reduced_*` = None to the payload (the host edit clears the reduction; `lead_reduced_changes` is kept). `reservation_update` needs the row: use the return value of `access.reservation(...)` instead of only testing it.
5. **`headcount.apply_declared_in`** (this is the `/party`, `/another`, first-form and claim-confirm writer):
   - Its SELECT adds `r.date_from, r.lead_reduced_guests, a.checkin_hour` through `LEFT JOIN apartment a ON a.id = r.apartment_id` (LEFT, so a stay never turns into `STAY_GONE` because of the join). Keep `WHERE r.id = ?`, and prefix the old columns with `r.`.
   - Keep the order of today's checks (`STAY_GONE`, `HOST_SET`, `OUT_OF_RANGE`, `ABOVE_CEILING`, `UNCHANGED`, `BELOW_FLOOR`). A stay with a host count still returns `HOST_SET` first and writes nothing, so its reduction stays.
   - After the `UNCHANGED` check, add: if `row["lead_reduced_guests"]` is truthy and `count == row["lead_reduced_guests"]`, return `UNCHANGED`.
   - After the floor check, and only when `config.HEADCOUNT_LEAD_LIVE` is on and `old is not None` and `count < reporting.expected_guest_count(row)` and the cut-off has passed, return the new code `AFTER_CUTOFF = "after_cutoff"`. "Passed" means `lead_cutoff(...)` is None or `_utcnow() >= lead_cutoff(row["date_from"], row["checkin_hour"])`, where `def _utcnow(): return datetime.now(timezone.utc)` is new in `headcount.py` and is the one clock both this check and `change_by_lead` use (tests monkeypatch it). Do not change the signature of `apply_declared_in`. `AFTER_CUTOFF` is not in `ACCEPTED`, so `/party` shows its existing `party_error`; `record` writes no row for it. A first count (`old is None`) and every raise skip this check.
   - On `SAVED`, and only when `row["lead_reduced_guests"]` is not None, the `update_in` payload also sets the three `lead_reduced_*` to None (the base changed). With no reduction, the payload stays exactly `{"declared_guests": count, "updated_at": ...}`.
   - Add the constant `NO_HOUR_CUTOFF_HOUR = 0` with the comment `# Cut-off hour (Europe/Prague) on arrival day when the flat has no check-in hour. 0 = midnight at the start of the day. Owner decision pending (15 is the other choice): change only this number.` Use it in `lead_cutoff` and nowhere else; write no literal midnight anywhere in the code or the tests (tests read the constant).
   - Add `def lead_cutoff(date_from, checkin_hour) -> Optional[datetime]` (aware, Europe/Prague): `datetime.combine(date.fromisoformat(str(date_from)[:10]), time(int(checkin_hour) if checkin_hour not in (None, "") else NO_HOUR_CUTOFF_HOUR), PRAGUE)`, with `PRAGUE = ZoneInfo("Europe/Prague")` defined in `headcount.py`. Do not import it from `booking_site`. On `ValueError` or `TypeError` return None (the caller then refuses lowering; nothing raises inside the block).
6. **`headcount.change_by_lead_in(cur, reservation_id, count, shown, now) -> (code, old_expected)`**, with new codes `LOWERED = "lowered"`, `RESTORED = "restored"`, `STALE = "stale"`, `TOO_MANY = "too_many"` and `MAX_LEAD_CHANGES = 6`. Steps:
   - `lock_key`, then one SELECT through `cur`: the reservation columns of step 5, plus `r.apartment_id, r.lead_reduced_from, r.lead_reduced_changes`.
   - Return, in this order: `STAY_GONE` (not active or archived); `OUT_OF_RANGE` (the current expected is None, or count < 1); `UNCHANGED` (count == current); `STALE` (shown != current); `ABOVE_CEILING` (count > the base, where the base is the rule with no reduction, i.e. the original number); `BELOW_FLOOR` (count < max(1, live rows)); `AFTER_CUTOFF` (count < current and the cut-off has passed, as in step 5, with `now`); `TOO_MANY` (count < current and changes >= `MAX_LEAD_CHANGES`). A raise (count > current, at most the base) passes the cut-off and the cap: it is the undo and must always work.
   - Then write with `db.update_in`. If count == base, set the three `lead_reduced_*` to None. Otherwise set `lead_reduced_guests = count`, `lead_reduced_from = base`, `lead_reduced_at = db.utcnow()`. In both cases set `lead_reduced_changes = changes + 1` and `updated_at`. Every lead change is counted, lowering and raising; only lowering is refused at the cap, so up-down toggling still ends after 6 changes. Return `LOWERED` if count < current, else `RESTORED`.
   - Never write `declared_guests`, `expected_guests_override`, `registration_completed_at` or any guest row.
   Then **`change_by_lead(reservation_id, count, shown, *, owner_user_id, now=None) -> str`**:
   - If `config.HEADCOUNT_LEAD_LIVE` is off, return `"feature_off"` before any block.
   - `now` defaults to `_utcnow()`. Run one `immediate()` block with `change_by_lead_in`; read `apartment_id` from its SELECT inside the block, as `set_declared_guests` does.
   - After the commit, on `LOWERED` or `RESTORED` only: write `db.audit("reservation_headcount_lowered" | "reservation_headcount_restored", f"id={id} from={old} to={count} source=lead", actor="guest", owner_user_id=...)`. Then make the three calls in the order of `guest.py:2668-2675` (submit, door code, `maybe_notify_completion` with a fresh `SELECT *` row and the apartment row). Import `claim` and `door_codes` inside the function, because `claim` imports `headcount`.
   - Write no audit row for any other code.
7. **Route** `POST /l/{token}/{reservation_id}/count` in `guest.py`, next to `/another`. There is no template. It returns:
   In this order:
   - Flag off: 404 at once, before anything else is read.
   - Copy the `/party` preamble from lines 1689-1702 exactly, throttle bucket `"guest_party"` included.
   - `not mail.mail_enabled()` (the test `_require_claim_session` uses at :1244): 404 (no lead, owner Q5).
   - `_host_owns_apartment`: 403 (a host on a guest page does not act as the lead, plan section 8). These two come BEFORE `_require_claim_session`, because that helper lets both through.
   - Call `_require_claim_session`; return its redirect when it gives one.
   - Read the integers `count` and `shown` (a bad value becomes 0).
   - Run `await run_in_threadpool(lambda: headcount.change_by_lead(...))`.
   - Redirect 303 to `_guest_link(token, reservation_id) + _lang_q(lang, f"&count={code}")`. The code is one of the fixed words, never a number or a name. H2a builds the review page that posts here. This is the only new POST in this brief; a test asserts that no other new route exists (`grep -c '@router.post' App/app/routes/guest.py` is the base count plus 1).
8. **Go.**
   - `go/internal/headcount/headcount.go`, package `headcount`, adds `func Expected(override, declared, reduced *int64) *int64`. It mirrors step 3: the base is a non-zero override, else declared (nil stays nil). A non-nil, non-zero reduced value wins when the base is nil or the reduction is smaller than the base. The doc comment names `reporting.expected_guest_count`.
   - `testdata/cases.json` is a JSON list of `{"name", "override", "declared", "reduced", "want"}` (null allowed). It has at least these 12 rows:
     - no count;
     - declared only;
     - override only;
     - override 0 with declared;
     - override wins over declared;
     - reduction below declared;
     - reduction below override;
     - reduction equal to base;
     - reduction above base (base wins);
     - reduction 0 ignored;
     - reduction with override 0 and declared;
     - reduction with no base.
   - `headcount_test.go` loads the file and checks `Expected` against every row.
   - `recover.go`: add `lead_reduced_guests` to the SELECT, `&reduced` to Scan (`var override, declared, reduced *int64`), and replace the four rule lines with `expected := headcount.Expected(override, declared, reduced)`.
   - `recover_test.go`: add a `TestRefreshRegistrationCompletedAtLeadReduction`. Use `refreshFixture` (declared nil, 2 filed, 0 blank, `recent`, existing nil), then `UPDATE reservation SET expected_guests_override = $2, lead_reduced_guests = $3`. Override 4 with reduced 2 gives a new stamp. Override 4 with reduced nil gives none. Then with an existing stamp `old` and a reduction added, the stamp stays `old`.
   - `progress.go`: add `reduced *int64` to `stayRow`. `expectedCount` converts `headcount.Expected(stay.override, stay.declared, stay.reduced)` to `*int`.
   - `handler.go:173`: add `r.lead_reduced_guests` after `r.expected_guests_override`, and `&s.reduced` after `&s.override` in the Scan at :191-192.
   - `calendar_test.go`: add one keyed `stayRow{...}` test of `expectedCount` with a reduction.
   Command: `cd go && gofmt -l . && go vet ./... && go test ./internal/headcount/ ./internal/ubyport/ ./internal/calendar/ -count=1 2>&1 | tail -30`. Expected: no gofmt output, and all tests ok. Without `UBYHOST_TEST_DATABASE_URL`, the DB tests skip: say so in the report (CI runs them).
9. **Tests** in `App/tests/test_headcount_1095.py` (fixtures as in `test_party_count_1092.py`; set `config.HEADCOUNT_LEAD_LIVE` with monkeypatch):
   - **Shared table:** load `go/internal/headcount/testdata/cases.json` (path from `Path(__file__).resolve().parents[2]`). For each row, a dict row gives `reporting.expected_guest_count(row) == want`.
   - **One rule:** for each table row, `claim._declared_count`, the `stays_export` guest column and `reservation_progress(...)["expected"]` agree with `want` (where want is not None).
   - **No copy left:** scan `App/app/**/*.py` and `App/app/templates/**/*.html` for lines holding both `expected_guests_override` and `declared_guests`. The only files allowed are `reporting.py`, `headcount.py`, `db.py`, `demo.py` and `routes/admin.py` (the CASE line). Skip `templates/guest/archive/`. Any other hit fails.
   - **Flag off:** `change_by_lead` returns `feature_off` and writes nothing. The route returns 404. A claimed `/party` lower after the cut-off is still saved, as today. Remove empty slot makes one submit call and no door-code or bill call. `headcount.lead_cutoff` is never called (spy).
   - **No reduction means no change:** for a stay with no reduction, `apply_declared_in`'s UPDATE payload has exactly the two keys of today. `expected_guest_count`, `refresh_registration_completed_at` and `submit_stay_if_complete` give the same stamp and the same submitted guest ids with the flag on and off. A row inserted without the new columns reads back NULL, NULL, NULL and 0.
   - **Lower and restore (flag on, claimed device):**
     - Override 4, 2 complete rows: post 2 with shown 4 gives `lowered`. The override is still 4 and `expected` is 2. One `_lowered` audit row has only `id= from= to= source=lead`.
     - Post 4 with shown 2 gives `restored`: the reduction is cleared and one `_restored` row is written.
     - 5 is `above_ceiling`; 1 is `below_floor`; shown 3 is `stale`.
   - **Double confirm:** the same lowering posted twice. The second post returns `unchanged`, writes no second audit row and calls no second submit.
   - **Cap:** six changes pass (lower, restore, three times). A seventh change that lowers returns `too_many` and writes nothing. After the cap a raise back to the base still returns `restored`, and a new person can then be saved.
   - **A person is never locked out:** with a reduction of 2 and 2 rows, `/save` of a third person is refused as today's full group. After the cut-off and after the cap, the lead's raise passes and the third person saves.
   - **Cut-off:** checkin_hour 14, now one minute before 14:00 Prague on arrival day: lowering passes. One minute after: `after_cutoff`, and raising still passes. With an empty hour the cut-off is `NO_HOUR_CUTOFF_HOUR`:00 on arrival day (the test reads the constant: one minute before passes, one minute after gives `after_cutoff`). `lead_cutoff("bad", 14)` is None and lowering is then refused. The same cut-off applies to claimed `/party` lowering with the flag on; a first count (no count yet) and a `/party` raise pass after the cut-off. Set the clock by monkeypatching `headcount._utcnow`.
   - **Member refused:** link and PIN without the claim cookie get 303 and the count is unchanged. A host session on the guest page gets 403. With mail off: 404.
   - **Two phones:** phone A lowers to 2 (2 rows) while phone B's `/save` of a third person waits on the lock. B is refused with "group is full", or A is refused by the floor, never both written. A spy on `db.lock_key` sees `("reservation", id)` in `change_by_lead`.
   - **Filing:**
     - `immediate` apartment, override 3, 2 complete rows: lowering to 2 files those 2 rows once, outside any block (spy).
     - A SENT row keeps all its columns and gets no new submission.
     - An existing `registration_completed_at` is unchanged after a lower and after a restore.
     - The deadline-cap filing time of a stay is the same with and without a later restore.
   - **Quiet path:** a quiet-complete stay (12 hours, count above the rows) gets the stamp and no bill. A lead lowering after that (before check-in) sends the bill once, and a repeat lowering does not send it again.
   - **Host:**
     - `reservation_update` with a different override clears the reduction.
     - Re-saving the shown number keeps it.
     - "Remove empty slot" on a reduced stay compares against the reduced number, clears the reduction and (flag on) runs the three calls.
   - **New phone:** with a reduction, the claim page prefill shows the reduced number. `claim.confirm` with that number keeps the reduction and the base on both kinds of stay (`apply_declared_in` gives `unchanged` when the guest declared the count, `host_set` when the host set it).
   - **Add another person:** on a stay the guest declared (4, reduced to 2), `/another` ends with expected 3 and the reduction cleared. On a host-set stay it stays a no-op and the reduction stays.
   - **1092 pins** (hole-closing, no flag): one test, parametrized over the flag off and on, re-asserts that claimed `/party` below the live rows is refused and that `start_claim` does not write `reservation`. The floors never read the flag. Do not change the 1092 tests; if one fails, STOP.
   Any old test that now fails on purpose: change it only if the failure is this brief's rule, and name it in the report.
10. Run section 6, take the screenshot (step 11), and write the report.
11. **Rule 7** (the `claim.html` value changed): the guest browser tests with 0 skipped, plus one 390 px screenshot of the claim page with a reduction, in the report.

## 5. Do not touch

- `App/app/ubyport/`, `worker`, `soap.py`, `client.py` and every submission or serializer file.
- `validation.py` and `door_codes.py` (call it, do not change it).
- `claim.py` outside `_declared_count`.
- `reporting.py` outside `expected_guest_count` (plus a column name in a SELECT found in step 1).
- `booking_direct.py`, `booking_webhook.py`, `icalsync.py` (they write the host count at insert only, H0 (c)).
- `App/tests/test_party_count_1092.py` and the rows of the Go table `TestRefreshRegistrationCompletedAt` (add tests, change none).
- `guest.py` routes other than the prefill and the new route, including `/party`, `/another`, `/save` and `/remove` (their behaviour changes only through `headcount.apply_declared_in`).
- All templates except `guest/claim.html:36` (`templates/guest/archive/` included: leave it); CSS; i18n and copy (H2a owns the guest copy, H3 the host side).
- `db.SCHEMA` and `db.ADDED_COLUMNS`; `scripts/pg_schema.py`; every existing migration file.
- `demo.py`.
- Go files outside section 3.
- The guest link, the review and confirm pages and any fee line (H2a); the `/party` claim check when mail is off (H2a); the confirm step for remove, add or edit (H2b); the host digest mail and "Set back" (H3); the nudge (H4).
- Any dependency.
- Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`, the [test-map](../context/test-map.md) rows "Filing, UbyPort, worker, claim", "Database, migrations", "Calendar, iCal feeds" (the dashboard part), "Retention", "Door codes" and "Guest pages":
- `.venv/bin/python -m pytest tests/test_headcount_1095.py tests/test_party_count_1092.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py tests/test_overview_headcount.py tests/test_dashboard_calendar*.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_retention*.py tests/test_door_code*.py -q --tb=short -x` (rows "Retention, privacy, personal data", the retention part, and "Door codes, TTLock": `retention.py` changes and the door-code call gets a new caller)
- `.venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x --ignore-glob='*browser*'`
- `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py -q --tb=short -x -rs` (0 skipped)

From `go/`: `gofmt -l . && go vet ./... && go test ./internal/headcount/ ./internal/ubyport/ ./internal/calendar/ -count=1`. Set `UBYHOST_TEST_DATABASE_URL` to a local Postgres if one is available.
From the repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance

- [ ] **Filing (UBYPORT_CORE "What works means" and "Features that must stay aligned"):** for every stay with no reduction, payloads, the people sent, `registration_completed_at` and the send time are unchanged. This holds in Python and Go, with the flag on and off (step 9 "No reduction means no change", the Go `TestRefreshRegistrationCompletedAt` table unchanged and green).
- [ ] The count is in no UbyPort payload. A count change writes no guest row and never moves an existing `registration_completed_at`.
- [ ] One shared file `go/internal/headcount/testdata/cases.json` is read by both the Python and the Go tests; both are green.
- [ ] `grep -rn 'expected_guests_override' App/app go --include=*.py --include=*.go --include=*.html | grep declared_guests` shows only the allowed files of step 9, the archived template and the Go SELECT lines.
- [ ] With the flag off: route 404, no reduction written, `/party` and remove-empty-slot act as on 30a2ef45. The flag default is off and no file in this PR turns it on. The 1092 floor pins pass with the flag off and on.
- [ ] The cut-off and the cap refuse lowering only; a raise back to the base always passes. The no-hour cut-off is the one constant `NO_HOUR_CUTOFF_HOUR`.
- [ ] Each `immediate()` block uses `cur` only and one `lock_key`. No audit, mail, door-code or UbyPort call is made inside it.
- [ ] Audit details hold numbers and the fixed source word only. The retention line and the ENVIRONMENT row are present.
- [ ] Both migrations are present (0044, 00015/version 44) and additive.
- [ ] All section 6 rows are green, the browser e2e has 0 skipped, and the 390 px claim-page shot is in the report.
- [ ] `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

**STOP and report `blocked`** if any of these happens:
- **Filing path change:** a filing path (who is sent, the send time, `registration_completed_at`, payload) would change for a stay with no reduction.
- **Anchor missing:** an anchor of step 1 is not found.
- **Python and Go disagree:** a Python and a Go result differ on any row of the table.
- **Extra columns needed:** a SELECT feeding the rule cannot take the new column without changing other columns.
- **A person locked out:** any state in which a real person cannot be saved and neither the lead's raise nor the host can lift the count.
- **1092 test fails:** a test in `test_party_count_1092.py`, or a row of the Go `TestRefreshRegistrationCompletedAt` table, fails or needs an edit.
- **Schema:** `test_migrations.py` asks for a `db.SCHEMA` or `pg_schema.py` change, or a migration needs more than the four ADD COLUMN lines.
- **Import cycle:** an import cycle appears that a local import does not solve.
- **Go change too big:** the Go change needs more than the files of section 3.
- **Deadlock:** the SQLite suite deadlocks in a new block.
- **Test fails twice:** a test fails twice on the same cause (attempt 3 of 3).
- **Limit reached:** you reach 60 tool calls or 60k tokens. Finish the current step, commit, and write `Done: steps 1 to k. Left: steps k+1 to n.`

UbyPort filing correctness beats every other goal in this brief: never trade it for a feature, a test or the schedule.

**Owner questions (open, do not block; the flag stays off):**

- **Cut-off when the flat has no check-in hour:** the plan says midnight at the start of arrival day, and this brief uses that. H0 (d) recommends 15:00, the booking site's default. If the owner picks 15:00, change `NO_HOUR_CUTOFF_HOUR` from 0 to 15 and nothing else.
- **Cap of 6:** the plan counts every change. This brief counts every change but refuses only lowering at the cap, so a guest can always be added back and registered. Say so in the report.
- **`/party` after check-in (flag on only):** a claimed lead who lowers through `/party` after the cut-off is refused, where today the lower count could complete the stay at once. The stay is then filed by the quiet path or the deadline cap, as any short stay is today. This is the plan's rule (section 2); name it in the PR body.

## 9. Report

`docs/tasks/1095-report.md`, 500 tokens at most. It holds:
- the files changed;
- each command with its last 5 lines;
- section 7 ticked;
- the callers found in step 1;
- the tests added and the old tests changed;
- the 390 px shot;
- whether the Go DB tests ran or skipped;
- deviations and questions.

Set this brief `Status: review`. After the strict fresh Fable review, open one PR. The PR body says:
- server rule behind `UBYHOST_HEADCOUNT_LEAD_LIVE` (off);
- the small Go change (owner Q12);
- no new request, no new personal data;
- migration 0044/00015.

Merge only with `scripts/merge-pr-on-green.sh`.
