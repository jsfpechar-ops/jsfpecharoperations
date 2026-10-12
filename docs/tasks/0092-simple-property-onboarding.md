# 0092: Create properties through one polished short form

Status: todo
Depends on: 0091 reviewed on the correction integration branch | Initial source baseline: 7b27d09402f9656b0c606c131793310925936526 | Branch: task/0092-simple-property-onboarding | PR base: task/production-host-ux-integration
Executor: Cursor local agent (composer, Kimi or GLM) | One scoped executor session

## 1. Objective

Create properties through one polished short form. Deliver the owner's less-is-more correction without losing working features, drafts, legal data or filing safeguards.

## 2. Context

Read AGENTS.md, this brief, the correction plan and the preceding correction report only. This is the urgent corrective lane before 0072–0086. The [owner requirements](../plans/production-host-ux-corrections.md) supersede conflicting older optional-platform/parser/toggle instructions. Do not read or execute a blocked navigation brief.

Anchors: apartment_form.html `{% else %}<nav class="section-nav"` (whitespace varies; inspect exact block); broad property form contains settings/integrations/notes on create; onboarding WIZARD_STEPS=(welcome,name,address,bookings), total=5; /setup redirects to numbered wizard. Use the synthetic mockup and requirements in the correction plan. Earlier navigation designs do not authorize bringing back removed explanations or switches.

The source anchors describe current main before these tasks. Compare the reviewed predecessor diff first: a change intentionally made by a listed predecessor must be retained, not reverted to match an older anchor. If any other drift exists, stop with the precise difference. Record the actual base SHA and baseline failures before editing. No live provider/tenant data during verification.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/apartment_form.html` | edit | Scoped correction/test specified below |
| `App/app/templates/_property_create.html` | create | Scoped correction/test specified below |
| `App/app/templates/_property_identity_fields.html` | create | Scoped correction/test specified below |
| `App/app/templates/_property_address_fields.html` | create | Scoped correction/test specified below |
| `App/app/templates/_property_operator.html` | edit | Scoped correction/test specified below |
| `App/app/templates/onboarding.html` | edit | Scoped correction/test specified below |
| `App/app/routes/admin.py` | edit | Scoped correction/test specified below |
| `App/app/routes/setup_wizard.py` | edit | Scoped correction/test specified below |
| `App/app/onboarding.py` | edit | Scoped correction/test specified below |
| `App/app/static/host.css` | edit | Scoped correction/test specified below |
| `App/app/host_i18n.py` | edit | Scoped correction/test specified below |
| `App/tests/test_setup_wizard.py` | edit | Scoped correction/test specified below |
| `App/tests/test_property_create_browser.py` | create | Scoped correction/test specified below |
| `App/tests/test_property_operator_defaults.py` | edit | Scoped correction/test specified below |
| `App/tests/test_calendar_platform_required.py` | edit | Scoped correction/test specified below |
| `docs/tasks/0092-simple-property-onboarding.md` | edit | Lifecycle only |
| `docs/tasks/0092-report.md` | create | Required report |
| `docs/tasks/0092-evidence/` | create | Synthetic screenshots/measurements only |

Read-only: docs/plans/production-host-ux-corrections.md; docs/plans/host-navigation-execution-protocol.md §§4–6; routed DESIGN/HOST_APP_DESIGN and UBYPORT_CORE/OPERATIONS/privacy sections when applicable; App/app/routes/admin_helpers.py; App/app/access.py; App/app/validation.py; App/app/templating.py; existing fixtures/conftest and directly referenced shared primitives. 0091 may inspect existing host templates/routes solely for the authorized read-only audit. No other file changes. New files apply only at the task which introduces them; later tasks edit them.

## 4. Steps

1. Extract identity (name/city) and seven structured address fields from the corrected property editor into shared partials. Use the operator partial from 0088. No partial owns a form or save route. Keep existing IDs/names/lengths and property_prefill binding; the edit form includes each partial once. No copied fields in separate create/mobile/editor templates. Preserve edit drafts, every unrelated setting and legacy #basics/#address anchors. Do not start the full 0072–0086 navigation refactor here.
2. Add a create-only partial with this fixed layout: one primary form column; Property details card (required name, optional city); Managed by card (required operator); a visible compact address card containing all structured fields; ordinary Cancel/Create property footer. Wide screens may show a narrow secondary panel with three simple optional follow-up links/explanations: Connect a calendar, Share the guest form, Set up reporting; optional lock link beneath. On <=900px put follow-ups below the main form, never a horizontally scrolling rail. Use existing sans-serif/tokens/icons despite the illustrative mockup's font. Keep copy/import-from-property available under one optional action, not an always-open introductory panel.
3. Choose the create partial at the existing not-editing branch before the broad editor form, wrapping the current broad form in the editing branch. Keep one POST /apartments; no new app/framework. Remove the create numbered section-nav, repeated onboarding banner, reporting-mode/hour/purpose controls, credential/lock/fee settings and guest-message/notes blocks from initial creation. Those settings stay in the canonical property editor after save. Successful create immediately offers Connect a calendar / Add stay manually / Continue, with no compulsory integration; it must not send users to a long document bottom. 0094 supplies the actual Bookings & calendars tab destination. New hidden defaults, only if required by existing contracts: automation_mode=manual, default_purpose=10. Activity is server-enforced, never a new toggle. Guest message is server-defaulted by 0087. Operator default/controller behavior comes from 0088.
4. Server create accepts a blank address as incomplete setup (existing readiness must block reporting until required details exist); if the host enters address components, retain current per-field validation and render meaningful errors/values before writing invalid data. Never parse a whole address. Validate name/operator before writes. No silent entity creation, fictional address/contact, preselected multi-operator, enabled reporting or auto-assigned lock. Existing copy prefill of settings remains intentional and must be preserved by an explicitly confirmed copy action; hiding those controls must not accidentally lose copied data.
5. Route /setup GET to /apartments/new when no property exists, otherwise to the actual property overview. Legacy GET /setup/welcome and /setup/name target the same create/overview entry; address and bookings target the property's #address/#calendars, or create when no property exists. Keep legacy POSTs as guarded adapters to their existing scoped mutation handlers during transition: preserve all authorization/CSRF/draft/error rules, no redirect-before-saving. Address-only POST remains address-only, legacy name POST enforces operator defaults, calendar POST enforces 0089. Successful responses return to the canonical property context. Do not require sequential completion or revive the five-step wizard as the normal entry.
6. Replace the forced onboarding progression/persistent checklist with optional setup shortcuts from the property overview and one dismissible first-use hint if an existing feature needs it. Keep demo load/reset labels and legal/TTLock terms acceptance where they actually apply. `wizard_step` may remain a compatibility/readiness indicator for other callers; it must not force navigation or label optional integrations as required. Update first-login and Resume entry tests and guidance links to prove they reach the canonical create route. If their actual handler is outside this allowlist, report the precise adapter correction before changing it.
7. Regressions cover new owner zero/one/many entities, operator creation detour with preserved name/city/address, optional address, invalid partial address, new Manual mode, guest default, successful one-submit creation, copy behavior, legacy GET/POST routes, authenticated/foreign/admin preview, no-JS and sidebar widths. Capture actual create page 360/390/1280 and larger-width synthetic screenshots; compare with mockup hierarchy. Shared fields/IDs occur once per document. All existing settings remain reachable after creation, without mandatory calendar/lock/fee/invoice steps.

Finish by comparing every changed file against §3 and writing §9. Do not automatically advance to the next task in the same session. Larger scoped edits above identify exact structures and invariants; small supplied replacements are mandatory. If the code required cannot be determined from these anchors without inventing business behavior, stop with an exact proposed diff instead of guessing.

## 5. Do not touch

No schema/migrations, dependencies, auth/access/CSRF policy, filing state machine, UbyPort SOAP, code lists, deadline computation, statutory field semantics, retention, signed records, issued invoice snapshots, TTLock/PIN lifecycle, live locks/feeds/emails/payments, public/guest design, workflow/deploy files or unrelated endpoints. No production/main push, merge or deploy. Required legal acceptance remains at its actual acceptance flow. This is presentation/default correction, not legal-policy revision.

## 6. Commands

Executor only; orchestrator does not run application tests. Use the existing Python/pinned-browser setup in the execution protocol. From App, run focused checks first:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_setup_wizard.py tests/test_property_create_browser.py tests/test_property_operator_defaults.py tests/test_calendar_platform_required.py -q -rs
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

- [ ] One short, polished create page with required name/operator and optional structured address; no forced numbered wizard. Reliable defaults, one maintained set of fields, legacy paths remain functional.
- [ ] All task-specific negative/draft/ownership/compatibility regressions in §4 pass; untouched settings and protected records survive.
- [ ] Actual browser evidence in EN/CS at 360/390/1280; geometry through 760/1024/1440/1680/1920/2048, expanded/collapsed sidebar, long labels and relevant error states. No visible obstruction/clipping; zero required-browser skips.
- [ ] No new schema/dependency/outbound call; fake/mocked integrations only; evidence contains fictional data and no token-bearing URLs/passwords/PINs.
- [ ] Current-head CI green, changed paths within §3, predecessor/candidate SHA and remaining audit findings recorded. Application change is not called deployed merely because a plan PR merged.

## 8. Stop and ask

Stop for unexplained source drift, foreign/archived access uncertainty, changing filing/legal semantics, an unlisted required file, missing browser prerequisites or a command that needs live providers/secrets/production. Send the exact blocker and proposed narrow correction. Do not reask approval for requirements already approved in chat. If baseline fails, isolate/report it; no test skips, assertion weakening, force push, main merge or deploy shortcut.

## 9. Report

Write docs/tasks/0092-report.md (max 1500 tokens), set Status: review. Include actual base/result SHA, file stat, test commands/last five output lines, counts/skips/coverage, §7 checkboxes, screenshot/measurement paths, source-vs-runtime audit boundary, deviations/unresolved defects and numbered owner steps. Do not claim production fixed or erase an open issue until reviewed application evidence exists.

## Risk list

Review the complete diff of every handler/template/default touched here, especially broad full-form payloads, negative validation, preservation of existing entity/controller/automation values and return paths. Read test fixtures for real provider calls and evidence for privacy leaks.

## Owner steps

1. Open a fresh Cursor chat and use the correction master prompt with this brief; its dependency must already be reviewed.
2. Review the report and actual CI on task/0092-simple-property-onboarding; its PR targets task/production-host-ux-integration, never main.
3. After all corrections and outstanding audit fixes pass, review the exact tested candidate on staging with synthetic data.
4. Approve that candidate SHA before production promotion through the existing release protocol. Main currently triggers production deployment; do not merge early for a preview.
