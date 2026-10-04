# WP23: Filing watchdog

Patch: `series/` (per-WP .patch files were removed; the series is the only code) (also `series/0010-WP23-Filing-watchdog.patch`). Written on top of WP01 to WP05, WP07, WP08, WP09 and WP22 in the new order (branch `reorder`, worktree `/tmp/wp/reorder`). It does not need WP06; it touches `scheduler.py`, which WP06 later moves into the worker.

## Summary
Every run of the deadline job (every 30 minutes) now also asks: which stays may miss their police deadline? A stay is at risk when:
- it has at least one reportable guest (`validation.guest_is_reportable`: every nationality except Czech, EU included) whose `submit_state` is not `sent`;
- the stay is active (not cancelled or ignored), not archived, and its property is active (the same set `check_deadlines` watches);
- `deadlines.reporting_deadline` of the deadline anchor (earliest guest arrival, `reporting.reservation_deadline_anchor`) is at most 24 hours away or already passed.

Then:
- (a) The host gets one e-mail per stay, the first time it is at risk. New mail kind `deadline_at_risk`. `reminder_host` does not cover this: it is the check-in day nudge about missing guest forms, sent on the arrival day only, and says nothing about the deadline or filing. The mail names the property (`internal_name`), the arrival date, the number of unfiled guests and the deadline, links to `/reservations/<id>`, and has one note on filing by hand in the UbyPort web application. Sent once: `reservation.at_risk_mailed_at` is set when the mail is queued. The outbox idempotency key `deadline_at_risk:<reservation_id>` is a second guard. A marker was needed because the outbox is purged after 14 days.
- (b) The operator (`config.OPERATOR_EMAIL`) gets a digest, new kind `deadline_digest`, at most once per 6 hours while any stay is at risk. It lists workspace (account username), property, arrival, deadline and unfiled count. It has no guest names. At most 50 rows, then "and N more". The throttle stamp is in `settings` (`filing_watchdog_digest_sent_at`, UTC).
- (c) New optional `UBYHOST_HEARTBEAT_FILING_URL`. It is pinged on every run of the deadline job: `<url>` when nothing is at risk, `<url>/fail` when at least one stay is at risk (healthchecks.io semantics). It also gets `/fail` when the in-app deadline-alert pass failed. If the watchdog itself fails, nothing is pinged, so the monitor alerts on the missing ping, the same as when the VM is down. Empty URL: nothing is sent.
- Guide (EN, CS): "If UbyHost cannot file in time" in the Police reporting section (`id="manual-filing"`). Steps: sign in to the UbyPort web application with your own access, enter the guests, keep the receipt, then mark the stay as filed by hand in UbyHost. The legal duty stays with the host.

### Filed by hand (added in the amended WP23)
When the host filed a stay directly in the UbyPort web application, the stay page (section Police reporting) offers "I filed this stay by hand in UbyPort" / "Tento pobyt jsem nahlásil(a) ručně v UbyPortu", with the filing time (`datetime-local`, default now, Prague time) and an optional receipt or reference (one line, at most 200 characters).
- Representation: the guests become `submit_state = 'sent'`, plus four new guest columns: `manual_filed_at` (UTC), `manual_reference`, `manual_marked_at` (UTC, when the mark was made) and `manual_prev_state`. No new state value. Reason: about 25 places in the code already treat `sent` as filed and as "never send again" (`collect_sendable`, `claim_sendable`, the sweep, `pending_reportable`, `guest_form_locked`, iCal keep rules, the watchdog query, guest edit and archive refusals). A new `sent_manual` state would have to be added to each one, and a missed one would file the guest a second time. With `sent`, each of those places already does the right thing.
- Which guests are marked: the stay's live guests in `pending`, `error` or `blocked` with a reportable nationality. Guests already filed by UbyPort and Czech guests are untouched. A guest with a live `submission_claim` (UbyHost is filing it at that moment) is skipped and the host is told to wait. The mark runs in one `BEGIN IMMEDIATE` transaction and updates each guest only if its state is unchanged.
- Sending: `collect_sendable` never offers a guest filed by hand, not even as a deliberate resend. `claim_sendable` re-reads `manual_filed_at` and drops the pair, so a sweep that built its list before the mark cannot file it.
- Status: `reservation_progress` counts a guest filed by hand as complete (UbyHost may still lack its signature), so the stay reads "reported" when nothing else is open.
- Deadline badge (WP01): `deadline_cell` takes `manual_filed_at` as the filing time and sets `by_hand`. The badge reads "Filed by hand 30.09. 14:32" / "Podáno ručně 30.09. 14:32", in the done style when on time and neutral when late. Guest cards on the stay page say "Filed by hand" with the time; the guest edit banner says "Filed by hand in UbyPort <time>".
- Watchdog: a stay filed by hand is not at risk (the query asks for `submit_state != 'sent'`).
- House book: CSV `reported` = "yes - filed by hand in UbyPort", `reported_at` = the hand filing time, `stamp` = the reference. The registration form PDF says "Reported to the Foreign Police (filed by hand in UbyPort)" with time and reference.
- "Minutes saved" on the dashboard does not count guests filed by hand.
- Audit: `stay_filed_manually` with `reservation=<id> guests=<n> filed_at=<utc>` and the reference if given (no guest data). Undo: "Undo, this was a mistake", only within 24 hours of the mark (`manual_marked_at`), restores each guest's previous state, audited as `stay_filed_manually_undone`. After 24 hours the button is gone and the route refuses.
- Validation: the filing time may not be more than 5 minutes in the future or more than 60 days back.

### Stays with no guest data ("unknown risk", added in the amended WP23)
A stay that is active, not archived, on an active property, with arrival today or earlier, no live guest entered, and its deadline (from the arrival date) less than 24 hours away or passed by at most 7 days, is "unknown risk".
- The host gets the `deadline_at_risk` mail once, in the variant "No guest details yet" / "Zatím bez údajů o hostech": it explains that UbyHost cannot tell whether a report is due, that the deadline applies if any guest is not a Czech citizen, and what to do. The same `reservation.at_risk_mailed_at` marker is used, so there is one warning per stay, whichever variant comes first.
- The operator digest lists these stays in their own section ("Stays without guest details (status unknown)"), without a guest count. A digest is also sent when only such stays exist. The subject then carries both counts.
- The heartbeat never goes to `/fail` because of them: only known reportable unfiled guests do. Czech-only stays nobody typed in would otherwise page the owner.
- The run line (WP13, later) and the log line carry `unknown_risk`. A failure of the unknown-risk query is logged and does not stop the main watchdog or its heartbeat.

## Files changed
- `App/app/filing_watchdog.py`: new. At-risk and unknown-risk queries, host mails, operator digest, heartbeat URL.
- `App/app/reporting.py`: filed-by-hand mark, undo, view helper, parsing; `reservation_progress`, `filed_at`/`deadline_cell`, `collect_sendable`, `claim_sendable` know about it.
- `App/app/routes/admin.py`: `POST /reservations/{id}/filed-by-hand` and `.../filed-by-hand/undo`; stay page context.
- `App/app/templates/reservation_detail.html`, `_components.html`, `guest_form_admin.html`: the mark form, the done panel with undo, the badge and the guest labels.
- `App/app/housebook.py`: CSV and PDF note a filing by hand.
- `App/app/celebrations.py`: "minutes saved" skips guests filed by hand.
- `App/app/scheduler.py`: `_job_deadlines` runs the watchdog after the alert pass; new `_filing_heartbeat`.
- `App/app/mail_notify.py`: `build_deadline_at_risk` (with the `no_guests` variant), `build_deadline_digest` (with the unknown section), `_digest_section`, `_block_table`.
- `App/app/mail.py`: kinds `deadline_at_risk`, `deadline_digest` (both in `HOST_KINDS`).
- `App/app/db.py`: `ADDED_COLUMNS` gets `reservation.at_risk_mailed_at` and `guest.manual_filed_at`, `manual_reference`, `manual_marked_at`, `manual_prev_state`.
- `App/app/config.py`: `HEARTBEAT_FILING_URL`.
- `App/app/host_i18n.py`: mail strings, mail-kind labels, filed-by-hand page and flash strings, EN and CS.
- `App/app/guide_i18n.py`, `App/app/templates/guide.html`: the manual-filing section, with step 4 (mark the stay).
- `App/tests/test_filing_watchdog.py`: new, 32 tests.
- `App/tests/test_filed_by_hand.py`: new, 18 tests.
- `App/tests/test_claim_mail.py`: pinned kind set gets the two new kinds.
- `deploy/lightsail/.env.example`, `docs/ENVIRONMENT.md`, `docs/OPERATIONS.md`, `docs/SES.md`: the new variable, the job and the kinds.

## Tests added
All in `tests/test_filing_watchdog.py`. Time is frozen by passing `now`; the repo has no freezegun.
- At-risk detection:
  - a Friday 25.09.2026 arrival before the Monday 28.09. holiday has its deadline on Wed 30.09. 23:59:59: not at risk on Tuesday noon, at risk Wednesday morning, overdue later;
  - the window opens exactly 24 h before the deadline;
  - an EU (SVK) guest is reportable;
  - a Czech-only stay is not at risk;
  - a cancelled or ignored stay is not at risk;
  - a filed stay is not at risk, and a partly filed one counts only the unfiled (`error`, `blocked`) guests;
  - a far deadline is not at risk.
- Host mail:
  - sent once across three runs, with the marker set;
  - contents checked: property, arrival, count, link, manual line, no guest name;
  - nothing is marked while mail is off;
  - EN and CS have no raw keys.
- Operator digest:
  - sent at T, not at T+30 min, T+1 h or T+5 h 59 min, sent again at T+6 h;
  - only to the operator address, no guest names;
  - none without stays at risk;
  - the stamp is UTC.
- Heartbeat:
  - success URL (trailing slash stripped);
  - `/fail` when a stay is at risk;
  - `/fail` when the alert pass broke;
  - no ping when the watchdog fails (and the job is marked failed);
  - nothing when the URL is empty;
  - the real watchdog inside `_job_deadlines` pings `/fail` for an overdue stay.
- Guide: strings in both languages, and the page renders the section in EN and CS.
- Unknown risk (`test_filing_watchdog.py`, frozen time):
  - an empty stay arriving Friday 25.09.2026: not before arrival, not on Tuesday noon (36 h left), in on Wednesday morning, overdue on Friday, gone a week after the deadline, never a known risk;
  - the 24 hour edge for an ordinary Wednesday arrival;
  - cancelled, ignored and Czech-only (guest entered) stays are not unknown risk;
  - the host gets the "no guest details yet" mail once, and not again when guests are entered later;
  - EN and CS variants have no raw keys and no "not filed" count line;
  - the digest has its own section and subject; a digest goes out for unknown stays alone;
  - the heartbeat stays green with only unknown stays (real `run()` and `_job_deadlines`);
  - a broken unknown-risk query does not stop the main watchdog.
- Filed by hand (`test_filed_by_hand.py`, frozen time where the code takes `now`; the route tests set stamps relative to the real clock):
  - only pending, error and blocked reportable guests are marked, with the previous state kept; Czech and already sent guests untouched; a second mark changes nothing;
  - the stay reads "reported" even without signatures and Send is off;
  - the badge says filed by hand, on time and late;
  - a stay filed by hand is not at risk and not unknown risk;
  - the sweep never sends it, not even as a resend, and `claim_sendable` drops a list built before the mark;
  - a guest under a live submission claim is not marked;
  - undo within 24 hours restores pending, error and blocked; at 25 hours it does nothing; UbyPort-accepted guests are never touched;
  - filing time parsing (Prague to UTC, skew, future, 60 days) and the reference cleanup;
  - house book CSV and PDF;
  - the stay page: form, POST, audit row with reference, badge, guest label, undo button, undo POST and its audit row; undo after 24 hours refused; a future time refused; another workspace's stay refused;
  - all new strings in EN and CS.

## Test commands and results
From `App/`, `/tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider`:
- Amended WP23, on its own commit (0010): `test_filed_by_hand test_filing_watchdog test_scheduler test_guide test_claim_mail test_alert_language test_host_i18n test_deadline_after_reporting test_wp07_cache_heartbeats test_ses_mail test_submission_mail test_stale_submission test_submission_retry_cap`: 236 passed, 1 failed. The failure is `test_stale_submission::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`, the known order-dependent test: it fails the same way on `wpbase` and on the old WP23 with `test_submission_retry_cap` before it, and passes alone.
- Also on 0010: `test_scheduler test_guide test_claim_mail test_mail* test_alert_language test_host_i18n test_deadline* test_wp07_cache_heartbeats test_ses_mail test_submission_mail test_filing_watchdog test_filed_by_hand`: 277 passed.
- Full suite in chunks on the whole series (0025): 2585 passed, 10 skipped, 1 failed (`test_host_geometry`, no Chromium, same on `wpbase`). That is the previous 2557 plus the 28 new tests.
- Ruff (`E9,F63,F7,F82,F401,F841` on app, tests, tools, scripts): all checks passed, on 0010 and on 0025.

## Deviations from the spec and why
- A stay with no guest entered is "unknown risk" (mail once, digest section, no `/fail`). A stay whose entered guests have no nationality is neither at risk nor unknown risk; the in-app `deadline` alert still covers it.
- Filed by hand is `sent` plus `guest.manual_*` columns, not a new `sent_manual` state (reason in the Summary). Four columns, not two: `manual_marked_at` makes the 24 hour undo independent of the filing time the host typed, and `manual_prev_state` lets the undo put a refused (`error`, `blocked`) guest back exactly as it was.
- The mark is per guest, so a stay with no guest entered cannot be marked. Such a stay drops off the unknown-risk lists 7 days after its deadline (`UNKNOWN_RISK_MAX_OVERDUE`); before that the host can enter the guests and mark them, or archive or ignore the stay. The 7 days are my choice so an empty calendar entry does not stay in the operator digest for ever.
- One host warning per stay: the "no guest details yet" mail and the at-risk mail share `reservation.at_risk_mailed_at`, so a stay warned as empty is not warned again when its guests are entered and are still unfiled. The digest still lists it.
- `manual_reference` is free text from the host and is stored in plain text (it is a UbyPort receipt number, not identity data) and written into the audit row.
- Guests filed by hand do not count towards "minutes saved".
- `blocked` and `error` guests count as unfiled. The spec says `submit_state != 'sent'`, and `blocked` means "refused in a way resending cannot fix", so it really is not filed.
- Inactive properties (`apartment.active = 0`) are skipped, as `check_deadlines` does.
- Host mail is not sent and not marked when mail is off or the legal entity has no contact address. The next run tries again.
- The deadline-alert pass and the watchdog run in separate `try` blocks, so one failing does not silence the other.

## What Cursor must verify or adapt when applying on the real main
- `reservation.at_risk_mailed_at` is added through `ADDED_COLUMNS`. WP23 comes before WP18 in the series, so it is part of the frozen baseline (version 1). If WP18 is already on main when WP23 lands, move it into a numbered migration file instead.
- `mail.KINDS` is pinned in `tests/test_claim_mail.py`. Any kind added on main has to be merged into that set.
- The four `guest.manual_*` columns are in `ADDED_COLUMNS` too (same rule as `at_risk_mailed_at` if WP18 is already on main).
- Any code on main that sends or re-sends guests outside `collect_sendable` must skip `guest.manual_filed_at`. Any new place that shows a guest's filing time should prefer `manual_filed_at` (see `reporting._filing_stamp`).
- The stay page form uses only existing CSS classes (`panel tight`, `settings-grid`, `field`), so no `app.css?v=` bump; check the layout on the real page.
- Check the Czech wording of the new stay page strings, the "no guest details" mail and the digest section with the owner.
- `config.OPERATOR_EMAIL` falls back to `support@ubyhost.com`. Check that this mailbox is read, or set `UBYHOST_OPERATOR_EMAIL`.
- Check the Czech wording of the mail and the guide with the owner.

## Manual steps for the owner
- Create a healthchecks.io (or similar) check with period 30 min and grace about 30 min. Let healthchecks.io notify the owner by e-mail. That mail is sent by healthchecks.io, so it still arrives when UbyHost's own mail is broken. Put its ping URL in `UBYHOST_HEARTBEAT_FILING_URL` in the production `.env`. Test it once: set the URL, wait for a run, check the check goes green.
- Production mail must be on (SES) for the host mails and the digest. The heartbeat does not depend on mail.
- Tell hosts: after filing in the UbyPort web application, open the stay and press "I filed this stay by hand in UbyPort". Until then the stay stays at risk and keeps the filing check red. A mistaken mark can be undone for 24 hours; after that it is the record.
- Unknown-risk stays (no guest entered) show in the digest but never turn the filing check red.

## Addendum: integration on main (PR 230 merged)
- No SMS or Telegram anywhere: the healthchecks.io filing check notifies the owner by e-mail. `config.py`, `deploy/lightsail/.env.example` and the old plan in `docs/plans/` say so. Code unchanged by this.
- PR 230 resends an unclear (`outcome_unknown`) batch once from the sweep and marks it with `submission.retried_at`. The watchdog now treats a stay whose every unfiled guest is on such a batch, not yet resent, before its deadline, as "awaiting the automatic resend" for at most `RETRY_GRACE` (two sweep intervals, 20 minutes by default) from the batch's finish time. In that window it gets no host mail, no digest line and no heartbeat `/fail`. After the grace, after the resend, with any other unfiled guest, or once the deadline has passed, it is at risk as before. `run()` returns `awaiting_retry`; the scheduler logs it and WP13's run line carries it. 6 new tests in `tests/test_filing_watchdog.py` (38 in the file).
