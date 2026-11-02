# 0713 report
Status: review

## Commits (branch task/0713-v2-shell-fixes, not pushed)
- f7993ac 0713 step 1: v2 row menu
- 601b985 0713 step 2: rail selector accepts v2 side-nav
- step 3 (this commit): app2.css banner link style, base.html key 20261101-0713, static_versions.json

## Final run (brief section 6)
`130 passed` in 380 s. 0 failed, 0 skipped (no skip lines in -rs output).
design_lint: OK. context_lint: OK.
`git diff --stat cb3671c` limited to section 3 files once test artifacts were reverted.

## Per item
- Row menu: guardrail menu-off-screen cause was an inline SVG in the copy item (266 px tall, no size rule), not the hidden items. Fix: `body.v2 .row-menu-item svg{16px}`. [hidden] rule and <1024 bottom sheet added. Guardrail 11 passed.
- Trigger in card: probed dashboard at 360, 768, 1280. Trigger stays inside the td and card at all three. No CSS change made.
- Rail selector: `.sidebar-nav a[href="/apartments"], .side-nav a[href="/apartments"]` with `.first`. Test passes.
- Hover test passed without CSS; no hover rules added.
- Onboarding banner link: v2 style added (coral pill via var(--acc), 44 px below 1024). Test passes.
- 0385 test passes unchanged; no change to that file.

## Deviations
- Test runs regenerate about 239 evidence PNGs under docs/tasks (screenshots-0410, 0102-evidence, etc.). They were reverted and not committed.
- `.first` added to the rail locator (strict mode with two matches).
- No PR opened and no screenshots taken: the 30-call budget ran out first.

## Owner steps left
- Open the PR from task/0713-v2-shell-fixes after review.
