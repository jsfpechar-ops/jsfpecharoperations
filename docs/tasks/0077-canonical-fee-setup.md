# 0077: Canonical fee setup and compatibility adapters

Status: todo — combined staging lane, run in the order and mode of [the combined plan](../plans/host-ux-combined-staging.md) §2–§3.

Depends on: 0076 done | Source baseline: c4c8f979319e53341833065b2a8790c30159581f | Branch: task/0077-canonical-fee-setup | PR base: task/production-host-ux-integration

Patch status: lifted 2026-10-13 — implement against the current integration branch per the combined plan §2.

Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Canonical fee setup and compatibility adapters. Deliver the approved design through one maintained implementation, preserving existing business behavior.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed prerequisite report/inventory. Designs are approved; do not repeat design approval. These verified source anchors document the starting contracts; the released exact patch must refresh any changed anchor against its actual predecessor.

`App/app/routes/stay_fees.py`:

```
def _fee_values(form) -> dict:
```

`App/app/templates/stay_fee_setup.html`:

```
  {% include "_stay_fee_fields.html" %}
```

`App/app/routes/stay_fees.py`:

```
@router.post("/stay-fees/{apartment_id}/setup")
```

## 3. Files

Explicit allowlist below. A partial introduced by an earlier task must already exist at the reviewed base. If a named path does not exist or another helper/file is needed, obtain a scope correction before editing.

| Path | Action | What |

|---|---|---|

| `App/app/templates/_stay_fee_fields.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/stay_fee_setup.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_property_settings_form.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/stay_fees.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/stay_fee_detail.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/admin.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/stay_fees.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/host_i18n.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/tests/test_fee_setup_compatibility.py` | create | Named shared rendering or meaningful regression coverage |

| `docs/tasks/0077-canonical-fee-setup.md` | edit | Lifecycle status only |

| `docs/tasks/0077-report.md` | create | Required report, 1500 tokens maximum |

| `docs/tasks/0077-evidence/` | create | Synthetic screenshots and measured evidence only |

Read-only source: the predecessor inventory/brief/report, relevant routes/guards identified by 0071, shared field/date/filter/account primitives already named in the plan, and the following tests/fixtures: `App/tests/test_stay_fee_property_panel.py`, `App/tests/test_stay_fee.py`, `App/tests/test_stay_fee_detail.py`, `App/tests/test_stay_fee_finalize.py`, `App/tests/test_stay_fee_downloads.py`, `App/tests/test_copy_property_settings.py`. No unrelated whole-repo audit.

## 4. Steps

1. Confirm prerequisite done, active task todo, Patch status ready, recorded reviewed base SHA and all exact anchors. Stop if any fails. This contract is not permission to design or improvise its missing code.

2. Apply the released exact patch only, then verify the following phase requirements in order:

3. Keep fee configuration in property Settings -> Reporting & fees -> Stay fee. All Set up/Fix links target that same editor with a validated return to the exact prior period/report/filter context.

4. Keep _stay_fee_fields.html as the authoritative field markup, including bank/account partials and copy-from-property behavior. Do not copy fields into a report or a second fee page.

5. Compare and explicitly preserve current _fee_values/property normalization semantics before factoring helpers: omitted fields keep, explicit blank clears where already defined, invalid account saves nothing, IBAN-only existing account survives unrelated saves, rate clamping and cadence/symbol rules remain identical.

6. Legacy GET setup becomes a guarded canonical link/redirect; legacy POST uses the same scoped fee save implementation and rerender context. It must not call the broad property saver with only fee fields. No unrelated credentials/timing/operator/lock update.

7. Retain rate 0 as optional/off, feature eligibility, archive/access checks, council metadata and original month after save/error. No report calculation, finalized snapshot, payment marker or exemption-policy edit.

8. Run §6, capture the actual changed pages with synthetic fixtures, compare every changed path with §3, write §9 and set review. Do not merge, deploy, advance to a blocked task or modify the next task.

## 5. Do not touch

Public/login/guest-facing designs, PDF/export content, filing state machine or live reporting, lock/PIN lifecycle, fee math/statutory rules, issued invoice snapshots, auth/retention/access policy, schema, dependencies, workflows/deploy files or arbitrary backend handlers. Only handlers explicitly in §3 may change, solely for the released presentation/ownership adapter patch. No production/main action. Never remove a unique control to match an abbreviated mockup.

## 6. Commands

Use the exact staging/mock/REQUIRE_BROWSER environment and setup from the execution protocol. From App, run these focused checks first:

```bash

.venv/bin/python -m pytest tests/test_stay_fee_property_panel.py tests/test_stay_fee.py tests/test_stay_fee_detail.py tests/test_stay_fee_finalize.py tests/test_stay_fee_downloads.py tests/test_copy_property_settings.py -q -rs

```

Include the named new regression tests once created. Then run the protocol full suite with coverage >=86, ruff, and root context lint/diff checks. Required browser/geometry has 0 skips. Capture EN/CS at 360/390/1280 minimum and measure all specified wide/mobile sizes through 2048, collapsed/expanded rail. No guessed screenshot environment variables.

## 7. Acceptance

- [ ] Identical field ownership and explicit blank/absent/invalid/IBAN-only behavior through property and legacy adapter entry points.

- [ ] Fee-only save preserves every non-fee property field; full property save without fee fields preserves stored fee configuration.

- [ ] Old setup URL and custom report month return work; invalid input retained with actionable error.

- [ ] Rate 0 stays optional; finalized report contents and fee math unchanged.

- [ ] Focused/full/CI checks pass at actual current head, coverage threshold retained, required browser/geometry 0 skips.

- [ ] Synthetic screenshots and measured action/lane/focus evidence linked; no real credentials/guest/operator data.

- [ ] Changed paths exactly §3; no new dependency/schema or unapproved domain behavior.

## 8. Stop and ask

Stop/report if the patch is pending, predecessor/anchor/base differs, source path missing, scope needs another file, contract conflicts with current audited behavior, dependency/new provider is needed, a required check skips or fails, or the same test fails twice. Orchestrator issues an exact correction; executor does not guess, weaken tests or deploy. This gate is source correctness, not repeated design approval.

## 9. Report

Create `docs/tasks/0077-report.md` (<=1500 tokens): starting/ending SHA, file/diff stat, exact commands/results including failures/skips, §7 evidence, synthetic screenshot/geometry links, deviations/risks and owner steps. Set this brief review or blocked with the reason; link full logs instead of dumping them. PR targets integration only.

## Risk list (for the reviewer)

Read all changed templates/handlers/shared assets plus the new regression coverage; inspect current-head CI and the behavioral invariants above. Extra paths or evidence tied to a different commit require a correction brief.

## Owner steps

1. Review the report and actual current-head CI/diff scope.

2. Confirm task PR base is task/host-navigation-integration before guarded merge.

3. Have the orchestrator review/release the next exact patch; remain off main until staging acceptance and explicit production promotion approval.
