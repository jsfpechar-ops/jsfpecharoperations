# 1067: Host pages, Q6: stylesheet duplicates (none to remove) and the blocking `platform.js`

Status: review
Depends on: none | Base commit: 0d851ca4 | Branch: task/1067-dedupe-css-defer-js
Executor: Sonnet 5.5 at medium effort (owner override; the template says Haiku) | Fits one session: 30 tool calls, 60k tokens
Tier: C (queue item 1.6, plan [speed-and-ease](../plans/speed-and-ease.md) section 5 row Q6)

## 1. Objective

`platform.js` is the only blocking script on host pages (a 1-line file that sets `data-mac` on `<html>`). Replace the blocking request with the same line inline in `<head>`, so it still runs before first paint. Plain `defer` is NOT used (finding B). The three "duplicate" stylesheet links are not duplicates (finding A): change nothing there and correct the plan.

## 2. Context

**Finding A: no duplicate stylesheets.** `App/app/templates/base.html` lines 21-40 contain `tokens.css`, `command.css` and `list-filter-compact.css` twice, but once in the `{% if v2 %}` branch and once in the `{% else %}` branch. A page renders one branch, so each is linked once. No child template links them again (grep over `App/app/templates`: `tokens.css` appears only in standalone shells such as `auth_base.html`, `landing.html`, `guest/base.html`, which do not extend `base.html`; `command.css` and `list-filter-compact.css` appear only in `base.html`). Hoisting `command.css` and `list-filter-compact.css` out of the branches WOULD change cascade order (v2: after `app2.css`; classic: after `components.css`), so do not. Hoisting `tokens.css` alone (first in both branches, same key) is safe but saves nothing; skip it. Result: no stylesheet change, no `?v=` bump.

**Finding B: plain `defer` is unsafe.** `App/app/static/platform.js` (whole file):

```
try{var p=(navigator.userAgentData&&navigator.userAgentData.platform)||navigator.platform||"";if(/mac|iphone|ipad|ipod/i.test(p))document.documentElement.setAttribute("data-mac","")}catch(e){}
```

`App/app/static/tokens.css:191-194` shows `.kbd-pc` ("Ctrl K") until `[data-mac]` is set, and its comment says platform.js sets it "before first paint". A deferred script runs after parsing, so Mac and iOS users could see a one-frame flash of "Ctrl K" then the Mac label. `App/tests/test_shortcut_hint_no_flash.py` guards exactly this. No other file calls into platform.js (grep: only `base.html:10`, the `tokens.css` comment, that test and `tests/static_versions.json`); it defines no globals, so nothing reads it synchronously. The CSP (`app/main.py` `_csp`) allows `'unsafe-inline'` scripts, and the line writes no storage (`test_cookie_inventory.py` scans inline scripts for storage writes and finds none). Inline in `<head>` keeps the no-flash behaviour and removes the request, which meets the intent of Q6 ("defer or inline"). It fits Tier C.

**Cache keys (decision 2026-10-19 [workflow], 0172).** Only static files carry `?v=`. No remaining static file changes content, so no key bumps; templates need no cache bump. `platform.js` is deleted, so `tests/static_versions.json` must be regenerated with `--write` (its `platform.js` entry goes away), which `test_the_manifest_is_current` requires.

**Auth forms.** The script is already skipped when `show_nav` is false and the inline line keeps the same guard. No form behaviour changes; no form needs JavaScript.

**Ordering.** 1064 and 1065 touch no template. Item 1.7 (Q7: `templating.py`, sidebar queries, `Server-Timing`) and 1066 (input attributes, form templates) should not touch `base.html` line 10 or `test_shortcut_hint_no_flash.py`. If either already changed `base.html`, the §4 anchor tells you. No required order.

Anchor, `App/app/templates/base.html` line 10, must be found verbatim:

```
  {% if show_nav | default(true) %}<script src="/static/platform.js?v=20261103-0920" data-turbo-track="reload"></script>{% endif %}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/base.html` | edit | line 10: inline script instead of `platform.js` |
| `App/app/static/platform.js` | delete | no longer referenced |
| `App/tests/test_shortcut_hint_no_flash.py` | edit | assert the inline line, in `<head>`, before `app.js` |
| `App/tests/static_versions.json` | regenerate | `--write` drops the `platform.js` entry |
| `docs/plans/speed-and-ease.md` | edit | correct the §4.7 rows and §5 row Q6 |

No other file may change.

## 4. Steps

1. Edit `App/app/templates/base.html`: replace line 10 (the anchor) with exactly:

```
  {% if show_nav | default(true) %}<script>try{var p=(navigator.userAgentData&&navigator.userAgentData.platform)||navigator.platform||"";if(/mac|iphone|ipad|ipod/i.test(p))document.documentElement.setAttribute("data-mac","")}catch(e){}</script>{% endif %}
```

   Command: `grep -c 'platform.js' App/app/templates/base.html; grep -c 'setAttribute("data-mac"' App/app/templates/base.html`. Expected: `0` then `1`.

2. Delete the file: `git rm App/app/static/platform.js`. Command: `grep -rn 'platform\.js' App/app --include=*.html --include=*.py --include=*.js | head`. Expected: no output. (The comment in `tokens.css:191` stays: editing a CSS file would force a `?v=` bump for no gain. Mention it in the report.)

3. Edit `App/tests/test_shortcut_hint_no_flash.py`: replace the first test with:

```python
def test_hint_markup_has_both_labels_and_head_sets_platform():
    base = (APP / "templates/base.html").read_text()
    head = base[: base.index("</head>")]
    assert 'setAttribute("data-mac"' in head, "the data-mac line must be inline in <head>"
    assert "/static/platform.js" not in base
    assert head.index('setAttribute("data-mac"') < head.index("/static/app.js")
    for name in ("_shell_v2.html", "_shell_sidebar.html"):
        html = (APP / "templates" / name).read_text()
        assert 'class="kbd-pc">Ctrl K' in html and 'class="kbd-mac">⌘ K' in html
```

   Leave `test_app_js_no_longer_rewrites_hint` unchanged. Command, from `App/`: `.venv/bin/python -m pytest tests/test_shortcut_hint_no_flash.py -q --tb=short -x 2>&1 | tail -30`. Expected: `2 passed`.

4. Regenerate the manifest, from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Expected: `wrote ... (N files)`, no `refusing:` line. Then `git diff --stat tests/static_versions.json | tail -3`: only the 4 lines of the `platform.js` entry deleted, 0 added. Any other entry changed: STOP.

5. Edit `docs/plans/speed-and-ease.md`. In the §4.7 table:
   - replace the row starting `| Up to 14 stylesheets, about 1.28 MB raw; ...` with `| Up to 14 stylesheets, about 1.28 MB raw. The three "duplicate" links in `base.html:21-40` sit in the v2 and classic branches, so none loads twice (1067 checked) | `templates/base.html:21-40` | Bundle per shell later |`
   - replace the row starting ``| `platform.js` is the only blocking script`` with ``| `platform.js` was the only blocking script; 1067 inlines it in `<head>` (defer would flash the Ctrl K hint on Mac) | `base.html:9` | Done |``
   In §5 change the Q6 "Win" text `Remove the 3 duplicate stylesheet links; defer `platform.js`` to `Inline the 1-line `platform.js` (no duplicate stylesheets exist, see 4.7); done by 1067`. Command: `grep -n 'Q6\|1067' docs/plans/speed-and-ease.md | head -5`. Expected: the new text. An anchor not found verbatim: STOP.

## 5. Do not touch

`App/app/static/*.css`, any other template, `main.py` CSP, any Python outside the test above. Hard rules: light mode only; auth forms work without JavaScript (unchanged); no new dependency; no third-party script.

## 6. Commands

From `App/`. Test-map rows: "Static files under App/app/static", "Any host template, host CSS or host JS", "Host pages". Browser runs use `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots`.

1. `.venv/bin/python -m pytest tests/test_shortcut_hint_no_flash.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_cookie_inventory.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.
2. `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30`. Expected: pass, 0 skipped.
3. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30`. Expected: pass, 0 skipped, zero host findings.
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. The only acceptable error is `docs/context/status.md` over its cap (fixed in PR #854).
5. Optional Mac check: in a Playwright Chromium host page with `navigator.platform` overridden to `MacIntel` through `add_init_script`, `page.evaluate("document.documentElement.hasAttribute('data-mac')")` is `true` at `domcontentloaded`.

## 7. Acceptance

- [ ] `grep -rn 'platform.js' App/app/templates | head` prints nothing.
- [ ] `base.html` `<head>` holds the inline `data-mac` line inside `{% if show_nav %}`.
- [ ] Commands 1 to 4 green, 0 skipped on browser files.
- [ ] `static_versions.json` diff removes only `platform.js`.
- [ ] UX gate (AGENTS rule 10): open `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` for every host page the lint renders (at least dashboard, reservations, properties, settings). The PR body says per page "390: ...; 768: ...; 1280: ..." and that the sidebar search hint reads "Ctrl K" on desktop with no layout shift. Expected: identical to main, since only a script moved.
- [ ] The design-system checklist (docs/design/design-system.md) is ticked in the PR body; nothing visual changed.
- [ ] Report states finding A (no duplicates), finding B (inline, not defer) and the stale `tokens.css:191` comment.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found verbatim (for example 1.7 or 1066 already changed `base.html` line 10);
- `test_static_versions.py --write` prints `refusing:` or changes any entry besides `platform.js`;
- a test fails twice, or a browser test is skipped;
- the layout lint reports a finding;
- a file outside §3 needs a change;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- you need push, merge, secrets, SSH or deploy (hand to the owner with the exact command).

## 9. Report

Write `docs/tasks/1067-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with the last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `App/app/templates/base.html` line 10: compare the inline script byte for byte with the deleted `platform.js`.
- `App/tests/test_shortcut_hint_no_flash.py`: the guard must still fail if the line leaves `<head>`.
- `App/tests/static_versions.json`: exactly one entry removed.

## Owner steps

1. When the executor's PR is open and CI is green, merge with `scripts/merge-pr-on-green.sh <PR number>`.
2. After the next deploy, open any host page on a Mac or iPhone and confirm the search hint shows the Mac label on first load.
