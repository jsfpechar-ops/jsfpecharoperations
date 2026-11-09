# 1069: F0, read-only check of quiet completion (what the lead gets when not everyone registered)

Status: todo
Depends on: none | Base commit: 0d851ca4 | Branch: claude/1069-f0-quiet-completion-check
Executor: Fable 5.2 (owner override, Tier A, read-only) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Answer, from the code only, what the lead (the person who booked) and the host receive when a stay is treated as complete after 12 quiet hours although fewer people registered than expected (plan P4). The answer decides brief F4; nothing in the code changes.

## 2. Context

Plan: `docs/plans/guest-group-registration.md` section 8 (P1-P6) and section 9 (F0-F6). P4 there says: "If one person never registers, the booking is treated as complete after 12 quiet hours and the door code is made, but no completion mail and no fee request are sent, and the pay box stays hidden. Must be re-checked before build" (`reporting.py:110,958-1006`). This brief is that re-check. Treat the plan's claims as hypotheses, not facts.

Rules that apply: UbyPort filing correctness beats every other feature (`docs/UBYPORT_CORE.md`, "What works means" and "Features that must stay aligned with filing"). Door codes in mail use the secret-marker pattern so the outbox never stores them (`docs/context/rules.md`, Mail). Do not assume the production value of any env var.

### Starting anchors (found by the orchestrator; verify each, quote line numbers from your checkout)

1. The 12-hour constant, `App/app/reporting.py:110`:
   ```
   HEADCOUNT_QUIET_HOURS = 12
   ```
2. The quiet path, `App/app/reporting.py` in `refresh_registration_completed_at` (about 954-1006):
   ```
       forms_settled = (
           bool(progress["guests"])
           and not progress["incomplete"]
           and _forms_quiet_for(progress, HEADCOUNT_QUIET_HOURS)
       )
       complete = declared_filled or forms_settled
   ```
   `_forms_quiet_for` (about 943) uses the newest `updated_at or created_at` of the stay's guest rows.
3. Who runs it when nobody saves a form, `App/app/reporting.py` in `sweep` (about 2214-2224):
   ```
               for pending in db.query(
                   "SELECT id FROM reservation WHERE apartment_id = ? AND status = 'active' "
                   "AND archived_at IS NULL AND registration_completed_at IS NULL",
   ```
   followed by `results = submit_for_apartment(apartment["id"], mode="auto")`. Scheduled by `_job_submit` in `App/app/scheduler.py` (about 189-192); intervals in `job_intervals` (about 84) and the `add_job` calls (about 614-663).
4. Filing gate, `App/app/reporting.py` `due_for_automatic_send` (about 1083): sends only when `registration_completed_at` is set; delay is 0 for `immediate`, else `submit_after_hours or 24`.
5. Completion mail, `App/app/claim.py` `maybe_notify_completion` (about 757):
   ```
       expected = progress["expected"]
       if expected is None or progress["filled"] < expected:
           return
   ```
   Fee block `_completion_fee` (about 372): `if not (apartment["stay_fee_collect"] and config.STAY_FEE_GUEST_PAY): return None`.
6. Door code: `App/app/door_codes.py` `_eligible_sql` (about 107) keys on `r.registration_completed_at IS NOT NULL`; `_issue_due` (about 1147) creates rows for every eligible stay; `reconcile` (about 1172) then calls `send_code_mail` for issued, unnotified rows. `_send_code_mail` (about 285):
   ```
       if not claim["completion_notified_at"]:
           # The confirmation has not gone yet: the code travels inside it.
           _release_confirmation(int(reservation["id"]))
           again = db.query_one("SELECT notified_at FROM door_code WHERE id = ?", (door_code_id,))
           if again and again["notified_at"]:
               return
   ```
   Then it goes on to enqueue `kind="door_code"`. The orchestrator suspects this means a door-code mail DOES go out after quiet completion, contrary to the plan's P4. Confirm or refute.
7. Guest pay box, `App/app/routes/guest.py` (about 1372 and 1403-1406): `remaining = (expected - progress["filled"]) ...` and `fee_panel` only `if remaining is not None and remaining <= 0`. Form-save hooks at about 2292-2295 (`submit_stay_if_complete`, `door_codes.on_registration_complete`, `claim.maybe_notify_completion`).
8. Host alert, `App/app/reporting.py` (about 2527-2552): `headcount_mismatch` raised only when `not settled` and `start < now.date()`, else resolved; `settled` = status in `reported`/`not_required`.
9. Config: `App/app/config.py:350` `STAY_FEE_GUEST_PAY = ... "off" ... == "on"`; `App/app/config.py:487` `MAIL_BACKEND` default `disabled`; `App/app/mail.py` `enqueue` (about 242) and backend checks (about 193-238).
10. Fee amount: `App/app/stay_fee.py` `charge_for_reservation` (about 486). Expected count: `App/app/reporting.py` about 352 (`expected_guests_override`) and `reservation_progress` (about 395-461).

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/tasks/1069-report.md | create | The answers |
| docs/tasks/1069-f0-quiet-completion-check.md | edit | `Status: todo` to `Status: review` only |

No other file may change. Read-only everywhere else.

## 4. Steps

Use `grep -n` first, then `sed -n 'A,Bp'` ranges of 150 lines or fewer. End every command with `| head -50` or `| tail -30`.

1. Confirm the anchors exist. Command: `cd App && grep -n 'HEADCOUNT_QUIET_HOURS\|def _forms_quiet_for\|def refresh_registration_completed_at\|def due_for_automatic_send\|def sweep' app/reporting.py | head -20`. Expected: all five found. If any anchor in §2 is missing, STOP (§8).
2. Q1 trigger and timing. Read `refresh_registration_completed_at`, `_forms_quiet_for`, the sweep loop and `job_intervals`. Command: `sed -n 940,1010p app/reporting.py; sed -n 2198,2230p app/reporting.py; sed -n 84,130p app/scheduler.py`. Answer: what exactly starts the 12-hour clock (which timestamps, which rows count, archived rows?), what blocks it (`incomplete`), how late after 12 h the sweep notices (job interval), whether the save-time path can also fire it, and whether a later form or a host headcount change can undo it (the `elif` branch).
3. Q2 mails. Trace every mail that can go to the lead or the host as a result of quiet completion: completion (`claim.maybe_notify_completion`, including the `force=True` path from `door_codes._release_held_confirmations`), door code (`door_codes._send_code_mail`, `mail_notify.build_door_code`), filing receipt or submission-outcome mails to the host (grep `mail.enqueue(` in `app/reporting.py` and `app/mail_notify.py`), and the reminder sweep (`claim.sweep_reminders`, about 814-880: does a quiet-completed stay still count as "not complete" and get a reminder?). Commands: `grep -n 'mail.enqueue(' app/*.py | head -40`; `grep -n 'def build_door_code' -A40 app/mail_notify.py | head -50`; `grep -n 'def forms_complete' -A15 app/alerts.py`. For each mail: kind, recipient (to / cc), trigger, whether it carries a fee block, which fee total (registered people only, or expected count; read `stay_fee.charge_for_reservation`), and which pay details or QR it carries.
4. Q3 door code. From `_eligible_sql`, `_issue_due`, `ensure_row`, `reconcile` and `_send_code_mail`, say whether a code is issued after quiet completion, whether it is mailed (and in which mail), and what `door_codes.view` shows on the guest page. Note the conditions (`DOOR_CODES_ENABLED`, `DOOR_CODES_LIVE`, TTLock account, `source`). Command: `sed -n 105,215p app/door_codes.py; sed -n 285,336p app/door_codes.py; sed -n 1147,1225p app/door_codes.py`.
5. Q4 host. What the host sees and is told: the `headcount_mismatch` alert (when raised, when resolved, is it resolved once the stay is filed?), the dashboard status for the stay, any host mail, and whether the host is copied on anything from step 3. Command: `sed -n 2470,2560p app/reporting.py; grep -n 'headcount_mismatch' app/*.py app/routes/*.py | head`.
6. Q5 filing. For the people who registered: is the stay filed, when (per `automation_mode`), with which guest rows? What happens when the missing person registers later (new guest row after `registration_completed_at` is set and after a filing): is that row filed, and by which path? Can quiet completion file a stay early, file it twice, or leave a row unfiled? Read `submit_for_apartment` selection of pending guests (grep `def submit_for_apartment`). Cross-check against `docs/UBYPORT_CORE.md` lines 12-33 and 59-78.
7. Q6 `UBYHOST_STAY_FEE_GUEST_PAY`. Describe the behaviour for both `on` and `off` (default off, `config.py:350`) for every mail and page in steps 3-4. Do not state what production uses; if a doc claims it, quote it with path and mark "not verified".
8. Q7 mail off. With `MAIL_BACKEND=disabled` (and `console`): does `enqueue` store, drop or log? Do `completion_notified_at` and `door_code.notified_at` still get set, so a later switch to `ses` never sends them? Command: `sed -n 185,300p app/mail.py`.
9. Bugs. List separately anything that looks wrong (for example: door-code mail without the fee block; reminder after completion; pay box hidden forever; mismatch alert resolved after filing; stale `filled` in the idempotency key). Do not fix anything.
10. Write `docs/tasks/1069-report.md` (format in §9). Set this brief to `Status: review`. Command: `git status --short | head`. Expected: only the two files in §3.

## 5. Do not touch

- Nothing under `App/` or `go/`. No code, test, template or migration edit. No test run is needed.
- No other doc. Do not edit the plan; the reviewer and orchestrator update it.
- Hard rules: never push to `main`; no secrets, no guest data, no operator identity in the report.

## 6. Commands

Only the read commands in §4, plus at the end from the repo root:

`python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no new errors. Known acceptable error: `docs/context/status.md` over its cap (fixed in PR #854).

## 7. Acceptance

- [ ] `docs/tasks/1069-report.md` exists and answers Q1-Q7, each with at least one `App/app/<file>.py:<line>` reference that a reviewer can open.
- [ ] Each answer ends with a line `Confidence: high|medium|low. Not verified: <what was not read or not run>`.
- [ ] Q2 has a table: mail kind, to, cc, trigger, fee block (yes/no, which total), pay details/QR.
- [ ] Q6 covers both `on` and `off`; Q7 covers `disabled` and `console`.
- [ ] A separate "Possible bugs" section, each item with file:line, none fixed.
- [ ] Anchor 6 (door-code mail after quiet completion) is explicitly confirmed or refuted.
- [ ] `git diff --stat origin/main` shows only the two files in §3.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in §2 is not found (say which, and what is there instead);
- answering would need a code change, a test run against a live service, or a guess about production settings;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, with the answers you have);
- a file outside §3 would change.

## 9. Report

Write `docs/tasks/1069-report.md` (up to 1500 words; this report is the deliverable) and set `Status: review`. Sections:

1. Summary: five lines, what the lead and the host get today after quiet completion.
2. Q1 to Q7, each: answer, references (`path:line`), `Confidence / Not verified` line.
3. Possible bugs (not fixed), each with `path:line` and one sentence why.
4. Where the plan (`guest-group-registration.md` P4, section 8 table) is wrong or incomplete.
5. Files changed (`git diff --stat`), the lint output's last 5 lines.
6. Questions for the owner.

## Risk list (for the reviewer)

A fresh reviewer checks every `path:line` in the report against the code at the base commit, especially Q2, Q3 (anchor 6) and Q5. No code diff exists to review.

## Owner steps

None. The owner later answers plan section 9, open item (3): whether `UBYHOST_STAY_FEE_GUEST_PAY` is on in production.
