# 0087: Remove address parsing and unnecessary host explanations

Status: review
Depends on: none; run before the navigation refactor | Initial source baseline: 7b27d09402f9656b0c606c131793310925936526 | Branch: task/0087-host-copy-address-corrections | PR base: task/production-host-ux-integration
Executor: Cursor local agent (composer, Kimi or GLM) | One scoped executor session

## 1. Objective

Remove address parsing and unnecessary host explanations. Deliver the owner's less-is-more correction without losing working features, drafts, legal data or filing safeguards.

## 2. Context

Read AGENTS.md, this brief, the correction plan and the preceding correction report only. This is the urgent corrective lane before 0072–0086. The [owner requirements](../plans/production-host-ux-corrections.md) supersede conflicting older optional-platform/parser/toggle instructions. Do not read or execute a blocked navigation brief.

Verified anchors: `apartment_form.html`: `text_field('address_line',`; `<details class="police-derived"`; `setup/address.html`: `{% if split_address %}`. `admin.py`: `def _apply_address_line_from_form`; `_apply_address_line_from_form(form, payload)`. `housebook.html`: `<details class="panel quiet housebook-legal" id="housebook-legal-details">`. `stay_fee_detail.html` links to `https://www.mojedatovaschranka.cz/`. The shared redirect helper already preserves fragments; do not alter it.

The source anchors describe current main before these tasks. Compare the reviewed predecessor diff first: a change intentionally made by a listed predecessor must be retained, not reverted to match an older anchor. If any other drift exists, stop with the precise difference. Record the actual base SHA and baseline failures before editing. No live provider/tenant data during verification.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/apartment_form.html` | edit | Scoped correction/test specified below |
| `App/app/templates/setup/address.html` | edit | Scoped correction/test specified below |
| `App/app/templates/housebook.html` | edit | Scoped correction/test specified below |
| `App/app/templates/guide.html` | edit | Scoped correction/test specified below |
| `App/app/templates/stay_fee_detail.html` | edit | Scoped correction/test specified below |
| `App/app/routes/admin.py` | edit | Scoped correction/test specified below |
| `App/app/routes/setup_wizard.py` | edit | Scoped correction/test specified below |
| `App/app/host_i18n.py` | edit | Scoped correction/test specified below |
| `App/tests/test_address_split.py` | edit | Scoped correction/test specified below |
| `App/tests/test_setup_wizard.py` | edit | Scoped correction/test specified below |
| `App/tests/test_host_property_controls_browser.py` | edit | Scoped correction/test specified below |
| `App/tests/test_host_copy_corrections.py` | create | Scoped correction/test specified below |
| `docs/tasks/0087-host-copy-address-corrections.md` | edit | Lifecycle only |
| `docs/tasks/0087-report.md` | create | Required report |
| `docs/tasks/0087-evidence/` | create | Synthetic screenshots/measurements only |

Read-only: docs/plans/production-host-ux-corrections.md; docs/plans/host-navigation-execution-protocol.md §§4–6; routed DESIGN/HOST_APP_DESIGN and UBYPORT_CORE/OPERATIONS/privacy sections when applicable; App/app/routes/admin_helpers.py; App/app/access.py; App/app/validation.py; App/app/templating.py; existing fixtures/conftest and directly referenced shared primitives. 0091 may inspect existing host templates/routes solely for the authorized read-only audit. No other file changes. New files apply only at the task which introduces them; later tasks edit them.

## 4. Steps

1. Restore structured addresses in the existing property editor: delete the address lede, address_line field, its warning loop, and the inner `property-address-police` details/summary/end tag. Retain the outer #address section and both grids of all seven addr_* fields verbatim. Preserve optional flags, maxlengths, normalization and validation. No new address defaults.
2. In setup/address.html delete the split_address branch from `{% if split_address %}` through its `{% else %}`, retaining the existing wizard-address-grid and removing the corresponding endif. Remove the preview label/preview element; retain scoped address save, drafts and errors. In setup_wizard.py remove the split_address context assignment. Keep legitimate reporting validation; one-line input must not return on a failed submission.
3. In admin.py delete `_apply_address_line_from_form` and its three call sites. Delete address-line mismatch query/context construction in the property GET, the two obsolete new-form context entries and the obsolete context keys in detail. In `_save_apartment_form`, replace `address_mismatch = _apply_address_line_from_form(form, payload)` with `address_mismatch = False` to retain the existing tuple return contract. Remove the mismatch append from apartment_update. Do not remove `_append_query_param` if used elsewhere. Leave standalone pure validation helpers alone unless their only tests referenced the deleted route helper: replace those tests with route-level regressions instead of disabling them.
4. Replace the complete ns.derived_open setup and police-derived details wrapper with these plain existing fields; keep fields and limits unchanged:

```jinja2
<div class="grid">
  {{ text_field('uby_mark', t('apartment.form.ubyport.mark_label'), apartment.uby_mark if editing else '', '', false, 6, none) }}
</div>
<div class="grid two">
  {{ text_field('uby_name', t('automation.facility_name'), apartment.uby_name if editing else '', '', false, 35, none) }}
  {{ text_field('uby_contact', t('automation.contact'), apartment.uby_contact if editing else '', '', true, 50) }}
</div>
```

Move the existing credential intro, sample PDF link and register-matching help together into contextual ? help headed “Where to find your credentials” / “Kde najdete přihlašovací údaje”, using the shared component introduced in 0093 (until then, move the help to Guide and link there without an accordion). Keep real field-specific errors visible. Remove password implementation/encryption narration from the normal helper; use “Leave blank to keep the saved password.” / “Pro zachování uloženého hesla nechte prázdné.” on edit and “Password from your police letter.” / “Heslo z dopisu od policie.” on create. Do not change `_apply_police_defaults`, facility validation or credential handling. In the property lock section remove only the second of the two consecutive identical /guide#door-codes links.
5. Replace both locale values of apartment.form.guest_message.default with the approved generic messages in the correction plan. Replace the textarea's value expression with:

```jinja2
{{ (apartment.guest_message or t('apartment.form.guest_message.default')) if editing else t('apartment.form.guest_message.default') }}
```

Create retains its existing blank-to-default fallback. A nonblank custom message survives exactly, including escaping and the 1000-character limit. Do not rewrite old nonblank default messages or guest records in bulk. New users see actual editable content, not only placeholder text.
6. Remove exactly this external shortcut from stay_fee_detail.html:

```jinja2
<a class="btn" href="https://www.mojedatovaschranka.cz/" target="_blank" rel="noopener">{{ t('stay_fees.send.open_databox') }}</a>
```

Retain request/report copy, recipient data, downloads and manual filing records. Do not remove a real police Send action. The owner's literal Czech send button is absent at this SHA: report that evidence boundary and any distinct deployed source; do not invent a replacement integration or claim an unlocated button was removed.
7. In housebook.html replace the header lede argument `t('housebook.lede')` with `''`. Replace the entire #housebook-legal-details disclosure with one small Help link to /guide#housebook (0093 standardizes it as a ?), using existing common Help translation if available. Move its existing body/paper/inspection/footnote paragraphs into the existing guide #housebook section, using each explanation once there; remove redundant equivalent paragraphs already in that destination. Keep the exact existing legal wording rather than interpreting retention rules. Leave the house book table, filters, export menu, archived list, receipt statuses and export content unchanged.
8. Add meaningful route/render regressions: structured values are stored unchanged; a contradictory legacy address_line is ignored; address-only save does not clear operator/controller/credentials/automation; new/edit/setup/error views contain no address_line input or derived summary; invalid address values still produce errors with draft values; new message is editable, custom message survives; house-book help anchor works in EN/CS without a legal-duty card; external data-box shortcut is absent and document exports still work. Keep existing validation and export tests. Capture synthetic changed-page screenshots.

Finish by comparing every changed file against §3 and writing §9. Do not automatically advance to the next task in the same session. Larger scoped edits above identify exact structures and invariants; small supplied replacements are mandatory. If the code required cannot be determined from these anchors without inventing business behavior, stop with an exact proposed diff instead of guessing.

## 5. Do not touch

No schema/migrations, dependencies, auth/access/CSRF policy, filing state machine, UbyPort SOAP, code lists, deadline computation, statutory field semantics, retention, signed records, issued invoice snapshots, TTLock/PIN lifecycle, live locks/feeds/emails/payments, public/guest design, workflow/deploy files or unrelated endpoints. No production/main push, merge or deploy. Required legal acceptance remains at its actual acceptance flow. This is presentation/default correction, not legal-policy revision.

## 6. Commands

Executor only; orchestrator does not run application tests. Use the existing Python/pinned-browser setup in the execution protocol. From App, run focused checks first:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_address_split.py tests/test_setup_wizard.py tests/test_host_property_controls_browser.py tests/test_host_copy_corrections.py -q -rs
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

- [ ] No address parsing in any reachable host form or save route. Fields are visible one by one. No derived-value narration or house-book legal accordion on the working page. Guest default is shown as editable content. Exports/filing preparation still work.
- [ ] All task-specific negative/draft/ownership/compatibility regressions in §4 pass; untouched settings and protected records survive.
- [ ] Actual browser evidence in EN/CS at 360/390/1280; geometry through 760/1024/1440/1680/1920/2048, expanded/collapsed sidebar, long labels and relevant error states. No visible obstruction/clipping; zero required-browser skips.
- [ ] No new schema/dependency/outbound call; fake/mocked integrations only; evidence contains fictional data and no token-bearing URLs/passwords/PINs.
- [ ] Current-head CI green, changed paths within §3, predecessor/candidate SHA and remaining audit findings recorded. Application change is not called deployed merely because a plan PR merged.

## 8. Stop and ask

Stop for unexplained source drift, foreign/archived access uncertainty, changing filing/legal semantics, an unlisted required file, missing browser prerequisites or a command that needs live providers/secrets/production. Send the exact blocker and proposed narrow correction. Do not reask approval for requirements already approved in chat. If baseline fails, isolate/report it; no test skips, assertion weakening, force push, main merge or deploy shortcut.

## 9. Report

Write docs/tasks/0087-report.md (max 1500 tokens), set Status: review. Include actual base/result SHA, file stat, test commands/last five output lines, counts/skips/coverage, §7 checkboxes, screenshot/measurement paths, source-vs-runtime audit boundary, deviations/unresolved defects and numbered owner steps. Do not claim production fixed or erase an open issue until reviewed application evidence exists.

## Risk list

Review the complete diff of every handler/template/default touched here, especially broad full-form payloads, negative validation, preservation of existing entity/controller/automation values and return paths. Read test fixtures for real provider calls and evidence for privacy leaks.

## Owner steps

1. Open a fresh Cursor chat and use the correction master prompt with this brief; its dependency must already be reviewed.
2. Review the report and actual CI on task/0087-host-copy-address-corrections; its PR targets task/production-host-ux-integration, never main.
3. After all corrections and outstanding audit fixes pass, review the exact tested candidate on staging with synthetic data.
4. Approve that candidate SHA before production promotion through the existing release protocol. Main currently triggers production deployment; do not merge early for a preview.
