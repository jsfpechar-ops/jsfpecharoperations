# 0094: Property tabs, one editor and early calendar setup

Status: todo
Depends on: 0093 reviewed | Initial source: 7b27d09402f9656b0c606c131793310925936526 | Branch: task/0094-property-tabs-early-calendars | PR base: task/production-host-ux-integration
Executor: Cursor local agent (composer, Kimi or GLM) | One property-navigation session

## 1. Objective

Implement Overview / Bookings & calendars / Settings with one maintained property editor. Make calendar connection the first optional action after create and keep it accessible in the local bar thereafter, without a long forced onboarding sequence.

## 2. Context

This task replaces 0072/0073/0074, whose old extraction patches predate the owner’s new corrections. Do not execute those stale patches. Keep the approved cross-host ownership map in the maintainability plan; this is the property part of that architecture. Latest correction-plan requirements take precedence over old arrows, optional platform and parser/toggle design.

Read AGENTS.md, the correction plan, 0093 report, maintainability plan §§4–9 and execution protocol. Source anchors after predecessors: one property POST form in apartment_form.html; ordinary sections #basics/#address/#ubyport/#automation/#communication/#stay-fee-settings/#door-code; calendar POST is a sibling form; `_render_property_detail` from 0089. Shared identity/address/operator partials already exist. Do not extract duplicated copies of those fields.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/apartment_form.html` | edit | Compose one tabbed detail; preserve short create |
| `App/app/templates/_property_overview.html` | create | Read-only cards/status/early setup actions |
| `App/app/templates/_property_editor.html` | create | Move corrected existing full settings form once |
| `App/app/templates/_property_calendars.html` | create | Move corrected existing calendar block once |
| `App/app/templates/_components.html` | edit | Reuse existing tab/section/help primitives only |
| `App/app/static/host.css` | edit | Scoped tabs/section grid and narrow wrapping |
| `App/app/static/app.js` | edit | Draft-preserving view/section/hash/error navigation |
| `App/app/routes/admin.py` | edit | GET presentation state and safe success/return targets only |
| `App/app/routes/setup_wizard.py` | edit | Early optional-calendar entry/legacy adapters only |
| `App/app/host_i18n.py` | edit | Local labels, no restored clutter |
| `App/tests/test_property_navigation_browser.py` | create | Navigation/draft/error/early setup regression |
| `App/tests/test_host_property_controls_browser.py` | edit | Corrected single-editor expectations |
| `App/tests/test_setup_wizard.py` | edit | Early calendar and non-forced entry |
| `App/tests/test_calendar_platform_required.py` | edit | Validation/draft return in tabbed context |
| `docs/tasks/0094-property-tabs-early-calendars.md` | edit | Lifecycle only |
| `docs/tasks/0094-report.md` | create | Report <=1500 tokens |
| `docs/tasks/0094-evidence/` | create | Synthetic captures/ownership inventory |

Read-only: corrected shared property partials, handlers/guards, preceding reports, the named plans and existing fixtures. No other handler/template modifications. All property fields stay in their current single authoritative form.

## 4. Steps

1. Record reviewed predecessor SHA and an inventory of successful control IDs/names, forms and all live capability links. Move the corrected broad property settings form byte-for-byte into _property_editor.html and calendar block into _property_calendars.html. Keep existing shared field includes rather than copying their contents. Put existing read-only shortcut cards and real setup/status summaries in _property_overview.html. Include each once in the editing branch of apartment_form; short create stays separate. Recompare names/actions/guards before styling. Move, do not reimplement full-save semantics or create three settings routes.
2. Local view keys are exactly `overview`, `bookings`, `settings`, default overview; settings section keys exactly `property`, `guests`, `reporting`, `automation`. Optional query view/section is a GET presentation choice, not a new data endpoint. Sanitize to these allowlists; all handler ownership remains unchanged. Tab label: Overview / Bookings & calendars / Settings; CS: Přehled / Rezervace a kalendáře / Nastavení. Settings groups: Property information (basics/address/notes/archive), Guest experience (communication/door-code), Reporting & fees (ubyport/request help/fee), Automation (timing/purpose). Every field occurs once across the document; overview contains no editable shadow form.
3. Render one existing full-property form for all Settings fields, using normal headers rather than collapsible essential sections. Desktop local section rail; mobile wrapping labels or ordinary select, never a horizontal scrolling tab rail. Do not disable inactive settings controls. Native browser invalid events must reveal/focus the relevant section before validation UI; server errors target that section and retain submitted values. Keep the same current full-save endpoint, hidden guards, credential test actions and settings data. Calendar POST remains outside it; no nested form.
4. Existing hash map is fixed: #basics/#address → settings/property; #communication → settings/guests; #door-code → settings/guests; #ubyport/#ws-request-letter/#stay-fee-settings → settings/reporting; #automation → settings/automation; #calendars/#calendar-connect → bookings. Real return paths and legacy hub links select their exact destination. Hash selection takes priority over default view. Overview cards use these same routes; business card opens its assigned shared entity editor, not a duplicate business form. A recognized hash reveals all necessary ancestors, then scrolls to its actual target. A missing/unknown hash does not jump to top or choose a foreign record.
5. In JS intercept ordinary unmodified same-property local navigation to switch the already-rendered view/section and update history without replacing document/form draft. Respect modifier keys, external links and back/forward. Save return_to reflects the active view/section using safe local URLs. Navigating away with dirty settings triggers existing draft protection rather than silently losing work. No credentials/URL tokens in history/storage. Preserve JS-disabled function: all relevant editor sections remain usable with ordinary hrefs/anchors from the same markup; no separately maintained fallback editor. Do not claim no-JS access based only on a JS-enabled screenshot.
6. Create success goes to the authorized property’s bookings view with #calendar-connect and an optional first-use choice: Connect calendar, Add stay manually, Continue to overview. Required platform + URL form is visible immediately for this first-use path; it is not the final panel of a long settings page. Manual choice uses the existing authorized stay-creation path; Skip/Continue uses property overview. No mandatory fee/lock/invoice/reporting step, fabricated progress counter or return-to wizard loop.
7. Bookings view has the real feed list (readable platform/name, actual sync check/result, management/removal) and Connect calendar action. After successful connection show the real connection/sync outcome and compact list; connection inputs reopen through an explicit Add calendar action, not an arrow hiding essential existing values. Blank/failure draft keeps that form visible; platform/URL fields remain visible in it. Existing names/statuses stay directly readable. Never infer synced/ready from presence of URL or merely creating the feed. Preserve partial failures, SSRF/duplicate guards and lifecycle/removal confirmation. A calendar remains reachable through the main local Bookings & calendars tab and Bookings overview card after onboarding.
8. Guest experience shows URL/PIN/change actions prominently and no Suggested portal message; archive lives in Property information; feature switch has truthful saved Enabled/Off state. ? help is shared; no chevron-based hiding of essentials. Preserve all corrected user requirements rather than replaying an old visual board.
9. Tests cover all three views/four groups, every old hash, one/many/no feeds, zero/one/many operators, required-platform errors, create→early calendar→overview, manual/skip, dirty drafts across sections/tabs/back/forward, successful save and credential test return, invalid hidden-field reveal, no-JS use and no duplicate IDs/successful controls. Snapshot full settings values before/after unrelated saves, including credentials/controller/fees/PIN/lock/reporting mode. Browser screenshot matrix EN/CS, 360/390/1280 plus measured widths through 2048 and sidebar states.
10. Hand off the refreshed single-editor inventory to remaining whole-host canonical tasks 0075–0083. Their blocked status is intentional until rebased exact changes are released against this reviewed implementation; never override a blocked task or fabricate its readiness. A property-navigation staging preview can be shown after this task; full-host navigation acceptance requires those remaining tasks plus integration checks. State scope clearly in the staging report.

## 5. Do not touch

No schema/dependency, full-save business semantics, filing/retention/provider lifecycle, statutory exports, guest/public design or real provider operations. No second settings editor, hidden cloned forms, lost dirty draft, disabled successful controls, main merge or production deploy.

## 6. Commands

Executor only, use the existing execution protocol/pinned browser. From App:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_property_navigation_browser.py tests/test_host_property_controls_browser.py tests/test_setup_wizard.py tests/test_calendar_platform_required.py -q -rs
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests -q -rs --cov=app --cov-report=term-missing --cov-fail-under=86
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841
```

Root: `python3 scripts/context_lint.py`; `git diff --check`; `git diff --name-only`. Expect passing checks, zero required-browser skips, real synthetic evidence, no new baseline failures. CI must pass on the exact task head. Do not normalize disappearing fields or weakened geometry assertions as success.

## 7. Acceptance

- [ ] Approved three-tab navigation and four Settings groups; familiar cards/header bars; one editor/field per setting.
- [ ] Calendar setup is offered immediately after create and always reachable in local navigation; connection form stays out of overview after completion, errors retain drafts.
- [ ] All old hashes/return paths, operator/defaults, guest/PIN/lock/archive placement, visible values and contextual help requirements survive.
- [ ] Drafts and all untouched values survive navigation/save; no-JS/keyboard/browser validation/error paths work without duplicated markup.
- [ ] Actual EN/CS/width/sidebars evidence, zero skips, exact-head CI green, protected data untouched, no actual production deployment claimed.

## 8. Stop and ask

Stop for unexplained anchor drift or changed/unclear handler semantics, unlisted files, unavailable browser or a need for real credentials/providers. Report an exact proposed correction. Do not restore stale 0072 extraction or run blocked downstream contracts.

## 9. Report

Write 0094-report.md <=1500 tokens, set review. Base/result SHA, changed files, successful-control inventory comparison, command output/counts, acceptance, screenshots/measurements, remaining whole-host work and owner staging steps. Distinguish property preview from full-host completion and plan mockups from application evidence.

## Risk list

Mechanical form extraction and preserve-all-fields save; credential/validation/dirty navigation; legacy hashes; view/section state; real feed outcomes; archive and provider switches; no duplicated business or property settings.

## Owner steps

1. Run this fresh Cursor session after 0093 review; PR targets task/production-host-ux-integration.
2. Review exact-head CI and actual property preview on staging; remaining whole-host canonical tasks continue on the same reviewed integration lane after their refreshed release.
3. Approve the exact fully tested candidate before final production promotion under the existing protocol. Main automatically deploys after CI; do not merge to obtain staging.
