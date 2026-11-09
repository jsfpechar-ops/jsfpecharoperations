# 1069 report: F0, what the lead gets after quiet completion

Status: review. Read-only; no code changed, no test run. All paths are under `App/app/`, lines from base 0d851ca4. "Shortfall" = fewer complete forms than the expected count.

## 1. Summary

1. Lead: no completion mail and no fee request by mail; the pay box on the stay page stays hidden.
2. Lead: a separate `door_code` mail IS sent (host contact in cc) when door codes are on, and the code shows on the stay page. Plan P4 is wrong here.
3. The registered people are filed with UbyPort: at once in `immediate` mode, after `submit_after_hours` (default 24) otherwise.
4. Host: no mail about the shortfall. Dashboard status stays `incomplete`; a `headcount_mismatch` alert appears once the arrival day has passed and stays until the count matches.
5. Quiet completion is only noticed by the sweep, which skips `manual` properties: there the stay is not completed and no code is made.

## 2. Answers

### Q1 Trigger and timing

- Clock: newest `updated_at or created_at` over the stay's non-archived guest rows (`reporting.py:943-956`; rows from `reservation_progress`, `reporting.py:401-406`, `archived_at IS NULL`). Any write to a guest row restarts it, including the sweep marking a non-reportable guest `NOT_REQUIRED` (`reporting.py:1453`).
- Needs at least one guest row and no incomplete (started, unfinished) form (`reporting.py:977-981`). One abandoned half-filled form blocks it for ever.
- Noticed by `sweep` (`reporting.py:2219-2224`), every `SUBMIT_SWEEP_MINUTES`, default 10 (`config.py:318`, `scheduler.py:92,189-192`). So 12 h plus up to 10 min.
- The sweep loops only over `active = 1 AND automation_mode != 'manual'` (`reporting.py:2201-2202`) and skips a property with an open `ubyport_auth_failed` alert before the refresh (`reporting.py:2206-2209`).
- The save-time path can also fire it: `submit_stay_if_complete` calls the same refresh (`reporting.py:1035`), from guest saves (`routes/guest.py:1098,1946,2292`) and host actions (`routes/admin.py:3901-4752`). A save restarts the clock, so in practice only host actions that touch no guest row.
- Undo: only when an incomplete form exists (`reporting.py:995-1005`). A new complete form or a headcount change does not undo it.

Confidence: high. Not verified: every admin call site; which guest writes set `updated_at`.

### Q2 Mails

| Kind | To | Cc | Trigger | Fee block | Pay details / QR |
|---|---|---|---|---|---|
| `completion` | lead (claim email) | host contact (`reply_to`) | NOT sent at quiet completion: returns while `filled < expected` (`claim.py:763`), also with `force=True`. Sent later by a guest save that reaches the count (`routes/guest.py:2295`) | yes if flag on and property collects (`claim.py:372-400,523`); total = registered guest rows only (`stay_fee.py:475-481,493`) | rails iban/revolut/cash, VS = reservation id (`claim.py:388-399`) |
| `door_code` | lead | host contact (`door_codes.py:318-328`) | reconcile, every 5 min, for issued, unnotified rows (`door_codes.py:1183-1189`) | no (`mail_notify.py:1434-1470`) | none |
| `reminder_guest` | lead | none | day before arrival from 9:00 if not `forms_complete` (`claim.py:851-888`; `alerts.py:107-115`) | no | none |
| `reminder_host` | host contact | none | check-in day from 9:00 if not complete (`claim.py:901-935`) | no | none |
| `submission_problem` | host | n/a | filing failure only (`mail_notify.py:912`) | no | none |

Quiet completion does not make the stay "complete" for reminders, so both reminders still go (once each, keyed by arrival date).

Confidence: high for `completion` and `door_code`; medium for the rest. Not verified: `build_reminder_host` body, `submission_problem` trigger, the completion template.

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
- Host mail: only the cc on `door_code` and the check-in-day `reminder_host`. Nothing says "filed with fewer people".

Confidence: high for alerts. Not verified: dashboard templates; whether alerts feed a digest mail.

### Q5 Filing

- Filed: yes, every complete, reportable, unsent row (`reporting.py:1458,1486,1497-1502`). `immediate`: in the same sweep (delay 0). Other modes: completion time + `submit_after_hours or 24`, capped 6 h before the deadline (`reporting.py:1105-1117`). `manual`: never automatic (`reporting.py:1090-1091`).
- Late person: the save calls `submit_stay_if_complete`; `immediate` sends at once, `SENT` rows are skipped (`reporting.py:1036-1060,1458`). Other modes: the next sweep sends the new row with no fresh delay, because the old completion time is already due.
- Twice: not seen (`SENT` skip plus the `claim_sendable` lease, `reporting.py:1506`).
- Early: quiet completion files without the missing person; that matches the code comment (`reporting.py:974-976`).
- Unfiled: if a late person leaves an unfinished form, completion is cleared (`reporting.py:995`) and every unsent co-guest waits (`reporting.py:1096-1098`); see bug 1.

Confidence: medium. Not verified: `submit_batch`, `claim_sendable` internals, `docs/UBYPORT_CORE.md` cross-check (not opened, call budget).

### Q6 `UBYHOST_STAY_FEE_GUEST_PAY`

- `off` (default, `config.py:350`): no fee block in any mail (`claim.py:379`), no pay box (`routes/guest.py:2418`), `charge_for_reservation` returns None (`stay_fee.py:488`). Quiet completion changes nothing about money.
- `on` and the property collects: fee block only in `completion`; pay box only when `expected - filled <= 0` (`routes/guest.py:1372,1403-1407`). After quiet completion with a shortfall: neither. The lead gets the door code and is never asked for the fee until the last person registers or the host lowers the count.
- Production value: `docs/ENVIRONMENT.md:180` gives only the default `off`. Not verified.

Confidence: high.

### Q7 Mail off

- `disabled`: `enqueue` logs and returns None, nothing stored (`mail.py:256-258`). `maybe_notify_completion` ignores the result and still sets `completion_notified_at` and the code's `notified_at` (`claim.py:801-810`): those are lost for ever. `_send_code_mail` returns before setting `notified_at` (`door_codes.py:329-330`), so it retries every 5 min and sends after a switch to `ses` while the code is valid.
- `console`: counts as enabled (`mail.py:197-198`); the row is stored and "sent" to `console_mail_log` (`mail.py:459-473,681`); both stamps are set as with `ses`.

Confidence: high for `enqueue`; medium for `console`.

## 3. Possible bugs (not fixed)

1. HIGH RISK (filing). `reporting.py:977-981,995-1005,1096-1098`: one abandoned unfinished form blocks or clears completion, so complete co-guests are never filed automatically, even at the deadline cap. Only the deadline alert and a host send remain. Not verified: any other forced-send path.
2. `reporting.py:2201-2202`: `manual` properties never get quiet completion, so with a shortfall no door code is issued. Same while `ubyport_auth_failed` is open (`reporting.py:2206-2209`): a police login problem holds back door codes.
3. `door_codes.py:262-282` with `claim.py:763`: after quiet completion the held-confirmation net matches the stay every 5 min for 24 h, logs `DOOR_CODE_PROBLEM` at error level each time, sends nothing, and uses a slot of `BATCH = 20`.
4. `door_codes.py:305-328`: door code mailed with no fee request while the pay box is hidden (flag on): entry without ever being asked to pay.
5. `routes/admin.py:3901-4752`: host lowering the count calls only `submit_stay_if_complete`; no completion mail follows, except through bug 3's net inside 24 h when a `door_code` row exists. Medium confidence.
6. `claim.py:801-810`: stamps set although `enqueue` returned None (mail disabled, or an empty address).
7. `reporting.py:1453`: the sweep's own `NOT_REQUIRED` write restarts the quiet clock once.
8. `reporting.py:2556-2580`: critical "Overdue" alert for a stay whose registered people are all filed.

Checked and not bugs: the mismatch alert is not resolved by filing; the idempotency key's `filled` is guarded by `completion_notified_at`.

## 4. Where plan P4 is wrong or incomplete

- Wrong: "no mail". A `door_code` mail goes to the lead with the host in cc.
- Incomplete: the completion mail (with fee) does arrive later if the last person registers; reminders still go; `manual` properties never complete quietly; filing happens for the registered people; "12 quiet hours" restarts on any guest-row write.

## 5. Files changed

`docs/tasks/1069-report.md` (new), `docs/tasks/1069-f0-quiet-completion-check.md` (Status line). Plus the cherry-picked `docs/context/status.md` compaction (eae5f018), as instructed by the orchestrator. Lint: `context lint: OK`.

## 6. Questions for the owner

1. Should the door code go out before the fee is asked for (bug 4)?
2. Should `manual` properties complete quietly (bug 2)?
3. Is an abandoned unfinished form meant to hold back the others' filing (bug 1)?
4. Is `UBYHOST_STAY_FEE_GUEST_PAY` on in production?
