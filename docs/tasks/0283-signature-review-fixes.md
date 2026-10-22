# 0283: Signature review fixes: font-face in tokens, dialog tabs

Status: todo
Depends on: 0282 | Base commit: 1330daa | Branch: claude/project-thread-j2cl8a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Two fixes from the 0282 review: the design lint (S1) forbids `font-family:` outside `tokens.css`, so the `@font-face` moves there; and the Draw/Type tabs in the signing dialog render as boxed buttons with no visible selected state, because `.ui-tab` only styles links (`aria-current`).

## 2. Context

`App/app/static/host2.css` line (from 0282):
```css
@font-face { font-family: "UbyHost Signature"; src: url("/static/fonts/DancingScript.ttf?v=20261022-0282") format("truetype"); font-weight: 400 700; font-display: swap; }
```
`App/app/static/host2.css`:
```css
.host-workspace .ui-tab[aria-current="page"] { color: var(--ink); border-color: var(--ink); }
```
`tokens.css` is linked from many templates with different `?v=` keys (`grep -rn "tokens.css?v=" App/app/templates`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | edit | remove @font-face; button tabs |
| App/app/static/tokens.css | append | @font-face |
| every template linking `tokens.css?v=` | edit | new key `20261022-0283` |
| App/app/templates/base.html | edit | also `host2.css?v=20261022-0283` |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_0282_signature_dialog_browser.py | edit | one tab assertion |

## 4. Steps

1. Delete the `@font-face` line from `host2.css` and append it unchanged to the end of `App/app/static/tokens.css`, preceded by the comment `/* 0282: handwriting font for typed signatures (Dancing Script, SIL OFL 1.1). */`.
2. In `host2.css`, directly below the `.ui-tab[aria-current="page"]` line, add:
```css
.host-workspace button.ui-tab { background: none; border: 0; border-bottom: 2px solid transparent; border-radius: 0; font: inherit; font-size: var(--size-14); font-weight: 600; color: var(--ink-2); cursor: pointer; }
.host-workspace .ui-tab[aria-selected="true"] { color: var(--ink); border-bottom-color: var(--ink); }
```
3. Change every `tokens.css?v=<anything>` in `App/app/templates` to `tokens.css?v=20261022-0283` (one `sed -i -E 's/tokens\.css\?v=[^"]+/tokens.css?v=20261022-0283/g'` over the files `grep -rl` lists), and `host2.css?v=20261022-0282` in `base.html` to `host2.css?v=20261022-0283`. Then `.venv/bin/python tests/test_static_versions.py --write` from `App/` (or the write command the test names).
4. In `test_0282_signature_dialog_browser.py`, after switching to the Type tab, assert the Type tab's computed `border-bottom-color` differs from the Draw tab's.
Commit each step as `0283 step k`.

## 5. Do not touch

`host.js`, the macro, Python. Hard rules 6, 7.

## 6. Commands

From `App/` with `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`:
- `.venv/bin/python -m pytest tests/test_0282_signature_dialog_browser.py tests/test_static_versions.py tests/test_design_lint.py tests/test_design_guardrails_browser.py tests/test_design_tokens.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
- `.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -5` if the script runs standalone.

## 7. Acceptance

- [ ] Design lint passes; all §6 tests pass, 0 skipped.
- [ ] Re-shoot the dialog at 390 and 1280 into `/mnt/project-files/notify-sign/0283/` (same method as 0282 step 7): the selected tab is underlined, the other is plain text.

## 8. Stop and ask

As in TEMPLATE §8. Never commit files under `docs/tasks/0102-evidence/` (other tests write there).

## 9. Report

`docs/tasks/0283-report.md`, as in TEMPLATE §9.
