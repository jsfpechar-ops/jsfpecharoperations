# 0088: Require an operator and remove the property active switch

Status: todo
Depends on: 0087 reviewed on the correction integration branch | Initial source baseline: 7b27d09402f9656b0c606c131793310925936526 | Branch: task/0088-property-operator-defaults | PR base: task/production-host-ux-integration
Executor: Cursor local agent (composer, Kimi or GLM) | One scoped executor session

## 1. Objective

Require an operator and remove the property active switch. Deliver the owner's less-is-more correction without losing working features, drafts, legal data or filing safeguards.

## 2. Context

Read AGENTS.md, this brief, the correction plan and the preceding correction report only. This is the urgent corrective lane before 0072–0086. The [owner requirements](../plans/production-host-ux-corrections.md) supersede conflicting older optional-platform/parser/toggle instructions. Do not read or execute a blocked navigation brief.

Anchors in admin.py: `payload["active"] = 1 if form.get("active") else 0`; `if payload["legal_entity_id"] and not access.entity`; `_save_apartment_form`. apartment_form.html renders hidden name=legal_entity_id plus legal_entity_id_select for one-entity create; offers common.none. setup_wizard.py inserts a name-only property. `data_controller_entity_id=None` is the existing representation for the operator being controller; retain it.

The source anchors describe current main before these tasks. Compare the reviewed predecessor diff first: a change intentionally made by a listed predecessor must be retained, not reverted to match an older anchor. If any other drift exists, stop with the precise difference. Record the actual base SHA and baseline failures before editing. No live provider/tenant data during verification.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | Scoped correction/test specified below |
| `App/app/routes/setup_wizard.py` | edit | Scoped correction/test specified below |
| `App/app/templates/apartment_form.html` | edit | Scoped correction/test specified below |
| `App/app/templates/setup/name.html` | edit | Scoped correction/test specified below |
| `App/app/templates/_property_operator.html` | create | Scoped correction/test specified below |
| `App/app/host_i18n.py` | edit | Scoped correction/test specified below |
| `App/tests/test_setup_wizard.py` | edit | Scoped correction/test specified below |
| `App/tests/test_property_operator_defaults.py` | create | Scoped correction/test specified below |
| `App/tests/test_host_property_controls_browser.py` | edit | Scoped correction/test specified below |
| `docs/tasks/0088-property-operator-defaults.md` | edit | Lifecycle only |
| `docs/tasks/0088-report.md` | create | Required report |
| `docs/tasks/0088-evidence/` | create | Synthetic screenshots/measurements only |

Read-only: docs/plans/production-host-ux-corrections.md; docs/plans/host-navigation-execution-protocol.md §§4–6; routed DESIGN/HOST_APP_DESIGN and UBYPORT_CORE/OPERATIONS/privacy sections when applicable; App/app/routes/admin_helpers.py; App/app/access.py; App/app/validation.py; App/app/templating.py; existing fixtures/conftest and directly referenced shared primitives. 0091 may inspect existing host templates/routes solely for the authorized read-only audit. No other file changes. New files apply only at the task which introduces them; later tasks edit them.

## 4. Steps

1. Add one shared operator field partial, reused by property create/edit and the temporary wizard name page. One successful legal_entity_id control per form. For one accessible non-archived entity select it automatically; for many preserve a valid existing/copy-selected entity, otherwise show disabled empty “Choose operator” / “Vyberte provozovatele” and require selection. Never offer a selectable empty `(none)`. With zero entities, show “Add business details” / “Přidat firemní údaje”, link to /entities, and prevent property submission with a visible explanation “Add an operator to continue.” / “Nejprve přidejte provozovatele.” Preserve the draft on that detour, without putting contact/passwords in URLs or browser persistent storage. Reuse existing copy context; do not silently choose the first of several entities. The partial includes no form tag or duplicated hidden field.
2. Replace the active mapping with `payload["active"] = 1`; remove the active checkbox and label from apartment_form.html and redundant hidden active controls in onboarding. In `_save_apartment_form`, immediately after loading the existing authorized apartment and creating its payload, set `payload["active"] = 0 if apartment["archived_at"] else 1`. This keeps archived edits inactive and ordinary non-archived saves active. Keep explicit archive/unarchive handlers unchanged; reject archived property creation/copy assignment where existing guards require it. No worker rewrite, SQL migration or mass active=1 update. Omitted, 0, false, and forged active values cannot disable a normal property. Existing Manual/Scheduled/Immediate mode and hours are unaffected.
3. Add a narrow server helper in admin.py after the form parsing helpers:

```python
def _valid_property_operator(request: Request, entity_id: Optional[int]) -> bool:
    if not entity_id:
        return False
    entity = access.entity(request, entity_id)
    return bool(entity and not entity["archived_at"])
```

Before any apartment insert/update in apartment_create, `_save_apartment_form`, and wizard name creation, require that helper to return true. Missing, malformed, archived and foreign operator IDs fail before writes/default application. Do not infer the owner itself is an operator. Translate error keys in both locales; render the submitted form values on errors rather than redirecting to a blank form. Retain full authorization/CSRF/name validation. Full-form saved-credentials/test-connection paths use the same required-operator check; address-only helpers remain scoped and must not require nonexistent full-form controls. A legacy property with no operator stays readable but must choose one before a full save.
4. Remove the same-controller checkbox and its recommendation from the main form. By default submit/resolve data_controller_entity_id=None and use the assigned operator through the existing controller/contact resolution. Keep one ordinary visible selector in property settings for a genuinely different existing controller (default “Same as operator”); do not put it under More options or a chevron, preserving its ID on an ordinary save. Do not overwrite legitimate overrides, add separate POC fields, or detach the guest contact from existing canonical operator resolution. A submitted alternate ID must pass owner/non-archived checks. A no-JS submission must preserve an existing override; hiding a control is not permission to clear it. If the owner explicitly clears an override, None means use the operator. Copy-from-property may preserve an explicitly selected override; ordinary new create defaults to None.
5. Add entities and selection context to the wizard name rendering, including error renders. Both create routes must require the same operator rule and produce the same controller/activity defaults. Keep all old route names until 0092 replaces their presentation; do not create a second entity store.
6. Regressions cover zero/one/many entities; exactly one successful operator control; missing/foreign/malformed/archived IDs; forged active=0; new active=1; archived saves remain inactive; archive/restore; preserved reporting mode and controller override; new default operator/controller/contact resolution; no-JS submission. Add route tests proving rejection causes no row or secret write. Update old wizard test expectations that explicitly allowed name-only creation.

Finish by comparing every changed file against §3 and writing §9. Do not automatically advance to the next task in the same session. Larger scoped edits above identify exact structures and invariants; small supplied replacements are mandatory. If the code required cannot be determined from these anchors without inventing business behavior, stop with an exact proposed diff instead of guessing.

## 5. Do not touch

No schema/migrations, dependencies, auth/access/CSRF policy, filing state machine, UbyPort SOAP, code lists, deadline computation, statutory field semantics, retention, signed records, issued invoice snapshots, TTLock/PIN lifecycle, live locks/feeds/emails/payments, public/guest design, workflow/deploy files or unrelated endpoints. No production/main push, merge or deploy. Required legal acceptance remains at its actual acceptance flow. This is presentation/default correction, not legal-policy revision.

## 6. Commands

Executor only; orchestrator does not run application tests. Use the existing Python/pinned-browser setup in the execution protocol. From App, run focused checks first:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_property_operator_defaults.py tests/test_setup_wizard.py tests/test_host_property_controls_browser.py -q -rs
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

- [ ] No property can be created/full-saved without an authorized non-archived operator. No active switch exists. Operator is the default controller/contact; existing overrides survive. Archived properties remain inactive.
- [ ] All task-specific negative/draft/ownership/compatibility regressions in §4 pass; untouched settings and protected records survive.
- [ ] Actual browser evidence in EN/CS at 360/390/1280; geometry through 760/1024/1440/1680/1920/2048, expanded/collapsed sidebar, long labels and relevant error states. No visible obstruction/clipping; zero required-browser skips.
- [ ] No new schema/dependency/outbound call; fake/mocked integrations only; evidence contains fictional data and no token-bearing URLs/passwords/PINs.
- [ ] Current-head CI green, changed paths within §3, predecessor/candidate SHA and remaining audit findings recorded. Application change is not called deployed merely because a plan PR merged.

## 8. Stop and ask

Stop for unexplained source drift, foreign/archived access uncertainty, changing filing/legal semantics, an unlisted required file, missing browser prerequisites or a command that needs live providers/secrets/production. Send the exact blocker and proposed narrow correction. Do not reask approval for requirements already approved in chat. If baseline fails, isolate/report it; no test skips, assertion weakening, force push, main merge or deploy shortcut.

## 9. Report

Write docs/tasks/0088-report.md (max 1500 tokens), set Status: review. Include actual base/result SHA, file stat, test commands/last five output lines, counts/skips/coverage, §7 checkboxes, screenshot/measurement paths, source-vs-runtime audit boundary, deviations/unresolved defects and numbered owner steps. Do not claim production fixed or erase an open issue until reviewed application evidence exists.

## Risk list

Review the complete diff of every handler/template/default touched here, especially broad full-form payloads, negative validation, preservation of existing entity/controller/automation values and return paths. Read test fixtures for real provider calls and evidence for privacy leaks.

## Owner steps

1. Open a fresh Cursor chat and use the correction master prompt with this brief; its dependency must already be reviewed.
2. Review the report and actual CI on task/0088-property-operator-defaults; its PR targets task/production-host-ux-integration, never main.
3. After all corrections and outstanding audit fixes pass, review the exact tested candidate on staging with synthetic data.
4. Approve that candidate SHA before production promotion through the existing release protocol. Main currently triggers production deployment; do not merge early for a preview.
