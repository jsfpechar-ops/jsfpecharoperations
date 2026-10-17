# 0090: Keep lock setup feedback in its relevant section

Status: review
Depends on: 0089 reviewed on the correction integration branch | Initial source baseline: 7b27d09402f9656b0c606c131793310925936526 | Branch: task/0090-lock-context-navigation | PR base: task/production-host-ux-integration
Executor: Cursor local agent (composer, Kimi or GLM) | One scoped executor session

## 1. Objective

Keep lock setup feedback in its relevant section. Deliver the owner's less-is-more correction without losing working features, drafts, legal data or filing safeguards.

## 2. Context

Read AGENTS.md, this brief, the correction plan and the preceding correction report only. This is the urgent corrective lane before 0072–0086. The [owner requirements](../plans/production-host-ux-corrections.md) supersede conflicting older optional-platform/parser/toggle instructions. Do not read or execute a blocked navigation brief.

Anchors: setup success `/smart-locks?return_to={quote(return_to, safe='')}`; refresh errors `_back(return_to, ...)`; share_block loops range(1,9). Property links encode #door-code. admin_helpers.back already places query before hash; leave it unchanged. JS openTarget opens only a target that itself is DETAILS, not its ancestors.

The source anchors describe current main before these tasks. Compare the reviewed predecessor diff first: a change intentionally made by a listed predecessor must be retained, not reverted to match an older anchor. If any other drift exists, stop with the precise difference. Record the actual base SHA and baseline failures before editing. No live provider/tenant data during verification.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | Scoped correction/test specified below |
| `App/app/templates/smart_locks.html` | edit | Scoped correction/test specified below |
| `App/app/templates/guide.html` | edit | Preserve full provider instructions in existing door-codes guidance |
| `App/app/templates/apartment_form.html` | edit | Scoped correction/test specified below |
| `App/app/static/app.js` | edit | Scoped correction/test specified below |
| `App/app/host_i18n.py` | edit | Scoped correction/test specified below |
| `App/tests/test_smart_locks_page.py` | edit | Scoped correction/test specified below |
| `App/tests/test_lock_navigation_browser.py` | create | Scoped correction/test specified below |
| `docs/tasks/0090-lock-context-navigation.md` | edit | Lifecycle only |
| `docs/tasks/0090-report.md` | create | Required report |
| `docs/tasks/0090-evidence/` | create | Synthetic screenshots/measurements only |

Read-only: docs/plans/production-host-ux-corrections.md; docs/plans/host-navigation-execution-protocol.md §§4–6; routed DESIGN/HOST_APP_DESIGN and UBYPORT_CORE/OPERATIONS/privacy sections when applicable; App/app/routes/admin_helpers.py; App/app/access.py; App/app/validation.py; App/app/templating.py; existing fixtures/conftest and directly referenced shared primitives. 0091 may inspect existing host templates/routes solely for the authorized read-only audit. No other file changes. New files apply only at the task which introduces them; later tasks edit them.

## 4. Steps

1. Preserve return_to sanitization and owner access. Add a narrow helper producing a lock-page URL with encoded sanitized return_to and a real section hash: #smart-locks-how for no account; #smart-locks-share for no locks; #smart-locks-add-more when sharing an additional lock; #smart-locks-list for existing lock refresh feedback. Include action context in forms through a constrained section value, never an arbitrary user-supplied path/hash.
2. Setup errors remain on #smart-locks-how with entered terms state handled truthfully; success goes to #smart-locks-share. Failed refresh/no lock/plain-key/reauth/budget outcomes stay on the actual sharing/list section, with real errors visible. Successful discovery invoked from a property returns to `/apartments/{authorized_id}#door-code`, where the lock selector is expanded and the found lock can be chosen. Do not auto-assign it or change enabled/provider state. Successful global discovery goes to #smart-locks-list. Remove/disconnect retains confirmation and its existing lifecycle; do not make it look successful on provider failure.
3. Harden existing openTarget without a new navigation system:

```javascript
function openTarget(hash) {
  if (!hash || hash.charAt(0) !== "#") return;
  var id;
  try { id = decodeURIComponent(hash.slice(1)); } catch (_) { return; }
  var target = document.getElementById(id);
  if (!target) return;
  var node = target;
  while (node) {
    if (node.tagName === "DETAILS") node.open = true;
    node = node.parentElement;
  }
  window.requestAnimationFrame(function () {
    target.scrollIntoView({ block: "start", behavior: "auto" });
  });
}
```

Retain existing link handlers and initial invocation; add hashchange listener calling openTarget(window.location.hash). Scope focus behavior to user-action/returned error target, not general autofocus that causes a page-top jump. Respect reduced motion. Native no-JS links still expose the setup sections; no hidden unsavable fields.
4. Replace the always-open eight-step share list with three short essentials: “Open your lock in TTLock.” / “Otevřete svůj zámek v TTLock.”; “Share administrator access with the account above.” / “Sdílejte přístup správce s účtem uvedeným výše.”; “Return here and check for locks.” / “Vraťte se sem a vyhledejte zámky.” Move the current complete eight-step instructions verbatim into the existing Guide door-codes section and link it with the contextual ? help pattern; do not add an accordion. Keep receiver Copy, actual authorized-admin warning, plain-key errors, terms checkbox and guidance link. Do not remove a required provider tap from the detailed instructions.
5. Browser regressions start deep in a property with a preview banner and long title: click Connect lock, accept mocked setup, check locks, no-lock error, discover one admin-shared lock, return to expanded #door-code, choose then save. Assert the relevant target is visible within the viewport and no irrelevant top jump; distinguish the necessary navigation to a different page from losing its target. Test shared account no/one/many locks, EN/CS, back navigation, no JS, external/foreign return attempts. Tests mock all TTLock calls and never issue/change/delete PINs.

Finish by comparing every changed file against §3 and writing §9. Do not automatically advance to the next task in the same session. Larger scoped edits above identify exact structures and invariants; small supplied replacements are mandatory. If the code required cannot be determined from these anchors without inventing business behavior, stop with an exact proposed diff instead of guessing.

## 5. Do not touch

No schema/migrations, dependencies, auth/access/CSRF policy, filing state machine, UbyPort SOAP, code lists, deadline computation, statutory field semantics, retention, signed records, issued invoice snapshots, TTLock/PIN lifecycle, live locks/feeds/emails/payments, public/guest design, workflow/deploy files or unrelated endpoints. No production/main push, merge or deploy. Required legal acceptance remains at its actual acceptance flow. This is presentation/default correction, not legal-policy revision.

## 6. Commands

Executor only; orchestrator does not run application tests. Use the existing Python/pinned-browser setup in the execution protocol. From App, run focused checks first:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_smart_locks_page.py tests/test_lock_navigation_browser.py tests/test_host_property_controls_browser.py -q -rs
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

- [ ] Connect/check failures and successes land on the correct visible lock section; property return expands the selector. Three essentials are shown, full provider steps remain available.
- [ ] All task-specific negative/draft/ownership/compatibility regressions in §4 pass; untouched settings and protected records survive.
- [ ] Actual browser evidence in EN/CS at 360/390/1280; geometry through 760/1024/1440/1680/1920/2048, expanded/collapsed sidebar, long labels and relevant error states. No visible obstruction/clipping; zero required-browser skips.
- [ ] No new schema/dependency/outbound call; fake/mocked integrations only; evidence contains fictional data and no token-bearing URLs/passwords/PINs.
- [ ] Current-head CI green, changed paths within §3, predecessor/candidate SHA and remaining audit findings recorded. Application change is not called deployed merely because a plan PR merged.

## 8. Stop and ask

Stop for unexplained source drift, foreign/archived access uncertainty, changing filing/legal semantics, an unlisted required file, missing browser prerequisites or a command that needs live providers/secrets/production. Send the exact blocker and proposed narrow correction. Do not reask approval for requirements already approved in chat. If baseline fails, isolate/report it; no test skips, assertion weakening, force push, main merge or deploy shortcut.

## 9. Report

Write docs/tasks/0090-report.md (max 1500 tokens), set Status: review. Include actual base/result SHA, file stat, test commands/last five output lines, counts/skips/coverage, §7 checkboxes, screenshot/measurement paths, source-vs-runtime audit boundary, deviations/unresolved defects and numbered owner steps. Do not claim production fixed or erase an open issue until reviewed application evidence exists.

## Risk list

Review the complete diff of every handler/template/default touched here, especially broad full-form payloads, negative validation, preservation of existing entity/controller/automation values and return paths. Read test fixtures for real provider calls and evidence for privacy leaks.

## Owner steps

1. Open a fresh Cursor chat and use the correction master prompt with this brief; its dependency must already be reviewed.
2. Review the report and actual CI on task/0090-lock-context-navigation; its PR targets task/production-host-ux-integration, never main.
3. After all corrections and outstanding audit fixes pass, review the exact tested candidate on staging with synthetic data.
4. Approve that candidate SHA before production promotion through the existing release protocol. Main currently triggers production deployment; do not merge early for a preview.
