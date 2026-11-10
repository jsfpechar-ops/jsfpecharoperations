# 1094: head-count change, H0 read-only check (written answers, no code)

Status: review
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
- The count rule today: `expected_guests_override` (host, direct booking, webhook) else `declared_guests` (lead). `reporting.expected_guest_count` is the Python copy; the plan lists six more copies (`claim.py`, `routes/admin.py` SQL, `stays_export.py`, `go/internal/ubyport/recover.go`, `go/internal/calendar/handler.go`, templates `reservation_detail.html`, `guest/claim.html`). The brief review found more files that hold the columns and that the plan does not list: templates `reservations.html`, `guest/assigned.html`, `_dashboard_calendar.html`, and `demo.py`, `booking_direct.py`, `booking_webhook.py`, `db.py`. Check each one. Line numbers in the plan are old: use grep, not the plan's numbers.
- A second column of the same name exists: `reservation_claim.declared_guests` (the count a lead typed before the e-mail is confirmed; written in `claim.start_claim`, moved or cleared near `claim.py:688-714`). (b) covers both tables.
- Seed line numbers in this brief are from main at `a166812a`. They are starting points: confirm each by grep and report the line you see.
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
   - `grep -rn "@router\.post\|@app\.post" App/app/routes/guest_leon.py App/app/routes/property_page.py App/app/routes/mail_unsubscribe.py App/app/routes/privacy_requests.py | head -20`
   - `grep -n "_require_claim_session\|_owned_ids\|_require_pin\|_removal_guard\|is_claimed\|audit" App/app/routes/guest.py | head -60`
   - `grep -rn "declared_guests\|expected_guests_override\|expected_guest_count" App/app --include=*.py | head -80`
   - `grep -rn "declared_guests\|expected_guests_override\|expectedGuests\|ExpectedGuests" go --include=*.go | head -40`
   - `grep -rln "declared_guests\|expected_guests_override\|expected_guest_count\|expected" App/app/templates | head -30`
   - `grep -rn "checkin_hour\|checkinHour\|CheckinHour" App/app go --include=*.py --include=*.go --include=*.sql | head -50` (the column is defined in `App/app/migrations/0007_door_codes.sql`; for templates use `grep -rln "checkin_hour" App/app/templates | head -20`)
   - `grep -n "declared_guests\|expected_guests_override\|UPDATE reservation\|INSERT INTO reservation\|db.update(\"reservation\"\|db.insert(\"reservation\"" App/app/icalsync.py App/app/booking_ical.py App/app/booking_direct.py App/app/booking_webhook.py App/app/booking_cancel.py | head -40`
   - `ls App/tests | grep -i "party\|guest\|claim\|save\|scan\|remove\|headcount\|calendar\|ical\|webhook\|ubyport_recover" | head -50`
2. **(a) Lead changes after claim.** List every guest-side route that changes saved data (stay or guest row) after a claim. Seeds: every row of this list must appear in your table, plus anything else you find.

   | Route (all under `/l/{token}/{reservation_id}` unless a full path is given) | Function, `App/app/routes/guest.py` line |
   |---|---|
   | POST `/l/{token}/pin` | 1268 |
   | GET `/claim` (does it write or send anything?) | 1580 |
   | POST `/claim/confirm` | `claim_confirm` 1636 |
   | POST `/party` (three branches: set the count, start the claim by e-mail, re-send or change the e-mail; one row per branch) | `set_party_size` 1687 |
   | POST `/another` | `add_another_person` 1813 |
   | GET `/new`, GET `/edit/{guest_id}` (does either write a row, a draft or a cookie?) | 2028, 2079 |
   | GET and POST `/remove/{guest_id}` | `_removal_guard` 2123, `guest_remove_confirm` 2162, `guest_remove` 2183 |
   | POST `/relang` | `guest_form_relang` 2236 |
   | POST `/save` (two rows: new person, existing person; the count write through `headcount.apply_declared_in` near 2595 is a third row) | `guest_form_save` 2312 |
   | POST `/draft` | `guest_form_draft` 2721 |
   | POST `/scan` | `guest_document_scan` 2785 |
   | POST `/guide/leon` and POST `/g/{token}/leon` | `App/app/routes/guest_leon.py` 70, 97 |
   | POST `/p/{slug}/b/{booking_id}/{token}/cancel` (the booker cancels a direct booking) | `App/app/routes/property_page.py` 536 |

   Also say in one line each whether `mail_unsubscribe.py` and `privacy_requests.py` let a guest change stay or guest data, and whether any guest GET route writes data. `stay_fees.py` and `payments.py` POST routes need a host login (`auth.require_login`): do not list them. Per route: path, method, function and `file:line`, fields written, template that posts to it, whether it checks a valid claim session, whether it checks that the caller is the lead (not a member, not a host view-as-guest session), and what it does when the check fails. The remove route gets its own paragraph (does it check the claim and the lead role at all, who can call it with only link and PIN). Today `_removal_guard` calls `_require_claim_session` and then `guest_id not in _owned_ids(request)`, which is a device rule ("the device that added the person"), not a lead rule: say exactly what `_require_claim_session` and `_owned_ids` check, whether a member's device can pass them, whether the lead can remove or edit a person another device added, and whether `/save` on an existing row and `/scan` use the same rule. For each `lead change` row also say where the OLD value can be read when the confirm page is built (column and table), so H2b can show old and new side by side, and name the fields that are encrypted or are files (signature, photo). Mark each row `lead change` (needs confirm and digest), `first registration` (not covered, Q8) or `other`. Say which changes are already audited and with what audit event name and detail (the digest is built from audit rows: detail must hold field names, never values).
3. **(b) Count writers and readers.** Verify `headcount.py` is the only writer of `reservation.declared_guests` for guests: list every `declared_guests` and `expected_guests_override` write (Python `db.insert`, `db.update`, raw SQL, schema in `db.py`, demo data, and any write in Go) with `file:line` and mark each `via headcount` or `bypass`; host writers (`routes/admin.py`, seeds 3871, 4082-4162), direct booking (`booking_direct.py:48`) and webhook (`booking_webhook.py:76`) writers are expected: list them as such. List the `reservation_claim.declared_guests` writes too (`claim.py:281`, `claim.py:714`) and say when that number reaches `reservation.declared_guests` and through which function (this is the plan's "second hole through `start_claim`"). Then list every reader in Python, in Go under `go/`, and in templates, with `file:line`, what it computes from the count, and whether it copies the rule (`override` else `declared`) or calls `reporting.expected_guest_count`. Go is part of (b), not only of (e): give one row per Go read (seeds: `RefreshRegistrationCompletedAt` at `go/internal/ubyport/recover.go:166`, column list at 172; the SELECT at `go/internal/calendar/handler.go:173`), follow each value to where it is used, and say whether the Go rule treats an override of 0 the same way as Python (`routes/admin.py:4133` uses `COALESCE(NULLIF(expected_guests_override, 0), declared_guests)`; `stays_export.py:56` uses `or`). Say in one line whether any other Go package counts expected guests under another name (`grep -rn "expected\|guestCount\|GuestCount" go --include=*.go | grep -v _test | head -30`). This list is what H1 must change together.
4. **(c) Sync.** For iCal sync (`icalsync.py`; `booking_ical.py` if it writes reservations), the direct booking (`booking_direct.py`), the booking webhook (`booking_webhook.py`) and a booking cancel (`booking_cancel.py`): on INSERT and on UPDATE of an existing reservation, does any of them write `declared_guests` or `expected_guests_override`, clear it, or overwrite it with the same number? Evidence per path (`file:line`). Say what happens to a lead's lowered count when the same booking is updated by sync.
5. **(d) `checkin_hour`.** Where it is defined (schema, migration, setup form), its type and default, what an empty or NULL value means in each reader (Python and Go), and what time the lead's cut-off ("until check-in time on arrival day") would use when it is empty. Give one recommended fallback hour with the reason, as a suggestion for the owner.
6. **(e) Go.** Record: owner Q12 (2026-11-10) allows a small Go change in the same PR as the Python count rule. Name every Go file and function H1 would change (expected: two, `RefreshRegistrationCompletedAt` in `go/internal/ubyport/recover.go` and the function around the SELECT at `go/internal/calendar/handler.go:173`; confirm or correct, and say which one decides filing time), quote the current rule (3 lines at most), say what columns Go already reads, and say whether the Go tests (`recover_test.go`, `handler_test.go`) have a table H1 can extend. Do not run Go tests.
7. **(f) Signature and passport photo in the lead edit form.** Read how the form that edits an existing guest posts `/save` and `/scan`: where the signature and the passport photo are held between steps (hidden field, session, temp file, database; `/draft`, `guest_form_draft` at `guest.py:2721`, is a server-side draft: say what it stores, where, for how long, and whether it holds the signature or the photo), what happens when the edit is posted without a new signature or photo (kept or cleared), size and format. Decide, with evidence, whether a stateless confirm page (hidden fields only, no server draft) can work for an edit: (i) for text fields only, (ii) with a new signature, (iii) with a new photo. If a photo or signature cannot be a hidden field, say what the smallest honest option is (for example: the confirm step shows "new photo" without a preview and carries a token, or editing the photo stays outside the confirm and gets a digest line only). Give one recommendation for H2b.
8. **Tests per route.** For every route in (a), plus the count routes of (b): the test files and test names that cover it (`grep -ln` the path in `App/tests`), or `none`. One table for H1 to H4.
9. **Pointers for H3 and H4** (only if you are under 24 tool calls; `file:line` only, three lines each at most): the audit write helper and the audit table columns (the digest reads them); the function that sends a host mail today and any existing "one mail per N minutes" limit; `claim.sweep_reminders` (`claim.py:854`) and the template of its mail; how a feature flag is read in `App/app` today (one example).
10. Write `docs/tasks/1094-headcount-h0-answers.md` (format below), set this brief `Status: review`, run `python3 scripts/context_lint.py | tail -30` from the repo root and fix findings in the answers file, commit, push (`git push -u origin claude/1094-headcount-h0`). No PR.

## 5. Do not touch

Everything under `App/`, `go/`, `scripts/`, `docs/` other than the answers file and this brief's `Status` line. No test run, no server start, no dependency. Never push to `main`.

## 6. Commands

Only greps and reads (section 4), then from the repo root: `python3 scripts/context_lint.py | tail -30`. No pytest, no `go test`.

## 7. Acceptance

- [ ] Six answers (a) to (f) and the tests table exist, each with `file:line` evidence.
- [ ] (a) has a row for every seed route in step 2 (or `not found`), each with a class and a brief.
- [ ] (a) names the remove route's claim and lead check result.
- [ ] (b) states whether `headcount.py` is the only guest writer, listing any bypass.
- [ ] (b) has rows for Python, Go and templates, and for both tables (`reservation`, `reservation_claim`).
- [ ] (e) names every Go file and function H1 must change.
- [ ] (f) ends with one recommendation for H2b.
- [ ] `git diff --stat origin/main` shows only the answers file and this brief.
- [ ] `python3 scripts/context_lint.py | tail -30` is clean.

## 8. Stop and ask

STOP and report `blocked` if: a file named here does not exist and grep finds no replacement; you would need to run the app. If any finding would need a code change, write it down in `## Needs a code change` and carry on: never make it. At 30 tool calls or 60k tokens: write what you have, mark the open questions `not answered`, commit, and end with `Done: (a) to (c). Left: (d) to (f), tests` (your real letters).

## 9. Report (output format of the answers file)

One `##` heading per question (`## (a)` to `## (f)`, then `## Tests per route`), each starting with a two-line verdict, then a table:

- (a): `Route | Method | Function file:line | Fields written | Posted from template | Claim checked | Lead checked | Class | Old value read from | Audit event and detail keys | Brief`. `Brief` is the one that must handle the row: `H1` (count, holes), `H2a` (count pages), `H2b` (confirm for remove, add, edit), `H3` (digest only) or `none`. Under the table: the remove paragraph, then one line `Lead changes with no audit row today: ...` (H3 cannot mail these until H2b adds the row).
- (b): `Where file:line | Language (Python, Go, template, SQL) | Table | Read or write | Via headcount or bypass or host or sync | Copies the rule | H1 must change (yes or no)`
- (c): `Path | Insert writes count | Update writes count | Evidence file:line | Effect on a lowered count`
- (d): `Reader file:line | Empty or NULL means | Default` (plus the recommended fallback)
- (e): `File | Function | Current rule | Columns Go reads | Test table`
- (f): `Item | Held in | Survives a stateless confirm | Evidence | Option`
- Tests: `Route | Test file | Test names or none`
- `## Pointers for H3 and H4` (step 9): plain lines, `file:line | what it is`. Write `not done` if you skipped it.

Last section `## Needs a code change` (never made here): one line per finding, `file:line | what is wrong | which brief (H1 to H4) should fix it`. A bypassing writer, a route with no claim or lead check, or a count copy not listed in the plan goes here. Evidence is `file:line`, never a guess: write `not found` when grep finds nothing. No guest data, names, IDUBs or addresses in the file (public repo). Keep it under 300 lines.
