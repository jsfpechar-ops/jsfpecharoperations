# 0089: Require visible platform names and valid calendar URLs

Status: review
Depends on: 0088 reviewed on the correction integration branch | Initial source baseline: 7b27d09402f9656b0c606c131793310925936526 | Branch: task/0089-required-calendar-platform | PR base: task/production-host-ux-integration
Executor: Cursor local agent (composer, Kimi or GLM) | One scoped executor session

## 1. Objective

Require visible platform names and valid calendar URLs. Deliver the owner's less-is-more correction without losing working features, drafts, legal data or filing safeguards.

## 2. Context

Read AGENTS.md, this brief, the correction plan and the preceding correction report only. This is the urgent corrective lane before 0072–0086. The [owner requirements](../plans/production-host-ux-corrections.md) supersede conflicting older optional-platform/parser/toggle instructions. Do not read or execute a blocked navigation brief.

Anchors: `@router.post("/apartments/{apartment_id}/feeds")`, `"label": _form_str(form, "label")`, `"own_name": _form_str(form, "own_name")`; label and own_name are inside More options. Existing feed_platform_key is URL-based and source_badge renders its supplied text. Owner explicitly requires BOTH platform and valid URL; no named-only draft storage.

The source anchors describe current main before these tasks. Compare the reviewed predecessor diff first: a change intentionally made by a listed predecessor must be retained, not reverted to match an older anchor. If any other drift exists, stop with the precise difference. Record the actual base SHA and baseline failures before editing. No live provider/tenant data during verification.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | Scoped correction/test specified below |
| `App/app/routes/setup_wizard.py` | edit | Scoped correction/test specified below |
| `App/app/templates/apartment_form.html` | edit | Scoped correction/test specified below |
| `App/app/templates/setup/bookings.html` | edit | Scoped correction/test specified below |
| `App/app/host_i18n.py` | edit | Scoped correction/test specified below |
| `App/tests/test_calendar_platform_required.py` | create | Scoped correction/test specified below |
| `App/tests/test_calendar_sync_ui.py` | edit | Scoped correction/test specified below |
| `App/tests/test_feed_url_ssrf.py` | edit | Scoped correction/test specified below |
| `App/tests/test_feed_no_duplicate_per_user.py` | edit | Scoped correction/test specified below |
| `App/tests/test_host_property_controls_browser.py` | edit | Scoped correction/test specified below |
| `docs/tasks/0089-required-calendar-platform.md` | edit | Lifecycle only |
| `docs/tasks/0089-report.md` | create | Required report |
| `docs/tasks/0089-evidence/` | create | Synthetic screenshots/measurements only |

Read-only: docs/plans/production-host-ux-corrections.md; docs/plans/host-navigation-execution-protocol.md §§4–6; routed DESIGN/HOST_APP_DESIGN and UBYPORT_CORE/OPERATIONS/privacy sections when applicable; App/app/routes/admin_helpers.py; App/app/access.py; App/app/validation.py; App/app/templating.py; existing fixtures/conftest and directly referenced shared primitives. 0091 may inspect existing host templates/routes solely for the authorized read-only audit. No other file changes. New files apply only at the task which introduces them; later tasks edit them.

## 4. Steps

1. Add one server-side allowlist and normalization helper, reused by add_feed and wizard feed creation. Keep the existing label and own_name database columns; no schema/dependency. Accepted platform choices: Airbnb, Booking.com, Vrbo, Agoda, e-chalupy, Other. Display names are not logo-only. Store a readable platform in label. Other requires a trimmed readable other-platform name (max 80); custom own_name is optional (max 100) and defaults to that readable platform. Reject control characters/blank/unknown choices before insert or sync. Existing wizard `myself` means manual stay and must not be inserted as a calendar. Do not silently infer a mandatory user choice from the URL.
2. Replace the portal text input with an always-visible required select before URL. Empty “Choose platform” is disabled; it is not a valid default. Add visible Other platform text when Other is selected and server validation when JS is absent. Show own_name as an ordinary optional field, without More options and supply values from feed_draft on rerender. Preserve canonical field names label/own_name/url. Use existing native select/error styling. Both platform and URL need server checks, even if HTML required is bypassed.
3. Keep validate_calendar_url, SSRF/DNS safeguards, duplicate checks, owner guards and sync_all scope unchanged. Reject blank URL before a network request. Validate platform and URL before db.insert. A successful add may sync that property's calendars as before; do not mislabel it as per-feed-only sync. Sync failure is a real partial failure with the created feed retained according to the existing ordinary-add lifecycle. Do not adopt the wizard's delete-on-failure behavior for ordinary adds.
4. Extract the existing apartment_detail rendering body mechanically into `_render_property_detail(apartment_id, request, *, extra=None, status_code=200)`. Keep the GET route signature unchanged and delegate to it. Add `**(extra or {})` after `**copy_ctx` in the render context; pass status_code to render. Preserve all guards, fields, readiness, secret redaction and ownership. POST validation failure invokes this helper with 400 and `feed_draft` containing only submitted platform/name/URL plus translated field errors. Open/focus the calendar error section; do not store URL drafts in query strings (iCal URLs can contain tokens). Never reflect credentials in logs/evidence. Success/partial sync redirects use the existing `_back` to `/apartments/{id}#calendars` rather than bare property URL. Errors before insert cause no write/sync.
5. For existing rows use own_name, else trimmed label, else a readable mapping from feed_platform_key(url), else “Calendar” / “Kalendář”. Portal uses trimmed label, else detected readable platform, else “Other” / “Jiný”. Never show a bare dash next to a recognized platform logo. Do not relabel rows in the database or invent a platform when URL recognition fails. Keep actual last_status/error/check time and removal confirmation.
6. Apply the same required platform/URL behavior to the existing wizard form and POST until 0092 adapters replace the wizard. Preserve invalid draft values. Use the helper's readable mapping, not two independently maintained allowlists. Manual stay path remains available.
7. Test missing/blank/whitespace/unknown/Other platform, empty/malformed/unsafe URL, foreign property, duplicate URL, draft retention, successful default name, custom name, old unlabeled Booking/Airbnb/unknown feeds, actual sync errors and return hash. Assert validation happens before db.insert and mocked sync/network calls. No live feed downloads. EN/CS screenshot shows platform first without opening More options.

Finish by comparing every changed file against §3 and writing §9. Do not automatically advance to the next task in the same session. Larger scoped edits above identify exact structures and invariants; small supplied replacements are mandatory. If the code required cannot be determined from these anchors without inventing business behavior, stop with an exact proposed diff instead of guessing.

## 5. Do not touch

No schema/migrations, dependencies, auth/access/CSRF policy, filing state machine, UbyPort SOAP, code lists, deadline computation, statutory field semantics, retention, signed records, issued invoice snapshots, TTLock/PIN lifecycle, live locks/feeds/emails/payments, public/guest design, workflow/deploy files or unrelated endpoints. No production/main push, merge or deploy. Required legal acceptance remains at its actual acceptance flow. This is presentation/default correction, not legal-policy revision.

## 6. Commands

Executor only; orchestrator does not run application tests. Use the existing Python/pinned-browser setup in the execution protocol. From App, run focused checks first:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_calendar_platform_required.py tests/test_calendar_sync_ui.py tests/test_feed_url_ssrf.py tests/test_feed_no_duplicate_per_user.py tests/test_host_property_controls_browser.py -q -rs
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

- [ ] Add and sync requires both explicit platform and valid URL. Every connection has readable platform/name text; error drafts survive and feedback stays in calendars.
- [ ] All task-specific negative/draft/ownership/compatibility regressions in §4 pass; untouched settings and protected records survive.
- [ ] Actual browser evidence in EN/CS at 360/390/1280; geometry through 760/1024/1440/1680/1920/2048, expanded/collapsed sidebar, long labels and relevant error states. No visible obstruction/clipping; zero required-browser skips.
- [ ] No new schema/dependency/outbound call; fake/mocked integrations only; evidence contains fictional data and no token-bearing URLs/passwords/PINs.
- [ ] Current-head CI green, changed paths within §3, predecessor/candidate SHA and remaining audit findings recorded. Application change is not called deployed merely because a plan PR merged.

## 8. Stop and ask

Stop for unexplained source drift, foreign/archived access uncertainty, changing filing/legal semantics, an unlisted required file, missing browser prerequisites or a command that needs live providers/secrets/production. Send the exact blocker and proposed narrow correction. Do not reask approval for requirements already approved in chat. If baseline fails, isolate/report it; no test skips, assertion weakening, force push, main merge or deploy shortcut.

## 9. Report

Write docs/tasks/0089-report.md (max 1500 tokens), set Status: review. Include actual base/result SHA, file stat, test commands/last five output lines, counts/skips/coverage, §7 checkboxes, screenshot/measurement paths, source-vs-runtime audit boundary, deviations/unresolved defects and numbered owner steps. Do not claim production fixed or erase an open issue until reviewed application evidence exists.

## Risk list

Review the complete diff of every handler/template/default touched here, especially broad full-form payloads, negative validation, preservation of existing entity/controller/automation values and return paths. Read test fixtures for real provider calls and evidence for privacy leaks.

## Owner steps

1. Open a fresh Cursor chat and use the correction master prompt with this brief; its dependency must already be reviewed.
2. Review the report and actual CI on task/0089-required-calendar-platform; its PR targets task/production-host-ux-integration, never main.
3. After all corrections and outstanding audit fixes pass, review the exact tested candidate on staging with synthetic data.
4. Approve that candidate SHA before production promotion through the existing release protocol. Main currently triggers production deployment; do not merge early for a preview.
