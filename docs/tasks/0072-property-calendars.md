# 0072: Focused property calendar management

Status: blocked — depends on reviewed 0071; exact patch must be released against that integration revision.

Depends on: 0071 done | Source baseline: 0e8e468f6f8a7d4e33109493c115f580e0006504 | Branch: task/0072-property-calendars | PR base: task/host-navigation-integration

Patch status: pending — acceptance contract only; not executable until the orchestrator adds exact code/diffs and the reviewed base SHA.

Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Focused property calendar management. Deliver the approved design through one maintained implementation, preserving existing business behavior.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed prerequisite report/inventory. Designs are approved; do not repeat design approval. These verified source anchors document the starting contracts; the released exact patch must refresh any changed anchor against its actual predecessor.

`App/app/routes/admin.py`:

```
@router.post("/apartments/{apartment_id}/feeds")
```

`App/app/routes/admin.py`:

```
@router.post("/feeds/{feed_id}/delete")
```

## 3. Files

Explicit allowlist below. A partial introduced by an earlier task must already exist at the reviewed base. If a named path does not exist or another helper/file is needed, obtain a scope correction before editing.

| Path | Action | What |

|---|---|---|

| `App/app/templates/_property_calendars.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/apartment_form.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_components.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/host.css` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/app.js` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/host_i18n.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/tests/test_property_calendar_navigation.py` | create | Named shared rendering or meaningful regression coverage |

| `docs/tasks/0072-property-calendars.md` | edit | Lifecycle status only |

| `docs/tasks/0072-report.md` | create | Required report, 1500 tokens maximum |

| `docs/tasks/0072-evidence/` | create | Synthetic screenshots and measured evidence only |

Read-only source: the predecessor inventory/brief/report, relevant routes/guards identified by 0069, shared field/date/filter/account primitives already named in the plan, and the following tests/fixtures: `App/tests/test_property_hub.py`, `App/tests/test_host_property_controls_browser.py`, `App/tests/test_host_wide_geometry_browser.py`, `App/tests/test_host_feedback_browser.py`. No unrelated whole-repo audit.

## 4. Steps

1. Confirm prerequisite done, active task todo, Patch status ready, recorded reviewed base SHA and all exact anchors. Stop if any fails. This contract is not permission to design or improvise its missing code.

2. Apply the released exact patch only, then verify the following phase requirements in order:

3. Show platform/name, actual last_status and last_checked_at before URL. Keep never-checked/suspect/error distinct and text-labelled; a green badge never comes from URL presence alone.

4. Connect calendar opens one connection form; advanced portal/name options stay optional and collapsed. Preserve original URL/label/own_name names and add-and-sync endpoint. No always-open second sidebar form and no nested settings/calendar forms.

5. Put full URL/removal under native details/More. Retain removal consequences/confirmation and the current calendar-import lifecycle. Keep recovery errors persistent and partial results honest.

6. Use only existing sync operations. No per-feed Sync now unless 0069 confirms an actual authorized handler; UI must describe the handler actual scope. Do not add backend sync functionality in this brief.

7. Preserve dirty settings navigation and entered connection URL on invalid input. Add meaningful tests of failed/successful connection feedback and scope, not screenshot-only tests.

8. Run §6, capture the actual changed pages with synthetic fixtures, compare every changed path with §3, write §9 and set review. Do not merge, deploy, advance to a blocked task or modify the next task.

## 5. Do not touch

Public/login/guest-facing designs, PDF/export content, filing state machine or live reporting, lock/PIN lifecycle, fee math/statutory rules, issued invoice snapshots, auth/retention/access policy, schema, dependencies, workflows/deploy files or arbitrary backend handlers. Only handlers explicitly in §3 may change, solely for the released presentation/ownership adapter patch. No production/main action. Never remove a unique control to match an abbreviated mockup.

## 6. Commands

Use the exact staging/mock/REQUIRE_BROWSER environment and setup from the execution protocol. From App, run these focused checks first:

```bash

.venv/bin/python -m pytest tests/test_property_hub.py tests/test_host_property_controls_browser.py tests/test_host_wide_geometry_browser.py tests/test_host_feedback_browser.py -q -rs

```

Include the named new regression tests once created. Then run the protocol full suite with coverage >=86, ruff, and root context lint/diff checks. Required browser/geometry has 0 skips. Capture EN/CS at 360/390/1280 minimum and measure all specified wide/mobile sizes through 2048, collapsed/expanded rail. No guessed screenshot environment variables.

## 7. Acceptance

- [ ] Connected/suspect/failed/never states accurate; no URL duplication or leaked secrets in feedback.

- [ ] Add/remove use current guards and expected archived/import behavior; cancellation has no mutation.

- [ ] One connection form, outside settings; desktop/mobile labels/actions fit.

- [ ] A connection failure retains typed URL and explains recovery; changing tabs does not discard the property draft silently.

- [ ] Focused/full/CI checks pass at actual current head, coverage threshold retained, required browser/geometry 0 skips.

- [ ] Synthetic screenshots and measured action/lane/focus evidence linked; no real credentials/guest/operator data.

- [ ] Changed paths exactly §3; no new dependency/schema or unapproved domain behavior.

## 8. Stop and ask

Stop/report if the patch is pending, predecessor/anchor/base differs, source path missing, scope needs another file, contract conflicts with current audited behavior, dependency/new provider is needed, a required check skips or fails, or the same test fails twice. Orchestrator issues an exact correction; executor does not guess, weaken tests or deploy. This gate is source correctness, not repeated design approval.

## 9. Report

Create `docs/tasks/0072-report.md` (<=1500 tokens): starting/ending SHA, file/diff stat, exact commands/results including failures/skips, §7 evidence, synthetic screenshot/geometry links, deviations/risks and owner steps. Set this brief review or blocked with the reason; link full logs instead of dumping them. PR targets integration only.

## Risk list (for the reviewer)

Read all changed templates/handlers/shared assets plus the new regression coverage; inspect current-head CI and the behavioral invariants above. Extra paths or evidence tied to a different commit require a correction brief.

## Owner steps

1. Review the report and actual current-head CI/diff scope.

2. Confirm task PR base is task/host-navigation-integration before guarded merge.

3. Have the orchestrator review/release the next exact patch; remain off main until staging acceptance and explicit production promotion approval.
