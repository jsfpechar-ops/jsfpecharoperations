# 0123 Cleaning marker visibility

Status: review
Branch: feature/host-design0123-20261016 · PR #397
Tested application SHA: a8a3de98db922c3ec1192e9f2d7e2927eec7cb29
CI: [run 38954296289](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289)

Cleaning now occupies a solid, localized full scheduled-day marker, so short or unknown-hour windows no longer render as tiny dashed slivers. Month/week layouts prioritize the cleaning lane; typed Gantt retains booking-first rows and its separate cleaning band. Overflow remains cleaning-specific and opens the existing day details. Booking bars keep fractional check-in/checkout geometry.

The full-day marker is visual only. It does not change scheduled dates or actual cleaning windows, and it does not persist fallback hours. Property check-in/check-out hours remain the canonical timing source. Missing/invalid hours keep their existing warning semantics.

All eight CI jobs passed. Calendar review: 103 passed, 0 failed, 0 skipped. Required browser suite: 181 passed, 0 failed, 0 skipped. Full tests, Docker, smoke, context, secrets, and shellcheck passed.

Evidence artifacts from the tested SHA:

- [Calendar feature review](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12069916705)
- [Dashboard/calendar review](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12069848493)
- [Onboarding screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12070648025)

The screenshots were neither downloaded nor inspected locally. The owner can review the artifacts before manually deploying the tested application SHA to Render staging. No merge or deployment was performed.
