# 0912b: help popover and "?" tooltip stay inside the phone screen

Status: in-progress
Depends on: 0912 (blocked on exactly this defect; its copy and fee-register label are already on this branch) | Base commit: current HEAD of `vibe/stay-fee-guest-payment-plan-73df64` | Branch: this branch (checked out). No commit, no push: the orchestrator commits.
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

At 390 px the page "?" popover on the stay-fee page runs past the right edge and the `help_tip` "?" tooltip on the fee register row runs past the left edge. Fix both once, in the shared components, so every opened help popover or tooltip stays inside the viewport with a 16 px gutter (320 and 390 px included), and add a layout-lint test so this is caught automatically from now on (design-system: "Fix the shared component").

## 2. Context

Rules: design-system rule 7 and the Help "?" row ("Popover opens next to the icon, max 360 px, fits the 390 px screen"); AGENTS.md hard rules 6 (light mode, no JS needed for auth forms) and 7 (browser + geometry tests 0 skipped, one 390 px screenshot per changed page). Evidence: `docs/tasks/0912-report.md`, `docs/tasks/screenshots-0912/help-390.png` and `fee-row-tip-390.png`.

There are two shared components. Both are verified by reading the code; the first by matching the screenshot numbers.

### A. Page "?" on list pages: `details.stays-how` (stay fees, invoices, reports, housebook)

Used by `App/app/templates/stay_fees.html:17-19`, `invoices.html:18-19`, `submissions.html:18-19`, `housebook.html:30-31` (all `<div class="head-title-row"><h1 class="big">...</h1><details class="ui-how stays-how">`). It is NOT the `page_help()` macro (that one is a centred fixed card and fits: measured 16..304 at 320 and 35..355 at 390 on /apartments).

Root cause, `App/app/static/app2.css:1038` and `:1040`:

```css
body.v2 .head-title-row>details.stays-how{position:relative;margin:0}
body.v2 .head-title-row>details.stays-how[open] .ui-how-body{position:absolute;top:calc(100% + 8px);left:0;z-index:30;width:min(520px,calc(100vw - 32px));box-sizing:border-box;padding:...
```

The body is anchored at `left:0` of the 44 px `<details>`, which sits right after the title (x about 143 at 390 px), and its width is `min(520px, 100vw - 32px)` = 358 px. So its right edge is 143 + 358 = 501 px, past the 390 px screen. The width clamp ignores where the box starts.

### B. `help_tip(...)` "?" tooltip (shared macro `_components.html:10-16`, positioned by `app.js` `place()`)

`App/app/static/app.js:1972-2003` (`function place(tip)` inside `initHelpTips`). On screens under 1024 px it clears `body.style.width` and `body.style.left` and sets only `top`; the horizontal position then comes from whichever of many conflicting CSS rules wins for that page (`app2.css:1606-1607` `left:16px;right:16px`; `app2.css:1801-1804` lane pages `left:0` + `position:fixed`; `app2.css:1921` `left:0`; plus `margin-left` and `help-tip-end` rules). The JS computes a clamped `left` (line 1988-1989) and then throws it away on phones. Any page where the winning rule or a containing block differs puts the box off the left edge (the fee row, `fee-row-tip-390.png`). Fix: the JS becomes the single authority and writes inline `position/left/top/width`, which beats every stylesheet rule, and corrects for a non-viewport containing block by measuring it.

Exact current code (anchor, must match verbatim):

```js
    function place(tip) {
      var btn = tip.querySelector(".help-tip-btn");
      var body = tip.querySelector(".help-tip-body");
      var margin = 8;
      var vw = document.documentElement.clientWidth;
      var vh = window.innerHeight;
      var wide = vw >= 1024;
      if (wide) {
        body.style.width = Math.min(320, vw - 2 * margin) + "px";
      } else {
        body.style.width = "";
        body.style.left = "";
      }
      var r = btn.getBoundingClientRect();
      var w = body.offsetWidth || Math.min(320, vw - 2 * margin);
      var h = body.offsetHeight;
      var left = tip.classList.contains("help-tip-end") ? r.right - w : r.left;
      left = Math.max(margin, Math.min(left, vw - w - margin));
      var top = r.bottom + 6;
      if (top + h > vh - margin && r.top - 6 - h >= margin) top = r.top - 6 - h;
      top = Math.max(margin, Math.min(top, vh - h - margin));
      if (wide) {
        // Desktop: the body is absolutely positioned inside .help-tip, so the viewport
        // coordinates must be made relative to its offset parent (else it drifts right).
        var ob = body.offsetParent ? body.offsetParent.getBoundingClientRect() : { left: 0, top: 0 };
        body.style.left = (left - ob.left) + "px";
        body.style.top = (top - ob.top) + "px";
      } else {
        body.style.top = top + "px";
      }
    }
```

The no-JS case is unchanged: `.help-tip:not([data-js])` keeps the CSS-only `:focus-within`/`:hover` display; the page "?" is a native `<details>` and works without JS.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app2.css` | edit | Add one `@media (max-width:1023px)` block after line 1213 (fix A) |
| `App/app/static/app.js` | edit | Replace the body of `place()` (fix B) |
| `App/app/templates/base.html` | edit | Bump `?v=` on lines 22 (`app2.css`) and 44 (`app.js`) |
| `App/tests/static_versions.json` | regenerate | `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_layout_lint_browser.py` | edit | New test `test_opened_help_stays_inside_the_viewport` (+ small shared route helper) |
| `docs/design/design-system.md` | edit | Help "?" row (line 31): add "16 px gutter; app.js place() and the layout-lint test enforce it." |
| `docs/tasks/screenshots-0912b/*.png` | add | 8 screenshots (see 6) |
| `docs/tasks/0912b-report.md` | add | The report (section 9 of TEMPLATE) |

No other file may change. `layout_lint.js` is not needed. Throwaway scripts go in the scratchpad directory, not in the repo.

## 4. Steps

1. Set `Status: in-progress` on this brief. Confirm the anchors: `grep -n 'details.stays-how\[open\] .ui-how-body' App/app/static/app2.css` shows line 1040 and `grep -n 'function place' App/app/static/app.js` shows 1972. If an excerpt in section 2 is not found verbatim, STOP (section 8).

2. **Fix A, `app2.css`.** Insert this block on its own lines directly after line 1213 (`body.v2 .head-title-row>details.stays-how{background:transparent;...}`). It later wins over line 1040 at equal specificity, and beats `host2.css:715` (`.host-workspace .ui-how-body{max-width:40rem}`) because it is more specific. The title row is a full-width flex row (`app2.css:1037`), so the box spans the page column below the title, never past either edge:

```css
/* 0912b: below desktop the page-help box is anchored to the full-width title row, not to the 44 px <details>,
   so it can never start at the icon and run past the right edge. Max 360 px, 16 px gutter on a 320 px phone. */
@media (max-width:1023px){
body.v2 .head-title-row:has(>details.stays-how){position:relative}
body.v2 .head-title-row>details.stays-how{position:static}
body.v2 .head-title-row>details.stays-how[open] .ui-how-body{left:0;right:0;width:auto;max-width:min(360px,calc(100vw - 32px))}
}
```

3. **Fix B, `app.js`.** Replace the whole `place()` function (the verbatim excerpt in section 2) with exactly this:

```js
    function place(tip) {
      var btn = tip.querySelector(".help-tip-btn");
      var body = tip.querySelector(".help-tip-body");
      var margin = 16; /* 0912b: 16 px gutter on every side, max 360 px, so a tooltip never leaves a 320 px phone */
      var vw = document.documentElement.clientWidth;
      var vh = window.innerHeight;
      var wide = vw >= 1024;
      var width = Math.min(wide ? 320 : 360, vw - 2 * margin);
      body.style.width = width + "px";
      body.style.maxWidth = width + "px";
      if (!wide) {
        /* Phones: inline styles beat every page-level rule; the JS owns the position. */
        body.style.position = "fixed";
        body.style.right = "auto";
        body.style.left = "0px";
        body.style.top = "0px";
      } else {
        body.style.position = "";
        body.style.right = "";
      }
      var r = btn.getBoundingClientRect();
      var w = body.offsetWidth || width;
      var h = body.offsetHeight;
      var left = tip.classList.contains("help-tip-end") ? r.right - w : r.left;
      left = Math.max(margin, Math.min(left, vw - w - margin));
      var top = r.bottom + 6;
      if (top + h > vh - margin && r.top - 6 - h >= margin) top = r.top - 6 - h;
      top = Math.max(margin, Math.min(top, vh - h - margin));
      if (wide) {
        // Desktop: the body is absolutely positioned inside .help-tip, so the viewport
        // coordinates must be made relative to its offset parent (else it drifts right).
        var ob = body.offsetParent ? body.offsetParent.getBoundingClientRect() : { left: 0, top: 0 };
        body.style.left = (left - ob.left) + "px";
        body.style.top = (top - ob.top) + "px";
      } else {
        /* The box sits at left:0 / top:0 now, so its rect is the origin of its containing block
           (0,0 when fixed to the viewport; non-zero inside a transformed ancestor). Correct for it. */
        var o = body.getBoundingClientRect();
        body.style.left = (left - o.left) + "px";
        body.style.top = (top - o.top) + "px";
      }
    }
```

4. **Cache keys.** In `App/app/templates/base.html` change `app2.css?v=0897c` to `app2.css?v=20261104-0912b` and `app.js?v=20261104-0100` to `app.js?v=20261104-0912b`. Then, from `App/`: `.venv/bin/python tests/test_static_versions.py --write | tail -30`, and check `git diff --stat` shows only `static_versions.json` entries for `app.js` and `app2.css` changed (new sha256 and `v`).

5. **Lint test, `App/tests/test_layout_lint_browser.py`.** (a) Extract the route-building lines at the top of `test_every_host_page_passes_the_layout_lint` (the `subst = dict(...)` and `routes = {...}` statements) into `def _route_map(wide_host): ... return routes` placed above it, and call it from there; behaviour must not change. (b) Check `grep -n 'stay' App/tests/test_design_guardrails_browser.py` for the stay-fee list route; if `/stay-fees` is not in `ROUTES`/`EXTRA_ROUTES`, add `"stay-fees": "/stay-fees"` to `EXTRA_ROUTES`. (c) Add this test at the end of the file:

```python
HELP_BOX_JS = """() => {
  const pick = [
    '.help-tip.is-open > .help-tip-body',
    'details.page-help[open] > .page-help-body',
    'details.ui-how[open] .ui-how-body',
  ];
  for (const sel of pick) {
    for (const el of document.querySelectorAll(sel)) {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (!r.width || cs.position === 'static') continue;
      return {sel, left: r.left, right: r.right, width: r.width, vw: document.documentElement.clientWidth};
    }
  }
  return null;
}"""


def test_opened_help_stays_inside_the_viewport(wide_host, wide_base):
    """0912b: an opened page "?" or "?" tooltip keeps a 16 px gutter at 320 and 390 px (and never exceeds 360 px)."""
    routes = _route_map(wide_host)
    bad: list[str] = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the help-fit check")
        for width in (320, 390):
            context = browser.new_context(viewport={"width": width, "height": 800})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/"}])
            page = context.new_page()
            for name, path in routes.items():
                sep = "&" if "?" in path else "?"
                page.goto(f"{wide_base}{path}{sep}lang=en")
                _wait_for_host_layout(page)
                _dismiss_optional_security_prompt(page)
                triggers = page.locator("details.page-help > summary, details.stays-how > summary, .help-tip-btn")
                for i in range(min(triggers.count(), 12)):
                    trigger = triggers.nth(i)
                    if not trigger.is_visible():
                        continue
                    trigger.scroll_into_view_if_needed()
                    trigger.click()
                    page.wait_for_timeout(120)
                    box = page.evaluate(HELP_BOX_JS)
                    if box and (box["left"] < 15.5 or box["right"] > box["vw"] - 15.5 or box["width"] > 360.5):
                        bad.append(f"{name}@{width} trigger {i}: {box}")
                    page.keyboard.press("Escape")
                    page.evaluate("document.querySelectorAll('details[open].page-help, details[open].ui-how').forEach(d => { d.open = false; })")
            context.close()
        browser.close()
    assert not bad, "opened help leaves the 16 px gutter:\n" + "\n".join(bad[:15])
```

Before step 2 changes are applied this test must FAIL on the stay-fees, invoices, reports or housebook route (prove it: run it once with `git stash` of the CSS and JS edits only if you still have budget; otherwise state in the report that the failing run was not done). After steps 2 and 3 it must pass.

6. **Screenshots (not committed as scripts).** Write a throwaway Playwright script in the scratchpad that reuses the `wide_host`/`wide_base` fixtures the same way, or run it as a temporary test file in `App/tests/` that you delete afterwards. For each of 320, 390, 768, 1280 take two screenshots (viewport shot, not full page) into `docs/tasks/screenshots-0912b/`:
   - `help-open-<w>.png`: `/stay-fees`, click `details.stays-how > summary`.
   - `fee-row-tip-<w>.png`: the stay-fee register row with the "Resident of this municipality" `?` tooltip open. That row comes from brief 0912 (`stay_fee_detail.html`, key `stay_fees.label.obec_resident`). Find a seeding helper with `grep -ln 'obec_resident\|Resident of this municipality' App/tests/*.py` and reuse it. If you cannot get the row seeded within 6 tool calls, take the tooltip shot on any page with a `.help-tip-btn` and say so in the report.
   Open every screenshot with Read and write one line per image in the report: fits or not.

7. **Design-system line** in `docs/design/design-system.md` line 31 (Help "?" row), append the sentence from section 3. Then `python3 scripts/design_lint.py | tail -30` and `python3 scripts/context_lint.py | tail -30`.

8. Write `docs/tasks/0912b-report.md` (max 600 tokens, section 9 of TEMPLATE), set `Status: review`. Do not commit, do not push.

## 5. Do not touch

`App/app/templates/_components.html` (the macro markup stays), `layout_lint.js`, any other CSS or JS file, `host_i18n.py` and the other 0912 files, `static/guest*` and guest pages. No new dependency, no inline `<style>`, no raw colours. Hard rules 6 (light mode only; auth forms still work without JS) and 7 apply. The no-JS CSS paths (`.help-tip:not([data-js])`, native `<details>`) must keep working: do not add JS-only gating.

## 6. Commands

From `App/`, each ending `| tail -30`:

```
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -rs -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_0505_row_menus_help_tips_once_browser.py tests/test_stay_fee*.py -q --tb=short -rs 2>&1 | tail -30
.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -30
```

Expect: all passed, `0 skipped` (no `s` in the summary, no SKIPPED lines from `-rs`). From the repo root: `python3 scripts/design_lint.py | tail -30` and `python3 scripts/context_lint.py | tail -30` OK (pre-existing WARN lines are fine). If the second command shows a test of the old `?v=` string or the old `place()` width ("320px") failing, fix only that expectation if it is in a test file; otherwise STOP.

## 7. Acceptance

- [ ] `app2.css` has the one new media block; `app.js` `place()` uses `margin = 16`, writes inline `position/left/top/width` on phones and measures the containing block.
- [ ] `test_opened_help_stays_inside_the_viewport` exists, passes at 320 and 390 on every host route, and covers `details.stays-how` and `.help-tip-btn`.
- [ ] Layout lint and geometry commands in section 6: green, 0 skipped.
- [ ] `base.html` `?v=` bumped for `app2.css` and `app.js`; `static_versions.json` regenerated; `test_static_versions.py` green.
- [ ] 8 screenshots in `docs/tasks/screenshots-0912b/` (help open and fee-row tooltip at 320, 390, 768, 1280), each opened and described in the report; every opened box sits at least 16 px inside both screen edges at 320 and 390.
- [ ] Opened help box on `/stay-fees` at 390: text fully readable, "More in the guide" visible, box not wider than 360 px.
- [ ] Design-system line added; design and context lints OK.
- [ ] No file outside section 3 changed (`git status --short` checked); no commit, no push.

## 8. Stop and ask

Stop and write the report as `blocked` if: an excerpt is not found verbatim; a test fails twice; you reach 25 tool calls or about 50k tokens; the new test finds an overflow on a page that neither fix A nor fix B covers (for example `.ov-head details.ui-how` at `app2.css:232` or `.props-head details.ui-how` at `app2.css:1897`): list the page, selector and numbers in the report and ask, do not widen the change; a file outside section 3 needs a change; a new dependency seems needed.

## 9. Report

Write `docs/tasks/0912b-report.md` as in TEMPLATE section 9: files changed (`git diff --stat`), each command with the last 5 output lines, section 7 ticked, one line per screenshot (fits or not), deviations, questions, owner steps left (none expected).

## Risk list (for the reviewer)

Read the full diff of `App/app/static/app.js` (`place()`: a shared component used on every host page, including the no-JS fallback and the desktop branch, which must be unchanged except the 16 px margin and `position`/`right` reset) and of the new block in `App/app/static/app2.css`.

## Owner steps

None until the orchestrator merges with `scripts/merge-pr-on-green.sh`. The production deploy stays manual.
