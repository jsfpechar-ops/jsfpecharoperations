# 0123 Calendar creation and in-page refresh

Status: review
Branch: feature/host-design0123-20261016 · PR #397
Tested application SHA / Render hand-off: a8a3de98db922c3ec1192e9f2d7e2927eec7cb29
CI: [run 38954296289](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289)

Dashboard and Cleaning now offer in-page Stay/Cleaning creation. Type changes preserve selected property and dates; existing Stay validation and canonical endpoint remain in use, while Cleaning uses its existing save path with localized JSON results/errors and normal HTML fallback. Saves do not navigate away.

Dashboard calendar serialization exposes only an explicit safe Cleaning whitelist; notes, instructions, door codes, guest identity and tokens remain private. Post-save Dashboard work/calendar refresh is separate from creation. A refresh retry makes GET requests only, so it cannot create a duplicate. A scoped content-update event lets the existing app.js initializers bind imported row controls idempotently without replaying global handlers. Property hours remain the sole time input.

All eight CI jobs passed. Calendar review: 103 passed, 0 failed, 0 skipped. Required browser suite: 181 passed, 0 failed, 0 skipped. Full tests, Docker, smoke, context, secrets, and shellcheck passed.

Evidence artifacts from the tested SHA:

- [Calendar feature review](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12069916705)
- [Dashboard/calendar review](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12069848493)
- [Onboarding screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38954296289/artifacts/12070648025)

The screenshots were neither downloaded nor inspected locally. The tested application SHA is the Render hand-off. Any subsequent report/context commit is documentation-only; owner staging deployment remains manual. No merge or deployment was performed.

Render staging steps:

1. Open the staging service in Render.
2. Choose Manual Deploy, then Deploy a specific commit.
3. Paste the tested application SHA above and deploy.
