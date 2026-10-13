# 0081: Invoice navigation and canonical configuration

Status: todo — combined staging lane, run in the order and mode of [the combined plan](../plans/host-ux-combined-staging.md) §2–§3.

Depends on: 0080 done | Source baseline: c4c8f979319e53341833065b2a8790c30159581f | Branch: task/0081-invoice-navigation | PR base: task/production-host-ux-integration

Patch status: lifted 2026-10-13 — implement against the current integration branch per the combined plan §2.

Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Invoice navigation and canonical configuration. Deliver the approved design through one maintained implementation, preserving existing business behavior.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed prerequisite report/inventory. Designs are approved; do not repeat design approval. These verified source anchors document the starting contracts; the released exact patch must refresh any changed anchor against its actual predecessor.

`App/app/routes/invoices.py`:

```
    raw_stay = request.query_params.get("reservation_id")
```

`App/app/routes/invoices.py`:

```
    active = invoices.active_invoice_for_stay(reservation_id)
```

## 3. Files

Explicit allowlist below. A partial introduced by an earlier task must already exist at the reviewed base. If a named path does not exist or another helper/file is needed, obtain a scope correction before editing.

| Path | Action | What |

|---|---|---|

| `App/app/templates/invoices.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/invoice_stay_picker.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/invoice_form.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/invoice_detail.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_host_navigation.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_components.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/host.css` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/host_i18n.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/tests/test_host_invoice_navigation.py` | create | Named shared rendering or meaningful regression coverage |

| `docs/tasks/0081-invoice-navigation.md` | edit | Lifecycle status only |

| `docs/tasks/0081-report.md` | create | Required report, 1500 tokens maximum |

| `docs/tasks/0081-evidence/` | create | Synthetic screenshots and measured evidence only |

Read-only source: the predecessor inventory/brief/report, relevant routes/guards identified by 0071, shared field/date/filter/account primitives already named in the plan, and the following tests/fixtures: `App/tests/test_invoice_stay_rules.py`, `App/tests/test_invoice_stay_pages.py`, `App/tests/test_invoice_stay_browser.py`, `App/tests/test_invoice_settings.py`, `App/tests/test_invoice_immutability.py`, `App/tests/test_invoice_numbering.py`, `App/tests/test_invoice_vat.py`, `App/tests/test_host_invoice_items_browser.py`. No unrelated whole-repo audit.

## 4. Steps

1. Confirm prerequisite done, active task todo, Patch status ready, recorded reviewed base SHA and all exact anchors. Stop if any fails. This contract is not permission to design or improvise its missing code.

2. Apply the released exact patch only, then verify the following phase requirements in order:

3. Retain searchable/filterable invoice list, period controls, Generate invoice, direct PDF and the canonical entity Invoice details link. Show existing manually recorded payment facts accurately; no bank-derived Unpaid inference.

4. Creation remains stay-linked: existing selector, eligibility, correct assigned entity and existing-invoice recovery. Preserve typed builder data on 422/ARES/preview and safe configuration-return context.

5. Keep the owner-selected invoice item grid, aligned Quantity/Unit/Unit price, optional Cleaning unit and custom Description only for Other. Do not replace it with a new card-based builder.

6. Detail keeps actual download/send/record-payment/cancel-correct capabilities and restrictions. No changes to numbering, amounts, rounding, VAT, issued snapshot, signatures, PDFs or emails.

7. Verify switching entity configuration and returning to the builder retains correct stay/entity and all fields. No duplicate business/account/VAT editor embedded in invoice form.

8. Run §6, capture the actual changed pages with synthetic fixtures, compare every changed path with §3, write §9 and set review. Do not merge, deploy, advance to a blocked task or modify the next task.

## 5. Do not touch

Public/login/guest-facing designs, PDF/export content, filing state machine or live reporting, lock/PIN lifecycle, fee math/statutory rules, issued invoice snapshots, auth/retention/access policy, schema, dependencies, workflows/deploy files or arbitrary backend handlers. Only handlers explicitly in §3 may change, solely for the released presentation/ownership adapter patch. No production/main action. Never remove a unique control to match an abbreviated mockup.

## 6. Commands

Use the exact staging/mock/REQUIRE_BROWSER environment and setup from the execution protocol. From App, run these focused checks first:

```bash

.venv/bin/python -m pytest tests/test_invoice_stay_rules.py tests/test_invoice_stay_pages.py tests/test_invoice_stay_browser.py tests/test_invoice_settings.py tests/test_invoice_immutability.py tests/test_invoice_numbering.py tests/test_invoice_vat.py tests/test_host_invoice_items_browser.py -q -rs

```

Include the named new regression tests once created. Then run the protocol full suite with coverage >=86, ruff, and root context lint/diff checks. Required browser/geometry has 0 skips. Capture EN/CS at 360/390/1280 minimum and measure all specified wide/mobile sizes through 2048, collapsed/expanded rail. No guessed screenshot environment variables.

## 7. Acceptance

- [ ] Invoice list/PDF/settings links work in EN/CS/mobile; configuration resolves to the same entity editor.

- [ ] New invoice needs an eligible stay and has current existing-invoice protection; no generic standalone creation.

- [ ] 422/preview/ARES and return navigation retain values; row/item controls align and do not clip.

- [ ] Issued bytes/data/numbering/VAT/manual payment rules unchanged.

- [ ] Focused/full/CI checks pass at actual current head, coverage threshold retained, required browser/geometry 0 skips.

- [ ] Synthetic screenshots and measured action/lane/focus evidence linked; no real credentials/guest/operator data.

- [ ] Changed paths exactly §3; no new dependency/schema or unapproved domain behavior.

## 8. Stop and ask

Stop/report if the patch is pending, predecessor/anchor/base differs, source path missing, scope needs another file, contract conflicts with current audited behavior, dependency/new provider is needed, a required check skips or fails, or the same test fails twice. Orchestrator issues an exact correction; executor does not guess, weaken tests or deploy. This gate is source correctness, not repeated design approval.

## 9. Report

Create `docs/tasks/0081-report.md` (<=1500 tokens): starting/ending SHA, file/diff stat, exact commands/results including failures/skips, §7 evidence, synthetic screenshot/geometry links, deviations/risks and owner steps. Set this brief review or blocked with the reason; link full logs instead of dumping them. PR targets integration only.

## Risk list (for the reviewer)

Read all changed templates/handlers/shared assets plus the new regression coverage; inspect current-head CI and the behavioral invariants above. Extra paths or evidence tied to a different commit require a correction brief.

## Owner steps

1. Review the report and actual current-head CI/diff scope.

2. Confirm task PR base is task/host-navigation-integration before guarded merge.

3. Have the orchestrator review/release the next exact patch; remain off main until staging acceptance and explicit production promotion approval.
