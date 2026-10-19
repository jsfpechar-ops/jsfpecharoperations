# 0157: fix the layout guard findings (except cleaning)

Status: todo
Depends on: 0156 | Branch: claude/project-thread-5hw8cf
Executor: Sonnet 5.5 or Haiku 5.5 | Fits one session

## 1. Objective

`test_design_guardrails_browser.py` (0156) fails with 130 findings. The orchestrator checked each kind:
- The `sr-only` inputs (a 2 px copy source and a hidden file input) are false positives, because they are not tap targets.
- The help "?" already has a 44 px hit area through `::after { inset: -11px }`. The guard must count that.
- Everything else is real.

Fix the guard's two false positives, then fix the pages. Cleaning ("Property instructions & codes" 61 px vs "Share schedule" 44 px) is left to brief 0143, which rebuilds that header. After this brief, the only remaining findings may be on route `cleaning`.

## 2. Context

Phone means below 1024 px. Tokens: `--control-h-phone` is 44 px; `--control-h` is 40 px. S2 lint forbids bare px in margin, padding, gap, radius and font-size. The current host2.css key is `20261019-0140`. MASTER 11.0 says no allowlist and no loosening, so steps 1 and 2 only stop counting things that are not tap targets or that already have a 44 px hit area.

## 3. Files

`App/tests/design_guard.js`, `App/tests/test_design_guardrails_browser.py`, `App/app/static/host2.css` (append), `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `App/app/templates/reservations.html`, `App/app/templates/_property_overview.html`, `App/app/templates/guest_form_admin.html`, `docs/tasks/0157-*`.

## 4. Steps

1. In `App/tests/design_guard.js`, replace the line

```
      if (r.height < 43.5 || r.width < 43.5) out.push(['tap-target-small', name(el), Math.round(r.width), Math.round(r.height)]);
```

with

```
      if (r.width <= 2 || r.height <= 2) continue; // visually hidden (sr-only), not a tap target
      const after = getComputedStyle(el, '::after');
      const grow = after.position === 'absolute' && after.content !== 'none' ? Math.max(0, -parseFloat(after.left) || 0) * 2 : 0; // hit area widened by a negative inset
      if (r.height + grow < 43.5 || r.width + grow < 43.5) out.push(['tap-target-small', name(el), Math.round(r.width), Math.round(r.height)]);
```

2. In `App/tests/test_design_guardrails_browser.py`, change the menu field selector `"input:not([type=hidden]):visible, textarea:visible, select:visible"` to `"input:not([type=hidden]):not(.sr-only):visible, textarea:visible, select:visible"`.
3. Append to `App/app/static/host2.css`:

```
/* 0157: layout guard (MASTER 11.0): phone fields and small controls reach 44 px; toolbar actions share one size */
@media (max-width: 1023px) {
  .host-workspace input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]):not(.sr-only), .host-workspace select { min-height: var(--control-h-phone); }
  .host-workspace .operator-phone-code { min-width: var(--control-h-phone); }
  .host-workspace [data-cal-scale] { min-width: var(--control-h-phone); min-height: var(--control-h-phone); }
  .host-workspace #sig-clear { min-height: var(--control-h-phone); min-width: var(--control-h-phone); }
}
```

4. Templates:
   - In `App/app/templates/reservations.html`, change `<button class="ui-btn ui-btn-quiet" type="button" data-save-view` to `<button class="ui-btn ui-btn-quiet ui-btn-compact" type="button" data-save-view`. This matches the compact "Export stays (CSV)" next to it.
   - In `App/app/templates/_property_overview.html`, change `<button class="link-button" type="submit" name="action" value="hide" formnovalidate>` to `<button class="ui-btn ui-btn-quiet" type="submit" name="action" value="hide" formnovalidate>`. This makes it the same height as "Continue".
   - In `App/app/templates/guest_form_admin.html`, change `<button type="button" id="sig-clear">` to `<button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" id="sig-clear">`. If design lint objects because the template is not enforced, keep the original markup; the CSS in step 3 already covers it.
   - Each anchor occurs once. If one does not, stop.
5. Bump host2.css in `base.html` from `20261019-0140` to `20261019-0157`. Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`, and from the root: `python3 scripts/design_lint.py 2>&1 | tail -3`.
6. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q -rs 2>&1 | tail -30` (foreground, timeout 600000). Expected: only findings on route `cleaning`. For any other finding: if it comes from your own change, fix it; if it is a new kind of problem, stop and report it verbatim. Then run `.venv/bin/python -m pytest tests/test_design_ui_macros.py tests/test_host_properties_navigation.py tests/test_stay_list_v2.py -q 2>&1 | tail -5` (skip any file that does not exist) and `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_host_list_cards_browser.py -q -rs 2>&1 | tail -6`. A test that pins `link-button` or the old Save-view class may be updated to the new class, and that is the only test edit allowed.
7. Commit by path: the files in section 3 plus any test updated in step 6. Message: `0157: layout guard findings fixed (phone fields 44 px, toolbar sizes, setup guide button)`. Do not push.

## 5. Do not touch

Cleaning templates (0143 owns them) and the guard rules beyond steps 1 and 2. Hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] The guard reports findings only on `cleaning`.
- [ ] Lint is OK, static versions pass, and the step 6 tests pass.

## 8. Stop and ask

A new finding kind appears, or a test fails twice.

## 9. Report

`docs/tasks/0157-report.md`, `Status: review`, with the guard output's last lines.
