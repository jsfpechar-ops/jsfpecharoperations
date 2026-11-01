# 0726 report: v2 sidebar background on long pages
Status: done

- Change: `App/app/static/app2.css`, after the `.side` rule: `@media (min-width:1024px){.app{background:linear-gradient(90deg,var(--side) 0 219px,var(--line) 219px 220px,transparent 220px)}}`. The sticky 100vh sidebar is unchanged; the colour column now runs the full page height.
- Key `20261101-0726`, manifest rewritten.
- Pixel check (temporary test, removed): 1280x800, `/` with `.main` min-height 3000px, scrolled to the bottom: pixel at x=100, y=780 = rgb(255,255,255), the sidebar colour (page background is #f6f6f4 without the fix).
- Tests: test_0710 + test_static_versions 25 passed, 0 skipped; design_lint OK; context_lint OK.
- No phone screenshot: the rule only applies at 1024 px and wider.
