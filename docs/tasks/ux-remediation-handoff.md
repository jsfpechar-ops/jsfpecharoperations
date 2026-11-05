# UX remediation: handoff (incomplete, do not merge)

Status: handoff. Nothing here is merged, integrated or deployed. No batch is fully finished and no integration build exists.
Base: `7b0355c45ccdd2557a28edfcfe228aa1dc766e36` (origin/main, #786).
Plan source: UX review and remediation plan (review uploads: 9e66688c-ux-remediation, b33c8519-design-brief, ac0148e7-report, dd4af45a-improvement-plan).

## How the work is organised

- Each batch B01 to B18 has its own branch `codex/09NN-*` from base, a brief `docs/tasks/09NN-*.md` (committed on that branch) and a report `docs/tasks/09NN-report.md`.
- Batch branches are not merged into each other. Several touch the same shared files, so an integration pass will conflict: `App/app/static/app2.css`, `App/app/templates/base.html` (cache-key bumps), `App/tests/static_versions.json` (regenerated manifest), `App/app/host_i18n.py` and `host_vi_i18n.py`.
- Worktrees live under `/tmp/ubyhost-bNN-worktree` in the session that produced them. They do not survive a new session. Recreate from the branch with `git worktree add /tmp/ubyhost-bNN-worktree codex/09NN-...`.
- Code commits below are the commits on each branch that touch `App/`, counted from base.

## Batch table (verified at handoff)

| Batch | Branch | Head | Code commits | Brief status | Where it stands | Next step |
|---|---|---|---|---|---|---|
| B01 guest draft on language change | codex/0959-guest-draft-language | a7e827df | 4 | review | Language switch re-draws the typed values and keeps the step. Signature guard skips language submits. Discard warning works. Exception: RUIAN address-suggest sends typed address in a GET query (pre-existing, not changed). | Privacy review of RUIAN (open decision 5). Otherwise ready for integration. |
| B02 calendar create actions | codex/0960-b02-calendar-create | 65a7a65a | 8 | review | Cancel is a quiet secondary button beside Create in one row at every width. Label input matches Guests. Cleaning day-cell names say cleaning. Centring test compares centres, not tops (content-sized dialogs kept). 24 screenshots reviewed. | Integrate. Commands 1 to 3 were not rerun after the centring change. |
| B03 host shell on detailed forms | codex/0961-b03-host-shell | 56c2951c | 0 (brief only) | todo | Root cause: `v2` flag decides the shell. Turning it on drops about 25 classes that exist only in the old stylesheets. Brief says STOP and split. | Write 0961a (guest form) and 0961b (invoice form), each porting its classes into `app2.css`. Run both. |
| B04 property readiness | codex/0962-b04-property-readiness | d03fc45e | 4 | blocked | Six pills and Preview removal in place. Two new tests were failing: a wait_for_function TypeError (test bug) and the copy-link "Copied" check. Fix run was in progress when work was stopped. P01 (owner's narrow column) not reproduced on base. Fee-navigation test is pre-existing. | Rerun `-k b04` with zero skips, then rows 2 to 6, then screenshots. |
| B05 property wrappers | codex/0963-b05-property-wrappers | 40088a45 | 4 | blocked | Stay fee heading, police subsections, direct Archive button and copy-chooser styling in place. Test race (archive tip read before close timer) diagnosed as test-only; wait-for-hidden fix pending. Real defect: tip markup causes 98 layout-lint findings at 320 px and a 24 px tap target; fix pending. The 0963 tests passed 20 of 20 in one later run. | Apply the markup fix (keep tip next to its label, 44 px hit area), rerun rows 2 to 5, screenshots, then commit `0963 step 4`. |
| B06 connection states | codex/0964-b06-connection-states | c1e378a9 | 7 | blocked | Smart lock Off shows the top-pill status and one action. Calendar URL moved into a disclosure. Feed-URL layout fix committed (57d7c6ef) after lint found table squeezing. Four new tests pass. | Rows 3 to 5 (WebKit and IPv6 are environment deselections, state them), lint zero findings, check 1280 px lock-tile word breaking against base 7b0355c. |
| B07 guest review and legal | codex/0965-b07-guest-review | b7954474 | 12 | blocked | Review surface, aligned rows, neutral acknowledgement, shorter save label, birth-date row fixed. Acknowledgement colours verified correct (settle wait added to test, step 8). Guest spacing guards at 320, 360 and 1280 px fail after this change; two more failures unidentified. | Meet the existing spacing guards in `guest.css` without changing any threshold (inset at least 16 px at 320/360; gaps at least 12 px). Identify the two unknown failures first. |
| B08 guide completion truth | codex/0966-b08-guide-truth | 014780b4 | 1 | blocked (line still says blocked) | Accepted by the orchestrator: completion message follows the real state (none, saved, partial, live), empty questions page has one state. All 30 screenshots reviewed. Every test row passed with zero skips. Two literal checks fail only because of the brief's own text (an em dash in its checklist, and the file count includes the brief). | Flip the status line to review, or accept as-is. Open item: "0 of 17 cards answered" subline next to a populated quick-answers list (out of scope, observation only). |
| B09 calendar orientation | codex/0967-b09-calendar-orient | 8e133cfb | 8 | blocked | H1 fix, +N overflow lane, narrow-width container query. Bound 184 to 226 approved (committed). 768 px failure found: a 0 px name on a one-night bar left by an earlier test; real layout defect at that width. Fix is UNCOMMITTED in the worktree (3 files: CSS container query, template key 0967b, manifest). Repeat runs were killed. | Commit the pending fix (`git -C /tmp/ubyhost-b09-worktree diff`), run the 0967 browser file twice with fresh DBs, then checks 2 to 7, then the 18 screenshots, then `0967 step 6`. |
| B10 stay list scope | codex/0968-b10-stay-list | 229825ea | 3 | blocked | Tab label "Upcoming, current & overdue" with note, Apply and Cancel in one row, Reset as a link. Panel height at 1280 measured 393 px with no before-value. Command 3 (host suite) not passing: fee-navigation test fails on base; other failures not yet named (full run killed). Three i18n tests fail with `no such table` on base too. | Run command 3 as background chunks, name every failure, base-prove any outside B10 files, then command 5 (lint) and screenshots. Vietnamese strings not covered by a test. |
| B11 alert stacks | codex/0969-b11-alerts | b2132982 | 2 | todo (brief line not updated) | Compact alert lines and workspace labelling in place. Fee-navigation test proven pre-existing on base (deselected). Passing so far: alert browser 6 of 6, alert and deadline set 100 of 100, chunk A 26 of 26. Chunks B and C, the non-browser set, and screenshots not done. | Run chunks B and C in background, then 3d, then the screenshots, then `0969 step 4`. |
| B12 register readability | codex/0970-b12-register | 91e2f9a5 | 3 | blocked | Table cut to five columns, facts in a same-page popover, export CSV byte-identical (740 bytes). Duplicate popover labels fixed (d34d2f44): Signed now shows Yes/No. Row A (geometry, test_host_geometry and two others) never finished. Vietnamese has no yes/no keys, so it falls back to English. | Rerun row A in a fresh session with a fresh DB. Decide the Vietnamese translation. |
| B13 feedback forms | codex/0971-b13-feedback | 89fed7f3 | 1 | blocked | Success notice macro, dismiss on existing notices, copy-link keeps its size, separate cleaning Save cards. Cleaning, copy and notice row 170 of 170 pass. Host row (6c): 85 passed, 3 failed in `test_host_wide_geometry_browser.py`; each passes alone and the whole file passes alone; two full reruns died. Screenshots: one red-button and layout concern noted by the executor. | Get one clean full 6c run (zero failures, zero skips). If the three failures recur, run that file on base to decide. Then 6d lint and screenshots. |
| B14 help and settings | codex/0972-b14-help-settings | 5bde965e | 3 | blocked | Help icons beside labels with contextual names, page-help panel out of the H1, mail status from runtime. Brief run stopped at a checkpoint after step 1; restarted once, result not recorded. | Check the restarted run's result; if none, rerun from step 2. Native-review Czech and Vietnamese strings. |
| B15 Leon setup | codex/0973-b15-leon-setup | c781881e (code unchanged at 5462f567) | 1 | blocked | Stepper, property line, and legal split in place. All checks green with zero skips: 0404 browser 3, Leon rows 76, lint 4, geometry 2, v2 mockup 183, guide 3, static 16. All 36 screenshots reviewed. The shared help button (`.havel-fab` from base.html) covers the right ~45 px of the primary button at 390 and 768 px on Leon pages (real overlap; the bottom nav is only a capture artifact). Terms link not clicked. | Owner decides the help-button placement (open decision 7). Then merge-ready. Legal split (open decision 2) still needs a legal read. |
| B16 operator layouts | codex/0974-b16-operator | 77a6b788 | 2 | blocked | Customers metrics balanced, create-host form in its own row, Billing controls aligned with existing components. Commands 1, 2, 4 and 5 passed. Host guard (command 3) not complete. Long plan e-mail is clipped, not wrapped, in the Customers table. | Run the host guard in the background, inspect the remaining screenshots (CS, empty, invalid-submit), decide whether clipping breaks the brief's long-value rule. |
| B17 backlog (F01 and A03) | codex/0975-b17-backlog | 5ad5222c | 1 | blocked | F01 (empty invoice state): patch applied; rows fail on a door-code editor test (fails on base too), and rows 3 and 4 not finished. A03 (readable alert kinds): not started. | Decide the door-code test (open decision 4). Then rows 3 and 4 for F01, then A03 from scratch. |
| B18 audience verification | codex/0976-b18-audience | 27a2ea20 | 1 (test files) | todo (line not updated; report says done) | Verification only. Matrix: QR door readable for `everyone`; booked readable only inside the stay window; host hidden everywhere. No leak reproduced. Guest suite 568 of 568. | Owner policy decisions (open decision 1). No production change. |

## Open decisions for the owner

1. B18 audience default: `booked` for access cards? Leave existing published cards alone? Preselect booked or leave blank? Add a warning when a code-like pattern is entered with `everyone`?
2. B15 legal warnings: show 2 points and disclose 4. Needs a legal read.
3. B12 Vietnamese yes/no keys: translation.
4. B17 door-code editor test: fails on base. Deselect it, or fix the door-code feature?
5. RUIAN address-suggest: sends typed address in a GET query. Separate privacy review.
6. B03 split (0961a and 0961b): approve the split.
7. Shared help button (`.havel-fab`, base.html) overlaps the primary CTA on Leon setup pages at 390 and 768 px: move it or give pages a bottom clearance. Shared component, so it needs a decision.

## Pre-existing failures on base 7b0355c (recorded, not fixed by this work)

- `test_host_fee_navigation.py::test_frozen_report_order_and_forms` ("Your records" not in page). Fails on base. Deselected in batch runs with proof.
- `test_host_i18n.py` three tests (`no such table`). Fails on base.
- `test_invoice_autofill.py::test_invoice_buyer_block_spacing_0896` (selectNodeContents TypeError). Fails on base.
- `test_dashboard_calendar_browser` / `test_feed_dns_pinning`: needs IPv6, not available in this sandbox.
- WebKit browser not installed in this sandbox (`en-webkit` cases). CI runs them.
- `test_each_property_setting_has_exactly_one_editable_control` (door codes): fails on base.

## Rules for the next session

- Never push to main. Merge only through `scripts/merge-pr-on-green.sh` and with owner approval. Production deploy is manual, by the owner.
- Commit trailer: `Co-authored-by: Codex <noreply@openai.com>`. No model names in commit messages or PR text.
- Every browser test run: its own `UBYHOST_DB` file. Browser runs also need `UBYHOST_REQUIRE_BROWSER=1` and their own `UBYHOST_SHOTS_DIR`.
- Test runs rewrite some tracked screenshots under `docs/tasks/`. Revert them before committing (`git checkout -- <path>`), never stage them.
- Run long browser groups in the background with a log file and poll it. A foreground command longer than about 10 minutes is killed.
- A check counts as passed only with zero skipped tests. Any deselection must be named in the report, with its base proof.
- Stop and report on the same failure twice; do not weaken assertions or thresholds to pass.

## Resume order

1. Settle the six open decisions above.
2. Commit B09's pending fix and finish B09.
3. Finish the blocked batches with one clean run each: B06, B07, B05, B04, B12 (row A), B13 (6c), B16, B15, B14, B10, B11, B17 (F01 then A03).
4. Write and run B03's split briefs (0961a, 0961b).
5. Flip stale brief status lines (B08, B11, B18) to match their reports.
6. Integrate: create an integration branch from base and merge the review-ready branches (B01, B02, B08, B18, then the others as they finish). Resolve the conflicts on the shared files above and regenerate `static_versions.json`.
7. Run the full Chromium checks on the integrated branch, review the 390, 768 and 1280 screenshots of every changed page, and only then move this draft PR out of draft for review.

## Not verified

- Most Chromium visual checks for most batches (see each report).
- No integrated build exists, so batch branches have never been tested together.
- Nothing is pushed to main or deployed.

## Integration status (branch codex/ux-remediation-handoff, head 3ae2f0be)

- All 18 batch branch heads are contained in this branch. Batch code is INCOMPLETE and UNTESTED together. Each batch's own status is in its brief and report.
- Merge conflicts resolved by hand: `App/app/templates/base.html` (cache keys: newest batch kept per conflict; app2.css key bumped to `20261105-0971c`), `App/app/static/app2.css` (both sides' blocks kept), `App/app/static/dashboard-calendar.css` (both sides kept), `App/app/templates/_dashboard_calendar.html` (B09 keys), `App/tests/test_host_property_controls_browser.py` (both sides' tests kept), `App/tests/test_dashboard_calendar_browser.py` (both sides kept; a `finally` block re-added after the 0960 test).
- `App/tests/static_versions.json` regenerated with `--write` (50 files). Static version and heartbeat tests: 16 passed.

## Open items found at integration (not fixed)

1. B09: the auto-merged branch removed the `assert max(heights) <= 184` line in the 0905 test and rewrote the tile-height assertion. The approved change was 184 to 226 in one assertion only. Check the rewrite is intended before B09 is finished.
2. `docs/tasks/0972-help-settings.md` is about 13,600 tokens, over the 12,000 cap, so `scripts/context_lint.py` reports ERROR. Split the brief (the B14 brief) before merging to main.
3. `git diff --check` reports trailing whitespace in branch-authored docs: `0963-property-wrappers.md`, `0968-stay-list-scope.md`, `0971-feedback-forms.md`. Likely intended markdown line breaks; check before merge.
4. The app2.css key `20261105-0971c` was bumped at integration because the generator refused the previous key. It is the only template that references app2.css. Confirm it is acceptable.
5. B11: final report says blocked on four `test_host_ux_acceptance.py` failures that also fail on base (door-code editor and three others). Owner decision on deselecting them, or a fix.
6. B17 F01: the door-code editor test (same as item 5) also blocks F01. Decide once for both.

## Late status (after integration)

- B06 (codex/0964-b06-connection-states): BLOCKED. Its branch has commits from another session that change a test assertion (9bd31be0), and status/report commits (a44e3f3f, 741447c7) that claim lint is green. The executor's own run on the same commit found 3 lint findings at 1920 px with accordions open. Decisions: keep the in-view assertion change only if documented as a test-scope correction; overwrite the false status/report; fix the 1920 px findings; deselect all six WebKit cases and state it. Rows 2 and 4 pass; row 3 passes with WebKit deselected.
- B16 (codex/0974-b16-operator): BLOCKED on the host guard. Five failures (fee-navigation plus four in test_host_ux_acceptance.py) also fail on base 7b0355c4. Decision needed: deselect them with base proof, as other batches do. Open item: long plan e-mail values clip at the card edge in the Customers table instead of wrapping; the table is overflow-x:auto, so they should scroll inside the card. Reviewer to decide.
- B07 (codex/0965-b07-guest-review, head bbba3cf9): REVIEW. All checks pass with zero skips (0965 group 19, guest and host set 592, static 16). Spacing fixes stay within the existing guards. Caveats: the acknowledgement row is out of frame in two cs/en captures; the native validation bubble covers part of text on attempted-invalid (native behaviour); the checkbox focus halo is coral and needs owner acceptance.
- B14 (codex/0972-b14-help-settings, head 709c5561): BLOCKED. Two page-help tests that pass on base fail at HEAD (test_host_wide_geometry_browser::test_direct_fee_backlinks_align_with_page_lane, and layout lint with 36 help-stranded findings on details.page-help at 320 px). Brief is 13,598 tokens, over the 12,000 cap (context lint ERROR). Its tests otherwise pass (A 48, C 46, E 3, D 234 with 7 failures: 5 pre-existing, 2 regressions). Decision needed: the page-help placement at 320 px, and split the brief.
- B05 (codex/0963-b05-property-wrappers, head c16b4d17): BLOCKED only on pre-existing failures. Batch work is done: archive tip test race fixed (wait for hidden), archive button and help tip grouped so the tap target is 44 px at 320 px, layout lint and property-320 geometry pass. Five failures, all also failing on base 7b0355c4: test_host_ux_acceptance (door_codes editor, two page_families, keyboard focus) and test_0710 stay-320 .stay-dates height. Fee-navigation deselected with base proof. Decision needed: deselect these five with base proof (same rule as other batches), or fix them. Not yet viewed: English police subsections and the stay-fee heading screenshots.
- B04 (codex/0962-b04-property-readiness, head d03fc45e): BLOCKED by a REGRESSION caused by this batch. The "Continue" and "Hide setup guide" buttons are 32 px tall at 390 px (44 px tap target required). Layout lint (design guardrails and layout lint) and the v2 property geometry tests at 320, 390 and 768 px pass on base 7b0355c4 and fail on this branch. Lint also reports 42 tight-stack and 10 tap-target findings on fee-setup, property-detail, guest-links and automation pages. Fixed in this branch: keyboard test (Playwright keyword-only arg) and copy test (selector). Pre-existing, not caused by B04: test_host_fee_navigation (Your records), four test_host_ux_acceptance, and stay-320 v2. A floating help button overlaps the Business details pill's lower-right corner (screenshot b04-en-390-longname). Command 4 (property row) still running at handoff. Decision and next step: fix the button heights in this batch's CSS, then rerun lint and geometry.
