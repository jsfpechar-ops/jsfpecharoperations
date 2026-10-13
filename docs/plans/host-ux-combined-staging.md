# Host UX combined staging lane (corrections + #378 navigation)

Owner decision 2026-10-13: the production corrections (0087–0095) and the approved #378 navigation design (0075–0083) ship together as **one big PR**, staging only. Corrections win wherever the two disagree. This page overrides the per-task PR and exact-patch release gates in the [execution protocol](host-navigation-execution-protocol.md) §3–§4; its environment, test, evidence and staging rules (§6–§8) still apply.

## 1. One branch, one PR

- Work branch: `task/production-host-ux-integration`. Every task in §3 is committed directly on it, in order (one or more commits per task, message prefix `NNNN:`). No per-task PRs from 0088 onward.
- The one big PR: `task/production-host-ux-integration` → `main`, **draft**, titled `STAGING ONLY — host UX corrections + navigation (do not merge)`. Reuse it if it already exists. Never mark it ready, never merge it; `main` auto-deploys production. Production promotion is 0086, after the owner approves the staged SHA.
- Push the branch after every finished task, so CI runs on each task head. A red CI on a task head is fixed before the next task starts.
- #381 (0087/0095) is merged into this branch by a merge commit once 0095 is done; #382 (the 0095 brief) is merged in the same way and then closed unmerged to `main`.

## 2. Execution mode for 0075–0083

These briefs say "Patch status: pending" and "apply the released exact patch only". That gate is lifted for this lane. Instead:

1. Prerequisite = the previous task in §3 is committed on the branch with its report at `Status: review`, and CI is green on that head.
2. Re-verify every anchor in the brief's §2 against the current branch. If an anchor moved because an earlier task in this lane changed it, use the current code and record old → new in the report. If the anchor is gone and the brief's intent is unclear, stop (§8 of the brief).
3. Implement the brief's numbered steps yourself, inside the brief's §3 file list only. Its §5, §7 and §8 are binding. Do not invent business behaviour: same input names, payloads, CSRF/access checks, filing, invoice, fee and lock semantics.
4. Where a brief conflicts with §4 below, §4 wins; note it in the report.

## 3. Order

| # | Task | Notes |
|---|---|---|
| 1 | [0095](../tasks/0095-0087-review-fixes.md) | Finish on `task/0087-host-copy-address-corrections`: steps 1, 2 and their step-5 tests were skipped; fix the vacuous zkratka test, delete `test_integration_head_browser_failures_recorded`, open the property page before the first sidebar toggle. Then merge that branch into the integration branch. |
| 2–8 | [0088](../tasks/0088-property-operator-defaults.md), [0089](../tasks/0089-required-calendar-platform.md), [0090](../tasks/0090-lock-context-navigation.md), [0091](../tasks/0091-host-fit-audit.md), [0092](../tasks/0092-simple-property-onboarding.md), [0093](../tasks/0093-visible-controls-contextual-help.md), [0094](../tasks/0094-property-tabs-early-calendars.md) | Corrections lane, as written. Their "PR base" lines now mean "commit on the integration branch". |
| — | **Checkpoint A** | Stop. Owner asks the orchestrator to review the branch (corrections done). |
| 9–17 | [0075](../tasks/0075-shared-entity-fields.md) → [0083](../tasks/0083-account-settings-navigation.md) | Navigation design, §2 mode. |
| 18 | [0084](../tasks/0084-host-navigation-integration-acceptance.md) | Whole-host acceptance matrix. |
| — | **Checkpoint B** | Stop. Orchestrator review, then the owner deploys to staging (0085, owner-run). 0086 waits for explicit owner approval. |

## 4. UX reconciliation (senior design rules)

The #378 boards set the structure; the corrections set the surface. Apply these to every task above.

1. **Navigation.** The global rail stays Dashboard · Stays · Properties · Invoices · Stay fees, with Search above and Help/Account below. A property has three local tabs: **Overview · Bookings & calendars · Settings**. Tabs only on property pages; list pages (Stays, Invoices, Fees) stay lists with filters.
2. **Visible, not folded.** No chevron, "More options" or `<details>` hiding real settings or values. Where a #378 board shows a disclosure (for example, the cross-property guest-link/automation summary on Properties), render it as a compact visible section with ordinary header bars. `<details>` remains acceptable only for the existing CSV/PDF export menus and confirmation dialogs.
3. **One editor per setting.** Overview cards show a summary plus one link to the canonical editor (plan §4 table). No card contains a form. Settings is grouped under visible sub-headers: Property information · Guest experience (Guest links, Digital door lock) · Reporting & fees (Police reporting, Stay fee) · Automation.
4. **Help is a `?`.** Routine helper text uses the 0093 help component (hover, keyboard focus and tap; not a `title` tooltip). Long guidance links to `/guide#…`. Errors, current state, required markers, confirmations and legal acceptance stay always visible.
5. **Honest state.** A field shows what is stored (the 0095 rule): guest message blank stays blank on edit; a saved password shows the fixed `••••••••` placeholder; a switch toggled but not yet saved says "Not saved yet", never "Enabled".
6. **Switches.** Genuine optional features use the switch with a short label and an Enabled/Off status (for example, **Automatic door codes**). Property activity has no switch. Legal acceptance stays a checkbox.
7. **Placement.** PIN and link actions sit at the top of Guest links, next to the URL and PIN. Archive/Restore sits at the bottom of Settings → Property information, visually separated from Save. Calendar comes first in onboarding and has its own tab.
8. **Copy.** One explanation in one place; no sentence that repeats its button; no backend narration ("filled for you", "encrypted before…"). EN and CS stay in step.
9. **Layout.** One content lane that adapts to the sidebar width, not only the viewport. Stays become labelled cards before a table would scroll sideways. Actions wrap; nothing is clipped or shrunk below readable size. Light mode only; existing tokens and fonts; no new dependency.
10. **Old links keep working.** `/guest-links`, `/automation`, old `#hash` anchors and fee-setup URLs redirect or scroll to the new home, with the right section open.

## 5. Evidence per task

From brief §6 plus this lane: focused tests, then the full suite with `UBYHOST_REQUIRE_BROWSER=1` (0 skipped); only the six baseline failures listed in `docs/tasks/0087-evidence/integration-head-browser-failures.txt` may remain, and any task that fixes one says so. Screenshots at 360/390/1280 EN/CS of every changed page, captured behind a `UBYHOST_CAPTURE_NNNN=1` gate into `docs/tasks/NNNN-evidence/`. Synthetic data only. Each task writes `docs/tasks/NNNN-report.md` and sets its brief to `Status: review`.
