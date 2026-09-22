# Follow-ups

Out-of-scope observations found while executing the remediation plan. Nothing
here was acted on: each entry needs a decision before it becomes work.

## From Phase 1 (missed filing paths)

### W1.5 — the completion gate waits for the quiet window, not for a save

`reporting.refresh_registration_completed_at` now treats a stay as final once
every form on file is complete and none has been touched for
`HEADCOUNT_QUIET_HOURS` (12 h). That function is only reached from a save path
(guest form save, host guest save, declared-count change), so a stay whose party
stopped growing and where nobody saves again stays unfiled until the next save.
The host is told: `headcount_mismatch` fires once the stay has started, so the
suppression is visible rather than silent. A periodic sweep in the `deadlines`
job would close the last gap, but it would also start unattended automatic
submissions, which is a product decision rather than a bug fix.

### W1.5 — a raise after completion re-opens the gate

`_set_declared_guests` calls `maybe_submit_after_completion`, which re-evaluates
completion. Raising the declared headcount therefore clears an already-reached
`registration_completed_at` and puts the stay back behind the quiet window. The
wait is bounded at 12 h and the host is alerted, but "the link holder cannot
hold the filing open" is only true after the quiet window, not immediately.

### W1.5 — the guest is not told the stay will be filed with fewer people

The plan's preferred option 1 would have refused the increase and told the guest
so. Under option 2 the guest link accepts the increase and says nothing; only
the host is alerted. Guest-facing copy explaining that the stay is filed with
the forms received would need a new EN/CS key in `host_i18n.py`.

### W1.5 — the plan's preferred remedy was not the one implemented

The plan prefers capping the declared headcount at what the guests filled
(option 1). That would have removed the "Add another person" affordance and
broken `test_completed_party_can_add_another_person` and
`test_an_unexpected_extra_guest_can_still_register`. Option 2 was chosen
deliberately and the reasoning belongs in the PR description.

### D3 — the inclusive reading still needs counsel, not just a decision

D3 was answered by the owner: the arrival day counts as the first working day
when it is one, so a Monday check-in now files by Wednesday. That is a product
call implementing the stricter reading of §100(c); the plan itself notes it
"needs counsel or a citation", and no citation has been recorded. If counsel
reads the window as starting the day after arrival, `deadlines.add_working_days`
reverts to `remaining = count` and the eight tests that pin the arithmetic will
need the same one-day shift. Worth one line of citation in `deadlines.py`
either way.

### W1.7 — an empty feed is now reported as incomplete

The retention guard raises `feed_incomplete` whenever the feed yields fewer
stays than the completeness threshold, which includes a feed that parsed
cleanly and returned nothing. All stays are still retained, so nothing is
cancelled, but a legitimately empty calendar will warn once per sync cycle.
Treating a fully empty parse as "nothing to compare against" instead is a
judgement call.

### Where the remediation plan lives

The plan was supplied as an attachment while Phase 1 ran and was not on disk;
it has since been committed to `main` as `CURSOR_REMEDIATION_PLAN.md` (root,
`f984560`). Two path notes: the plan's own header calls itself a companion to
`UBYHOST_CODE_AUDIT.md`, which lives under `docs/`, so the two documents do not
sit together; and the plan's `[Fnn]` references point at the audit in `docs/`.

## From Phase 2 (guest passport data at rest)

### W2.1 — the orphan-submission delete waits for the retention clock

The plan says to delete `submission` rows that have no surviving `guest` rows
after the guest purge. It is implemented that way *and* gated on the six-year
`retention_cutoff`, because a submission row with no guests is not always a
submission that never happened: a host who deletes a guest entered by mistake
would otherwise lose the Doručenka for a filing that really was sent, and the
receipt is the evidence the host has to be able to produce. Pinned by
`test_deleting_a_guest_by_hand_does_not_take_a_recent_receipt_with_it`. If the
intent was the literal reading, the gate comes out and that test is inverted.

### W2.1 — "terminal state" was read as every settled state

`reporting.purge_submission_payloads` blanks a payload once the submission is
no longer in flight (`ok`, `partial`, `error`, `transport_error`). The plan says
"terminal" without defining it. `running` is the only state excluded, so an
attempt that failed and will never be retried keeps its XML until the 90 days
elapse. The narrower reading — only `ok` — would retain envelopes for failures
the host may still need to diagnose.

### W2.2 — the plaintext columns are already dead, and are not dropped

The plan's step 3 says to write through both columns and step 5 says to stop
writing the plaintext one "only in a later release". Those two cannot both hold
with the plan's own required test that the stored value must not be the
plaintext, so plaintext writing stopped immediately and the plaintext column
survives only as a read fallback for rows the backfill has not reached. Two
things follow that a later release should pick up:

1. **The backfill is a manual deploy step.** `App/scripts/migrate_encrypt_doc_fields.py`
   is documented in `docs/OPERATIONS.md` but is not wired into
   `deploy/lightsail/scripts/deploy.sh`. Nothing runs it automatically, so
   production stays on the fallback until someone runs it. Wiring it in (or
   gating the deploy on it) is the durable fix; it was left out here because
   changing the deploy script is outside this work item.
2. **The plaintext columns are never dropped.** Once production is confirmed
   backfilled, `doc_number` and `visa_number` can stop being read and can be
   dropped, which removes the fallback path and the `_hydrate` shim with it.

### W2.2 — names and birth dates are still cleartext

The plan scopes this work item to `doc_number` and `visa_number` and defers the
rest. Guest `surname`, `given_names`, `birth_date` and `birth_place` are still
stored as plaintext and are the same class of personal data; they were deferred
because they appear in search, sort and PDF paths, so encrypting them changes
more than a column. Worth doing as its own change if the owner wants it.

### W2.4 — a link queued before this release still sends

`mail.delivery_body` passes a body with no marker through untouched, which is
what lets a rolling deploy finish the rows the previous release queued with a
cleartext link. That also means a cleartext link in a payload written before
this release keeps working until it is sent or purged. Once no such row can
exist — 14 days of retention, so one release cycle — the pass-through can
become a hard error.

### W2.4 — the platform-admin console view still reveals the secret

`recent_console_messages(None)` returns every workspace's console rows and puts
the secret back in each, because that is what it did before this change and who
may see what is not part of this work item. A platform admin therefore still
sees a working claim link for any host's guest. Narrowing that branch is a
product decision about platform-admin access, not a fix to the retention
finding.
