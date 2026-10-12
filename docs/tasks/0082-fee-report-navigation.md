# 0082: Fee lists and report detail under the shared host layout

Status: blocked — depends on reviewed 0081; exact patch must be released against that integration revision.

Depends on: 0081 done | Source baseline: c4c8f979319e53341833065b2a8790c30159581f | Branch: task/0082-fee-report-navigation | PR base: task/host-navigation-integration

Patch status: pending — acceptance contract only; not executable until the orchestrator adds exact code/diffs and the reviewed base SHA.

Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Fee lists and report detail under the shared host layout. Deliver the approved design through one maintained implementation, preserving existing business behavior.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed prerequisite report/inventory. Designs are approved; do not repeat design approval. These verified source anchors document the starting contracts; the released exact patch must refresh any changed anchor against its actual predecessor.

`App/app/routes/stay_fees.py`:

```
@router.get("/stay-fees/{apartment_id}/pdf")
```

`App/app/routes/stay_fees.py`:

```
@router.post("/stay-fees/{apartment_id}/finalize")
```

## 3. Files

Explicit allowlist below. A partial introduced by an earlier task must already exist at the reviewed base. If a named path does not exist or another helper/file is needed, obtain a scope correction before editing.

| Path | Action | What |

|---|---|---|

| `App/app/templates/stay_fees.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/stay_fee_detail.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_components.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/host.css` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/host_i18n.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/tests/test_host_fee_navigation.py` | create | Named shared rendering or meaningful regression coverage |

| `docs/tasks/0082-fee-report-navigation.md` | edit | Lifecycle status only |

| `docs/tasks/0082-report.md` | create | Required report, 1500 tokens maximum |

| `docs/tasks/0082-evidence/` | create | Synthetic screenshots and measured evidence only |

Read-only source: the predecessor inventory/brief/report, relevant routes/guards identified by 0071, shared field/date/filter/account primitives already named in the plan, and the following tests/fixtures: `App/tests/test_stay_fee_list.py`, `App/tests/test_stay_fee_detail.py`, `App/tests/test_stay_fee_downloads.py`, `App/tests/test_stay_fee_finalize.py`, `App/tests/test_stay_fee_send_panel.py`, `App/tests/test_stay_fee_adjustment.py`, `App/tests/test_host_wide_geometry_browser.py`. No unrelated whole-repo audit.

## 4. Steps

1. Confirm prerequisite done, active task todo, Patch status ready, recorded reviewed base SHA and all exact anchors. Stop if any fails. This contract is not permission to design or improvise its missing code.

2. Apply the released exact patch only, then verify the following phase requirements in order:

3. Keep period-first list and current audited per-facility report unit. Not set up shows state/action instead of meaningless blank totals. Do not mix a different period report detail into the selected-period list.

4. Report detail prioritizes identity/period, calculated totals, actual blockers, PDF/CSV, council payment details and current protected guest fee decisions. Set up/Fix links go to 0077 canonical fee editor and return to the exact report period.

5. Preserve finalized snapshots, legal register fields, exemptions/reasons, adjustments and current manually recorded sent/paid facts. Payment details ready means an account/QR is available, not paid. No automatic bank/municipal claim.

6. Retain current protected download/export handlers and Invoice Companion PDF design. Align period/filter/results lanes and action geometry without modifying report data or calculations.

7. Check rate-off/incomplete/blocked/finalized/report-ready cases, long Czech council names/amounts, responsive cards and safe return links. No fee engine/backend edits.

8. Run §6, capture the actual changed pages with synthetic fixtures, compare every changed path with §3, write §9 and set review. Do not merge, deploy, advance to a blocked task or modify the next task.

## 5. Do not touch

Public/login/guest-facing designs, PDF/export content, filing state machine or live reporting, lock/PIN lifecycle, fee math/statutory rules, issued invoice snapshots, auth/retention/access policy, schema, dependencies, workflows/deploy files or arbitrary backend handlers. Only handlers explicitly in §3 may change, solely for the released presentation/ownership adapter patch. No production/main action. Never remove a unique control to match an abbreviated mockup.

## 6. Commands

Use the exact staging/mock/REQUIRE_BROWSER environment and setup from the execution protocol. From App, run these focused checks first:

```bash

.venv/bin/python -m pytest tests/test_stay_fee_list.py tests/test_stay_fee_detail.py tests/test_stay_fee_downloads.py tests/test_stay_fee_finalize.py tests/test_stay_fee_send_panel.py tests/test_stay_fee_adjustment.py tests/test_host_wide_geometry_browser.py -q -rs

```

Include the named new regression tests once created. Then run the protocol full suite with coverage >=86, ruff, and root context lint/diff checks. Required browser/geometry has 0 skips. Capture EN/CS at 360/390/1280 minimum and measure all specified wide/mobile sizes through 2048, collapsed/expanded rail. No guessed screenshot environment variables.

## 7. Acceptance

- [ ] List and detail show the same selected/audited period and facility scope; frozen data unchanged.

- [ ] Configuration links reach one editor and return to the same month; rate 0 remains optional.

- [ ] Actual protected PDF/CSV and guest decision/adjustment/finalization controls remain available with guards.

- [ ] Manual filing/payment markers are labelled truthfully, no copied configuration form on the report.

- [ ] Focused/full/CI checks pass at actual current head, coverage threshold retained, required browser/geometry 0 skips.

- [ ] Synthetic screenshots and measured action/lane/focus evidence linked; no real credentials/guest/operator data.

- [ ] Changed paths exactly §3; no new dependency/schema or unapproved domain behavior.

## 8. Stop and ask

Stop/report if the patch is pending, predecessor/anchor/base differs, source path missing, scope needs another file, contract conflicts with current audited behavior, dependency/new provider is needed, a required check skips or fails, or the same test fails twice. Orchestrator issues an exact correction; executor does not guess, weaken tests or deploy. This gate is source correctness, not repeated design approval.

## 9. Report

Create `docs/tasks/0082-report.md` (<=1500 tokens): starting/ending SHA, file/diff stat, exact commands/results including failures/skips, §7 evidence, synthetic screenshot/geometry links, deviations/risks and owner steps. Set this brief review or blocked with the reason; link full logs instead of dumping them. PR targets integration only.

## Risk list (for the reviewer)

Read all changed templates/handlers/shared assets plus the new regression coverage; inspect current-head CI and the behavioral invariants above. Extra paths or evidence tied to a different commit require a correction brief.

## Owner steps

1. Review the report and actual current-head CI/diff scope.

2. Confirm task PR base is task/host-navigation-integration before guarded merge.

3. Have the orchestrator review/release the next exact patch; remain off main until staging acceptance and explicit production promotion approval.
