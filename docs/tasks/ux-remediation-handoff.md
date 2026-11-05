# UX remediation: handoff (incomplete, draft)

Status: handoff. Nothing here is merged, nothing is deployed, and no batch is fully finished.
Base: `7b0355c45ccdd2557a28edfcfe228aa1dc766e36` (origin/main, #786).
Plan: the UX review and remediation plan (review uploads 9e66688c-ux-remediation, b33c8519-design-brief, ac0148e7-report).

Each batch lives on its own branch with a brief `docs/tasks/09NN-*.md` and a report. Branches are not merged into each other yet.

## Batch state

| Batch | Branch | Head | State |
|---|---|---|---|
| B01 guest draft on language change | codex/0959-guest-draft-language | a7e827df | review. One documented exception: the RUIAN address-suggest GET query carries typed text (pre-existing; needs a privacy review). |
| B02 calendar create actions | codex/0960-b02-calendar-create | 65a7a65a | review. Centring test now compares centres, not tops (content-sized dialogs kept). |
| B03 host shell on detailed forms | codex/0961-b03-host-shell | 56c2951c | blocked. Needs split: 0961a (guest form) and 0961b (invoice form). Not run. |
| B04 property readiness | codex/0962-b04-property-readiness | d03fc45e | blocked. Two new tests were failing; fixes in progress. Fee-navigation test pre-existing on base. |
| B05 property wrappers | codex/0963-b05-property-wrappers | 40088a45 | blocked. Test race fixed (wait for hidden); tip markup fix pending; uncommitted edits in worktree. |
| B06 connection states | codex/0964-b06-connection-states | c1e378a9 | blocked. Feed-URL layout fix committed; rows 3-5 and 1280 base comparison pending. WebKit and IPv6 are environment deselections. |
| B07 guest review and legal | codex/0965-b07-guest-review | b7954474 | blocked. Spacing guards at 320/360/1280 fail; CSS fix pending; two unidentified failures. |
| B08 guide truth | codex/0966-b08-guide-truth | 014780b4 | accepted by orchestrator (all 30 screenshots reviewed). Brief status line still says blocked: two literal checks are artifacts (em dash in the brief's own checklist; file count includes the brief). |
| B09 calendar orientation | codex/0967-b09-calendar-orient | 8e133cfb | blocked. Bound 184 to 226 approved. 768 px narrow-name failure cause found (0 px name on a one-night bar left by an earlier test); CSS fix uncommitted; repeat runs were killed. |
| B10 stay list scope | codex/0968-b10-stay-list | 229825ea | blocked. Host suite not complete; failures not yet named (full run killed). Three i18n failures pre-existing. |
| B11 alert stacks | codex/0969-b11-alerts | b2132982 | incomplete. Fee-navigation base proof done; chunks B and C, 3d and screenshots pending. |
| B12 register readability | codex/0970-b12-register | 91e2f9a5 | blocked. Duplicate popover labels fixed (d34d2f44); row A geometry never finished. Vietnamese yes/no translation missing. |
| B13 feedback and cleaning forms | codex/0971-b13-feedback | 89fed7f3 | blocked. Host row 85 passed, 3 failed in test_host_wide_geometry_browser.py (pass alone); two full reruns died. Needs a clean run. |
| B14 help and settings | codex/0972-b14-help-settings | 5bde965e | blocked. Run pending after the executor's checkpoint. |
| B15 Leon setup | codex/0973-b15-leon-setup | 5462f567 | blocked. Remaining checks and the nav-overlap decision pending; uncommitted edits. Legal warning split needs a legal read. |
| B16 operator layouts | codex/0974-b16-operator | 77a6b788 | blocked. Host guard and clipping decision pending. |
| B17 backlog (F01, A03) | codex/0975-b17-backlog | 5ad5222c | F01 blocked on the door-code editor test (fails on base too; decision needed). A03 not started. |
| B18 audience verification | codex/0976-b18-audience | 27a2ea20 | review (verification only). Owner policy decisions pending. |

## Open decisions for the owner

1. B18 audience default: `booked` for access cards? Leave existing cards? Preselect or blank? Code-pattern warning?
2. B15 legal warnings: split 2 visible / 4 disclosed. Needs a legal read.
3. B12 Vietnamese yes/no keys: translation decision.
4. B17 door-code editor test: deselect (fails on base) or fix the feature?
5. RUIAN address-suggest: typed text in a GET query string. Separate privacy review.
6. Pre-existing base failures: `test_host_fee_navigation.py::test_frozen_report_order_and_forms` ("Your records"), the three i18n `no such table` tests, IPv6 feed-DNS test, WebKit not installed in this sandbox.

## Rules for the next session

- Do not push to main. Do not merge without `scripts/merge-pr-on-green.sh` and owner approval.
- Commit trailer: `Co-authored-by: Codex <noreply@openai.com>`. No model names in commit messages.
- Every test run: a unique `UBYHOST_DB` file; browser runs also `UBYHOST_REQUIRE_BROWSER=1` and a unique `UBYHOST_SHOTS_DIR`.
- Test runs rewrite some tracked screenshots under `docs/tasks`. Revert them before committing (`git checkout -- <path>`), never stage them.
- Run long browser groups in the background with a log file and poll it; foreground calls time out around 10 minutes.
- Never report a check as passed unless it ran with zero skipped (environment deselections must be stated).

## Resume order

1. Decide the open items above.
2. Finish the blocked batches with a clean run each: B06, B09, B12 (row A), B13 (6c), B05, B04, B07, B15, B16, B14, B10, B11, B17 (F01 then A03).
3. Write B03's split briefs (0961a, 0961b) and run them.
4. Integrate the review-ready branches (B01, B02, B08, B18, and whichever finish) into one integration branch. Expect conflicts on `static_versions.json`, `base.html` cache keys and `app2.css`.
5. Run the full Chromium checks on the integrated result, look at the 390/768/1280 screenshots for every changed page, and only then open the real PR.

## Not verified

- Chromium visual checks for most batches (screenshots not all reviewed).
- No integrated build exists yet; batch branches have not been tested together.
- Nothing has been pushed to main or deployed.
