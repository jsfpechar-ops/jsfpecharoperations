# 0091: Eliminate cramped stays and audit all host layout families

Status: todo
Depends on: 0090 reviewed on the correction integration branch | Initial source baseline: 7b27d09402f9656b0c606c131793310925936526 | Branch: task/0091-host-fit-audit | PR base: task/production-host-ux-integration
Executor: Cursor local agent (composer, Kimi or GLM) | One scoped executor session

## 1. Objective

Eliminate cramped stays and audit all host layout families. Deliver the owner's less-is-more correction without losing working features, drafts, legal data or filing safeguards.

## 2. Context

Read AGENTS.md, this brief, the correction plan and the preceding correction report only. This is the urgent corrective lane before 0072–0086. The [owner requirements](../plans/production-host-ux-corrections.md) supersede conflicting older optional-platform/parser/toggle instructions. Do not read or execute a blocked navigation brief.

Anchors: reservations.html `<div class="panel tight scroll-x stays-view">`; seven stay-col columns and possible Send + Copy + More row actions. host.css uses viewport media ranges 721–1100 and min-width 1101; Copy width percentages reserve different action space. Normal working stays must fit without horizontal sliding. Owner likes the house book table: preserve that register, including its intentional wide-record presentation rather than globally hiding table overflow.

The source anchors describe current main before these tasks. Compare the reviewed predecessor diff first: a change intentionally made by a listed predecessor must be retained, not reverted to match an older anchor. If any other drift exists, stop with the precise difference. Record the actual base SHA and baseline failures before editing. No live provider/tenant data during verification.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/host.css` | edit | Scoped correction/test specified below |
| `App/app/templates/reservations.html` | edit | Scoped correction/test specified below |
| `App/tests/test_host_wide_geometry_browser.py` | edit | Scoped correction/test specified below |
| `App/tests/test_host_stay_actions_browser.py` | edit | Scoped correction/test specified below |
| `App/tests/test_host_fit_browser.py` | create | Scoped correction/test specified below |
| `docs/tasks/0091-host-fit-audit.md` | edit | Lifecycle only |
| `docs/tasks/0091-report.md` | create | Required report |
| `docs/tasks/0091-evidence/` | create | Synthetic screenshots/measurements only |

Read-only: docs/plans/production-host-ux-corrections.md; docs/plans/host-navigation-execution-protocol.md §§4–6; routed DESIGN/HOST_APP_DESIGN and UBYPORT_CORE/OPERATIONS/privacy sections when applicable; App/app/routes/admin_helpers.py; App/app/access.py; App/app/validation.py; App/app/templating.py; existing fixtures/conftest and directly referenced shared primitives. 0091 may inspect existing host templates/routes solely for the authorized read-only audit. No other file changes. New files apply only at the task which introduces them; later tasks edit them.

## 4. Steps

1. Before changing CSS reproduce with synthetic data: long property/platform names, ready/scheduled stay with Send + Copy + More, incomplete stay without Send, archived rows, many records, sidebar expanded/collapsed, preview/banner present. Measure the stays container clientWidth/scrollWidth and every cell/action/date rectangle, not just whole-page width or shared outer edges. Record the failing reproduction and exact width/state. Do not dismiss a visible screenshot defect because an existing test passed.
2. Implement a named CSS inline-size container on .stays-view and scope every correction to the host stays view. Use compact labeled row cards when its available lane is at most 1100px, regardless of viewport. Two columns above 600px, one column at most 600px; stay dates and actions span the row. Preserve current data-label and primary links. On larger lanes retain the table, min-width:0, fixed width 100%, breakable property/status/deadline text. Remove .scroll-x from normal stays; no overflow:hidden clipping workaround.
3. Use the existing medium-width card rules as the exact starting declarations, moving them from viewport-only conditions to `@container stays-list (max-width: 1100px)`. Make `.host-workspace .stays-view { container-name: stays-list; container-type: inline-size; min-width: 0; overflow: visible; }` the containing rule. Replace the row-action nowrap and calc percentage widths in this view with flex-wrap:wrap, gap:8px, min-width:0, bounded natural button widths and a fixed-size More button. Apply to ready Send+Copy+More and to Copy+More equally. A button label can wrap on a narrow card; whole labels remain readable and tap targets follow existing 44px mobile rules. Put all narrow controls on a new line before crowding data. Keep desktop table semantics/headers; do not duplicate rows for mobile or create two action forms.
4. Keep filters, preset tabs, exports, saved views, pagination, status/deadline meaning, manual send confirmations and row link/menu keyboard behavior unchanged. Do not solve width by removing Send/Copy/More. Assert menus stay in the viewport and operate without triggering row navigation. No changes to filing controls/state machine.
5. Extend the real geometry/browser tests to assert document and normal stays scrollWidth <= clientWidth+1, first/last column bounds inside the lane, date/label visibility, no overlaps and all buttons reachable. Run EN/CS through widths 360/390/760/1024/1280/1440/1680/1920/2048, both sidebar states, 200% zoom-equivalent smaller available lane, longest localized labels and empty/loading/error states. Distinguish intentional register/export-wide regions from accidental normal work-list overflow: no blanket allowance for the broken stays panel.
6. Audit route/state families using existing seeded browser fixtures: Dashboard; Properties list/detail/create; calendar add/error; Stays/detail; reports/register; business and invoice settings; invoice list/create/detail; fee list/detail; account settings; guest-link/automation hubs; locks and first-login/setup. For each record actual route, fixture/state, locale, width, overflow/obstruction/duplicate-field/default/copy result and screenshot. Classify confirmed source issue, observed browser issue, already-correct, or not executable. Read-only source files for these families may be opened; do not edit their templates/routes in this task.
7. Fix only the named stays/shared scoped CSS in this task. Any separate family defect gets an exact small correction proposal with affected files and reproduction in the report for orchestrator release; do not improvise out-of-allowlist edits, or claim the entire app clean before those corrections are tested. The house book layout remains owner-approved; only its help copy changed in 0087. Save synthetic evidence of the ready row at every representative width and a machine-readable measurement matrix.

Finish by comparing every changed file against §3 and writing §9. Do not automatically advance to the next task in the same session. Larger scoped edits above identify exact structures and invariants; small supplied replacements are mandatory. If the code required cannot be determined from these anchors without inventing business behavior, stop with an exact proposed diff instead of guessing.

## 5. Do not touch

No schema/migrations, dependencies, auth/access/CSRF policy, filing state machine, UbyPort SOAP, code lists, deadline computation, statutory field semantics, retention, signed records, issued invoice snapshots, TTLock/PIN lifecycle, live locks/feeds/emails/payments, public/guest design, workflow/deploy files or unrelated endpoints. No production/main push, merge or deploy. Required legal acceptance remains at its actual acceptance flow. This is presentation/default correction, not legal-policy revision.

## 6. Commands

Executor only; orchestrator does not run application tests. Use the existing Python/pinned-browser setup in the execution protocol. From App, run focused checks first:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_host_stay_actions_browser.py tests/test_host_fit_browser.py -q -rs
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests -q -rs --cov=app --cov-report=term-missing --cov-fail-under=86
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841
```

From repo root:

```bash
python3 scripts/context_lint.py
git diff --check
git diff --name-only
```

Expected: checks pass, required browsers zero skipped, no introduced baseline failure. Record real output; do not invent a pass count or weaken old assertions merely because they now fail. Intentional changed product expectations get new meaningful regression coverage. Browser unavailable is a blocker, not acceptance. CI must pass on the exact task head before integration/release.

## 7. Acceptance

- [ ] Normal stays require no horizontal sliding, clipping or tiny text. All supported actions fit. Every named host family has an evidence-backed audit result; remaining separate defects are explicitly recorded.
- [ ] All task-specific negative/draft/ownership/compatibility regressions in §4 pass; untouched settings and protected records survive.
- [ ] Actual browser evidence in EN/CS at 360/390/1280; geometry through 760/1024/1440/1680/1920/2048, expanded/collapsed sidebar, long labels and relevant error states. No visible obstruction/clipping; zero required-browser skips.
- [ ] No new schema/dependency/outbound call; fake/mocked integrations only; evidence contains fictional data and no token-bearing URLs/passwords/PINs.
- [ ] Current-head CI green, changed paths within §3, predecessor/candidate SHA and remaining audit findings recorded. Application change is not called deployed merely because a plan PR merged.

## 8. Stop and ask

Stop for unexplained source drift, foreign/archived access uncertainty, changing filing/legal semantics, an unlisted required file, missing browser prerequisites or a command that needs live providers/secrets/production. Send the exact blocker and proposed narrow correction. Do not reask approval for requirements already approved in chat. If baseline fails, isolate/report it; no test skips, assertion weakening, force push, main merge or deploy shortcut.

## 9. Report

Write docs/tasks/0091-report.md (max 1500 tokens), set Status: review. Include actual base/result SHA, file stat, test commands/last five output lines, counts/skips/coverage, §7 checkboxes, screenshot/measurement paths, source-vs-runtime audit boundary, deviations/unresolved defects and numbered owner steps. Do not claim production fixed or erase an open issue until reviewed application evidence exists.

## Risk list

Review the complete diff of every handler/template/default touched here, especially broad full-form payloads, negative validation, preservation of existing entity/controller/automation values and return paths. Read test fixtures for real provider calls and evidence for privacy leaks.

## Owner steps

1. Open a fresh Cursor chat and use the correction master prompt with this brief; its dependency must already be reviewed.
2. Review the report and actual CI on task/0091-host-fit-audit; its PR targets task/production-host-ux-integration, never main.
3. After all corrections and outstanding audit fixes pass, review the exact tested candidate on staging with synthetic data.
4. Approve that candidate SHA before production promotion through the existing release protocol. Main currently triggers production deployment; do not merge early for a preview.
