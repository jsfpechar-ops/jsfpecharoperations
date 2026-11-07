# 1003: Help "?" boxes anchored to the button, hover and focus, restyled card

Status: todo
Depends on: none | Base commit: HEAD of main when you start | Branch: task/1003-ux-help-tips
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every "?" help box opens right below (or above) its own button instead of in the middle of the screen, shows on hover and keyboard focus on mouse devices, stays tap-to-open on touch, and uses one restyled card (readable lists, "More in the guide" as an accent link with an arrow). Two components are involved: the page "?" next to titles (`page_help`, a `<details>`, the one that opens centred) and the field "?" (`help_tip`, already anchored, only restyled).

## 2. Context

Rules: light mode only; auth forms work without JS; copy rule 9 (no new copy; the arrow is CSS only); host UX gate (AGENTS rule 10); no new dependency; no anchor positioning (it is used in the repo only for `host2.css` account menu, not for these boxes), so a small JS function positions the page-help box. Read nothing else; grep, then ranges of 150 lines or fewer.

Facts already checked by the orchestrator:

- `help_tip` (`App/app/templates/_components.html` line 10 to 15) renders `<span class="help-tip" data-help-tip><button class="help-tip-btn" aria-expanded aria-controls=ID>?</button><span class="help-tip-body" id=ID role="tooltip">...</span></span>`. Its JS `initHelpTips` (`App/app/static/app.js` ~1926 to 2075) ALREADY does hover (mouse only), focus-visible, click toggles pinned, Esc, outside click, 150 ms `closeSoon`, and anchors the box under/above the button via `place()`. Only its width (360 on phones) and card styling change. Do not touch its markup, aria or event wiring.
- `page_help(how)` (`_components.html` line 18 to 21) is `<span class="page-help-wrap"><details class="page-help" data-how data-lint-ignore><summary class="page-help-btn" aria-label=...><span class="page-help-dot">?</span></summary><div class="page-help-body"><ol class="page-help-steps"><li>..</li></ol><a class="page-help-more" href="/guide#..">{{ t('how.more') }}</a></div></details></span>`. It has NO JS; the native `<details>` toggles on click. CSS `app2.css` line 2158 makes the open body `position:fixed; top:50%; transform:translateY(-50%)`, which centres it on screen. Lines 2159 to 2161 style `.page-help-steps` (browser-default look) and `.page-help-more` (bold, underlined, plain ink).
- Keep the markup of both macros. Existing browser tests find `.page-help-body`, `.page-help-btn`, `.page-help-dot`, `details.page-help[open]`, `.help-tip-body`, `.help-tip-btn`, `.help-tip.is-open`; none may break.
- Layout lint rule `help-stranded` (`tests/layout_lint.js` ~line 205 to 252, brief 0790) checks the "?" stays beside its label; this brief moves only the box, never the "?" (brief 0993 keeps the dashboard "?" inline; do not touch that).
- Tokens exist (tokens.css): `--surface`, `--line`, `--ink`, `--ink-2`, `--accent-ink`, `--accent`, `--shadow-2`, `--focus-ring-2`.
- Cache keys now: `base.html` line 22 `/static/app2.css?v=20261107-1010`, line 44 `/static/app.js?v=20261106-pr790-ux-js`.

Anchors (each must be found verbatim, else STOP):

`App/app/static/app2.css` line 2157 and the start of 2158:
```
body .page-help:not([open]) > .page-help-body{display:none}
body .page-help[open] > .page-help-body{display:block;position:fixed;z-index:60;left:0;right:0;top:50%;width:min(360px,calc(100% - 32px));
```
`app2.css` lines 2159 to 2161:
```
body .page-help-steps{margin:0 0 12px;padding-left:20px}
body .page-help-steps li{margin:0 0 6px}
body .page-help-more{display:inline-block;min-height:44px;line-height:44px;color:#222;font-weight:600;text-decoration:underline}
```
`app2.css` lines 1613 and 1614 (start of each):
```
body.v2 .help-tip.is-open>.help-tip-body,body.v2 .help-tip:not([data-js]):focus-within>.help-tip-body{display:block;position:absolute;z-index:70;left:0;top:100%;margin:6px 0 0;box-sizing:border-box;width:min(320px,calc(100vw - 32px));padding:10px 12px;background:var(--s);color:var(--ink);border:1px solid var(--line);border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.12);font-size:13px;
@media (max-width:1023px){body.v2 .help-tip.is-open>.help-tip-body{position:fixed;left:16px;right:16px;width:auto;top:auto}}
```
`app.js` in `place(tip)`:
```
      var width = Math.min(wide ? 320 : 360, vw - 2 * margin);
```
`app.js` init list (around line 2455):
```
    initHelpTips();
    initBirthDateInputs();
```
`app.js` last line of `initHelpTips`'s body, directly before the closing of the function (the `reflow` block):
```
      window.addEventListener("scroll", reflow, { capture: true, passive: true });
    }
  }
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app.js | edit | width 320 for help_tip; new `initPageHelp()` (hover, focus, anchor, outside tap, Esc) and its call |
| App/app/static/app2.css | edit | edit lines 1613 (font, radius, padding), append card and page-help rules after line 2161 |
| App/app/templates/base.html | edit | bump the two cache keys |
| App/tests/test_host_help_browser.py | edit | add one anchoring test for `help_tip` |
| App/tests/test_0830_airbnb_pages_browser.py | edit | add an anchoring assertion for the page "?" |

No other file may change.

## 4. Steps

1. `app.js` `place()`: replace the anchor `var width = Math.min(wide ? 320 : 360, vw - 2 * margin);` with `var width = Math.min(320, vw - 2 * margin);`. Check: `grep -n "Math.min(320, vw" App/app/static/app.js | tail -30` prints one line.

2. `app.js`: directly after the closing `}` of `initHelpTips` (the `  }` after the `scroll` listener anchor above), insert this function (2-space indent, same IIFE scope):
```js
  /* 1003: the page "?" (details.page-help). Mouse: hover or keyboard focus opens it under the dot (above if no room),
     leaving closes after 150 ms, click pins it. Touch: tap toggles, tap outside closes. Esc closes. No JS: native details. */
  var pageHelpState = { current: null, timer: null };
  function initPageHelp() {
    var items = Array.prototype.slice.call(document.querySelectorAll("details.page-help"));
    if (!items.length) return;
    var hoverOk = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)");
    function place(d) {
      var body = d.querySelector(".page-help-body");
      var dot = d.querySelector(".page-help-dot") || d.querySelector("summary");
      if (!body || !dot || !d.open) return;
      var m = 8;
      var vw = document.documentElement.clientWidth;
      var vh = window.innerHeight;
      var w = Math.min(320, vw - 2 * m);
      body.style.width = w + "px";
      body.style.maxWidth = w + "px";
      body.style.position = "fixed";
      body.style.right = "auto";
      body.style.margin = "0";
      body.style.transform = "none";
      body.style.left = "0px";
      body.style.top = "0px";
      var r = dot.getBoundingClientRect();
      var h = body.offsetHeight;
      var left = Math.max(m, Math.min(r.left - 8, vw - w - m));
      var top = r.bottom + 8;
      if (top + h > vh - m && r.top - 8 - h >= m) top = r.top - 8 - h;
      top = Math.max(m, Math.min(top, vh - h - m));
      var o = body.getBoundingClientRect(); /* origin of the containing block (non-zero inside a transformed ancestor) */
      body.style.left = (left - o.left) + "px";
      body.style.top = (top - o.top) + "px";
    }
    function close(d) {
      d.open = false;
      d.removeAttribute("data-pinned");
      if (pageHelpState.current === d) pageHelpState.current = null;
    }
    function show(d, pinned) {
      if (pageHelpState.current && pageHelpState.current !== d) close(pageHelpState.current);
      window.clearTimeout(pageHelpState.timer);
      pageHelpState.current = d;
      d.open = true;
      if (pinned) d.setAttribute("data-pinned", "1");
      place(d);
    }
    function closeSoon(d) {
      window.clearTimeout(pageHelpState.timer);
      pageHelpState.timer = window.setTimeout(function () {
        if (!d.hasAttribute("data-pinned") && !d.contains(document.activeElement)) close(d);
      }, 150);
    }
    items.forEach(function (d) {
      if (!claimNode(d, "initPageHelp")) return;
      var summary = d.querySelector("summary");
      d.addEventListener("toggle", function () { if (d.open) place(d); });
      if (summary) {
        summary.addEventListener("click", function (e) {
          e.preventDefault(); /* we own open/close, so hover and click never fight over the native toggle */
          if (d.open && d.hasAttribute("data-pinned")) close(d);
          else show(d, true);
        });
        summary.addEventListener("focus", function () {
          if (hoverOk && hoverOk.matches && summary.matches(":focus-visible")) show(d, false);
        });
      }
      d.addEventListener("pointerenter", function (e) {
        if (e.pointerType === "mouse" && hoverOk && hoverOk.matches) show(d, false);
      });
      d.addEventListener("pointerleave", function (e) {
        if (e.pointerType === "mouse" && hoverOk && hoverOk.matches) closeSoon(d);
      });
      d.addEventListener("focusout", function (e) {
        if (!d.contains(e.relatedTarget) && !d.hasAttribute("data-pinned")) close(d);
      });
    });
    if (claimNode(document, "initPageHelp")) {
      document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape" || !pageHelpState.current) return;
        var d = pageHelpState.current;
        close(d);
        var s = d.querySelector("summary");
        if (s) s.focus();
      });
      document.addEventListener("click", function (e) {
        if (pageHelpState.current && !pageHelpState.current.contains(e.target)) close(pageHelpState.current);
      });
      function reflow() { if (pageHelpState.current) place(pageHelpState.current); }
      window.addEventListener("resize", reflow);
      window.addEventListener("scroll", reflow, { capture: true, passive: true });
    }
  }
```
   Then in the init list replace `    initHelpTips();\n    initBirthDateInputs();` with `    initHelpTips();\n    initPageHelp();\n    initBirthDateInputs();`. Check: `grep -n "initPageHelp" App/app/static/app.js | tail -30` prints 4 lines (declaration, call, two `claimNode` uses).

3. `app2.css` line 1613: in that one line replace `padding:10px 12px;background:var(--s);color:var(--ink);border:1px solid var(--line);border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.12);font-size:13px;` with `padding:12px 14px;background:var(--s);color:var(--ink);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow-2);font-size:14px;` and `width:min(320px,calc(100vw - 32px))` with `width:min(320px,calc(100vw - 16px))`. The rest of the line (font-weight, line-height:1.45, text-align, white-space) stays. Line 1614 stays unchanged (inline styles from `place()` win).

4. `app2.css`: insert directly after line 2161 (`body .page-help-more{...}`) this block (later rules of equal or higher specificity override 2158 to 2161, the old lines stay):
```css
/* 1003: one help card. Page "?" opens under its dot (JS sets left/top; this is the no-JS fallback under the button). */
body .page-help[open]>.page-help-body{position:absolute;left:0;right:auto;top:100%;margin:8px 0 0;transform:none;width:min(320px,calc(100vw - 16px));max-width:calc(100vw - 16px);max-height:min(70vh,calc(100vh - 16px));padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);box-shadow:var(--shadow-2);font-size:14px;line-height:1.45}
body :is(.page-help-body,.help-tip-body) :is(p,ol,ul){margin:0 0 8px}
body :is(.page-help-body,.help-tip-body) :is(ol,ul){padding-left:18px}
body :is(.page-help-body,.help-tip-body) li{margin:0 0 6px;padding-left:2px}
body :is(.page-help-body,.help-tip-body) li:last-child{margin-bottom:0}
body :is(.page-help-body,.help-tip-body) :is(p,ol,ul):last-child{margin-bottom:0}
body .page-help-body .page-help-more,body .help-tip-body a{display:inline-flex;align-items:center;gap:4px;min-height:32px;margin-top:4px;color:var(--accent-ink);font-weight:500;line-height:1.45;text-decoration:none}
body .page-help-body .page-help-more::after{content:"\2192";font-weight:400}
body .page-help-body .page-help-more:hover,body .help-tip-body a:hover{text-decoration:underline}
body .page-help-body .page-help-more:focus-visible,body .help-tip-body a:focus-visible{outline:0;box-shadow:var(--focus-ring-2);border-radius:4px}
```
   Check: `grep -c "1003: one help card" App/app/static/app2.css | tail -30` prints 1.

5. `base.html`: line 22 value after `/static/app2.css?v=` becomes `20261107-1003`; line 44 value after `/static/app.js?v=` becomes `20261107-1003`. Check: `grep -n "20261107-1003" App/app/templates/base.html | tail -30` prints 2 lines.

6. `tests/test_host_help_browser.py`: append one test after `test_help_tip_interactions_aria_and_fit`, reusing the helpers and constants of that file (`_context`, `_open_page`, `BTN`, `TIP`, `host`, `base`, `sync_playwright` as it is imported there, `chromium_launch_kwargs`):
```python
def test_1003_help_tip_opens_under_its_button_on_hover_and_focus(host, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in (390, 1280):
            context = _context(browser, host, base, width)
            page = _open_page(context, base, host, "en")
            button = page.locator(BTN)
            tip = page.locator(TIP)
            if width == 1280:
                button.hover()
                tip.wait_for(state="visible")
                assert button.get_attribute("aria-expanded") == "true"
                page.mouse.move(2, 2)
                tip.wait_for(state="hidden", timeout=2000)
            button.click()
            tip.wait_for(state="visible")
            b, t = button.bounding_box(), tip.bounding_box()
            below = 0 <= t["y"] - (b["y"] + b["height"]) <= 16
            above = 0 <= b["y"] - (t["y"] + t["height"]) <= 16
            assert below or above, (width, b, t)
            assert 0 <= t["x"] and t["x"] + t["width"] <= width - 8 + 0.5, (width, t)
            assert t["width"] <= 320.5, (width, t)
            page.keyboard.press("Escape")
            tip.wait_for(state="hidden")
            context.close()
        browser.close()
```
   If the file's imports use another name than `sync_api`, copy the name used by `test_help_tip_interactions_aria_and_fit`.

7. `tests/test_0830_airbnb_pages_browser.py`: in the page-help test (`test_0831G_page_help`, around line 354 to 365), directly after the line `pb = body.bounding_box()` and `viewport = page.viewport_size`, add:
```python
                    dot_box = page.locator(".page-help-dot").first.bounding_box()
                    gap_below = pb["y"] - (dot_box["y"] + dot_box["height"])
                    gap_above = dot_box["y"] - (pb["y"] + pb["height"])
                    if not (0 <= gap_below <= 24 or 0 <= gap_above <= 24):
                        problems.append(f"{path} {width}: help body is not anchored to its ? ({gap_below:.0f}/{gap_above:.0f})")
                    if pb["width"] > 320.5:
                        problems.append(f"{path} {width}: help body is {pb['width']:.0f} px wide")
```
   (Keep the indentation of the surrounding lines; the existing visibility and viewport check below it stays.)

## 5. Do not touch

`_components.html` markup, `host2.css`, `host-design0123.css`, `layout_lint.js`, the dashboard "?" placement (0993), `host_i18n.py`, `help_tip` event wiring, other `<details>` (`.ui-how`, `.stays-how`). AGENTS rules: no new dependency, no new outbound request, no new personal-data field, no tracking cookies, light mode only, never silence a layout-lint finding.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_host_*.py -q --tb=short -x -k "help or tooltip" 2>&1 | tail -30` expect pass (non-browser).
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_help_browser.py tests/test_0830_airbnb_pages_browser.py tests/test_0896_ux_fixes_browser.py tests/test_0505_row_menus_help_tips_once_browser.py -q --tb=short -x 2>&1 | tail -30` expect pass, 0 skipped.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0786_settings_geometry_browser.py tests/test_host_geometry.py -q --tb=short -x -k "help" 2>&1 | tail -30` expect pass, 0 skipped.
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` green, 0 skipped, zero host findings (watch `help-stranded`). Then read `/tmp/shots/layout-lint/{properties,stays,dashboard}-{390,768,1280}.png`, and take 390 / 768 / 1280 screenshots of the Properties page with the page "?" hovered (1280) or tapped (390, 768) and of one field "?" open (a settings page), using the Playwright helper of `test_0830_airbnb_pages_browser.py`.
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Page "?": box opens directly below the dot (above if no room), never centred on screen; hover and keyboard focus open it on a mouse device, leaving closes it after about 150 ms, click pins it, Esc and a tap outside close it; touch tap toggles.
- [ ] Field "?" (`help_tip`): same behaviour as before, width at most 320 px and at most viewport minus 16 px at 320 and 390 px.
- [ ] Card: 12 px radius, 1px `--line` border, soft shadow, 14 px text, 1.45 line height; lists 18 px indent with 6 px between items; paragraphs 8 px apart; "More in the guide" is an accent-ink link with a trailing arrow, not bold, not underlined until hover.
- [ ] `aria-expanded` on the field "?", native expanded state on the page "?", `role="tooltip"` and `aria-controls` unchanged; the no-JS page "?" still opens (native details).
- [ ] Test-map rows pass with 0 skipped; layout lint zero findings; the PR body has per page "390: ...; 768: ...; 1280: ..." plus the design-system checklist ticked; one 390 px screenshot of each open box in the report.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- an existing test asserts the old centred position or a 16 px page-help gutter (report the test name; do not weaken it);
- a layout-lint finding appears that you cannot fix inside §3 (never silence it);
- you need push, merge, secrets, SSH or deploy (hand to the owner with the exact command).

## 9. Report

Write `docs/tasks/1003-report.md` (600 tokens at most) and set `Status: review`. It has: files changed (`git diff --stat`), each command with the last 5 lines, §7 ticked, deviations.
