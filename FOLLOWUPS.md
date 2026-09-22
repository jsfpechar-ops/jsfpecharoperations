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

### The remediation plan itself is not in the repository

`docs/audit/CURSOR_REMEDIATION_PLAN.md` was supplied as an attachment and does
not exist on disk; the audit it references lives at `docs/UBYHOST_CODE_AUDIT.md`,
not `docs/audit/UBYHOST_CODE_AUDIT.md`. If the plan is meant to be the durable
record of this work, it needs committing alongside the code.
