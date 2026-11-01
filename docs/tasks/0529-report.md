# 0529 report: stay page v2, part 2

Status: blocked (call cap reached after step 2; see Deviations)
Branch: task/0529-v2-stay-detail-rest. Commits: 1086612f (step 0), step 1 commit "police card, door code, allgood, payment link", e7768383 (step 2, amended). No push, no PR.

## Files changed
- App/app/static/app2.css: 0528 block: removed re-declared 0718 rules (.top, .round, .big, .facts and children); added .police-card, .police-deadline, red .police-failed, .code.
- App/app/templates/reservation_detail.html: police card (h2.sec + .card with the old "Now" note text and deadline), allgood line, door code as h2.sec + .card with .code, payment link `.list > a.link`, settings as `details.card#stay-quick-edit`.
- App/app/templates/base.html: app2.css key 20261101-0529.
- App/tests/static_versions.json: `--write` (41 files).

## Form count
`action="/reservations/`: 12 before, 12 after.

## Commands
- `.venv/bin/python tests/test_0525_stay_detail.py tests/test_design_stay_detail.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_static_versions.py -q --tb=line -rs`
  tail: `9 failed, 57 passed in 5.82s`, 0 skipped.
- `-k stay` on tests/test_0710_v2_mockup_match_browser.py: `21 deselected` (no stay PAGES entry yet, step 3).

## Failing tests
- Expected old markup (0528 list, still to update in step 3): `ui-ph-back`, `class="btn` / `style="` asserts, `Next step`, `id="now"`, `class="ui-section stay-settings"`, `guest-card`.
- NEW from step 1: `Reporting deadline` (test_overhaul.py:395). I removed the metric label and moved the deadline into the police card without the label text. Fix in step 3: add the `stay.detail.metric.deadline` label into `.police-deadline` or update the assert.

## Deviations
1. Done: steps 0, 1 and most of 2. Not done: step 2 action bar (`.actbar`, phone); header actions stay inline on phone. Dead-CSS sweep not done.
2. Door code: the mockup icon `#i-key` is not in the sprite; used an empty decorative `.ic.acc`. Validity line shows dates only (no translated "valid from" wording).
3. Submissions table and file-by-hand details are not yet wrapped as `.card`.
4. Police card heading uses `host.reporting` (one key, both texts).
5. Done: `Done: steps 0 to 2 (2 partial: no action bar, no dead-CSS sweep). Left: step 2 action bar and dead CSS; step 3 PAGES entry, shared test, old test updates, the "Reporting deadline" fix; step 4 screenshots (390 and 1280 pairs, all six widths) and this report's test tails.`

## Questions
- Action bar: render the header form once and place it with CSS, or render a second identical form? Owner decision needed for the phone bar.

## Owner steps left
- None until the PR. Merge only with `scripts/merge-pr-on-green.sh`.

## Continuation (executor, session 2)
Status: blocked. Done: steps 0 to 2 (step 2 complete). Left: step 3 (PAGES entry `stay`, old test updates) and step 4 (screenshots, final commands, report).

- Step 2 commit f73d9c2e: action bar. Jinja macro `stay_cta()` holds the send/fix/receipt/view-reports chain; it is called in `.head` and in `<div class="actbar">` at the end of the page (shown when `has_cta`). Source `grep -c 'action="/reservations/'` = 12 (the macro is one line). Rendered, the submit form appears twice when the send button shows; both copies come from the same macro, so they are identical. Resend-claim is not in the actbar (deviation: no CTA means no actbar, so the resend fallback stays in the header only).
- Police deadline label: `<small class="police-deadline">` starts with `stay.detail.metric.deadline`, so "Reporting deadline" is on the page again.
- Door code: `icon('key-round', 22)` in the `.ic.acc` (imported in the template).
- Submissions table and file-by-hand details: each wrapped in `<div class="card">`, inside unchanged.
- Dead CSS sweep: every selector in the `/* 0528 stay page */` block is used by the template; nothing removed.
- Manifest: `tests/test_static_versions.py --write` run.

Open question for step 3: the PAGES path needs a seeded active stay id (`/reservations/{id}`), but `PAGES` is static and `_open_app` takes `spec["path"]`. Owner or orchestrator decision: resolve the id in the shared test from a fixture (a change to `test_0710_v2_mockup_match_browser.py`), or seed a fixed id. Not decided by the executor.

## Continuation (executor, session 3)
Status: blocked. Done: steps 0 to 2; step 3 partial (PAGES entry and path helper committed, old-marker asserts updated). Left: step 3 blockers below, step 4 (screenshots, §6 commands, report tails).

- Commit b1844468 "0529 step 3": `tests/test_0710_v2_mockup_match_browser.py` resolves `{stay_id}` from `dashboard_rich_host["ready"]` (active stay, one guest of that host; no new DB query needed). `tests/v2_mockup.py` PAGES entry `stay` (view `stay`, phone `pobyt`, selectors per brief, data-dependent ones in `missing_ok`). Overview and menu paths are unchanged.
- Shared test `-k stay`: 12 failed, 21 deselected. Style checks fail at all six widths; geometry fails at all six. Not fixed (no mockup-value fix applies):
  1. Phone (320, 390): the `.actbar` (fixed, bottom calc(84px)) and the phone tab bar cover the security prompt's "Not now" button, so the harness cannot dismiss the prompt. Decision needed: z-index or hide the bar while the prompt is open (shell/prompt, brief §8).
  2. Desktop (1024 to 1440): horizontal page scroll (1408 > 1280, 1568 > 1440) and tap targets under 24 px: `Stays` nav link (31x17), settings inputs and Save buttons, help-tip `?` (23x21), `Request payment` link (19 px), `Mark as filed by hand` (21 px). Shell nav link is shell scope (brief §8).
  3. Style diffs were not reviewed in detail; `.chip.on` and `button.round` were not reported yet.
- Pre-existing, not from this change: `overview-768` (21 style differences) and `menu-320` (1 style difference) fail on this branch.
- Old-test updates (commit pending, see git log): `id="now"` to `police-card`; `Next step` and `stay-command-panel` to `police-card`; `ui-ph-back` to `crumb`; `stay-settings` class dropped; `ui-btn-primary`, `ui-table-stack` and `class="btn"`/`class="pill"` asserts dropped or relaxed (`class="btn"` count <= 2).
- Tails: `tests/test_0525_stay_detail.py tests/test_design_stay_detail.py tests/test_overhaul.py -q --tb=line -rs`: 3 failed, 31 passed, 0 skipped.
  - test_0525:79 guest-card-doc: `guest-card` markup is gone in the v2 list. Decision: which v2 element carries the doc-type label and must not show the document number.
  - test_design:15 and test_overhaul:413: the police card is after Guests in the DOM (13133 > 10405). The old intent is Now, then Guests. Decision: move the police card above Guests, or change the ordering assert to the mockup order.
- `tests/test_host_stay_detail_layout_browser.py` not updated: `.guest-card` and `#now` (line 37 and below). It also fails the 360 px horizontal-overflow check on the ready stay (scrollWidth > innerWidth). Layout bug, needs a fix before the test can pass.
- Screenshots, §6 commands (the other stay test files, design_lint, context_lint), manifest rerun: not done.

## Owner or orchestrator decisions needed
1. Phone security prompt is covered by the action bar and tab bar (see 1 above).
2. Desktop overflow and tap targets in the stay page and shell nav (see 2 above).
3. Police card order: before or after Guests.
4. Guest doc-type label location in the v2 list (test_0525:79).
