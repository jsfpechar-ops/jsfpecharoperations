# 1118: OPERATIONS.md submit_state section describes the code

Status: review
Depends on: PR #920 merged to main (the `TRANSITIONS` table and the pin test must exist) | Base commit: PR #920 merged to main | Branch: task/1118-sm-submit-state-doc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**HIGH RISK: police filing documentation.** Docs only. You replace one section of one file. You change no code, no test and no other doc.

## Open questions

None block the work. Every disagreement listed in brief 1105 was re-checked against the code of PR #920 (see section 2, "Checked against the code"); all nine were confirmed, none dropped. The Python line numbers in 1105 have shifted; this brief cites functions instead.

## 1. Objective

Replace the section "The `submit_state` state machine" in `docs/OPERATIONS.md` so it describes what the code does today: a table of every from-to move in `TRANSITIONS`, with the writer (file and function, Python and Go) that makes it. It also says the table in `App/app/reporting.py` and the pin test are the source of truth, so a reader stops trusting this prose over the code.

## 2. Context

Rules that bind this brief: this section describes, it does not decide ([plan](../plans/explicit-state-machines.md) rule 1: derive, never design). Each of the four moves in "Rulings" is described as the owner ruled: kept as intended, or current and changing with brief 1121. Plain words, short sentences. Write "no tracking cookies", never "no cookies" (no such text is in this section). The heading text must not change: `AGENTS.md`, `docs/context/glossary.md` and `docs/integrations/ubyport-police-api.md` link to `#the-submit_state-state-machine`.

Size and link rules checked: `docs/context/rules.md` has no cap or link rule for `docs/OPERATIONS.md`, and `scripts/context_lint.py` has no entry for it in `CAPS` and does not list it in `CHECKED`. This brief itself is capped at 12000 tokens by the lint.

### Checked against the code (PR #920 branch)

All nine disagreements from brief 1105, re-read in the code. Each is confirmed.

1. **A record-level 150 gives `sent`, not `blocked`.** `App/app/reporting.py:plan_outcome` sets `new_state = SENT` when `uby_errors.record_is_duplicate(record_error, codebook)`; Go: `go/internal/ubyport/outcome.go:PlanOutcome` does the same with `RecordIsDuplicate`. `record_is_duplicate` reads only the record's own codes. `classify` reads header and record codes and returns `not_correctable` for code 150, so a duplicate named only in the batch header becomes `blocked`.
2. **Moves out of `sent` exist.** `collect_sendable` lets a `sent` guest through when `allow_resend` is set and it was not filed by hand. A refusal then writes `error` or `blocked` (`plan_outcome`, `PlanOutcome`).
3. **Hand filing.** `mark_filed_by_hand` moves `pending`, `error`, `blocked` to `sent` (`UPDATE ... WHERE id = ? AND submit_state = ?`). `undo_filed_by_hand` moves `sent` back to `manual_prev_state` if it is `pending`, `error` or `blocked`, else `pending`.
4. **`error` and `blocked` move both ways.** `plan_outcome` and `PlanOutcome` write from any state.
5. **The guest form also resets.** `guest_form_save` sets `pending` (or `not_required`) on edit of any non-`sent` row, clears `last_errors`, and resets `submit_attempts` through `reporting.guest_correction_resets_attempts`.
6. **Not "anything to `not_required`".** `guest_update` keeps `sent`; `guest_form_save` refuses `sent`; `collect_sendable` and `CollectSendable` skip `sent` and `not_required` before the write. The move also happens in the sweep's collect step.
7. **A duplicate-blocked guest is sendable after an edit.** `collect_sendable` skips `blocked` plus `blocked_as_duplicate(guest)` even on a resend, but `blocked_as_duplicate` reads `last_errors`, and `guest_update` and `guest_form_save` both set `last_errors` to `None` and the state to `pending`.
8. **`not_required` can be sent.** `collect_sendable` and `CollectSendable` have no check that excludes a reportable guest in `not_required`, and the outcome write has no state test.
9. **Not a move.** `guest_update` saves the fields of a `sent` row and keeps the state. The guest form and the host delete paths refuse `sent` rows.

The 19 pairs in the new table equal the pairs in `TRANSITIONS` (`App/app/reporting.py`, the dict right after the five state constants). The brief author checked this by script.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/OPERATIONS.md` | edit | Replace the one section "The `submit_state` state machine" (step 2). Nothing else in the file |
| `docs/tasks/1118-report.md` | create | Your report (section 9) |

No other file may change.

## 4. Steps

Run every command from the repo root. Commit after each step with the message `1118 step k`.

1. Confirm the anchors.

   ```
   grep -nF '## The `submit_state` state machine' docs/OPERATIONS.md | tail -30
   grep -nF '## UbyPort error codes, and what 112 and 150 really do' docs/OPERATIONS.md | tail -30
   grep -cF 'in practice code 150, a duplicate' docs/OPERATIONS.md | tail -30
   grep -nF 'TRANSITIONS = {' App/app/reporting.py | tail -30
   ```

   Expected: one line with the heading; one line with the next heading (the old section is the 39 lines before it, plus one blank line); `1`; one line `TRANSITIONS = {`. Any difference: STOP.

2. In `docs/OPERATIONS.md`, replace the whole old section (the text between the two headings above, and including the first heading, not including the `## UbyPort error codes` heading or the blank line before it) with the new section below. Use the Edit tool with the old text as `old_string` and the new text as `new_string`. The anchor is the whole old section; if it is not found verbatim, STOP.

   OLD (verbatim, 39 lines):

   `````markdown
## The `submit_state` state machine

One value per guest row, defined in `App/app/reporting.py`. It is the record of
whether that individual has been reported.

| State | Meaning |
| --- | --- |
| `pending` | Not yet accepted by UbyPort. The default, and where a record sits between the guest signing and the next sweep. |
| `sent` | UbyPort holds this record. Never resent automatically. |
| `error` | Rejected in a way that correcting the data can fix. |
| `blocked` | Rejected in a way resending will not fix — in practice code 150, a duplicate. 112 does **not** belong here: it is an accept; see below. |
| `not_required` | Czech national: house book only, no reporting duty. |

Transitions:

- `pending → sent` — the response carried no error codes for this record, or
  only codes of severity 0-2 (for example 112, reported late).
- `pending → error` — code(s) of severity 4-6, or of unknown severity, returned.
- `pending → blocked` — a non-correctable code (150, or a codebook text
  matching `duplic`/`pozd`/`late`).
- `error`/`blocked`/`pending` **→ `sent`** when the response says duplicate
  (code 150). See below.
- `error`/`blocked`/`not_required` → `pending` when a host edits the guest —
  rule 10.4(5), correcting a rejected record must make it sendable again. A host
  edit of a reportable guest also stamps `identity_verified_at`, and it resets
  `submit_attempts` to 0.
- **Nothing changes state when the automatic sweep gives a record up.** After
  one refusal the sweep stops offering it (`submit_attempts`), but the row
  stays `error` and a host send still works. See the severity rule below.
- anything → `not_required` when the nationality is changed to Czech.
- **A transport failure changes nothing.** The guest stays `pending` and the
  `submission` row is marked `transport_error`, so the next sweep retries. This
  is deliberate: rule 10.2(e) forbids losing the queue on a network blip.

`sent` rows refuse edit and delete from both the host and guest surfaces. A
deliberate resend of a `sent` or `blocked` record requires an explicit
confirmation in the UI, and a record blocked *as a duplicate* is refused even
then, because a second duplicate cannot be accepted and duplicates count
against the host's web-service access.
   `````

   NEW (exact):

   `````markdown
## The `submit_state` state machine

One value per guest row, defined in `App/app/reporting.py`. It is the record of
whether that individual has been reported.

**Source of truth.** The `TRANSITIONS` table in `App/app/reporting.py` and the
pin test `App/tests/test_sm_guest_submit_state.py` say what the code does. This
section describes them. If this section and the table differ, the table is
right and this section is stale. The test fails when a writer is added, removed
or changed without the table; it does not read this section.

This section lists what happens today. Four moves carry a ruling by the owner
(2026-11-11), listed at the end of this section.

| State | Meaning |
| --- | --- |
| `pending` | Not yet accepted by UbyPort. The default, and where a record sits between the guest signing and the next sweep. |
| `sent` | UbyPort holds this record. The sweep never resends it. A host resend or a hand-filing undo can still move it (see the table). |
| `error` | Rejected in a way that correcting the data can fix. |
| `blocked` | Rejected with a code that resending will not fix: a header-level 150, or a code the code book calls non-correctable. A record-level 150 does **not** give `blocked`: it gives `sent`. 112 is an accept, not a refusal; see the next section. |
| `not_required` | Czech national: house book only, no reporting duty. |

### Writers

Each move below is made by one of these. `UbyPort outcome` means the answer to
a send is written back to the guest rows.

| Short name | Python | Go |
| --- | --- | --- |
| outcome | `App/app/reporting.py:plan_outcome`, applied by `submit_batch` | `go/internal/ubyport/outcome.go:PlanOutcome`, applied by `RecordOutcome` in `go/internal/ubyport/store.go` |
| collect | `App/app/reporting.py:collect_sendable` | `go/internal/ubyport/collect.go:CollectSendable` |
| hand mark | `App/app/reporting.py:mark_filed_by_hand` | none |
| hand undo | `App/app/reporting.py:undo_filed_by_hand` | none |
| host edit | `App/app/routes/admin.py:guest_update` | none |
| guest form | `App/app/routes/guest.py:guest_form_save` | none |

The outcome write has no state test in its SQL, so it can move a guest from any
state. Collect also writes without a state test; it only acts on `pending`,
`error` and `blocked` guests. The hand mark, hand undo, host edit and guest form
writes only apply if the row still has the state they read.

### Moves

Every move in `TRANSITIONS`: 19 from-to pairs. A write that leaves the state the same
is not a move and is not listed.

| From | To | Made by | When |
| --- | --- | --- | --- |
| `pending` | `sent` | outcome (Python and Go); hand mark | Outcome: no error codes, only codes of severity 0-2, or a record-level duplicate (150). Hand mark: the host marks the guest as filed by hand. |
| `pending` | `error` | outcome (Python and Go) | A correctable refusal. |
| `pending` | `blocked` | outcome (Python and Go) | A non-correctable refusal that is not a record-level duplicate. |
| `pending` | `not_required` | collect (Python and Go); host edit; guest form | The nationality is not reportable. |
| `error` | `sent` | outcome (Python and Go); hand mark | As for `pending` to `sent`. |
| `error` | `blocked` | outcome (Python and Go) | A non-correctable refusal. |
| `error` | `pending` | host edit; guest form | A correction. Rule 10.4(5): a corrected record must be sendable again. |
| `error` | `not_required` | collect (Python and Go); host edit; guest form | The nationality is not reportable. |
| `blocked` | `sent` | outcome (Python and Go); hand mark | As for `pending` to `sent`. The outcome only reaches a `blocked` guest on a host resend. |
| `blocked` | `error` | outcome (Python and Go) | A correctable refusal, on a host resend. |
| `blocked` | `pending` | host edit; guest form | A correction. For a guest blocked as a duplicate this changes with brief 1121 (see 1 below). |
| `blocked` | `not_required` | collect (Python and Go); host edit; guest form | The nationality is not reportable. |
| `sent` | `pending` | hand undo | The host undoes a hand filing; the guest returns to the state it had before, or `pending`. |
| `sent` | `error` | hand undo; outcome (Python and Go) | Undo to a prior `error`; or a host resend that came back refused. Kept for now (see 3 below). |
| `sent` | `blocked` | hand undo; outcome (Python and Go) | Undo to a prior `blocked`; or a host resend refused with a non-correctable code. Kept for now (see 3 below). |
| `not_required` | `pending` | host edit; guest form | The nationality is now reportable. |
| `not_required` | `sent` | outcome (Python and Go) | A guest who is reportable but still marked `not_required` was sent. Intended (see 4 below). |
| `not_required` | `error` | outcome (Python and Go) | Same. |
| `not_required` | `blocked` | outcome (Python and Go) | Same. |

No writer moves `sent` to `not_required`. A host edit of a `sent` row saves the
fields and keeps the state; collect skips a `sent` row.

A new guest row starts `pending`, or `not_required` for a Czech national. It is
inserted by `guest_create` (`App/app/routes/admin.py`), `guest_form_save`
(`App/app/routes/guest.py`) and the setup-guide demo (`App/app/demo.py:_guest`).
Go never inserts a guest.

### Rules that go with the moves

- **Accepted.** A record with no error codes, or only codes of severity 0-2
  (for example 112, reported late), becomes `sent`.
- **Duplicate.** A duplicate answer in the record's own codes (150, or a code
  the code book names as a duplicate) becomes `sent`, not `blocked`. A
  duplicate named only in the batch header becomes `blocked`. Intended
  (see 2 below).
- **Host edit.** A host edit of a reportable guest in `error`, `blocked` or
  `not_required` sets `pending`, clears the stored error text and sets
  `submit_attempts` to 0. It also stamps `identity_verified_at`. The guest form
  does the same reset when the guest saves their own form.
- **Collect.** When the nationality is not reportable, collect sets
  `not_required` on any state except `sent` and `not_required`. This happens
  during every sweep, not only on an edit.
- **Nothing changes state when the automatic sweep gives a record up.** After
  `SUBMISSION_MAX_AUTO_ATTEMPTS` refusals the sweep stops offering the record,
  but the row stays `error` and a host send still works.
- **A transport failure changes nothing.** The guest stays `pending` and the
  `submission` row is marked `transport_error`, so the next sweep retries. Rule
  10.2(e) forbids losing the queue on a network blip.
- **Resend.** A host resend of a `sent` or `blocked` guest needs an explicit
  confirmation in the UI. Collect skips a `blocked` guest whose stored error
  text names a duplicate, even on a resend, and skips a `sent` guest filed by
  hand. That skip depends on the stored error text, which an edit clears (see 1
  below).
- **Edit and delete of a `sent` row.** The guest form and the host delete
  paths refuse a `sent` row. The host edit saves it and keeps the state.

### Rulings

The owner ruled on these on 2026-11-11. Brief 1118 gives an example for each.

1. A guest blocked as a duplicate returns to `pending` after any host or guest
   edit, which removes the refusal to resend. This is today's behaviour.
   Changes with brief 1121: an edit that changes no field reported to the police will
   leave the guest `blocked`; an edit to a reported field may still reset it.
2. A record-level duplicate (150) becomes `sent`. Intended: it follows the
   police letter of 24 September 2026 (C2) cited in the comment in
   `plan_outcome`.
3. `sent` can move to `error` or `blocked` after a host resend is refused. Kept
   for now: it shows the host that the correction was refused. Known cost: the
   guest shows as not filed although the register holds the first record.
4. A reportable guest still marked `not_required` can be sent. Intended: it is
   the safe direction for the filing duty.
   `````

   Command: `git diff --stat docs/OPERATIONS.md | tail -30`. Expected: one file changed, only `docs/OPERATIONS.md`.

3. Check the old claim is gone and the new section is whole.

   ```
   grep -cF 'in practice code 150, a duplicate' docs/OPERATIONS.md | tail -30
   grep -cF '## The `submit_state` state machine' docs/OPERATIONS.md | tail -30
   grep -cF 'Changes with brief 1121' docs/OPERATIONS.md | tail -30
   grep -cF 'anything → `not_required` when the nationality is changed to Czech' docs/OPERATIONS.md | tail -30
   ```

   Expected: `0`, `1`, `1`, `0`.

4. Check every function the new section names still exists.

   ```
   grep -nE 'def (plan_outcome|collect_sendable|mark_filed_by_hand|undo_filed_by_hand|submit_batch|blocked_as_duplicate|guest_correction_resets_attempts)\b' App/app/reporting.py | tail -30
   grep -nE 'def (guest_update|guest_create)\b' App/app/routes/admin.py | tail -30
   grep -nE 'def guest_form_save\b' App/app/routes/guest.py | tail -30
   grep -nE 'def _guest\b' App/app/demo.py | tail -30
   grep -nE 'func (PlanOutcome|RecordOutcome|CollectSendable)\b' go/internal/ubyport/outcome.go go/internal/ubyport/store.go go/internal/ubyport/collect.go | tail -30
   ```

   Expected: 7 lines, 2 lines, 1 line, 1 line, 3 lines. Any missing: STOP.

5. Run the pin test, so the doc's claim that it exists and passes holds. From `App/`:

   ```
   .venv/bin/python -m pytest tests/test_sm_guest_submit_state.py -q --tb=short -x 2>&1 | tail -30
   ```

   Expected: all tests pass. If it fails twice: STOP and report.

6. Context lint. From the repo root:

   ```
   python3 scripts/context_lint.py 2>&1 | tail -30
   ```

   Expected: no errors (warnings about other briefs are fine). Fix nothing that is not in this brief; report any error.

7. Write `docs/tasks/1118-report.md` (section 9), set `Status: review` in this brief, open one draft PR.

## 5. Do not touch

- Every path except `docs/OPERATIONS.md` and the report.
- The heading text, the section after this one ("UbyPort error codes, and what 112 and 150 really do"), and every other section of `docs/OPERATIONS.md`.
- Code, tests, `TRANSITIONS`, Go files. Hard rule 3: no secrets, no guest data. Hard rule 8: never push to `main`; the owner merges with `scripts/merge-pr-on-green.sh`.

## 6. Commands

Exactly those in section 4, each ending `| tail -30`. No full test suite.

## 7. Acceptance

- [ ] `grep -cF 'in practice code 150, a duplicate' docs/OPERATIONS.md` prints `0`.
- [ ] `grep -cF '## The `submit_state` state machine' docs/OPERATIONS.md` prints `1`.
- [ ] `git diff --stat` lists only `docs/OPERATIONS.md` and `docs/tasks/1118-report.md`.
- [ ] `python3 scripts/context_lint.py 2>&1 | tail -30` shows no error.
- [ ] The pin test passes.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1118-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read in full: `docs/OPERATIONS.md` (the replaced section only), and compare its table against `TRANSITIONS` in `App/app/reporting.py` and `PINNED` in `App/tests/test_sm_guest_submit_state.py`.

## Rulings (owner: do the recommended, 2026-11-11; recommendations by the orchestrator)

Behaviours where the old doc and the code disagree. The new section describes each as ruled below. Names in the examples are made up. Only item 1 needs a code change; that is brief 1121, not this brief.

1. **A guest blocked as a duplicate returns to `pending` after any host or guest edit.**
   - What happens today: a `blocked` guest whose stored error text names a duplicate is skipped even on a deliberate resend (`App/app/reporting.py:collect_sendable`, `blocked_as_duplicate`). A host edit (`App/app/routes/admin.py:guest_update`) or a guest form save (`App/app/routes/guest.py:guest_form_save`) sets `pending`, clears the error text and sets `submit_attempts` to 0. The skip reads that error text, so it no longer applies.
   - Example: the register answers a batch for Anna Novak with a header-level 150, so she is `blocked`. The host fixes a typo in her phone number. She is `pending` with no error text, and the next sweep sends her again.
   - Why it may be wrong for police filing: the old doc says a second duplicate cannot be accepted and duplicates count against the host's web-service access. The edit gets round the refusal without any change to the data that matters.
   - Ruling: change the code (brief 1121). An edit that changes no field reported to the police must leave a duplicate-blocked guest `blocked`; an edit to a reported field may reset it. Reason: a second duplicate cannot be accepted and counts against the host.

2. **A record-level duplicate (150) becomes `sent`.**
   - What happens today: `plan_outcome` and Go `PlanOutcome` write `sent` when the record's own codes include 150 or a code the code book names as a duplicate. The code comment cites the police letter of 24 September 2026 (C2) that a duplicate answer proves the register accepted the record earlier. The old doc said `blocked`.
   - Example: a send for Ben Carter times out after the register took it. The next send returns 150 for him. He becomes `sent` and the house book shows him as filed.
   - Why it may be wrong: a false `sent` is a guest who was never filed. A 150 for a different person with the same document number would also read as filed.
   - Ruling: keep the code. Reason: it follows the police letter of 24 September 2026 (C2) cited in the `plan_outcome` comment.

3. **`sent` can move to `error` or `blocked` after a host resend is refused.**
   - What happens today: a host can resend a `sent` guest (not one filed by hand) after a confirmation. If the register refuses that resend with a non-duplicate code, the outcome write sets `error` or `blocked`.
   - Example: Carla Dvorak is `sent`. The host resends her after correcting a field; the register refuses the resend with a severity 4 code. She becomes `error` although the register holds her first record.
   - Why it may be wrong: she disappears from the filed count and may show as a stranded record, though she was filed. The old doc listed no move out of `sent`.
   - Ruling: keep the code for now. Reason: it shows the host that the correction was refused. Known cost: the guest shows as not filed although the first record is held.

4. **A reportable guest still marked `not_required` can be sent.**
   - What happens today: neither `collect_sendable` nor Go `CollectSendable` skips a reportable guest whose state is `not_required`, and the outcome write has no state test, so the guest moves to `sent`, `error` or `blocked`.
   - Example: Dmitri Ivanov was saved with a nationality the code treated as Czech, so he is `not_required`. A code list change makes that nationality reportable. The next sweep sends him with no host edit.
   - Why it may be wrong: this is the safe direction for the filing duty, but nothing in the code says it is meant. A guest who was never meant to be filed could be sent.
   - Ruling: keep the code. Reason: it is the safe direction for the filing duty.
