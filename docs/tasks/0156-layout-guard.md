# 0156: layout guard, a browser test that fails CI on broken layout

Status: done
Depends on: 0140 | Branch: claude/project-thread-5hw8cf
Executor: Sonnet 5.5 (new test logic; Haiku and Sonnet are allowed by the owner) | Fits one session

## 1. Objective

MASTER section 11.0 now lists hard layout rules. This brief adds the test that enforces them on every host page at 390, 1280 and 2000 px, with the sidebar open and collapsed, and adds that test to the CI browser job. The test is expected to fail on some pages today. Those failures are the work list for the page briefs that follow. Do **not** fix pages in this brief, and do **not** add an allowlist, skip, xfail or loosened threshold.

## 2. Context

- `App/tests/test_host_wide_geometry_browser.py` already has module fixtures `wide_host` (a host with long property names, a business, stays, an invoice and a submission) and `wide_base` (a live server). It also has `CAPTURE_ROUTES`, the formatting of those routes (lines 450–460), and the helpers `_wait_for_host_layout` and `_dismiss_optional_security_prompt`. `tests/` has no `__init__.py`, so `from test_host_wide_geometry_browser import ...` works under pytest. Imported fixtures are re-created for the new module, which is fine.
- `chromium_launch_kwargs` and `REQUIRE_BROWSER` come from the same imports that file uses. Copy its import lines.
- The guard script is given verbatim in step 1. It returns a list of `[kind, ...detail]` and takes one argument, `phone` (true below 1024 px).

## 3. Files

| File | Change |
|---|---|
| `App/tests/design_guard.js` | new, verbatim from step 1 |
| `App/tests/test_design_guardrails_browser.py` | new |
| `.github/workflows/ci.yml` | add the new test file to the "Walk the guest flow in a browser" pytest list |
| `docs/context/test-map.md` | one row |
| `docs/tasks/0156-report.md` | report |

## 4. Steps

1. Create `App/tests/design_guard.js` with exactly this content:

```js
(phone) => {
  const out = [];
  const vw = window.innerWidth;
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const inScroller = (el) => { for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) { const ox = getComputedStyle(a).overflowX; if (ox === 'auto' || ox === 'scroll') return true; } return false; };
  const name = (el) => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.classList.length ? '.' + [...el.classList].slice(0, 3).join('.') : '') + ' "' + (el.textContent || el.value || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 30) + '"');
  // 1. no sideways page scroll
  const sw = document.documentElement.scrollWidth;
  if (sw > vw + 1) out.push(['page-scroll', sw, vw]);
  // 2. nothing under the rail or past the right edge
  const ws = document.querySelector('.host-workspace main, .host-workspace') || document.body;
  const lane = ws.getBoundingClientRect();
  for (const el of ws.querySelectorAll('h1,h2,h3,p,label,a,button,input,select,textarea,td,th,li,.ui-badge,img,svg')) {
    if (!vis(el) || el.closest('[role=menu],[hidden],dialog:not([open]),.ui-table-wrap,.scroll-x,[data-scroll-x]')) continue;
    if (inScroller(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.left < lane.left - 1) out.push(['under-rail', name(el), Math.round(r.left), Math.round(lane.left)]);
    if (r.right > vw + 1) out.push(['past-right-edge', name(el), Math.round(r.right), vw]);
  }
  // 3. clipped or overlapping text: an element whose text is cut by its own box
  for (const el of ws.querySelectorAll('td,th,h1,h2,h3,p,a,button,label,.ui-badge,li')) {
    if (!vis(el) || el.closest('[role=menu],[hidden]')) continue;
    const s = getComputedStyle(el);
    if (s.textOverflow === 'ellipsis' || el.clientHeight <= 2 || el.clientWidth <= 2) continue;
    if (el.scrollHeight > el.clientHeight + 2 && s.overflowY !== 'visible' && s.overflowY !== 'auto' && s.overflowY !== 'scroll' && el.clientHeight > 0) out.push(['text-clipped', name(el), el.scrollHeight, el.clientHeight]);
  }
  // table rows must contain their cells (catches fixed row heights with wrapping text)
  for (const tr of ws.querySelectorAll('tr')) {
    if (!vis(tr)) continue;
    const rr = tr.getBoundingClientRect();
    for (const td of tr.children) {
      if (!vis(td)) continue;
      for (const kid of td.querySelectorAll('*')) {
        if (!vis(kid) || kid.closest('[role=menu]') || kid.tagName === 'IFRAME') continue;
        const kr = kid.getBoundingClientRect();
        if (kr.bottom > rr.bottom + 2 || kr.top < rr.top - 2) { out.push(['spills-out-of-row', name(kid), Math.round(kr.top), Math.round(kr.bottom), Math.round(rr.top), Math.round(rr.bottom)]); break; }
      }
    }
  }
  // 4. buttons that share a row have one height and one centre line
  const btnSel = '.ui-btn:not(.row-menu-trigger):not(.ui-btn-icon),.btn,input[type=submit],button[type=submit]';
  const parents = new Set([...ws.querySelectorAll(btnSel)].filter(vis).map((b) => b.parentElement));
  for (const p of parents) {
    const bs = [...p.children].filter((c) => c.matches(btnSel) && vis(c));
    // also buttons wrapped one level deep in a form (inline-form pattern)
    for (const c of p.children) if (c.tagName === 'FORM') for (const b of c.children) if (b.matches(btnSel) && vis(b)) bs.push(b);
    for (let i = 0; i < bs.length; i++) for (let j = i + 1; j < bs.length; j++) {
      const a = bs[i].getBoundingClientRect(), b = bs[j].getBoundingClientRect();
      const sameRow = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0;
      if (!sameRow) continue;
      if (Math.abs(a.height - b.height) > 2) out.push(['button-heights-differ', name(bs[i]), Math.round(a.height), name(bs[j]), Math.round(b.height)]);
      else if (Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) > 2) out.push(['buttons-misaligned', name(bs[i]), name(bs[j])]);
    }
  }
  // 5. phone tap targets
  if (phone) {
    for (const el of ws.querySelectorAll('button,.ui-btn,input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,[role=menuitem],[role=tab]')) {
      if (!vis(el) || el.closest('[role=menu],[hidden]')) continue;
      const r = el.getBoundingClientRect();
      if (r.height < 43.5 || r.width < 43.5) out.push(['tap-target-small', name(el), Math.round(r.width), Math.round(r.height)]);
    }
  }
  return out;
}
```

2. Create `App/tests/test_design_guardrails_browser.py`:
   - Import `wide_host`, `wide_base`, `CAPTURE_ROUTES`, `_wait_for_host_layout` and `_dismiss_optional_security_prompt` from `test_host_wide_geometry_browser`, plus the browser helpers it uses.
   - `ROUTES` = every `CAPTURE_ROUTES` path, plus `"cleaning": "/cleaning"`, `"guest-new": "/reservations/{reservation_id}/guests/new"`, `"setup-property": "/apartments/{property_id}/setup/property"`, `"setup-police": "/apartments/{property_id}/setup/police"`, `"settings-account": "/settings"`. Format the paths with the same keyword arguments that `test_host_wide_lanes_align` uses. Drop the selector half of each tuple.
   - One test, `test_every_host_page_passes_the_layout_guard(wide_host, wide_base)`:
     - Launch Chromium like the wide test (skip only when Chromium is missing and `REQUIRE_BROWSER` is off).
     - For each width in `(390, 1280, 2000)`, and each `collapsed` in `(False, True)` when width ≥ 1024 (`(False,)` otherwise), make a context with viewport width × 1000, the session cookie, and the init script `try { localStorage.setItem('ubyhost-sidebar-collapsed', '1' or '0'); } catch (e) {}`.
     - For each route, go to `path + ?lang=en` (or `&lang=en`), assert HTTP < 400, wait with `_wait_for_host_layout`, call `_dismiss_optional_security_prompt`, then `page.evaluate(GUARD, width < 1024)` with GUARD read from `design_guard.js`. Collect each finding as `(route, width, "collapsed"|"open", finding)`.
     - Menu check, on the same page: if a visible `button.row-menu-trigger` exists, click the first one and read its `.row-menu-panel` box. Record `menu-off-screen` if the panel's left < 0, right > width or bottom > the document height, and `menu-holds-form` if the panel contains a visible `input:not([type=hidden])`, `textarea` or `select`. Then press Escape.
   - At the end, write all findings as JSON to `os.environ.get("UBYHOST_GUARD_REPORT", "/tmp/ubyhost-layout-guard.json")`, and `assert not findings` with a message of the count by kind plus the first 40 findings, one per line.
3. In `.github/workflows/ci.yml`, in the run line of the step "Walk the guest flow in a browser", add `tests/test_design_guardrails_browser.py` right after `tests/test_host_wide_geometry_browser.py`. Change nothing else in the workflow.
4. In `docs/context/test-map.md`, add a row: `| Any host template, host CSS or host JS | test_design_guardrails_browser.py (0 skipped; the rules are in MASTER 11.0) |`.
5. Run from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q -rs 2>&1 | tail -50` (foreground, timeout 600000). It is expected to **fail** with findings. Check that it ran (0 skipped) and that the findings look real, not test errors such as a 404, a bad selector or a fixture failure. If you see test errors, fix your test (not pages) and rerun.
6. Commit: `git add App/tests/design_guard.js App/tests/test_design_guardrails_browser.py .github/workflows/ci.yml docs/context/test-map.md docs/tasks/0156-* && git commit -m "0156: layout guard browser test in CI (MASTER 11.0)"`. Do not push.

## 5. Do not touch

Templates, CSS, JS under `App/app/`, other tests, and the guard rules. Hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] The test runs with 0 skipped and reports real layout findings, or passes.
- [ ] CI's browser step lists it.
- [ ] The report contains the findings grouped by route and kind (copy from the JSON file), so page briefs can be written from it.

## 8. Stop and ask

The fixture import fails in a way a copy of the fixture would not fix, or a route 404s for a reason outside the test.

## 9. Report

`docs/tasks/0156-report.md`, `Status: review`. List findings grouped by route, then by kind, with counts and one example each.
