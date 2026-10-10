---
date: 2026-10-10T21:38:54Z
author: AI session (Codex orchestrator)
branch: task/host-design-staging
commit: ee3a85cbf77037a5f01e837bd67fc9e9c02f6100
type: session
status: blocked
tags: [host-design, draft, geometry, guest-links]
previous_handoff: docs/plans/host-design-staging-handoff.md
---

# Handoff: paused host design and unfinished stay actions

## Summary

The owner rejected the current host redesign, wants to hand-pick changes, and
asked to stop implementation, prepare this Markdown document and push a draft
for another AI. PR [#338](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/338)
holds the existing redesign and the unfinished two-action correction. It is
not ready to merge or deploy. No further redesign, merging or deployment is
authorized by this handoff.

The frontmatter commit is the last committed checkpoint before this handoff;
the next commit packages the work described below. Confirm the actual PR head
and working tree before resuming. Active checkout: `/workspace/jsfpecharoperations`.

## Current State

- [x] Identified why Copy guest form link was missing: the template restricted it
  to awaiting-guest/incomplete progress even when another status had a guest link.
- [x] Changed Stays and dashboard Copy visibility to existing token availability.
- [x] Replaced dashboard's bespoke `> More` control with the shared SVG ellipsis.
- [x] Added optional menu semantics to the shared Copy helper, plus shared menu
  keyboard navigation and manual-copy focus handling.
- [x] Added mixed-status Copy/Send browser coverage and adapted dashboard tests.
- [x] Documented the owner's reopened design selection and stopped all executors.
- [ ] Resolve Stays action overflow when Send, Copy and ellipsis appear together.
- [ ] Resolve mobile shared-menu opening/dismissal failure.
- [ ] Bump the static asset cache token after final JavaScript changes.
- [ ] Complete focused browser checks, full coverage, screenshots and final CI.
- [ ] Obtain the owner's choices for the remaining design changes below.

## Key Decisions

- Read `AGENTS.md` first, then `docs/context/status.md`. Codex is the
  orchestrator/reviewer; normal execution goes through Cursor. The existing
  2026-10-10 session exception authorized Luna executors and feature-branch
  delivery. It does not allow the orchestrator to edit App or run App tests.
- The owner first stopped broad design work, then authorized only investigation
  and correction of missing Copy links and inconsistent dashboard More controls.
  The latest instruction pauses those corrections too; preserve the draft.
- Copy means **Copy guest form link**, using the existing canonical
  `/l/{slug-or-token}/{reservation-id}` URL. Keep tokenless rows guarded and
  preserve expiry, permissions and server behavior. Do not create links merely
  to make every row show a button.
- Dashboard action label is **Open**. More actions should use the same
  three-dot component as Stays and Properties, with an accessible name.
- The app should be extremely easy and intuitive for anyone, including older
  people: minimal vital information, predictable placement and clear labels.
  Geometry and keyboard behavior must be tested, not assumed from screenshots.
- Do not alter police filing, guest access, fees, invoice calculations/PDFs,
  backend deletion semantics, dependencies or address requiredness as a UI fix.

## Design inventory for owner selection

These are changes already discussed or present on the branch, **not renewed
approval of the rejected design**. Let the owner hand-pick them before more
implementation. Items 8 and 22 contain the last narrowly authorized corrections,
which are now paused and unfinished.

| # | Design update | Details to preserve or reconsider |
|---|---|---|
| 1 | Shared page edges | Align headings, tabs, filters and results to one content lane. |
| 2 | Consistent buttons | Matching heights, gaps and positions; reserve action tracks across rows. |
| 3 | Hover and keyboard highlighting | Consistent feedback on actionable rows throughout the app. |
| 4 | Responsive dense tables | Readable label/card arrangement on mobile without hiding vital actions. |
| 5 | Quiet dashboard | Simple white cards; no flat photos or extra property information. |
| 6 | Status colors | Amber action, taupe waiting, blue ready, red overdue, neutral zero counts; text still explains status. |
| 7 | Dashboard limits | Five unique stays total; current stays and arrivals within 30 days, older unresolved urgent work first. |
| 8 | Dashboard actions | Open plus shared ellipsis in the same reserved position on every row; unfinished menu bug. |
| 9 | Filters on demand | Matching expandable inline panels for Stays, Invoices, fees and guest register. |
| 10 | Filter editing | Draft values with Apply and Cancel rather than unexpected immediate changes. |
| 11 | One date-range control | From/Until together for Stays and guest register. |
| 12 | Month picker | Twelve-month grid, year arrows and soft coral selection for invoices and fees. |
| 13 | Closed filter summaries | Stays: All properties · Active. Invoices: All dates · All properties. Custom dates only after selection. |
| 14 | Invoice-item alignment | Same Description, Quantity, Unit, Unit price and Remove tracks for all rows. |
| 15 | Other item text | Show custom Description only when Other is selected. |
| 16 | Cleaning unit | Leave Unit blank for Cleaning, as requested by the owner. |
| 17 | Form actions | Save, Preview and Issue follow the form in normal flow without covering fields. |
| 18 | Address labels | Aligned labels and inputs; remove Needed to report badges; preserve validation until source-verified. |
| 19 | Operator actions | Edit, Invoice settings and More visible consistently; explain unavailable Delete and keep backend guards. |
| 20 | Property tools | Remove duplicate local menu; preserve useful cross-property access. |
| 21 | Delete wording | Delete archives the stay; Archived view and Restore remain. |
| 22 | Copy controls | Explicit Copy guest form link, Copied/checkmark feedback and manual fallback; visibility follows token availability. |
| 23 | Search presentation | Refresh presentation while retaining the existing search engine; reassess the supplied prototype against actual needs. |
| 24 | Notification cards | Consistent in-flow updates, maximum three; retain persistent warnings/errors and Undo where applicable; truthful statuses. |

## Open Issues and latest evidence

The last **required Chromium** focused run was
`.venv/bin/python -m pytest tests/test_host_stay_actions_browser.py tests/test_host_quiet_dashboard_browser.py -q`
from `App/`, with the existing browser/mock environment. It finished
**2 failed, 1 passed, 0 skipped in 30.24s**. It validates neither the complete
draft nor the earlier rejected design. All test processes have stopped.

1. **Stays geometry:** `App/tests/test_host_stay_actions_browser.py:197` fails
   at 1280px. Send is x=992.58/w=103.36, Copy x=1105.56/w=150.42 and ellipsis
   x=1265.61/w=34. Its right edge is 1299.61, outside the viewport. Mixed-status
   visibility and the real Ready Send assertion passed before this failure.
   `host.css` has not been adjusted for the newly visible third action.
2. **Dashboard menu:** `App/tests/test_host_quiet_dashboard_browser.py:216`
   fails in a mobile iteration after clicking ellipsis: expanded=false,
   scrollY=163, panel returned to its row instead of remaining open in the body
   portal. `App/app/static/app.js:481` focuses the first item without
   `preventScroll`; line 518 closes menus on scroll. Investigate whether opening
   focus causes that scroll; this is a hypothesis, not an established root cause.
3. **Cache:** `App/app/templates/base.html:306` still references the 0040 asset
   version although JavaScript changed. Do not deploy this unfinished snapshot.
4. **Shared-menu regression risk:** the JavaScript changes apply beyond the
   dashboard. Check other row menus, Copy fallback, keyboard navigation, Escape,
   outside click, Tab focus and Delete cancellation before acceptance.
5. **CI remains unresolved:** run 38081411963 at checkpoint ee3 failed its test
   step with exit 2. Logs could not be retrieved (signed log endpoint EOF/403).
   Read-only collection of its exact merge tree found 3,030 tests cleanly; a
   current-main merge snapshot found 3,051 cleanly. Two earlier UI modules had
   42 passes. None establishes the cause of the CI failure. Do not blame
   collection or mark CI green without the actual final result.
6. **Legal/source question:** the owner asked whether street and other address
   components are mandatory. Existing flags/validation were preserved; do not
   treat the redesign or its labels as legal verification. Resolve from current
   authoritative Czech invoice and facility-reporting sources before changing it.
7. **Evidence is partial:** local `generated_images/0041-evidence/` contains
   synthetic action strips and early Stays captures, not a completed acceptance
   gallery. Full generated directories are not committed in this draft.

Historical 0040 checks recorded **3,030 passed, 0 skipped, 89.57% coverage** and
444 geometry combinations with zero lane mismatches at the App checkpoint
`9a6fcf2f216fc0a966b59a69c69124cfb03e5720`; ee3 was a subsequent documentation
commit. These results **do not cover the current 0041 changes**. Historical
screenshots can still contain the old More control and progress-gated Copy.
Do not use them as proof that this draft meets the owner's expectations.

## Artifacts

- `AGENTS.md:1` — role boundary, routing and owner-authorized exception.
- `docs/context/workflow.md:43` — blocked briefs must not be executed unchanged.
- `docs/tasks/0041-host-stay-actions.md:1` — paused scope and unchecked acceptance.
- `docs/tasks/0041-host-stay-actions-report.md:1` — truthful draft result summary.
- `docs/plans/host-design-application-review.md:1` — historical design inventory.
- `docs/DESIGN.md:1` and `docs/HOST_APP_DESIGN.md:1` — intended UX rules, not acceptance evidence.
- `App/app/templates/reservations.html:1` — token-gated inline Copy change.
- `App/app/templates/dashboard.html:30` — shared ellipsis and guest-link actions.
- `App/app/templates/_components.html:280` — optional Copy menu semantics.
- `App/app/static/app.js:406` — shared-menu state and focus behavior.
- `App/tests/test_host_stay_actions_browser.py:197` — three-action containment failure.
- `App/tests/test_host_quiet_dashboard_browser.py:216` — mobile menu-opening failure.
- `docs/tasks/0040-luna_validation-report.md:1` — historical commands and limitations.
- `docs/tasks/0040-evidence/` — committed historical synthetic screenshots.

The uploaded copy/search/status HTML snippets were referenced in the earlier
conversation. They are not newly saved as standalone source files by this
handoff; compare branch implementation and reports before claiming exact reuse.
Do not put real guest/operator details, databases, credentials or tokens into
the public repository or new screenshots.

## Next Steps

1. Confirm `task/host-design-staging`, PR #338 head and git status. Read the
   role rules and this handoff; summarize the 24-item inventory for the owner
   to hand-pick. Respect the stop; get a renewed execution instruction before
   running or implementing the blocked brief.
2. Once authorized, use an executor for scoped work. Fix the Send/Copy/ellipsis
   containment with measured tracks or an appropriate existing breakpoint;
   keep all legitimate actions visible. Reproduce the mobile menu failure and
   address its actual cause without broad untested JavaScript changes.
3. Check genuine Ready/Reported/Waiting/Incomplete/Preview/Failed/Scheduled
   fixtures and tokenless guards. Verify actual copied canonical URLs, manual
   fallback, Delete guards, mouse and keyboard in EN/CS at 360, 390, 1280, 1920.
4. Bump the cache token after final asset changes. Freeze App edits, rerun focused
   Chromium checks and the relevant filter/feedback/wide-geometry modules, then
   the full CI-equivalent suite. Use the historical verified environment:

   ```bash
   # Executor only, from App/. Remove smoke-only login/bootstrap overrides first.
   PATH=/tmp/ubyhost-ci-tools/usr/bin:$PATH UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium XDG_CONFIG_HOME=/tmp/ubyhost-wide-xdg-config XDG_CACHE_HOME=/tmp/ubyhost-wide-xdg-cache XDG_DATA_HOME=/tmp/ubyhost-wide-xdg-data .venv/bin/python -m pytest tests -q -rs --cov=app --cov-report=term-missing --cov-fail-under=86
   ```

   Verify these local tools/paths exist in a new environment rather than silently
   skipping browsers or accepting missing dependencies. Preserve logs and exit status.
5. Capture unmodified synthetic screenshots for the actual final head; update
   the 0041 report and acceptance only when checks pass with zero skips. Diagnose
   final GitHub CI independently. Root can run `python3 scripts/context_lint.py`.
6. Push only the feature branch. Leave the PR draft until the owner accepts the
   selected designs and final evidence. The owner handles staging, merging and
   production; this handoff is not authorization for any deployment.

## Conflict-resolution follow-up

The owner subsequently requested PR #338 conflict resolution. Main was integrated
into the feature branch; overlapping 0038/0040 door-code reports keep their main
filenames, while historical host reports use explicit distinct Report paths.
Design work remains paused, the two browser failures remain unresolved, and the
PR stays draft. Application changes from main were automatically merged; this
follow-up does not claim a newly passing application test suite.

## CI collection follow-up, 2026-10-11

CI run 38089667240 stopped at coverage collection, exit 2. Exact-head no-Playwright
reproduction found unconditional imports in host controls, property controls and
wide geometry modules. Brief 0042 only restores the existing optional import
contract; required browser mode must still hard-fail without its dependency.
This is separate from the two paused 0041 browser failures. See the 0042 report
and final GitHub run for validation; no renewed design acceptance is implied.
