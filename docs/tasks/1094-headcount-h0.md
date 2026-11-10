# 1094: head-count change, H0 read-only check (written answers, no code)

Status: todo
Tier: C | Depends on: 1092 (merged in #884; `App/app/headcount.py` is in main) | Base: origin/main | Branch: claude/1094-headcount-h0
Executor: Sonnet (Tier C), effort medium | Attempts: 1 | Fits one session: stop at 30 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: orchestrator reads the answers file before it writes H1.
Report: docs/tasks/1094-headcount-h0-answers.md (the answers file is the report; no separate report file)

## 1. Objective

Read-only investigation. You change NO code, template, test, migration or doc except one new file, `docs/tasks/1094-headcount-h0-answers.md`. It answers the six H0 questions (a) to (f) of the head-count plan ("Fewer people coming?") with `file:line` evidence, so the orchestrator can write the H1 to H4 briefs. Do not fix anything you find: write it down.

Owner decisions that shape the questions (2026-11-10):
- Every change a lead makes to saved data after claiming gets a "Check your changes" confirm step (old and new value side by side; "Confirm changes" / "Go back"; a server page, works without JavaScript). Nothing is saved or mailed before the confirm. A first registration is NOT covered (Q8).
- Every confirmed lead change also feeds a host digest mail: field names and guest position only ("Guest 2: document number changed"), never names or values (Q9), with a button to the stay page, where the host (logged in) sees old and new values.
- Q12: a small Go change may ship in the same PR as the Python count rule.
- (a) therefore must be complete: any change route it misses ships with no confirm step and no host mail.

## 2. Context

- 1092 (PR #884) made `App/app/headcount.py` the single locked writer of `reservation.declared_guests` for guests (`set_declared_guests`, `apply_declared_in`, floor = live guest rows, ceiling 60, audit rows `reservation_declared_guests_set` / `_refused`).
- The count rule today: `expected_guests_override` (host, direct booking, webhook) else `declared_guests` (lead). `reporting.expected_guest_count` is the Python copy; the plan lists six more copies (`claim.py`, `routes/admin.py` SQL, `stays_export.py`, `go/internal/ubyport/recover.go`, `go/internal/calendar/handler.go`, templates `reservation_detail.html`, `guest/claim.html`). Line numbers in the plan are old: use grep, not the plan's numbers.
- Lead = the claimed lead guest of a stay (claim session). Member = any other guest with the link only.
- The plan's source text is not in the repo. Do not look for it. Everything you need is in this section and in section 4.

## 3. Files

| Path | Action |
|---|---|
| `docs/tasks/1094-headcount-h0-answers.md` | create (the only change) |
| everything else | read only |

## 4. Steps

Commit once at the end: `1094: H0 answers`. Run every command with `| tail -30` (or `head -50`). Grep first, then read ranges of 150 lines or fewer.

1. **Start commands** (run these, do not widen them):
   - `grep -n "@router\.\(post\|get\)" App/app/routes/guest.py | head -60`
   - `grep -rn "declared_guests\|expected_guests_override\|expected_guest_count" App/app --include=*.py | head -80`
   - `grep -rn "declared_guests\|expected_guests_override\|expectedGuests\|ExpectedGuests" go --include=*.go | head -40`
   - `grep -rln "declared_guests\|expected_guests_override\|expected_guest_count\|expected" App/app/templates | head -30`
   - `grep -rn "checkin_hour\|checkinHour\|CheckinHour" App/app go --include=*.py --include=*.go --include=*.html | head -50`
   - `grep -rn "declared_guests\|expected_guests_override" App/app/ical*.py App/app/booking_site.py App/app/booking_manage.py go/internal/calendar --include=*.py --include=*.go | head -40`
   - `ls App/tests | grep -i "party\|guest\|claim\|save\|scan\|remove\|headcount\|calendar\|ical\|webhook\|ubyport_recover" | head -50`
2. **(a) Lead changes after claim.** List every guest-side route that changes saved data (stay or guest row) after a claim: `/party`, `/another`, `/save` on an existing row, the remove-person route, any `/scan`-type route, document or photo replace or delete, language, contact or e-mail change, claim re-send, and anything else you find in the `@router.post` list for guest pages. Per route: path, method, function and `file:line`, fields written, template that posts to it, whether it checks a valid claim session, whether it checks that the caller is the lead (not a member, not a host view-as-guest session), and what it does when the check fails. The remove route gets its own paragraph (does it check the claim and the lead role at all, who can call it with only link and PIN). Mark each row `lead change` (needs confirm and digest), `first registration` (not covered, Q8) or `other`. Say which changes are already audited and with what audit event name and detail (the digest is built from audit rows: detail must hold field names, never values).
3. **(b) Count writers and readers.** Verify `headcount.py` is the only writer of `reservation.declared_guests` for guests: list every `declared_guests` and `expected_guests_override` write (Python `db.insert`, `db.update`, raw SQL, migrations, demo data) with `file:line` and mark each `via headcount` or `bypass`; host writers (admin), direct booking and webhook writers are expected: list them as such. Then list every reader in Python, in Go under `go/`, and in templates, with `file:line`, what it computes from the count, and whether it copies the rule (`override` else `declared`) or calls `reporting.expected_guest_count`. This list is what H1 must change together.
4. **(c) Sync.** For iCal sync, channel sync and the webhook (direct booking): on INSERT and on UPDATE of an existing reservation, does any of them write `declared_guests` or `expected_guests_override`, clear it, or overwrite it with the same number? Evidence per path (`file:line`). Say what happens to a lead's lowered count when the same booking is updated by sync.
5. **(d) `checkin_hour`.** Where it is defined (schema, migration, setup form), its type and default, what an empty or NULL value means in each reader (Python and Go), and what time the lead's cut-off ("until check-in time on arrival day") would use when it is empty. Give one recommended fallback hour with the reason, as a suggestion for the owner.
6. **(e) Go.** Record: owner Q12 (2026-11-10) allows a small Go change in the same PR as the Python count rule. Name the exact Go file and function H1 would change (expected: the count read in `go/internal/ubyport/recover.go` and the one in `go/internal/calendar/handler.go`; confirm or correct), quote the current rule (3 lines at most), say what columns Go already reads, and say whether the Go tests (`recover_test.go`, `handler_test.go`) have a table H1 can extend. Do not run Go tests.
7. **(f) Signature and passport photo in the lead edit form.** Read how the form that edits an existing guest posts `/save` and `/scan`: where the signature and the passport photo are held between steps (hidden field, session, temp file, database), what happens when the edit is posted without a new signature or photo (kept or cleared), size and format. Decide, with evidence, whether a stateless confirm page (hidden fields only, no server draft) can work for an edit: (i) for text fields only, (ii) with a new signature, (iii) with a new photo. If a photo or signature cannot be a hidden field, say what the smallest honest option is (for example: the confirm step shows "new photo" without a preview and carries a token, or editing the photo stays outside the confirm and gets a digest line only). Give one recommendation for H2b.
8. **Tests per route.** For every route in (a), plus the count routes of (b): the test files and test names that cover it (`grep -ln` the path in `App/tests`), or `none`. One table for H1 to H4.
9. Write `docs/tasks/1094-headcount-h0-answers.md` (format below), set this brief `Status: review`, run `python3 scripts/context_lint.py | tail -30` from the repo root and fix findings in the answers file, commit, push (`git push -u origin claude/1094-headcount-h0`). No PR.

## 5. Do not touch

Everything under `App/`, `go/`, `scripts/`, `docs/` other than the answers file and this brief's `Status` line. No test run, no server start, no dependency. Never push to `main`.

## 6. Commands

Only greps and reads (section 4), then from the repo root: `python3 scripts/context_lint.py | tail -30`. No pytest, no `go test`.

## 7. Acceptance

- [ ] Six answers (a) to (f) and the tests table exist, each with `file:line` evidence.
- [ ] (a) names the remove route's claim and lead check result.
- [ ] (b) states whether `headcount.py` is the only guest writer, listing any bypass.
- [ ] (e) names one Go file and one function for H1.
- [ ] (f) ends with one recommendation for H2b.
- [ ] `git diff --stat origin/main` shows only the answers file and this brief.
- [ ] `python3 scripts/context_lint.py | tail -30` is clean.

## 8. Stop and ask

STOP and report `blocked` if: a file named here does not exist and grep finds no replacement; you would need to run the app. If any finding would need a code change, write it down in `## Needs a code change` and carry on: never make it. At 30 tool calls or 60k tokens: write what you have, mark the open questions `not answered`, commit, and end with `Done: (a) to (k). Left: ...`.

## 9. Report (output format of the answers file)

One `##` heading per question (`## (a)` to `## (f)`, then `## Tests per route`), each starting with a two-line verdict, then a table:

- (a): `Route | Method | Function file:line | Fields written | Posted from template | Claim checked | Lead checked | Class | Audit event`
- (b): `Where file:line | Language | Read or write | Via headcount or bypass or host or sync | Copies the rule`
- (c): `Path | Insert writes count | Update writes count | Evidence file:line | Effect on a lowered count`
- (d): `Reader file:line | Empty or NULL means | Default` (plus the recommended fallback)
- (e): `File | Function | Current rule | Columns Go reads | Test table`
- (f): `Item | Held in | Survives a stateless confirm | Evidence | Option`
- Tests: `Route | Test file | Test names or none`

Last section `## Needs a code change` (never made here): one line per finding, `file:line | what is wrong | which brief (H1 to H4) should fix it`. A bypassing writer, a route with no claim or lead check, or a count copy not listed in the plan goes here. Evidence is `file:line`, never a guess: write `not found` when grep finds nothing. No guest data, names, IDUBs or addresses in the file (public repo). Keep it under 300 lines.
