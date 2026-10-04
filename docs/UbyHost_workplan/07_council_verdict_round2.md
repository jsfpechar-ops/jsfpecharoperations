# Council round 2 and poteto-mode review of the 33-patch plan

Status: applied. WP33 is patch 0021, the later patches are now 0022 to 0034, and the gates and Cursor rules are in `00_README_for_cursor.md`. Patch numbers below are the new ones.

Question. Is this the right plan and order for Joe right now? What should be cut, reordered or added before Cursor gets it? What could go wrong when a non-developer runs 33 PRs through an AI agent?

Five advisors (Contrarian, First Principles, Expansionist, Outsider, Executor), five anonymous peer reviews, then a chairman check against the plan files and the repo.

## Where the council agrees

- The core promise is unproven. Patch 0006 (Doručenka) was inferred from the official document. Nothing past 0007 matters until one filing returns a real Doručenka PDF.
- The tests were written by the same AI that wrote the code. They prove the code matches the tests. They do not prove UbyPort accepts the XML.
- Joe cannot review 25k lines. So the gates have to be things he can see and click, not code review.
- 0021 to 0033 wait until a paying host asks for one of them.
- AI-translated German, Spanish and French on a legal form should not go live unread.
- All five advisors want one paid hour with a Czech lawyer.

## Where the council clashes

- Infra first or filing first. Three advisors want 0006 and 0007 before 0001 to 0005. The chairman keeps the order. Joe asked for the infra now, the infra PRs are low risk, and the filing test needs staging (0004). If the infra stalls, 0006 and 0007 can go first. They apply cleanly straight on main (measured). The watchdog 0018 does not.
- Cut staging and the scheduler split. The Contrarian wants both cut. Every reviewer disagreed. A non-developer needs staging most. The split is already built and tested. Kept.
- Expand now. The Expansionist wants Stripe now, a filing adapter for other countries, and channel-manager integrations. All five reviewers named this the biggest blind spot. Rejected for now. Logged as a later option.

## Corrections against the plan files

- "Cut the Meta and Google ads work." It is already in 0021 to 0033 and behind switches that stay off. No change needed.
- "Cursor re-implements the patches." The README tells Cursor to apply them with `git am -3`. Drift is still a real risk if Cursor "improves" a patch. A rule now covers it (below).
- "Add a restore drill." It already exists. See `restore_test.sh` in 0001 and checklist step B6.
- "Filing a fake guest to the live police system may be unlawful." The plan uses the UbyPort test endpoint (`UBYHOST_UBYPORT_ENV=test`, checklist C1 and D1). No fake guest goes to production.
- "Hosts must authorise UbyHost to file." Covered by the "zmocňuje" clause in 0019.
- "Encryption is scheduled too late." Guest data is already encrypted. 0028 (WP16) separates the data key from the session secret. That is worth doing before real passports. Moved up (below).

## Blind spots the reviewers caught

- Overdue stays are missing from the default Stays view (WP28 open item). In a deadline product, this hides exactly the stays a host is about to be fined for. This is a must-fix before the first host.
- Solo coverage. If Joe is ill or travelling, deadlines slip. Checked in the code: the watchdog already e-mails the host for every stay at risk (WP23), and every host gets `compliance/05_manual_filing_fallback.md`. No change needed.
- Cutting or reordering a linear stack breaks later patches. Any change goes on top as a new patch. The stack is never rewritten.

## The recommendation

Keep the series. Add four gates and two changes.

1. Gate 1. Merge 0001 to 0005, then run the restore drill.
2. Gate 2. Merge 0006 and 0007, then file one test stay on the UbyPort test endpoint. If no Doručenka comes back, stop and report.
3. Gate 3. Merge 0008 to 0020 one PR a day, each clicked through on staging. If Joe cannot explain a PR in one sentence, it waits.
4. Gate 4, first real host. 0001 to 0021 merged, a live Doručenka received, every health check green, and the two changes below in place.

Change A (done, 0021 WP33). The default Stays view shows overdue stays that are not yet filed.

Change B (done, 0021 WP33). A switch `UBYHOST_GUEST_LANGS` (default `en,cs`) keeps German, Spanish and French off until a native speaker reads each one.

Not done. Moving WP16 (separate data key, now 0029) to right after Gate 4 conflicts in `db.py` with WP12, WP14 and WP15 (measured). It stays in place. Guest data is already encrypted, so this is defence in depth, not a gap.

Rule for Cursor. Apply each patch exactly as written. Never edit an earlier patch. Any fix is a new commit on top.

## The one thing to do first

Book the UbyPort test-endpoint access now, so Gate 2 is not waiting on the police when 0007 lands.

## Poteto-mode review

The leaf skills were not installed, so the one-line summaries were applied.

- Prove It Works. The Doručenka fix stays unverified until the test endpoint returns a PDF (inferred from the plan files). Gate 2 makes that the stop point.
- Sequence Work into Verifiable Units. The series is linear and verified as a whole (measured, 2,775 tests passed on the final tree). The gates add a check Joe can see after each unit.
- Laziness Protocol. 13 of the 34 patches wait for real demand (measured from the README order). The filing adapter, Stripe and multi-country work do not earn their place yet.
- Fix Root Causes. The Doručenka bug was the element order in the SOAP header (inferred from the WCF serialisation rule). 0006 fixes the order instead of patching around it.
- Make Operations Idempotent. 0007 resends an interrupted filing exactly once (measured by its tests). A double police filing is the worst outcome of a retry loop.
- Encode Lessons in Structure. The cookie guard, analytics guard and em-dash tests turn the privacy brand into failing tests (measured, present in 0016 and 0033). The language switch in Change B does the same for unread translations.
- No is an acceptable answer. The council's calls to cut staging and to expand now were declined, with reasons above.
