# 0073: Property tabs, grouped editor and safe drafts

Status: replaced — 0094 implements the corrected property editor/tabs/calendars after 0087–0093; do not apply this stale patch.

Depends on: 0072 done | Source baseline: c4c8f979319e53341833065b2a8790c30159581f | Branch: task/0073-property-navigation | PR base: task/host-navigation-integration

Patch status: pending — acceptance contract only; not executable until the orchestrator adds exact code/diffs and the reviewed base SHA.

Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Property tabs, grouped editor and safe drafts. Deliver the approved design through one maintained implementation, preserving existing business behavior.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed prerequisite report/inventory. Designs are approved; do not repeat design approval. These verified source anchors document the starting contracts; the released exact patch must refresh any changed anchor against its actual predecessor.

`App/app/routes/admin.py`:

```
async def apartment_update(apartment_id: int, request: Request):
```

`App/app/routes/admin.py`:

```
    if "automation_mode" not in form:
```

## 3. Files

Explicit allowlist below. A partial introduced by an earlier task must already exist at the reviewed base. If a named path does not exist or another helper/file is needed, obtain a scope correction before editing.

| Path | Action | What |

|---|---|---|

| `App/app/templates/apartment_form.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_property_settings_form.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_property_calendars.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_components.html` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/host.css` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/static/app.js` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/host_i18n.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/routes/admin.py` | edit | Only the released phase-specific patch; retain unrelated behavior |

| `App/app/templates/_property_section_navigation.html` | create | Named shared rendering or meaningful regression coverage |

| `App/tests/test_property_navigation_browser.py` | create | Named shared rendering or meaningful regression coverage |

| `App/tests/test_property_navigation_save.py` | create | Named shared rendering or meaningful regression coverage |

| `docs/tasks/0073-property-navigation.md` | edit | Lifecycle status only |

| `docs/tasks/0073-report.md` | create | Required report, 1500 tokens maximum |

| `docs/tasks/0073-evidence/` | create | Synthetic screenshots and measured evidence only |

Read-only source: the predecessor inventory/brief/report, relevant routes/guards identified by 0071, shared field/date/filter/account primitives already named in the plan, and the following tests/fixtures: `App/tests/test_property_hub.py`, `App/tests/test_property_form_save.py`, `App/tests/test_property_form_nav.py`, `App/tests/test_new_property_defaults.py`, `App/tests/test_copy_property_settings.py`, `App/tests/test_stay_fee_property_panel.py`, `App/tests/test_host_property_controls_browser.py`, `App/tests/test_host_wide_geometry_browser.py`. No unrelated whole-repo audit.

## 4. Steps

1. Confirm prerequisite done, active task todo, Patch status ready, recorded reviewed base SHA and all exact anchors. Stop if any fails. This contract is not permission to design or improvise its missing code.

2. Apply the released exact patch only, then verify the following phase requirements in order:

3. Use the approved three property views: overview, calendars, settings. Group values are information, guest, reporting, automation. Normal links use the existing property URL with view/section query parameters and old anchors; unknown values safely fall back rather than executing arbitrary template names.

4. Build the four-group desktop section navigation and labelled mobile selector using one shared rendering. Information owns basics/address/notes; Guest experience owns communication/door-code; Reporting & fees owns ubyport/stay-fee-settings; Automation owns automation. Keep the real extended address/credential/fee/lock fields and conditional feature guards.

5. Render one canonical full property form. Keep all successful controls, hidden Enter-default submit, return_to, CSRF and formaction buttons. JS may change visibility and focus but must never disable/drop an unrelated field. Show normal-flow Save/Discard at form end, with drafts preserved across sections.

6. Map each existing shortcut to its exact tab/section, and assigned business to the shared entity editor. Preserve setup readiness and archived behavior. Legacy hash activation must reveal the correct group on load/history. JS-disabled navigation must remain usable using the same markup, not a duplicate template.

7. Use explicit clean/dirty/saving/error state. Leaving the draft offers Save/Discard/Stay. Save navigates only after confirmed persistence; Discard restores all edited sections; cancelled/failed submission retains values. Native unload warning only. No localStorage/sessionStorage for credentials or personal data.

8. Reveal the first invalid inactive field and its details/group before native error/focus. Preserve server validation inputs/errors in the canonical render context; do not normalize away errors or show successful navigation after a rejected save. Keep current save-first credential test and PIN/link regeneration behavior.

9. Add EN/CS meanings once: Overview/Přehled, Bookings & calendars/Rezervace a kalendáře, Settings/Nastavení, Property information/Informace o ubytování, Guest experience/Pro hosty, Reporting & fees/Hlášení a poplatky, Automation/Automatizace. Reuse existing Save/Discard/field keys where meanings match.

10. Run §6, capture the actual changed pages with synthetic fixtures, compare every changed path with §3, write §9 and set review. Do not merge, deploy, advance to a blocked task or modify the next task.

## 5. Do not touch

Public/login/guest-facing designs, PDF/export content, filing state machine or live reporting, lock/PIN lifecycle, fee math/statutory rules, issued invoice snapshots, auth/retention/access policy, schema, dependencies, workflows/deploy files or arbitrary backend handlers. Only handlers explicitly in §3 may change, solely for the released presentation/ownership adapter patch. No production/main action. Never remove a unique control to match an abbreviated mockup.

## 6. Commands

Use the exact staging/mock/REQUIRE_BROWSER environment and setup from the execution protocol. From App, run these focused checks first:

```bash

.venv/bin/python -m pytest tests/test_property_hub.py tests/test_property_form_save.py tests/test_property_form_nav.py tests/test_new_property_defaults.py tests/test_copy_property_settings.py tests/test_stay_fee_property_panel.py tests/test_host_property_controls_browser.py tests/test_host_wide_geometry_browser.py -q -rs

```

Include the named new regression tests once created. Then run the protocol full suite with coverage >=86, ruff, and root context lint/diff checks. Required browser/geometry has 0 skips. Capture EN/CS at 360/390/1280 minimum and measure all specified wide/mobile sizes through 2048, collapsed/expanded rail. No guessed screenshot environment variables.

## 7. Acceptance

- [ ] Editing notes preserves timing, rate/account, operator/controller and lock assignment; unchecked/omitted values obey current contract.

- [ ] Switching sections keeps drafts; Save/Discard/Stay works for tabs/cards/Back/sidebar/entity links/history without loops or premature success.

- [ ] Hidden required error opens/focuses the appropriate group; server rejection retains the submitted draft and has one clear error.

- [ ] One rendered instance of each editor control/ID; no independently edited overview copy; every old anchor lands correctly.

- [ ] Creation/copy-from-property/address-only wizard and existing test/refresh/regeneration/Enter actions remain correct; EN/CS mobile/wide geometry and keyboard pass.

- [ ] Focused/full/CI checks pass at actual current head, coverage threshold retained, required browser/geometry 0 skips.

- [ ] Synthetic screenshots and measured action/lane/focus evidence linked; no real credentials/guest/operator data.

- [ ] Changed paths exactly §3; no new dependency/schema or unapproved domain behavior.

## 8. Stop and ask

Stop/report if the patch is pending, predecessor/anchor/base differs, source path missing, scope needs another file, contract conflicts with current audited behavior, dependency/new provider is needed, a required check skips or fails, or the same test fails twice. Orchestrator issues an exact correction; executor does not guess, weaken tests or deploy. This gate is source correctness, not repeated design approval.

## 9. Report

Create `docs/tasks/0073-report.md` (<=1500 tokens): starting/ending SHA, file/diff stat, exact commands/results including failures/skips, §7 evidence, synthetic screenshot/geometry links, deviations/risks and owner steps. Set this brief review or blocked with the reason; link full logs instead of dumping them. PR targets integration only.

## Risk list (for the reviewer)

Read all changed templates/handlers/shared assets plus the new regression coverage; inspect current-head CI and the behavioral invariants above. Extra paths or evidence tied to a different commit require a correction brief.

## Owner steps

1. Review the report and actual current-head CI/diff scope.

2. Confirm task PR base is task/host-navigation-integration before guarded merge.

3. Have the orchestrator review/release the next exact patch; remain off main until staging acceptance and explicit production promotion approval.
