# 1069 report: F0, what the lead gets after quiet completion

Status: review

## 1. Summary

1. Lead: no completion mail and no fee request by mail; the pay box on the stay page stays hidden.
2. Lead: a separate `door_code` mail IS sent (host contact in cc) when door codes are on, and the code shows on the stay page. Plan P4 is wrong here.
3. The registered people are filed with UbyPort in the sweep that notices the quiet completion: at once in `immediate` mode, after `submit_after_hours` (default 24) otherwise, capped 6 h before the deadline.
3a. HIGH RISK (filing): with a shortfall, or with no expected count (host-entered stays), nothing is filed before 12 quiet hours have passed, and the deadline cap cannot act before that. A guest-row write later than about 12 h 10 min before the legal deadline means the registered people are filed AFTER the deadline (bug 9).
4. Host: no mail about the shortfall. Dashboard status stays `incomplete`; a `headcount_mismatch` alert appears once the arrival day has passed and stays until the count matches.
5. Quiet completion is only noticed by the sweep, which skips `manual` properties: there the stay is not completed and no code is made.

## 2. Answers

### Q1 Trigger and timing

- Clock: newest `updated_at or created_at` over the stay's non-archived guest rows (`reporting.py:943-956`; rows from `reservation_progress`, `reporting.py:401-406`, `archived_at IS NULL`). Any write to a guest row restarts it, including the sweep marking a non-reportable guest `NOT_REQUIRED` (`reporting.py:1453`).
- Needs at least one guest row and no stored row that fails validation (`reporting.py:421,977-981`). There are no drafts: both insert paths validate before they save (`routes/guest.py:2180-2206` before `:2276`; `routes/admin.py:4323-4324` before `:4358`), and a host edit of an unfiled guest is refused on errors (`routes/admin.py:4442-4443`). The other guest writes touch no validated field (`reporting.py:1158,1453`; `routes/admin.py:4523,4546,4581,4689,4716`; `routes/stay_fees.py:1165`). So an "abandoned half-filled form" does not exist as a row. A saved row can only turn incomplete later: (a) the booking dates move and the row has no own dates, so `_stay_dates` falls back to the booking (`reporting.py:132-139`) and `stay_to <= stay_from` or a birth date after arrival fails (`validation.py:413,665`); `icalsync.py:431-447` rewrites unsent guest windows on a calendar move; (b) a deploy tightens a rule in `validation.validate_guest`; (c) a host edit of a filed guest is saved despite errors (`routes/admin.py:4443`). `signature_dates_stale` (`reporting.py:1009-1022`) is not part of completeness: it only skips that row at send time (`reporting.py:1488-1494`).
- Noticed by `sweep` (`reporting.py:2219-2224`), every `SUBMIT_SWEEP_MINUTES`, default 10 (`config.py:318`, `scheduler.py:92,189-192`). So 12 h plus up to 10 min.
- The sweep loops only over `active = 1 AND automation_mode != 'manual'` (`reporting.py:2201-2202`) and skips a property with an open `ubyport_auth_failed` alert before the refresh (`reporting.py:2206-2209`).
- The save-time path can also fire it: `submit_stay_if_complete` calls the same refresh (`reporting.py:1035`), from guest saves (`routes/guest.py:1098,1946,2292`) and host actions (`routes/admin.py:3901-4752`). A save restarts the clock, so in practice only host actions that touch no guest row.
- Undo: only when an incomplete form exists (`reporting.py:995-1005`). A new complete form or a headcount change does not undo it.

Confidence: high for the save paths, medium for the later-incomplete triggers. Not verified: every admin call site; that the guest route's own checks (`routes/guest.py:2100-2180`) are a superset of `guest_issues`; whether the icalsync rewrite can itself produce an invalid window; rows older than today's rules.

### Q2 Mails

| Kind | To | Cc | Trigger | Fee block | Pay details / QR |
|---|---|---|---|---|---|
| `completion` | lead (claim email) | host contact (`reply_to`) | NOT sent at quiet completion: returns while `filled < expected` (`claim.py:763`), also with `force=True`. Sent later by a guest save that reaches the count (`routes/guest.py:2295`) | yes if flag on and property collects (`claim.py:372-400,523`); total = registered guest rows only (`stay_fee.py:475-481,493`) | rails iban/revolut/cash, VS = reservation id (`claim.py:388-399`) |
| `door_code` | lead | host contact (`door_codes.py:318-328`) | reconcile, every 5 min, for issued, unnotified rows (`door_codes.py:1183-1189`) | no (`mail_notify.py:1434-1470`) | none |
| `reminder_guest` | lead | none | day before arrival from 9:00 if not `forms_complete` (`claim.py:851-888`; `alerts.py:107-115`) | no | none |
| `reminder_host` | host contact | none | check-in day from 9:00 if not complete (`claim.py:901-935`) | no | none |
| `submission_problem` | host | n/a | filing failure only (`mail_notify.py:912`) | no | none |

Quiet completion does not make the stay "complete" for reminders, so both reminders still go (once each, keyed by arrival date).

Lead changes the count: `_set_declared_guests` (`routes/guest.py:1088-1099`, called at `:1537`, `:1612`, `:1644`, `:2209`) updates `declared_guests` and calls only `reporting.submit_stay_if_complete`. A lead who lowers the count to the number registered completes the stay (and files it in `immediate` mode) with no call to `claim.maybe_notify_completion`. The only other callers are the guest save (`routes/guest.py:2295`) and the door-code module (`door_codes.py:259`, reached from `:281`, `:301`, `:616`, `:657`, `:689`). So the completion mail follows only if (a) a `door_code` row is still unnotified, at the next 5-minute reconcile (`door_codes.py:299-301,1183-1189`), or (b) a `door_code` row exists and `registration_completed_at` is between 5 minutes and 24 hours old, through the held-confirmation net (`door_codes.py:262-282`, `force=True`). With door codes off, or more than 24 h after a quiet completion whose code mail already went, no completion mail and no fee request are ever mailed unless a guest form is saved again.

Confidence: high for `completion`, `door_code` and the missing call in `_set_declared_guests`; medium for the rest. Not verified: `build_reminder_host` body, `submission_problem` trigger, the completion template, `issue()` at `door_codes.py:600-690` (only its three call lines were seen).

### Q3 Door code (anchor 6: CONFIRMED)

- Eligibility keys on `registration_completed_at IS NOT NULL` (`door_codes.py:107-119`), so quiet completion makes the stay eligible. `_issue_due` creates and issues the row (`door_codes.py:1147-1169`).
- `_send_code_mail` first tries the confirmation (`door_codes.py:299-304`); that returns at `claim.py:763`, `notified_at` stays empty, so it goes on and enqueues `kind="door_code"` (`door_codes.py:305-328`). The lead gets a code-only mail.
- Guest page: `door_codes.view` shows the issued PIN (`door_codes.py:136-182`, `routes/guest.py:1400`).
- Conditions: `DOOR_CODES_ENABLED` (`door_codes.py:1174`), TTLock property with check-in/out hours, `source = 'manual'` unless `DOOR_CODES_LIVE` (`door_codes.py:118-119`), TTLock account ok (`door_codes.py:196-200`), a claim with an email (`door_codes.py:297`).
- Un-completing a stay does not revoke the code (`door_codes.py:807-812` keys on status/archive only).

Confidence: high. Not verified: `issue()` (lines 374-690) was not read.

### Q4 Host

- `headcount_mismatch` warning: raised when status is not `reported`/`not_required`, `filled < expected` and the anchor day is before today (`reporting.py:2539-2553`); otherwise resolved (`reporting.py:2555`). With a shortfall the status is `incomplete` even after filing (`reporting.py:437-438`), so filing does NOT resolve it. It clears when the count matches or the stay is cancelled/archived (`reporting.py:2478-2489`).
- The `deadline` alert also stays (up to critical "Overdue · 1/2") although every registered person is filed (`reporting.py:2556-2580`).
- `guest_incomplete_checkin` warning ("check-in today · Forms incomplete"): a host dashboard alert raised by the reminder sweep on the check-in day from 9:00 local, next to the `reminder_host` mail, when `alerts.forms_complete` is false (`claim.py:901,938-946`; `alerts.py:107-115`). `forms_complete` reads only status and counts, never `registration_completed_at`, so quiet completion does not resolve it; filing does not either while there is a shortfall (status stays `incomplete`). It is resolved when the count is reached (`claim.py:844-846`) or, in any case, from the day after check-in (`claim.py:847-850`). It lives one day at most.
- Host mail: only the cc on `door_code` and the check-in-day `reminder_host`. Nothing says "filed with fewer people". The lead lowering the count sends the host nothing either (see Q2).

Confidence: high for alerts. Not verified: dashboard templates; whether alerts feed a digest mail; the query that selects stays for the reminder sweep.

### Q5 Filing

- Filed: yes, every complete, reportable, unsent row (`reporting.py:1458,1486,1497-1502`). `immediate`: in the same sweep (delay 0). Other modes: completion time + `submit_after_hours or 24`, capped 6 h before the deadline (`reporting.py:1105-1117`). `manual`: never automatic (`reporting.py:1090-1091`).
- Late person: the save calls `submit_stay_if_complete`; `immediate` sends at once, `SENT` rows are skipped (`reporting.py:1036-1060,1458`). Other modes: the next sweep sends the new row with no fresh delay, because the old completion time is already due.
- Twice: not seen (`SENT` skip plus the `claim_sendable` lease, `reporting.py:1506`).
- Early: quiet completion files without the missing person; that matches the code comment (`reporting.py:974-976`).
- Unfiled: a late person cannot leave an unfinished form (no drafts, Q1). Only a stored row that later fails validation clears completion (`reporting.py:995-1005`) and makes every unsent co-guest wait (`reporting.py:1099-1101`); see bug 1.
- Deadline the code uses: end of the third working day, arrival day counted when it is a working day, weekends skipped, public holidays counted as working days (`deadlines.py:16,19-21,41-43`), local time `Europe/Prague` (`config.py:442`), from the earliest guest `stay_from`, else the booking start (`reporting.py:2436-2459`). `docs/UBYPORT_CORE.md` and `docs/plans/guest-group-registration.md`: not stated (no "deadline" or "working day" wording in either).
- Can a registered guest be filed after the legal deadline? YES. `due_for_automatic_send` returns False while `registration_completed_at` is empty (`reporting.py:1099-1101`), so the cap at `:1110-1117` cannot act. With a shortfall the stamp is set only by the quiet path, no earlier than the newest guest-row write + 12 h (`reporting.py:110,943-956,977-985`) and only when a sweep runs (`reporting.py:2219-2225`, every `SUBMIT_SWEEP_MINUTES`, default 10, `config.py:318`). Every other sender needs the stamp too (`reporting.py:1035-1036` for `completion_immediate`; `:1981`, `:2107` are resends) or is a host action (`routes/admin.py:3752,4180,4786`).
- Timeline (dates computed with `deadlines.reporting_deadline`): check-in Mon 2026-11-09, lead declared 3, 2 registered. Legal deadline in code: Wed 2026-11-11 23:59:59; cap Wed 17:59:59. Last form saved Wed 14:00. Wed 17:59:59: nothing happens, no stamp. Thu 2026-11-12 02:00: 12 h quiet; the sweep between 02:00 and 02:10 stamps completion and files both people in the same pass, in `immediate` (delay 0) and in a 24 h mode alike, because `min(Fri 02:00, Wed 17:59:59)` is already past. Filed about 2 h late. If a guest corrects a name Wed 23:00, the clock restarts: filed Thu 11:00-11:10, 11 h late. To be on time the last guest-row write must be no later than Wed 11:49. Host-side writes restart the clock too: fee decision (`routes/stay_fees.py:1165`), identity check (`reporting.py:1158`), restrict (`routes/admin.py:4523`).
- Warning in time: only on the dashboard. The `deadline` alert turns to warning "Due now · 2/3" in the last 24 h and critical "Overdue" after (`reporting.py:2559-2580`; `deadlines.py:72-76`); `headcount_mismatch` from the day after arrival. Neither says that filing is waiting for quiet hours, and no mail was found for them.
- `docs/UBYPORT_CORE.md` cross-check: "What works means" (`:12-33`) lists build, send once, read, persist proof and point 5 "Surface failure honestly: the host must see that filing failed or is incomplete" (`:27-28`). It has no timeliness item. A shortfall stay whose registered people are filed still shows `incomplete` plus a critical "Overdue": incompleteness is surfaced (meets point 5 as written), but the host cannot tell "2 filed, 1 missing" from "nothing filed" (bug 8). In the late case the host sees "Due now"/"Overdue", so it is not silent, but nothing is filed in time. The table at `:59-78` names "Auto-submit & scheduler: stays never filed or filed twice" (`:66`); bugs 2 and 9 fall in that row. `:79-92` has only process rules.

Confidence: high for the gate, the cap and the dates (formula re-run outside the repo); medium for the rest. Not verified: `submit_batch`, `claim_sendable` internals, that a host send ignores the schedule (`ignore_schedule` default not read), the production sweep interval and automation modes, the legal text itself.

### Q6 `UBYHOST_STAY_FEE_GUEST_PAY`

- `off` (default, `config.py:350`): no fee block in any mail (`claim.py:379`), no pay box (`routes/guest.py:2418`), `charge_for_reservation` returns None (`stay_fee.py:488`). Quiet completion changes nothing about money.
- `on` and the property collects: fee block only in `completion`; pay box only when `expected - filled <= 0` (`routes/guest.py:1372,1403-1407`). After quiet completion with a shortfall: neither. The lead gets the door code and is never asked for the fee until the last person registers or the host lowers the count.
- Production value: `docs/ENVIRONMENT.md:180` gives only the default `off`. Not verified.

Confidence: high.

### Q7 Mail off

- `disabled`: `enqueue` logs and returns None, nothing stored (`mail.py:256-258`). `maybe_notify_completion` ignores the result and still sets `completion_notified_at` and the code's `notified_at` (`claim.py:801-810`): those are lost for ever. `_send_code_mail` returns before setting `notified_at` (`door_codes.py:329-330`), so it retries every 5 min and sends after a switch to `ses` while the code is valid.
- `console`: counts as enabled (`mail.py:197-198`, read); `_send_console` builds the mail and inserts it into `console_mail_log` (`mail.py:459-474`, read); nothing is delivered. Both stamps are set as with `ses`, because `claim.py:801-810` sets them unconditionally after `enqueue`. On production the config check warns "mail is logged, not delivered" (`mail.py:233-236`, read).

Confidence: high for `enqueue` and for `console` enabled/logged/warning; medium for the outbox row state after a console send (`mail.py:681` not re-read). Not verified: where the production warning is shown; the production backend.

## 3. Possible bugs (not fixed)

1. LOW likelihood, filing impact (was HIGH RISK). `reporting.py:977-981,995-1005,1099-1101`: one stored row that fails validation blocks or clears completion, so complete co-guests are not filed automatically, even at the deadline cap. The trigger is not an abandoned form (none can be saved, Q1) but a saved row that turns invalid: moved booking dates on a row without own dates, a tightened rule after a deploy, or an edited filed guest. Re-rated because every save path validates first, so it needs a second event. Not verified: how often dates move under a dateless row.
2. `reporting.py:2201-2202`: `manual` properties never get quiet completion, so with a shortfall no door code is issued. Same while `ubyport_auth_failed` is open (`reporting.py:2206-2209`): a police login problem holds back door codes.
3. `door_codes.py:262-282` with `claim.py:763`: after quiet completion the held-confirmation net matches the stay every 5 min for 24 h, logs `DOOR_CODE_PROBLEM` at error level each time, sends nothing, and uses a slot of `BATCH = 20`.
4. `door_codes.py:305-328`: door code mailed with no fee request while the pay box is hidden (flag on): entry without ever being asked to pay.
5. `routes/admin.py:3901-4752` (host) and `routes/guest.py:1088-1099` (lead, high confidence): lowering the count calls only `submit_stay_if_complete`; no completion mail and no fee request follow, except through the door-code paths when a `door_code` row exists (unnotified row, or the net inside 24 h of completion). Door codes off: never. Medium confidence for the host side.
6. `claim.py:801-810`: stamps set although `enqueue` returned None (mail disabled, or an empty address).
7. `reporting.py:1453`: the sweep's own `NOT_REQUIRED` write restarts the quiet clock once.
8. `reporting.py:2556-2580`: critical "Overdue" alert for a stay whose registered people are all filed.
9. HIGH RISK (filing). `reporting.py:1099-1101,977-985,2219-2225`: with a shortfall, or with no expected count (`declared_filled` needs `expected is not None`, `reporting.py:970-972`; the host insert sets no count, `routes/admin.py:4358-4363`), the deadline cap (`:1110-1117`) cannot act until quiet completion, which needs 12 h without any guest-row write plus a sweep. A write later than deadline minus 12 h minus one sweep interval gets the registered people filed after the legal deadline (timeline in Q5: 2 h late, 11 h after a late edit). `manual` properties and an open `ubyport_auth_failed` never complete quietly at all (bug 2).

Checked and not bugs: the mismatch alert is not resolved by filing; the idempotency key's `filled` is guarded by `completion_notified_at`.

## 4. Where plan P4 is wrong or incomplete

- Wrong: "no mail". A `door_code` mail goes to the lead with the host in cc.
- Incomplete: the completion mail (with fee) does arrive later if the last person registers; reminders still go; `manual` properties never complete quietly; filing happens for the registered people; "12 quiet hours" restarts on any guest-row write.

## 5. Files changed

`docs/tasks/1069-report.md` (new), `docs/tasks/1069-f0-quiet-completion-check.md` (Status line). Plus the cherry-picked `docs/context/status.md` compaction (74f25f7b), as instructed by the orchestrator. Lint: `context lint: OK`. 1069-cont-1 changed this report and the Status line of `docs/tasks/1069-cont-1.md` only.

## 6. Questions for the owner

1. Should the door code go out before the fee is asked for (bug 4)?
2. Should `manual` properties complete quietly (bug 2)?
3. Should the registered people of a shortfall stay, or of a stay with no expected count, be filed at the deadline cap (6 h before the deadline) without waiting for 12 quiet hours (bug 9)? Today they can be filed late.
4. Should one stored row that later fails validation (moved dates, new rule) hold back the others' filing (bug 1)?
5. Should a lead or host who lowers the count get the completion mail with the fee request (bug 5)?
6. Is "end of the third working day, arrival day counted, holidays counted as working days" the deadline to rely on? It is in `deadlines.py` only, not in `docs/UBYPORT_CORE.md`.
7. Is `UBYHOST_STAY_FEE_GUEST_PAY` on in production?

## 7. Review notes (fresh Fable review, second pass)

Diff: docs only. Every answer and bug confirmed against the code, with these corrections (applied above where they change a conclusion):
- Bug 9 and owner question 3 also cover stays with no expected count, not only a shortfall.
- Q1: quiet completion at save time can also be fired by a guest removal (`routes/guest.py:1934-1946`) and a lead count change (`:1098`), not only host actions. Writes that restart the quiet clock also include the send-result write (`reporting.py:1737`), the filed-by-hand marks (`:2362`, `:2402`) and the calendar-move rewrite (`icalsync.py:445`).
- Q2: `reminder_host` also goes at 18:00 the day before for unclaimed stays (`claim.py:895-903`).
- Q6: the cited line is `routes/guest.py:2417`, not 2418.
- Not read by the reviewer: `claim_sendable` internals, host send routes (`routes/admin.py:3748, 4176, 4782`), `validation.py:413,665`.
