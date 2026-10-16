# Dashboard calendar shows stays only

Status: review  
Branch: feature/host-design0123-20261016 | PR #397  
Tested application SHA: `b51e0bb07a0c8eea81ebaaa0199348b42cf51984`

The owner-scoped Dashboard calendar endpoint now returns reservations only. Dashboard Gantt, Calendar, Year, overflow, and details no longer include Cleaning event tags. Add cleaning and popup type selection remain available; a Dashboard-created Cleaning is saved once and remains visible with its note in the authenticated Cleaning page. Cleaning scheduling, Property hours, and Cleaning/shared markers are unchanged.

The API regression seeds a real stay and Cleaning with private note data, asserts the stay payload remains correct, and fails if Dashboard calls `cleaning.schedule`. The browser flow verifies the Cleaning’s exact saved ID/property/date, its absence in Dashboard views, and its presence and note in the separate Cleaning page before continuing the existing Stay refresh/menu checks.

CI run [38969976286](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38969976286) completed successfully: all 8 jobs passed. Calendar review: 103 passed, 0 failed, 0 skipped. Required browser suite: 181 passed, 0 failed, 0 skipped. Full tests, Docker, smoke, context, secrets, and shellcheck passed.

Artifacts from the tested SHA:

- [Calendar feature review](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38969976286/artifacts/12076367225)
- [Dashboard/calendar review](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38969976286/artifacts/12077716596)
- [Onboarding screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38969976286/artifacts/12076299654)

The PNG artifacts were not downloaded or inspected locally. This tested application SHA is the Render hand-off; the later documentation commit is docs-only. No merge or deployment was performed.

Render staging steps:

1. Open the staging service in Render.
2. Choose Manual Deploy, then Deploy a specific commit.
3. Paste the tested application SHA above and deploy.
