# 0076: One business editor with invoice details

Status: blocked — depends on reviewed 0075; exact patch must be released against that integration revision.

Depends on: 0075 done | Source baseline: c4c8f979319e53341833065b2a8790c30159581f | Branch: task/0076-canonical-entity-navigation | PR base: task/host-navigation-integration

Patch status: pending — acceptance contract only; not executable until the orchestrator adds exact code/diffs and the reviewed base SHA.

Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

One business editor with invoice details. Deliver the approved design through one maintained implementation, preserving existing business behavior.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed prerequisite report/inventory. Designs are approved; do not repeat design approval. These verified source anchors document the starting contracts; the released exact patch must refresh any changed anchor against its actual predecessor.

`App/app/routes/invoices.py`:

```
@router.get("/invoices/settings")
```

`App/app/routes/invoices.py`:

```
@router.post("/invoices/settings")
```

`App/app/templates/entities.html`:

```
  <form method="post" action="/entities/{{ edit_entity.id }}" enctype="multipart/form-data">
```

## 3. Files

Explicit allowlist below. A partial introduced by an earlier task must already exist at the reviewed base. If a named path does not exist or another helper/file is needed, obtain a scope correction before editing.

| Path | Action | What |

|---|---|---|

| `App/app/templates/entities.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/invoice_settings.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/invoice_form.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/apartments.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/apartment_form.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/settings.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_host_navigation.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_components.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/admin.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/invoices.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/api.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/host.css` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/app.js` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/host_i18n.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/tests/test_entity_editor_navigation.py` | create | Named shared rendering or meaningful regression coverage |

| `docs/tasks/0076-canonical-entity-navigation.md` | edit | Lifecycle status only |

| `docs/tasks/0076-report.md` | create | Required report, 1500 tokens maximum |

| `docs/tasks/0076-evidence/` | create | Synthetic screenshots and measured evidence only |

Read-only source: the predecessor inventory/brief/report, relevant routes/guards identified by 0071, shared field/date/filter/account primitives already named in the plan, and the following tests/fixtures: `App/tests/test_invoice_settings.py`, `App/tests/test_invoice_entity.py`, `App/tests/test_invoice_immutability.py`, `App/tests/test_invoice_autofill.py`, `App/tests/test_ares.py`, `App/tests/test_host_property_controls_browser.py`, `App/tests/test_host_wide_geometry_browser.py`. No unrelated whole-repo audit.

## 4. Steps

1. Confirm prerequisite done, active task todo, Patch status ready, recorded reviewed base SHA and all exact anchors. Stop if any fails. This contract is not permission to design or improvise its missing code.

2. Apply the released exact patch only, then verify the following phase requirements in order:

3. Present one entity editor based on /entities?edit={id}, with Business details and Invoice details sections. Show assigned entity/linked properties context without inventing a per-property business record. Selecting a different operator remains a property relationship operation.

4. Render 0075 partials once. Preserve required business context for create/edit and all invoice defaults. Do not hide Edit/Invoice settings/More actions on the entity list; unavailable Delete retains its explanation/guard.

5. Route property business cards, Properties, Settings and invoice supplier/details links to the correct shared record/section. Preserve original invoice/stay/property return and safe-local-path validation, including multi-entity selection and no-entity recovery.

6. Keep legacy GET /invoices/settings as a canonical redirect/adapter selecting the correct entity. Keep authenticated legacy POST as a compatibility delegate to the same save/validation/rerender implementation, not a redirect that silently drops submitted data. Avoid cyclic imports between routers; release the shared helper structure in the exact patch.

7. Preserve dirty business/invoice drafts and failed ARES/account validation. Successful business changes update linked live views and future drafts, while issued invoices remain immutable. No GET mutation or template-only authorization.

8. Run §6, capture the actual changed pages with synthetic fixtures, compare every changed path with §3, write §9 and set review. Do not merge, deploy, advance to a blocked task or modify the next task.

## 5. Do not touch

Public/login/guest-facing designs, PDF/export content, filing state machine or live reporting, lock/PIN lifecycle, fee math/statutory rules, issued invoice snapshots, auth/retention/access policy, schema, dependencies, workflows/deploy files or arbitrary backend handlers. Only handlers explicitly in §3 may change, solely for the released presentation/ownership adapter patch. No production/main action. Never remove a unique control to match an abbreviated mockup.

## 6. Commands

Use the exact staging/mock/REQUIRE_BROWSER environment and setup from the execution protocol. From App, run these focused checks first:

```bash

.venv/bin/python -m pytest tests/test_invoice_settings.py tests/test_invoice_entity.py tests/test_invoice_immutability.py tests/test_invoice_autofill.py tests/test_ares.py tests/test_host_property_controls_browser.py tests/test_host_wide_geometry_browser.py -q -rs

```

Include the named new regression tests once created. Then run the protocol full suite with coverage >=86, ruff, and root context lint/diff checks. Required browser/geometry has 0 skips. Capture EN/CS at 360/390/1280 minimum and measure all specified wide/mobile sizes through 2048, collapsed/expanded rail. No guessed screenshot environment variables.

## 7. Acceptance

- [ ] One edit destination and one shared implementation reached through every business/invoice settings link.

- [ ] Correct entity, safe next destination, legacy GET/POST behavior and 422/error values retained.

- [ ] Two properties sharing one entity reflect a new business contact; historical issued invoice PDF/data remains identical.

- [ ] Cross-owner forged entity ID and external return URL rejected; list actions and signatures preserved.

- [ ] Focused/full/CI checks pass at actual current head, coverage threshold retained, required browser/geometry 0 skips.

- [ ] Synthetic screenshots and measured action/lane/focus evidence linked; no real credentials/guest/operator data.

- [ ] Changed paths exactly §3; no new dependency/schema or unapproved domain behavior.

## 8. Stop and ask

Stop/report if the patch is pending, predecessor/anchor/base differs, source path missing, scope needs another file, contract conflicts with current audited behavior, dependency/new provider is needed, a required check skips or fails, or the same test fails twice. Orchestrator issues an exact correction; executor does not guess, weaken tests or deploy. This gate is source correctness, not repeated design approval.

## 9. Report

Create `docs/tasks/0076-report.md` (<=1500 tokens): starting/ending SHA, file/diff stat, exact commands/results including failures/skips, §7 evidence, synthetic screenshot/geometry links, deviations/risks and owner steps. Set this brief review or blocked with the reason; link full logs instead of dumping them. PR targets integration only.

## Risk list (for the reviewer)

Read all changed templates/handlers/shared assets plus the new regression coverage; inspect current-head CI and the behavioral invariants above. Extra paths or evidence tied to a different commit require a correction brief.

## Owner steps

1. Review the report and actual current-head CI/diff scope.

2. Confirm task PR base is task/host-navigation-integration before guarded merge.

3. Have the orchestrator review/release the next exact patch; remain off main until staging acceptance and explicit production promotion approval.
