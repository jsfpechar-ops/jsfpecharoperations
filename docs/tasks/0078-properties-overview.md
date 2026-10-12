# 0078: Properties list and read-only cross-property summaries

Status: blocked — depends on reviewed 0077; exact patch must be released against that integration revision.

Depends on: 0077 done | Source baseline: c4c8f979319e53341833065b2a8790c30159581f | Branch: task/0078-properties-overview | PR base: task/production-host-ux-integration

Patch status: pending — rebase against reviewed 0094/correction predecessors and release the exact patch; acceptance contract only; not executable until the orchestrator adds exact code/diffs and the reviewed base SHA.

Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Properties list and read-only cross-property summaries. Deliver the approved design through one maintained implementation, preserving existing business behavior.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed prerequisite report/inventory. Designs are approved; do not repeat design approval. These verified source anchors document the starting contracts; the released exact patch must refresh any changed anchor against its actual predecessor.

`App/app/routes/admin.py`:

```
@router.get("/apartments")
```

`App/app/routes/admin.py`:

```
    return _property_hub_redirect(request, "communication")
```

## 3. Files

Explicit allowlist below. A partial introduced by an earlier task must already exist at the reviewed base. If a named path does not exist or another helper/file is needed, obtain a scope correction before editing.

| Path | Action | What |

|---|---|---|

| `App/app/templates/apartments.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_components.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/admin.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/api.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/host.css` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/host_i18n.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/tests/test_host_properties_navigation.py` | create | Named shared rendering or meaningful regression coverage |

| `docs/tasks/0078-properties-overview.md` | edit | Lifecycle status only |

| `docs/tasks/0078-report.md` | create | Required report, 1500 tokens maximum |

| `docs/tasks/0078-evidence/` | create | Synthetic screenshots and measured evidence only |

Read-only source: the predecessor inventory/brief/report, relevant routes/guards identified by 0071, shared field/date/filter/account primitives already named in the plan, and the following tests/fixtures: `App/tests/test_property_hub.py`, `App/tests/test_host_redesign.py`, `App/tests/test_host_property_controls_browser.py`, `App/tests/test_host_wide_geometry_browser.py`, `App/tests/test_property_readiness.py`. No unrelated whole-repo audit.

## 4. Steps

1. Confirm prerequisite done, active task todo, Patch status ready, recorded reviewed base SHA and all exact anchors. Stop if any fails. This contract is not permission to design or improvise its missing code.

2. Apply the released exact patch only, then verify the following phase requirements in order:

3. Use the approved compact property list: name/location, actual setup state/calendar count and aligned Open. Retain Add property, active/archive/filter views, restoration and copied-property navigation.

4. Expose shared Business & legal details and connected lock accounts once as contextual links, using their canonical record scopes.

5. Add the approved optional native disclosure of read-only guest-link/automation summaries using existing authorized property data. Each row links to its exact property editor; no editable controls, new global settings route or inferred status.

6. Preserve /guest-links and /automation one-property redirect and multiple/no-property return to Properties. Search entries lead to canonical features without losing authorized destinations.

7. Keep empty/no-match/archived states distinct; no photos, cards full of decorative setup claims, fee/lock onboarding nags or duplicated legal-entity fields.

8. Run §6, capture the actual changed pages with synthetic fixtures, compare every changed path with §3, write §9 and set review. Do not merge, deploy, advance to a blocked task or modify the next task.

## 5. Do not touch

Public/login/guest-facing designs, PDF/export content, filing state machine or live reporting, lock/PIN lifecycle, fee math/statutory rules, issued invoice snapshots, auth/retention/access policy, schema, dependencies, workflows/deploy files or arbitrary backend handlers. Only handlers explicitly in §3 may change, solely for the released presentation/ownership adapter patch. No production/main action. Never remove a unique control to match an abbreviated mockup.

## 6. Commands

Use the exact staging/mock/REQUIRE_BROWSER environment and setup from the execution protocol. From App, run these focused checks first:

```bash

.venv/bin/python -m pytest tests/test_property_hub.py tests/test_host_redesign.py tests/test_host_property_controls_browser.py tests/test_host_wide_geometry_browser.py tests/test_property_readiness.py -q -rs

```

Include the named new regression tests once created. Then run the protocol full suite with coverage >=86, ruff, and root context lint/diff checks. Required browser/geometry has 0 skips. Capture EN/CS at 360/390/1280 minimum and measure all specified wide/mobile sizes through 2048, collapsed/expanded rail. No guessed screenshot environment variables.

## 7. Acceptance

- [ ] One/many/no/archived properties render truthful summaries with usable Open/setup/restore paths.

- [ ] Read-only summaries cannot mutate settings and every configuration link chooses the correct property/section.

- [ ] Search/legacy redirects/shared entity/lock routes remain reachable without the removed global sub-bar.

- [ ] Labels/actions align and remain readable in CS and mobile/wide lanes.

- [ ] Focused/full/CI checks pass at actual current head, coverage threshold retained, required browser/geometry 0 skips.

- [ ] Synthetic screenshots and measured action/lane/focus evidence linked; no real credentials/guest/operator data.

- [ ] Changed paths exactly §3; no new dependency/schema or unapproved domain behavior.

## 8. Stop and ask

Stop/report if the patch is pending, predecessor/anchor/base differs, source path missing, scope needs another file, contract conflicts with current audited behavior, dependency/new provider is needed, a required check skips or fails, or the same test fails twice. Orchestrator issues an exact correction; executor does not guess, weaken tests or deploy. This gate is source correctness, not repeated design approval.

## 9. Report

Create `docs/tasks/0078-report.md` (<=1500 tokens): starting/ending SHA, file/diff stat, exact commands/results including failures/skips, §7 evidence, synthetic screenshot/geometry links, deviations/risks and owner steps. Set this brief review or blocked with the reason; link full logs instead of dumping them. PR targets integration only.

## Risk list (for the reviewer)

Read all changed templates/handlers/shared assets plus the new regression coverage; inspect current-head CI and the behavioral invariants above. Extra paths or evidence tied to a different commit require a correction brief.

## Owner steps

1. Review the report and actual current-head CI/diff scope.

2. Confirm task PR base is task/host-navigation-integration before guarded merge.

3. Have the orchestrator review/release the next exact patch; remain off main until staging acceptance and explicit production promotion approval.
