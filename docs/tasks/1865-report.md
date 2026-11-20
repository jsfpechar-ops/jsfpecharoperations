# 1865 report

Status: review

## Files changed

- `App/app/static/app2.css` — host workspace white canvas + `--side` tint from 768px (v2)
- `App/app/static/host2.css` — legacy `.ui-sidebar` warm tint from 768px
- `App/app/templates/base.html`, `go/internal/hostweb/layout/shell.html` — cache bust `20261120-host-palette-1865`
- Eight `go/internal/hostweb/layout/testdata/*.html` — URL-only regen
- `App/tests/static_versions.json` — `app2.css`, `host2.css` hashes
- `App/tests/v2_mockup.py` — wide overview `.side` `rgb(252, 248, 245)`

## Commands (last lines)

```
go test ./internal/hostweb/layout → ok (0.148s)
pytest subset (mockup, geometry, guardrails, golden, static) → 200 passed
test_layout_lint_browser.py → 4 passed (390/768/1280 shots in UBYHOST_SHOTS_DIR)
§6 full pytest → FAILED test_host_flash_outcomes.py::test_browser_renders_saved_warning_as_sticky_amber (twice; toast timeout; unrelated to CSS)
git diff --check → (no output)
```

## Colors

At ≥768px on v2 host workspace (customer, not admin): body `rgb(255, 255, 255)` via `var(--s)`; rail/gradient uses `--side` / `.side` `rgb(252, 248, 245)`. Confirmed by `test_0710_v2_mockup_match_browser.py` (overview `.side` override). Layout-gate screenshots: `previews/warm-sidebar-*.png` (plan) + `/opt/cursor/artifacts/1865/layout-lint/` (dashboard/reservations/stays/properties/settings at 390/768/1280).

Below 768px: scoped rules do not apply (mockup phone paths unchanged).

## §7 acceptance

- [x] White canvas + warm rail at tablet/laptop (mockup + layout lint visuals)
- [x] Sub-768 unchanged by scoped `@media (min-width:768px)`
- [x] Navigation/coral/separators unchanged (color-only diff)
- [x] Matching stylesheet URLs Python + Go; golden/static manifest URL-only
- [ ] Full §6 pytest green — blocked on pre-existing flash sticky toast test

## Deviations

None to brief scope. §6 aggregate fails on `test_browser_renders_saved_warning_as_sticky_amber` (pre-existing; not introduced by this branch).

## Owner steps

1. Review draft PR screenshots (dashboard 1280, reservations/stays 768 examples in layout-lint artifact).
2. Merge via `scripts/merge-pr-on-green.sh` when CI green (may need flash test triage on main).