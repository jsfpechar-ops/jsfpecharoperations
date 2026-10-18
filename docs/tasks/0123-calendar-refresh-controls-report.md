# 0123 Imported Dashboard controls

Status: review
Branch: feature/host-design0123-20261016 · PR #397
Tested application SHA: a8a3de98db922c3ec1192e9f2d7e2927eec7cb29
CI: [run 38954296289](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289)

After the Dashboard work region is refreshed, a scoped content-updated event asks the existing app.js initializers to bind imported nodes. Copy controls, row menus, clickable rows, confirmation forms/buttons, and dismissible banners use one idempotent binding helper while retaining their original callback bodies and private state. Global and shell handlers still register once.

Browser coverage verified the imported menu and copy/fallback, archive confirmation cancellation without a POST, keyboard row navigation, repeated updates, and a refresh-only retry that does not repeat the creation POST. Dashboard's five-row cap and queue ranking remain unchanged.

All eight CI jobs passed. Calendar review: 103 passed, 0 failed, 0 skipped. Required browser suite: 181 passed, 0 failed, 0 skipped. Full tests, Docker, smoke, context, secrets, and shellcheck passed.

Evidence artifacts from the tested SHA:

- [Calendar feature review](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12069916705)
- [Dashboard/calendar review](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12069848493)
- [Onboarding screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12070648025)

The screenshots were neither downloaded nor inspected locally. The tested application SHA is the Render hand-off; no merge or deployment was performed.
