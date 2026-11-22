# 2027 report — `--ink-faint`: blocked, no single-token fix exists

Status: blocked (the brief's own §8 condition: no value satisfies both AA and the hierarchy)

## What was measured

Computed against the two surfaces the token is used on (`App/app/static/tokens.css`:
`--surface: #ffffff`, `--canvas: #f7f7f5`), WCAG 2.x relative-luminance formula:

| Token | value | on white | on canvas |
|---|---|---|---|
| `--ink-faint` (current) | `#92928c` | 3.13 fail | 2.92 fail |
| `--ink-muted` (the tone above it) | `#73736e` | 4.77 pass | **4.44 fail** |

## Why this cannot be fixed by changing one token

AA for normal text is 4.5:1. On the canvas, **nothing lighter than `--ink-muted` can reach
it** — and `--ink-muted` itself is already 4.44, just under. The candidates on the warm
neutral ramp, all of which are lighter than `--ink-muted` (so the emphasis order survives):

```
#84847e  3.76 / 3.51   fail
#81817b  3.92 / 3.65   fail
#7f7f79  4.03 / 3.75   fail
#7d7d77  4.14 / 3.86   fail
#7b7b75  4.26 / 3.97   fail
#797973  4.38 / 4.08   fail
#777771  4.50 / 4.20   fail   (passes on white, fails on canvas)
#75756f  4.64 / 4.32   fail
#73736e  4.77 / 4.44   fail   (this is --ink-muted)
```

To clear 4.5 on the canvas, `--ink-faint` has to become **darker than `--ink-muted`**, which
inverts the ramp this token exists to sit at the bottom of. The palette cannot currently
hold four emphasis levels of text above the canvas at AA: `--ink`, `--ink-secondary` and
`--ink-muted` are fine on white, but `--ink-muted` and `--ink-faint` cannot both be AA on
the canvas and still be ordered.

So the brief's instruction ("do not change `--ink-muted` or any other token in the same
pass") and its §8 fallback ("if no single value satisfies both AA and the visual hierarchy,
then the token must split, and that is a design-system decision") collide, and the brief
says a design-system decision is the owner's.

## Files changed

None. `App/app/static/tokens.css` is untouched — deliberately. Changing it to a passing
value would have inverted the ramp silently, and changing two tokens would have made the
regression unattributable, which is exactly what the brief forbids.

## Options for the owner (pick one, then the brief runs again)

1. **Shift the whole text ramp darker** — `--ink-muted` to ~`#5f5f5b`, `--ink-faint` to
   ~`#6f6f6a`. Both then pass on canvas (4.5+) and keep their order, but every muted and
   faint text in the product gets heavier. Needs a look at three or four real pages.
2. **Split the token by role** — keep `--ink-faint` for disabled and placeholder controls
   (where AA for normal text does not apply) and add `--ink-helper` at a passing value for
   hints and fine print, repointing only the 12 non-archived text uses. Preserves the current
   look for controls; helper text gets darker where it is read.
3. **Accept it and narrow the claim** — record that fine print is below AA as a known
   accessibility debt, and stop describing the product as AA-conformant anywhere.

## Use inventory (12 non-archived uses)

`App/app/static/tokens.css` (definition + `--faint` alias), `app.css`, `host.css`. Archived
stylesheets under `App/app/static/archive/` also use it and were **not** touched.

## Deviation

The brief expected one token to change. It cannot, and the numbers above are why. Nothing
else was modified.
