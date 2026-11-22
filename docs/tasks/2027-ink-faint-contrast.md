# 2027: `--ink-faint` clears AA, so the fine print is readable everywhere

Status: todo | Depends on: — | Branch: task/2027-ink-faint-contrast
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens | Tier: C (one token, wide blast radius)

## 1. Objective — measured 2026-11-22

`--ink-faint` is `#92928c` in `App/app/static/tokens.css:23`. Measured against the two surfaces it is used on:

| Surface | Contrast | AA for normal text (4.5:1) |
|---|---|---|
| white | **3.13:1** | fails |
| canvas | **2.92:1** | fails |

It is the colour of helper text, hints and fine print across the product — so this is a rule 7 (browser/geometry) and accessibility defect on every page that uses it, not one page's problem. For comparison, both pass: primary button **5.51:1**, coral links **6.90:1**.

Source: `docs/tasks/2019-ux-gate-2011-2018.md` (§ "Measured bonus").

**Good news, and the reason this brief is cheap:** the CSS is shared. `App/app/static` ships in the Go image (index §2.1, PR #1230), so **one token change fixes Go and Python together** and `docs/plans/staging-prod-identical.md` stays true without any `UBYHOST_GO_PATHS` step. This is also why it must not be done page-by-page.

## 2. Context

- `App/app/static/tokens.css` — `--ink-faint: #92928c` (line 23) and its alias `--faint` (line 109).
- Consumers: `grep -rn 'var(--ink-faint)\|var(--faint)' App/app/static --include='*.css' | grep -v archive | head -20`. **Ignore `App/app/static/archive/`** — archived styles, do not edit.
- Do not change `--ink-muted` or any other token in the same pass: this brief is one token, so a regression is attributable.
- The token may also be used for **disabled** or **placeholder** text, where AA does not apply and lightening/darkening may be wrong. Enumerate those uses before choosing a value, and if one needs a different colour, split the token (`--ink-faint` for text that must pass AA, a new one for disabled) rather than compromising.

## 3. Files

- `App/app/static/tokens.css`
- Any non-archived stylesheet that needs splitting if disabled/placeholder uses cannot share the value.
- Read-only: `docs/design/design-system.md` §1 rule 2 (tokens only — this fix must not introduce a raw hex anywhere).

## 4. Steps

1. Enumerate every non-archived use of `--ink-faint` / `--faint` and classify: body-adjacent text (must pass AA), disabled state, placeholder, decorative rule.
2. Pick the value: the nearest shade that reaches **≥4.5:1 on both white and canvas** while staying the same family and keeping the intended hierarchy (it must stay visibly lighter than `--ink-muted`. If it cannot, say so and propose the split).
3. Apply in `tokens.css` only. If a split is needed, add the token and repoint only the disabled/placeholder uses.
4. Measure and record: compute contrast for the new value against both surfaces, and paste the numbers.

## 5. Do not touch

`App/app/static/archive/`, `App/app/templates/`, `go/`, other tokens, deploy files, secrets. No new dependency. No raw hex outside `tokens.css` (rule 2). Light mode only.

## 6. Commands

```bash
grep -rn 'var(--ink-faint)\|var(--faint)' App/app/static --include='*.css' | grep -v archive | wc -l | tail -3

# contrast of the new value on both surfaces (paste the output)
python3 - <<'PY' 2>&1 | tail -10
def lum(h):
    h = h.lstrip('#'); r, g, b = (int(h[i:i+2], 16)/255 for i in (0, 2, 4))
    f = lambda c: c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    r, g, b = map(f, (r, g, b)); return 0.2126*r + 0.7152*g + 0.0722*b
def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return round((la+0.05)/(lb+0.05), 2)
for bg in ('#ffffff', '#f7f6f2'):
    print('new ink-faint on', bg, ratio('#7a7a73', bg))
PY

cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
```

The candidate `#7a7a73` in the snippet is a **starting point to compute, not a decision** — substitute what §4.2 chooses and keep the printed numbers.

## 7. Acceptance

- The new value reaches ≥4.5:1 on both white and canvas, with the computed numbers in the report.
- Still visibly lighter than `--ink-muted`; the hierarchy is unchanged.
- No raw hex outside `tokens.css`; nothing under `archive/` touched.
- `test_layout_lint_browser.py` green, 0 skipped; parity audit still `fail: 0` (a colour change must not move a single text row).
- 390/768/1280 screenshots of one helper-text-heavy page (e.g. `/login` and `/guests/{id}`) before/after, opened (rule 10).

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if no single value satisfies both AA and the visual hierarchy (then the token must split, and that is a design-system decision); if the audit moves at all.

## 9. Report

`docs/tasks/2027-report.md`, ≤600 tokens: the use inventory, the chosen value, the computed ratios, before/after screenshots, deviations.
