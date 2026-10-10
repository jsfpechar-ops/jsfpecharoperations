# Host UI decisions

Continuation of [decisions](decisions.md), split to respect its token cap.
Append-only: date | decision | reason | link. Keep superseded lines and name
replacements. Grep by topic. Archive only unreferenced entries older than 90 days
per [workflow](workflow.md#compaction). Initial host entries moved here on integration:

- 2026-10-10 | Month grid for Invoices/Stay fees; pills/operator actions pending | owner choice | [plan](../plans/host-control-polish.md)
- 2026-10-10 | Expandable Stays/Invoice filters; hover/focus default; simple near-term dashboard | owner | [UI](../plans/host-control-polish.md)
- 2026-10-10 | Quiet overview; 5 stays; 14 days; overdue first | owner | [UI](../DESIGN.md)
- 2026-10-10 | 30d replaces 14d; Delete archives | owner | DESIGN

- 2026-10-10 | Address option A: aligned labels, separate aligned reporting badges and aligned input tops | owner choice | [DESIGN](../DESIGN.md)
- 2026-10-10 | Operator Edit/Invoice settings/More always visible; consistent Delete menu, unavailable with visible explanation when linked | owner choice; easier keyboard/touch discovery | [plan](../plans/host-control-polish.md)
- 2026-10-10 | Keep invoice-item layout; Cleaning unit may stay blank; custom description only for Other | owner choice; remove irrelevant input without inventing values | [plan](../plans/host-control-polish.md)
- 2026-10-10 | Remove duplicate Property tools menu on individual property pages; retain all-property overviews from Properties landing and Search, local cards and shared-lock setup | owner choice | [HOST_APP_DESIGN](../HOST_APP_DESIGN.md)
- 2026-10-10 | Uniform host filter components/geometry/interactions where possible; preserve each page's fields, default semantics and simple visible view choices | owner choice | [filter audit](../plans/host-filter-audit.md)
- 2026-10-10 | Produce an interactive review-only design prototype and Chromium/Playwright captures; Cursor remains the application executor | owner request | [preview](../plans/host-control-review.html)
- 2026-10-10 | Extremely easy, intuitive host UX: familiar labels, relevant information, predictable controls, touch/keyboard access; current-source invoice-address verification still open | owner direction; legal source access blocked | [legal check](../plans/invoice-address-check.md)
- 2026-10-10 | Remove Needed to report pills; complete aligned labels/inputs, plain optional flags only; supersedes earlier address A badges | owner revised the screenshot; field legal verification still open | [DESIGN](../DESIGN.md)
- 2026-10-10 | Restore four white Quiet overview status cards with semantic dots/attention lines; align Open stay and every invoice/control column across rows; responsive previews follow their available width | owner screenshot correction | [review](../plans/host-control-review-report.md)
- 2026-10-10 | Adapt pasted copy/checkmark and stacked feedback to all transient host updates; actual clipboard/save/report outcomes, persistent errors/partial results, accessible feedback, no demo cycling | owner request | [feedback](../plans/host-feedback-review.md)
- 2026-10-10 | Dashboard button Open; guest registration URL action Copy guest form link, preserving other copy targets' specific names | owner wording correction | [DESIGN](../DESIGN.md)
- 2026-10-10 | One shared Stay dates control on day-range filter pages; both/open-ended dates, draft confirmation, clear and invalid-range protection | owner supplied date-range reference | [filter audit](../plans/host-filter-audit.md)
- 2026-10-10 | Stays summary All properties · Active; custom dates only, no preset date/ellipsis. Preview defaults to unbounded All dates, interpreting “all the time”; Upcoming/Past retained | owner direction; optional preset clarification unanswered at preparation | [DESIGN](../DESIGN.md)
- 2026-10-10 | Owner authorizes staging review of the new host design before production; deploy the implemented and checked feature commit to Render ubyhost-staging, with mock UbyPort | current deliverable is a prototype; Cursor application execution remains prerequisite | [handoff](../plans/host-design-staging-handoff.md)
- 2026-10-10 | [workflow] Owner designates Luna 6.0 executors and explicitly permits multiple implementation subagents; Codex reviews and may push the feature branch/PR and deploy staging | supersedes Cursor-only/exact-phrase/search-only restrictions for this host redesign; no main push or production deployment | [workflow](workflow.md#owner-authorized-host-design-execution)
- 2026-10-10 | Selected host redesign implemented on task/host-design-staging; 3,022 tests passed, required Chromium zero skips, coverage 89.53%; no new type findings | local acceptance only; PR/CI and Render still blocked by network publication, address-law verification open | [application review](../plans/host-design-application-review.md)
- 2026-10-10 | PR #338 opened for owner review; GitHub API reachable; CI/staging pending | owner requested PR; no merge or deployment | [PR](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/338)
- 2026-10-10 | Owner's staging screenshots reopen host design acceptance: shared content edges, table/action tracks and notification obstruction require a full measured audit through 2048 CSS pixels | earlier narrow browser checks missed wide-screen defects | [0040](../tasks/0040-host-wide-geometry-audit.md)

- 2026-10-10 | Shared host lanes/actions corrected; persisted warnings stay in flow; 444 EN/CS/width cases had zero lane mismatches, 3,030 tests passed with zero skips and 89.57% coverage | supersedes initial narrow-screen acceptance; CI and owner staging redeploy remain pending | [0040](../tasks/0040-host-wide-geometry-audit.md)

- 2026-10-10 | Owner reopened design selection; only guest-link Copy availability and shared dashboard ellipsis authorized now | other design choices await hand-picking; no broader redesign | [0041](../tasks/0041-host-stay-actions.md)

| 2026-10-10 | Owner stopped implementation; preserve WIP as draft #338 for another AI | No further fixes/deploys; 0041 blocked; designs await hand-picking | 0041 |

| 2026-10-10 | Owner requested draft #338 conflict resolution | Preserve main door-code reports and host reports under distinct names; UI remains paused | 0041 |
