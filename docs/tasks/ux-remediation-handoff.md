# UX remediation: handoff (incomplete, do not merge)

Status: handoff. Nothing here is merged, integrated or deployed. No batch is fully finished and no integration build exists.
Base: `7b0355c45ccdd2557a28edfcfe228aa1dc766e36` (origin/main, #786).
Plan source: UX review and remediation plan (review uploads: 9e66688c-ux-remediation, b33c8519-design-brief, ac0148e7-report, dd4af45a-improvement-plan).

## How the work is organised

- Each batch B01 to B18 has its own branch `codex/09NN-*` from base, a brief `docs/tasks/09NN-*.md` (committed on that branch) and a report `docs/tasks/09NN-report.md`.
- Batch branches are not merged into each other. Several touch the same shared files, so an integration pass will conflict: `App/app/static/app2.css`, `App/app/templates/base.html` (cache-key bumps), `App/tests/static_versions.json` (regenerated manifest), `App/app/host_i18n.py` and `host_vi_i18n.py`.
- Worktrees live under `/tmp/ubyhost-bNN-worktree` in the session that produced them. They do not survive a new session. Recreate from the branch with `git worktree add /tmp/ubyhost-bNN-worktree codex/09NN-...`.
- Code commits below are the commits on each branch that touch `App/`, counted from base.

## Batch final status (B01–B18), integration branch `codex/ux-remediation-handoff`

Integration head: **`e6094132`** (see **Integration status** below). Each batch’s code is merged into this branch; remaining work is verification (full browser run), owner decisions, and any failures that still reproduce on base.

| Batch | Theme | Final status |
|---|---|---|
| B01 | Guest draft on language change | **Integrated.** Language switch + discard path in tree; RUIAN GET query called out under owner decisions (accepted). |
| B02 | Calendar create actions | **Integrated.** Create/Cancel row and calendar dialog behaviour in tree; re-run 0960 browser file after any calendar CSS conflict. |
| B03 | Host shell on detailed forms | **Integrated.** Detailed forms use v2 shell work merged on handoff; follow **Resume order** if 0961a/0961b gaps remain. |
| B04 | Property readiness | **Integrated.** Strip, save bar, readiness copy; property-row browser run was green on earlier handoff snapshot — re-confirm on `e6094132` after full suite. |
| B05 | Property wrappers (stay fee, police, archive) | **Integrated.** Markup/tap-target fixes in tree; pre-existing `test_host_ux_acceptance` / stay-320 items may still fail on base (see **Open items**). |
| B06 | Connection states (lock, calendar URL, feeds) | **Integrated.** Lock states + feed disclosure in tree; full lint/webkit run on handoff still required. |
| B07 | Guest review and legal | **Integrated.** Review/legal UI in tree; spacing and acknowledgement caveats in batch report still apply until re-verified. |
| B08 | Guide completion truth | **Integrated.** Completion + empty questions flows; i18n body de-dupe for empty questions added on `e6094132` (`guest_questions.empty.body`). |
| B09 | Calendar orientation | **Integrated.** Calendar lane/container work in tree; confirm 0967 tests + screenshots on current head. |
| B10 | Stay list scope | **Integrated.** Filters/tab copy in tree; host-suite pre-exists (fee-navigation, i18n DB) unchanged unless fixed globally. |
| B11 | Alert stacks | **Integrated.** Compact alerts in tree; door-code / ux_acceptance items tie to global backlog (see **Open items**). |
| B12 | Register readability | **Integrated.** Table + popover + CSV in tree; Vi **Có/Không** per owner decision — confirm in i18n. |
| B13 | Feedback forms | **Integrated.** Wide geometry: `pageHeader.titleLeft` kept strict; back link stacks + `airbnb-back` hook restored (`e6094132`). |
| B14 | Help and settings | **Integrated.** Page-help and settings patterns in tree; brief over 12k tokens and 320px help placement still tracked in **Open items**. |
| B15 | Leon setup | **Integrated.** Leon stepper/UI in tree; `.havel-fab` vs primary CTA overlap still an **owner decision**. |
| B16 | Operator layouts | **Integrated.** Operator/customer layouts in tree; host-guard base failures + long email clipping still tracked. |
| B17 | Backlog F01 + A03 | **Integrated.** Empty invoice / backlog patches in tree; door-code editor failure class still tied to base unless fixed. |
| B18 | Audience verification | **Integrated.** Verification tests in tree; policy defaults per owner decision **#1**. |

### Full browser verification (`test_*browser*.py`)

- **Running** (tmux `ubyhost-full-chromium`, log `/tmp/ubyhost-chromium-full.log`): `UBYHOST_DB=/tmp/ubyhost-full-chromium.db`, `UBYHOST_SHOTS_DIR=/tmp/ubyhost-full-chromium-shots`, `UBYHOST_REQUIRE_BROWSER=1`, **Chromium + WebKit** (Playwright `webkit` + system deps installed — not deselected for “missing WebKit”).
- Replace this sentence with **passed / failed / skipped** counts from the log when complete. Requirement: **0 skipped** unless deselection is named with base proof.

### Human review screenshots (DESIGN.md: spacing, tap targets ≥44px, hierarchy, buttons)

Copied to store **`/cursor/stores/bc-28288bf2-47f9-474f-9b23-be49bcaa5d94/media/ux-review/`** (sources: `/tmp/ubyhost-full-chromium-shots` during full run):

| File | Viewport | What was checked |
|---|---|---|
| `dashboard-phone390.png` | 390 | Rail + primary actions; tap targets for nav and list rows; vertical rhythm. |
| `dashboard-desk1280.png` | 1280 | Sidebar + content lane width; heading scale vs body; action hierarchy. |
| `apartments-phone390.png` | 390 | Card list spacing; CTA visibility; no horizontal scroll. |
| `apartments-desk1280.png` | 1280 | Grid/list balance; header alignment with lane. |
| `property-help-open-en-390.png` | 390 | Property settings: section help pattern, controls, 44px-ish targets on help close / fields. |
| `property-help-open-en-768.png` | 768 | Same page at tablet width: title row vs content width, help panel. |
| `reservations-phone390.png` | 390 | Stays list density; row tap targets; filters vs content hierarchy. |
| `guide-phone390.png` | 390 | Host guest guide workspace: typography, section cards, primary actions (guest-facing copy). |
| `calendar-0967-heading-en-390.png` | 390 | Host calendar: H1 + overflow lane + controls; spacing and button hierarchy at phone width. |

Tablet **820** shots in the run align with **768** for layout checks where no dedicated 768 asset exists for a given route.

**Guest-new / guest form:** no single named PNG landed in `/tmp/ubyhost-full-chromium-shots` under this run’s prefix; spot-check when a `guests/new` or `0139` capture appears, or extend the shot path in `test_design_guest_admin` / related browser tests.

## Owner decisions (2026-11-06)

Resolved by owner; implement in the batches below (see internal note `b04-and-owner-decisions-20261106.md` in the project store).

1. **B18:** Apply the **recommended** audience default, treatment of existing published cards, preselect behaviour, and code-pattern warning from that batch’s brief/report.
2. **B15:** Legal split **2 visible / 4 disclosed** approved as recommended. **`.havel-fab`:** apply recommended placement so it does not overlap the primary CTA at 390/768 on Leon pages.
3. **B14:** Page-help at **320 px:** apply recommended placement; split/trim B14 brief under 12k tokens (separate B14 work).
4. **B12:** Vietnamese yes/no = **"Có" / "Không"** (recommended).
5. **Door-code editor / B17 / B11:** **Fix the feature** (TTLock smart-lock flow — confirm in code/tests); do **not** deselect the test.
6. **RUIAN GET query:** **Accepted** as-is; record in **B01** report.
7. **B03:** Split **approved** — implement **0961a** (guest form) and **0961b** (invoice form).
8. **B05 and B11:** **Fix** listed pre-existing failures (not deselect), with base proof of prior failure.
9. **B16:** Fix the **five host-guard** failures; long e-mail in Customers: use **recommended** option (vs clipping).

Items 1–9 supersede the earlier “open decisions” list until implementation lands.

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

## Integration status (branch codex/ux-remediation-handoff, head e6094132)

- All 18 batch branch heads are contained in this branch. **Full `test_*browser*.py` suite:** in progress — tmux `ubyhost-full-chromium`, log `/tmp/ubyhost-chromium-full.log`, fresh DB and shots (see batch table above).
- Recent integration fixes on **`e6094132`**: `host_page` back link **`class="ui-ph-back airbnb-back"`** (CSS prevents duplicate round-pill styling); **`guest_questions.empty.body`** no longer repeats the empty-state title (0966); **`test_ttlock_setup_0954_browser`** targets the correct lock tile; **`app2.css`** cache key **`20261106-ui-ph-airbnb-back`**; **`App/tests/static_versions.json`** regenerated (50 files).
- Merge conflicts were resolved earlier on this branch (shared files listed in prior handoff revisions); subsequent commits keep `static_versions.json` in sync with template `?v=` keys.

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
- B04 (integration on handoff): **419 passed, 0 skipped** on property row (`de9360cd`, log from foreground run Nov 2026; DB/shots as in batch table). Prior 32px setup-continue regression addressed (44px at &lt;1024px). **UX review (human-style, 390 / 768 / 1280, EN screenshots in `/tmp/ubyhost-b04-row5-shots`):** six status pills read clearly; primary next actions are copy link (coral) and opening sections; hierarchy matches DESIGN.md (light surfaces, one obvious action per card row). **Remaining product issue:** `.havel-fab` still crowds the bottom-right of the strip on narrow widths (owner decision → B15). Mock UbyPort banner is expected in dev. **design.md:** light-only, 44px touch targets on strip copy + setup buttons, keyboard focus visible on strip links — satisfied for this page set.
