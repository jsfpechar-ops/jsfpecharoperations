# 1865: White host workspace and warm sidebar

Status: todo
Depends on: none | Base commit: 7637273d9be268df6f1dd5cf9f498b3c37430065 or newer green main with the same anchors | Branch: task/1865-host-workspace-palette
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Use a white workspace and a softly tinted sidebar throughout the signed-in customer host app at laptop and tablet widths. Make the change in the shared chrome so it applies across host routes and both renderers.

## 2. Context

Josef approved white `#FFFFFF` and warm off-white `#FCF8F5` on 2026-11-20. The preview also showed different spacing, table framing and control fills. Those are outside this color-only task. At 768 CSS px and up, use white for the background behind content and the warm tint for the existing sidebar or rail wherever rendered. Keep the active navigation, separator, cards, alerts and controls as they are. Leave screens below 768 px, guest/public/auth and the separate operator workspace out of the change.

The v2 body paints `var(--bg)`. That token also colors components such as notice strips and progress tracks, so target the body background directly using the existing white surface token. Scope the sidebar token to the host body so both the rail and the existing desktop backdrop update together. The older host shell already uses a white workspace. Its rail is `.ui-sidebar` in `host2.css`.

Exact anchors:

- `App/app/static/app2.css`: `*{box-sizing:border-box}body{margin:0;background:var(--bg)}` and `@media (min-width:1024px){.app{background:linear-gradient(90deg,var(--side) 0 219px,var(--line) 219px 220px,transparent 220px)}}`
- `App/app/static/host2.css`: `.host-workspace .ui-sidebar { position: fixed; inset: 0 auto 0 0; width: var(--nav-w); box-sizing: border-box; background: var(--surface);` (prefix of the rail rule)
- Both shell templates: `/static/app2.css?v=20261120-stay1863b` and `/static/host2.css?v=20261109-bsite-wrap-h2`.
- `App/tests/v2_mockup.py`: `WIDE_OVERRIDES = {` and `"name": "overview",`. The overview selector list compares `.side` with the older mockup.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app2.css` | Edit | Shared v2 host canvas and rail |
| `App/app/static/host2.css` | Edit | Legacy host rail |
| `App/app/templates/base.html` | Edit | Two stylesheet versions |
| `go/internal/hostweb/layout/shell.html` | Edit | Same two stylesheet versions |
| `go/internal/hostweb/layout/testdata/v2_cs_impersonating.html` | Regenerate | Stylesheet version only |
| `go/internal/hostweb/layout/testdata/v2_alerts_hidden.html` | Regenerate | Stylesheet version only |
| `go/internal/hostweb/layout/testdata/alerts_invoices_en.html` | Regenerate | Stylesheet version only |
| `go/internal/hostweb/layout/testdata/visitor_cenik.html` | Regenerate | Stylesheet version only |
| `go/internal/hostweb/layout/testdata/legacy_en.html` | Regenerate | Stylesheet version only |
| `go/internal/hostweb/layout/testdata/alerts_reservations_scope.html` | Regenerate | Stylesheet version only |
| `go/internal/hostweb/layout/testdata/alerts_dashboard_cs.html` | Regenerate | Stylesheet version only |
| `go/internal/hostweb/layout/testdata/property_err_minutes0.html` | Regenerate | Stylesheet version only |
| `App/tests/static_versions.json` | Regenerate | Two assets |
| `App/tests/v2_mockup.py` | Edit | Approved wide overview rail expectation |
| `docs/tasks/1865-host-workspace-palette.md` | Edit status | Execution tracking |
| `docs/tasks/1865-report.md` | Create | Report and screenshot references |

## 4. Steps

1. In `app2.css`, insert this immediately after the anchored body rule.

   ```css
   @media (min-width:768px) {
     body.v2.host-workspace:not(.admin-workspace) {
       --side:#fcf8f5;
       background-color:var(--s);
     }
   }
   ```

   Run `git diff -- App/app/static/app2.css 2>&1 | tail -30`. Expect one block and no changes to existing declarations.

2. In `host2.css`, append this block. The legacy selector covers the active rail. The host body and lane already render white.

   ```css
   @media (min-width:768px) {
     body.host-workspace:not(.v2):not(.admin-workspace) .ui-sidebar {
       --host-sidebar-background:#fcf8f5;
       background-color:var(--host-sidebar-background);
     }
   }
   ```

   Run `git diff -- App/app/static/host2.css 2>&1 | tail -30`. Expect one rail-only block.

3. In `App/app/templates/base.html`, change the versions of both named stylesheets to `20261120-host-palette-1865`. Run `git diff -- App/app/templates/base.html 2>&1 | tail -30`. Expect two URL-only changes.

4. Repeat the same version substitutions in `go/internal/hostweb/layout/shell.html`. Run `git diff -- go/internal/hostweb/layout/shell.html 2>&1 | tail -30`. Expect two URL-only changes.

5. From `App/` run `.venv/bin/python scripts/go_layout_golden.py 2>&1 | tail -30`. Expect only the listed generated HTML files with URL-only changes.

6. From `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. Expect the manifest to reflect the two new asset versions and hashes.

7. Immediately after `WIDE_OVERRIDES = {` in `App/tests/v2_mockup.py` add:

   ```python
       "overview:.side": {"background-color": "rgb(252, 248, 245)"},
   ```

   Run `git diff -- App/tests/v2_mockup.py 2>&1 | tail -30`. Expect one added expectation for the approved color. Keep the existing checks and tolerances.

8. Run §6 and review the screenshots. Capture using mock/demo data. Check the computed body and rail backgrounds in DevTools or Playwright, using an authenticated customer host session. Record the routes, widths and RGB values in the report. Send a separate finding if a route paints over the shared background and requires a file outside §3.

## 5. Do not touch

Routing, data, behavior, layout, spacing, typography, component fills, sidebar selection and navigation, and public, guest, login and operator styling. Keep `--bg` and the root `--side` defaults. Keep Go and Python asset URLs in sync. Use demo data. No secrets or real guest details in screenshots, reports or commits. No pushing to main, merging or deployment.

## 6. Commands

Use pipeline failure propagation in the shell. From `App/`:

```sh
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_go_layout_golden.py -q --tb=short -x 2>&1 | tail -30
palette_shots=$(mktemp -d "${TMPDIR:-/tmp}/ubyhost-1865-shots.XXXXXXXX")
printf '%s\n' "$palette_shots" | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR="$palette_shots" .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30
```

Expect both runs green, with zero skipped host browser checks and zero host layout findings. From `go/` run `go test ./internal/hostweb/layout 2>&1 | tail -30`. Expect pass. From the repository root run `git diff --check 2>&1 | tail -30`. Expect no output.

## 7. Acceptance

- [ ] At 768, 820 and 1280 px, the shared host canvas is `rgb(255, 255, 255)` and any visible rail is `rgb(252, 248, 245)`. Verify Dashboard, Calendar, Stays list and detail, Properties, Cleaning, Stay fees and Settings across the representative tablet and laptop sizes. Include an existing legacy host route if served.
- [ ] At 390 and 767 px the pre-change colors still apply. Check both sides of the breakpoint using the same route and demo account. Guest/public/auth and operator chrome keep their prior colors.
- [ ] Visual review confirms readable navigation, coral active selection and intact separators, alerts and card edges. Attach the 390, 768 and 1280 px layout-gate evidence per host page and note what was observed at each width in the draft PR. Include laptop Dashboard and tablet Stays examples.
- [ ] The two renderers use the same versioned stylesheet URLs. Golden and static manifest changes contain only the expected asset updates.
- [ ] Browser, geometry, cache and layout checks pass. Record results and complete the design-system checklist in the draft PR.

## 8. Stop and ask

Report a missing anchor, a test failing twice, a necessary additional file, a dependency, unclear scope, or a session cap. Queue 1865 first among the overlapping todo briefs for the shared CSS, shell templates and manifest, including 1762 and 1763. If an overlapping branch is already in progress, wait for it to merge and have the orchestrator refresh the anchors before starting 1865. Surface pre-existing failures with evidence. Keep the gate intact.

## 9. Report

In `docs/tasks/1865-report.md` record the files changed, commands and final results, screenshot paths, computed colors by route and width, acceptance checkboxes, deviations and owner steps. Set the brief to `review` and open one draft PR if permitted. Otherwise give the owner the branch and the exact draft PR command.

## Risk list (for the reviewer)

Both shared CSS files and both shell templates. Confirm the selector scope, breakpoint and matching cache keys.

## Owner steps

1. Open the draft PR and read the screenshot summary after review.
2. When approved and checks are green, use the repository's `scripts/merge-pr-on-green.sh` process.
