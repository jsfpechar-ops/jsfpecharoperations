# Explicit state machines: rounds 2 to 4

Follows round 1 (`docs/plans/explicit-state-machines.md`, on PR #920: tables and pin tests, no runtime change). Owner asked 2026-11-11 for every remaining brief now, and for Go where it saves a later port.

## Language rule

- A fix goes where the writer lives. A writer that exists in both languages is fixed in both, in one brief, so the twins stay in step.
- New shared logic that must outlive the Python app is written in Go (`go/internal/statemachine`) or in Postgres (needs no port at all).
- Nothing is ported to Go only to host a one-line fix. Door codes, cleaning codes, claim, mail and guide import stay in Python until their domain is ported as a whole (status: further Go slices are on hold).

## Round 2: fix what round 1 found

Each brief starts with a test that fails on today's code and shows the fault, then the smallest fix, then the pin-test update. Base: PR #920 merged to main (the tables and pin tests must be present).

| Brief | What | Language | Risk | Writer |
|---|---|---|---|---|
| 1113 | CI: retry the `apt-get install age` step that fails on runner DNS | workflow | low | Sonnet |
| 1114 | Stale-submission recovery overwrites a state that changed after the read: add the state guard to the write | Python and Go | HIGH RISK filing | Opus |
| 1115 | `claim.start_claim` can turn `claimed` back to `provisional`: guard the write | Python | guest-data access | Opus |
| 1116 | `door_codes._handle_cancellations` read-then-write: guard the write | Python | concurrency | Opus |
| 1117 | `guide_import` row stays `running` when its worker dies: stale reset | Python | low | Sonnet |
| 1118 | `docs/OPERATIONS.md` submit_state section: make it describe the code; list the moves the owner must rule on | docs | filing doc | Sonnet |
| 1121 | A guest blocked as a duplicate stays `blocked` when an edit changes no field reported to the police (ruling 1 below) | Python | HIGH RISK filing | Opus |

These touch different files and run in any order. 1113 first helps every other PR's CI.

## Round 3: one source that survives the port, and observation in production

| Brief | What | Language | Risk | Writer |
|---|---|---|---|---|
| 1119 | `go/internal/statemachine`: every round 1 table as Go data, plus a parity test that fails when a Go table and its Python table differ. No caller yet | Go | low | Sonnet |
| 1120 | Observe mode in Postgres: one trigger per state column that records, and never blocks, a state change the table does not allow, into a small log table. Covers Python and Go writers with no writer change | Postgres | HIGH RISK migration | Opus |
| 1111 | CHECK constraints (written in round 1; its migration number `00015` is now taken and must be renumbered before it runs) | Postgres | HIGH RISK migration | written |

1120 is Postgres only, which bends rule 5 (Postgres-portable SQL). Owner agreed 2026-11-11: Postgres only. 1120 runs after 1119 and takes migration `00016`; 1111 is renumbered to `00017` and runs after it.

## Round 4: enforce (cannot be briefed yet)

After 1120 has run in production with no recorded violation for a machine, that machine's trigger changes from "record" to "refuse", one machine per brief, filing machines last. These briefs need the production record first, so they are written then.

## Owner decisions needed

1. Filing rulings from 1118. Owner, 2026-11-11: "do the recommended"; the recommendations are the orchestrator's:
   - Duplicate-blocked guest returns to `pending` after any edit: change the code (brief 1121). Only an edit to a reported field may reset it.
   - A record-level 150 becomes `sent`: keep. It follows the police letter the code comment cites.
   - `sent` moves to `error` or `blocked` after a refused host resend: keep for now. It shows the host their correction was refused.
   - A reportable guest still marked `not_required` is sent: keep. It is the safe direction for the filing duty.
2. 1120: Postgres-only trigger. Answered yes (owner, 2026-11-11).
3. 1111: run its production query; merge only when ready to run `pg_schema.py apply` at once.
