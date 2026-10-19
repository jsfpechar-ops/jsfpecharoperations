# 0125: Design v2 tokens (three layers in tokens.css)

Status: review
Depends on: 0124 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step on the branch as `0125 step k`. Never push, never open a PR.

## 1. Objective

Add the v2 token layers (primitive, semantic, component) from `docs/design/MASTER.md` section 2 to `App/app/static/tokens.css` without changing any current value, so later briefs can build the new host stylesheet from tokens only. Nothing visible changes in this brief.

## 2. Context

Rules: MASTER 2.1 to 2.3 (tokens), hard rule 6 (light mode only), never a raw colour outside `tokens.css`.

Anchor A, `App/app/static/tokens.css`, the end of the `:root` block and the reduced-motion block:

```
  --sidebar: var(--sidebar-width);
  --ease: var(--ease-standard);
}

@media (prefers-reduced-motion: reduce) {
  :root { --motion-fast: 0.01ms; --motion-base: 0.01ms; }
}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/tokens.css` | edit | append the v2 layers inside `:root` and extend the reduced-motion rule |
| `App/tests/test_design_tokens.py` | create | asserts the v2 names exist and no v2 primitive leaks outside the file |

No other file may change.

## 4. Steps

1. In `App/app/static/tokens.css`, replace Anchor A with:

```
  --sidebar: var(--sidebar-width);
  --ease: var(--ease-standard);

  /* ---- Design v2 (docs/design/MASTER.md section 2). Three layers. ---- */
  /* 2.1 primitive: used only inside this file */
  --coral-50: #fbf0ee; --coral-100: #f9e9e7; --coral-200: #f0c9c4; --coral-500: #c85a52; --coral-600: #ad4942; --coral-700: #963e38;
  --sand-0: #ffffff; --sand-50: #fbfaf8; --sand-100: #f7f7f5; --sand-150: #f1f1ef; --sand-200: #ececea; --sand-300: #deded9; --sand-400: #c9c9c2;
  --ink-900: #20201e; --ink-700: #50504c; --ink-500: #6b6b66; --ink-400: #92928c;
  --amber-700: #6b3a00; --amber-100: #fde9c2; --amber-300: #eec27a; --amber-dot: #c27a00;
  --green-700: #1f5f3b; --green-100: #e6f5ec; --green-300: #bfe0cb; --green-dot: #2e8a57;
  --red-700: #b42318; --red-100: #fcebea;
  --blue-700: #245cb5; --teal-700: #08736b; --purple-700: #7840a2;
  --size-11: 0.6875rem; --size-12: 0.75rem; --size-13: 0.8125rem; --size-14: 0.875rem; --size-15: 0.9375rem; --size-16: 1rem; --size-18: 1.125rem; --size-22: 1.375rem; --size-26: 1.625rem;
  --radius-1: 6px; --radius-2: 8px; --radius-3: 12px; --radius-4: 16px;
  --shadow-1: 0 1px 2px rgba(20, 20, 18, 0.06); --shadow-2: 0 8px 24px rgba(20, 20, 18, 0.12), 0 2px 6px rgba(20, 20, 18, 0.08); --shadow-3: 0 20px 60px rgba(20, 20, 18, 0.2);
  --motion-1: 120ms; --motion-2: 180ms; --motion-3: 240ms;
  /* 2.2 semantic */
  --canvas-2: var(--sand-100); --surface-2: var(--sand-150); --surface-3: var(--sand-200);
  --ink-2: var(--ink-700); --ink-3: var(--ink-500); --line-1: var(--sand-300); --line-strong: var(--sand-400);
  --accent: var(--coral-600); --accent-hover: var(--coral-700); --accent-pressed: var(--coral-700); --accent-soft: var(--coral-100); --accent-ink: var(--coral-700); --on-accent: #ffffff;
  --focus-ring-2: 0 0 0 1px var(--sand-0), 0 0 0 4px rgba(200, 90, 82, 0.32);
  --st-action-bg: var(--coral-100); --st-action-ink: var(--coral-700); --st-action-dot: var(--coral-600);
  --st-attention-bg: var(--amber-100); --st-attention-ink: var(--amber-700); --st-attention-dot: var(--amber-dot);
  --st-done-bg: var(--green-100); --st-done-ink: var(--green-700); --st-done-dot: var(--green-dot);
  --st-neutral-bg: var(--sand-150); --st-neutral-ink: var(--ink-700); --st-neutral-dot: var(--ink-400);
  --danger: var(--red-700); --danger-bg: var(--red-100);
  --property-1: var(--teal-700); --property-2: var(--blue-700); --property-3: var(--purple-700); --property-4: var(--amber-700);
  /* 2.3 component */
  --control-h: 40px; --control-h-phone: 44px; --control-h-compact: 32px; --control-px: 14px; --control-radius: var(--radius-2); --control-font: var(--size-14); --control-weight: 600;
  --input-h: var(--control-h); --input-border: var(--line-strong); --input-radius: var(--radius-2); --input-px: 12px;
  --row-h: 48px; --row-py: 12px; --row-px: 16px; --row-gap: 12px; --card-radius: var(--radius-3); --card-p: 16px;
  --badge-h: 22px; --badge-px: 8px; --badge-font: var(--size-12); --badge-radius: var(--radius-pill);
  --nav-w: 240px; --nav-w-collapsed: 64px; --nav-item-h: 40px; --nav-icon: 20px; --tabbar-h: 56px; --topbar-h: 52px;
  --lane: 1080px; --lane-narrow: 720px; --gutter: 32px; --section-gap: 32px; --body-size: var(--size-16);
  --sheet-radius: var(--radius-4); --dialog-w: 480px; --toast-w: 360px;
  --skeleton-delay: 300ms; --skeleton-min: 400ms;
}

@media (prefers-reduced-motion: reduce) {
  :root { --motion-fast: 0.01ms; --motion-base: 0.01ms; --motion-1: 0.01ms; --motion-2: 0.01ms; --motion-3: 0.01ms; }
}
```

   Note: `--line`, `--canvas`, `--surface`, `--ink`, `--focus-ring` keep their current names and values (they are already the semantic names); v2 adds `--line-1` as the explicit v2 alias of `--line` only for the lint allowlist. Command: `cd App && .venv/bin/python -c "import re,pathlib;s=pathlib.Path('app/static/tokens.css').read_text();print(s.count('--coral-600'), s.count('--skeleton-min'))"`. Expected: `3 1` (one definition plus two uses).

2. Create `App/tests/test_design_tokens.py`:

```python
"""Design v2 tokens (docs/design/MASTER.md section 2) exist in tokens.css.

The three layers are the only place a raw colour may live. Later briefs
build the host stylesheet from these names; this test keeps them stable.
"""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
TOKENS = (APP_DIR / "static" / "tokens.css").read_text(encoding="utf-8")

V2_NAMES = [
    "--coral-600", "--sand-100", "--ink-900", "--amber-700", "--green-700", "--red-700",
    "--size-16", "--radius-2", "--shadow-2", "--motion-2",
    "--surface-2", "--ink-2", "--ink-3", "--line-strong", "--accent", "--accent-soft", "--accent-ink",
    "--focus-ring-2", "--st-action-bg", "--st-attention-bg", "--st-done-bg", "--st-neutral-bg", "--danger",
    "--property-1", "--control-h", "--control-h-phone", "--control-h-compact", "--row-h", "--badge-h",
    "--nav-w", "--tabbar-h", "--topbar-h", "--lane", "--lane-narrow", "--body-size",
    "--skeleton-delay", "--skeleton-min",
]


def test_every_v2_token_is_defined_once():
    for name in V2_NAMES:
        assert len(re.findall(rf"{re.escape(name)}\s*:", TOKENS)) == 1, name


def test_primitive_values_are_what_master_says():
    assert "--coral-600: #ad4942" in TOKENS
    assert "--coral-500: #c85a52" in TOKENS
    assert "--ink-900: #20201e" in TOKENS
    assert "--body-size: var(--size-16)" in TOKENS


def test_reduced_motion_zeroes_the_v2_motion_tokens():
    assert "--motion-1: 0.01ms; --motion-2: 0.01ms; --motion-3: 0.01ms;" in TOKENS
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_tokens.py -q --tb=short -x 2>&1 | tail -30`. Expected: `3 passed`.

3. Commit: `git add App/app/static/tokens.css App/tests/test_design_tokens.py && git commit -m "0125 step 3: design v2 token layers"`. Expected: one commit on `claude/project-thread-td6fpc`.

## 5. Do not touch

Any other stylesheet or template; existing token names or values; `App/app/static/guest.css`; hard rules 3, 6, 8.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_design_tokens.py tests/test_host_button_contrast_browser.py -q --tb=short -x 2>&1 | tail -30` expected: all passed (the contrast test proves nothing visible changed).
- `cd App && .venv/bin/python -m pytest tests/test_skeleton_loaders.py -q --tb=short -x 2>&1 | tail -30` expected: passed.
- `python3 scripts/context_lint.py` from the repo root expected: `context lint: OK` (warnings allowed).

## 7. Acceptance

- [ ] `tests/test_design_tokens.py` passes (3 tests).
- [ ] `git diff df8b842 --stat` lists exactly the two files in section 3.
- [ ] No existing token line changed: `git diff df8b842 -- App/app/static/tokens.css | grep '^-' | grep -v '^---' | wc -l` prints `2` (the two replaced closing lines only).

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0125-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/static/tokens.css` (additions only).

## Owner steps

None.
