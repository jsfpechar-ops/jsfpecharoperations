# 0075: Shared business and invoice field ownership

Status: blocked — depends on reviewed 0094; exact patch must be released against that integration revision.

Depends on: 0094 reviewed | Source baseline: c4c8f979319e53341833065b2a8790c30159581f | Branch: task/0075-shared-entity-fields | PR base: task/production-host-ux-integration

Patch status: pending — rebase against reviewed 0094/correction predecessors and release the exact patch; acceptance contract only; not executable until the orchestrator adds exact code/diffs and the reviewed base SHA.

Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Shared business and invoice field ownership. Deliver the approved design through one maintained implementation, preserving existing business behavior.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed prerequisite report/inventory. Designs are approved; do not repeat design approval. These verified source anchors document the starting contracts; the released exact patch must refresh any changed anchor against its actual predecessor.

`App/app/templates/entities.html`:

```
{% macro operator_fields(prefix, entity) %}
```

`App/app/routes/invoices.py`:

```
    """Presence-checked invoice details: sent = update (blank clears), absent = keep."""
```

## 3. Files

Explicit allowlist below. A partial introduced by an earlier task must already exist at the reviewed base. If a named path does not exist or another helper/file is needed, obtain a scope correction before editing.

| Path | Action | What |

|---|---|---|

| `App/app/templates/entities.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/invoice_settings.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/admin.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/invoices.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/host_i18n.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_entity_business_fields.html` | create | Named shared rendering or meaningful regression coverage |

| `App/app/templates/_entity_invoice_fields.html` | create | Named shared rendering or meaningful regression coverage |

| `App/tests/test_entity_editor_fields.py` | create | Named shared rendering or meaningful regression coverage |

| `docs/tasks/0075-shared-entity-fields.md` | edit | Lifecycle status only |

| `docs/tasks/0075-report.md` | create | Required report, 1500 tokens maximum |

| `docs/tasks/0075-evidence/` | create | Synthetic screenshots and measured evidence only |

Read-only source: the predecessor inventory/brief/report, relevant routes/guards identified by 0071, shared field/date/filter/account primitives already named in the plan, and the following tests/fixtures: `App/tests/test_invoice_settings.py`, `App/tests/test_invoice_entity.py`, `App/tests/test_invoice_immutability.py`, `App/tests/test_invoice_numbering.py`, `App/tests/test_invoice_vat.py`, `App/tests/test_ares.py`, `App/tests/test_host_property_controls_browser.py`. No unrelated whole-repo audit.

## 4. Steps

1. Confirm prerequisite done, active task todo, Patch status ready, recorded reviewed base SHA and all exact anchors. Stop if any fails. This contract is not permission to design or improvise its missing code.

2. Apply the released exact patch only, then verify the following phase requirements in order:

3. Use the 0071 field-by-field matrix, not a generic entity field list. Separate business identity/contact/signature fields from invoice defaults; shared registration/VAT/account representations get one authoritative field markup/normalization definition with explicit context.

4. Extract current business create/edit and invoice fields into named Jinja partials while preserving input names, prefixes, types, requiredness, file upload encoding and action targets. Do not assume creating an entity and saving invoice defaults require identical payloads.

5. Preserve click-only ARES fetch, actual copied registry values, stale/error rerender, existing request limit/cache and returned VAT facts. No new outbound request, dependency or automatic register lookup.

6. Consolidate overlapping normalization only after equivalence tests cover absent versus blank, bank prefix/number/bank, IBAN-only preservation, explicit BIC versus derived BIC, VAT modes, invoice prefix/year/number/due days and signature lifecycle. If handlers differ intentionally, share helpers with explicit policy rather than erase the difference.

7. Do not redirect entry URLs yet; prove shared field rendering/update behavior before the canonical entity navigation in 0076. Never mutate issued invoice snapshots or numbering history.

8. Run §6, capture the actual changed pages with synthetic fixtures, compare every changed path with §3, write §9 and set review. Do not merge, deploy, advance to a blocked task or modify the next task.

## 5. Do not touch

Public/login/guest-facing designs, PDF/export content, filing state machine or live reporting, lock/PIN lifecycle, fee math/statutory rules, issued invoice snapshots, auth/retention/access policy, schema, dependencies, workflows/deploy files or arbitrary backend handlers. Only handlers explicitly in §3 may change, solely for the released presentation/ownership adapter patch. No production/main action. Never remove a unique control to match an abbreviated mockup.

## 6. Commands

Use the exact staging/mock/REQUIRE_BROWSER environment and setup from the execution protocol. From App, run these focused checks first:

```bash

.venv/bin/python -m pytest tests/test_invoice_settings.py tests/test_invoice_entity.py tests/test_invoice_immutability.py tests/test_invoice_numbering.py tests/test_invoice_vat.py tests/test_ares.py tests/test_host_property_controls_browser.py -q -rs

```

Include the named new regression tests once created. Then run the protocol full suite with coverage >=86, ruff, and root context lint/diff checks. Required browser/geometry has 0 skips. Capture EN/CS at 360/390/1280 minimum and measure all specified wide/mobile sizes through 2048, collapsed/expanded rail. No guessed screenshot environment variables.

## 7. Acceptance

- [ ] Every shared editable field has one canonical rendering/validation owner, with create/edit context explicit.

- [ ] Identity/contact/signature saves preserve omitted invoice defaults; invoice-default saves preserve business identity/contact/signatures.

- [ ] ARES and invalid account rerenders retain typed values and actual errors; VAT/account/prefix behavior and issued snapshots unchanged.

- [ ] No broad legal_entity overwrite, new dependency, unguarded cross-owner entity access or hidden second editor definition.

- [ ] Focused/full/CI checks pass at actual current head, coverage threshold retained, required browser/geometry 0 skips.

- [ ] Synthetic screenshots and measured action/lane/focus evidence linked; no real credentials/guest/operator data.

- [ ] Changed paths exactly §3; no new dependency/schema or unapproved domain behavior.

## 8. Stop and ask

Stop/report if the patch is pending, predecessor/anchor/base differs, source path missing, scope needs another file, contract conflicts with current audited behavior, dependency/new provider is needed, a required check skips or fails, or the same test fails twice. Orchestrator issues an exact correction; executor does not guess, weaken tests or deploy. This gate is source correctness, not repeated design approval.

## 9. Report

Create `docs/tasks/0075-report.md` (<=1500 tokens): starting/ending SHA, file/diff stat, exact commands/results including failures/skips, §7 evidence, synthetic screenshot/geometry links, deviations/risks and owner steps. Set this brief review or blocked with the reason; link full logs instead of dumping them. PR targets integration only.

## Risk list (for the reviewer)

Read all changed templates/handlers/shared assets plus the new regression coverage; inspect current-head CI and the behavioral invariants above. Extra paths or evidence tied to a different commit require a correction brief.

## Owner steps

1. Review the report and actual current-head CI/diff scope.

2. Confirm task PR base is task/host-navigation-integration before guarded merge.

3. Have the orchestrator review/release the next exact patch; remain off main until staging acceptance and explicit production promotion approval.
