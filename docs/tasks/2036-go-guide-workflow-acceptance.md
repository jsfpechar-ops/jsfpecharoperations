# 2036: Recheck guide import, Leon setup and guest guide from their real controls

Status: todo
Depends on: staging SHA and fixtures from 2037 steps 1–2, and 2033 before claim-gated guest guide acceptance | Base commit: bd961426570f07a214f9840bf165a0bca397b450 | Branch: task/2036-go-guide-workflow-acceptance
Executor: Haiku 5.5 | Tier: B | One session, hand off at 25 calls or about 50k tokens

## 1. Objective

Verify the Go guide workflows using their normal entry points. File a scoped fix for a reproducible failure seen with the correct flags and fixture.

## 2. Context

The audit created a guide card. It loaded the import action URL by GET, which produced 422. The active route is POST. Leon setup returned 404 and the guide index lacked an import link for that fixture. Eligibility includes feature, configured provider, owner allowlist and billing state. The guest guide URL rendered the PIN gate. That response alone cannot establish guide content or access correctness.

Exact anchors: `guideAdd("POST", "/apartments/{id}/guide/import", (*guideServer).importPost)` in `go/internal/web/ai/guide_import.go` and `id="leon-setup-import"` in `go/internal/web/ai/leon_templates/leon_setup.tmpl`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/2036-report.md` | new | Sanitized results and exact reproduction or required fixture/config. |

Read only: `go/internal/web/ai/guide_index.go`, `go/internal/web/ai/guide_import.go`, `go/internal/web/ai/guide_import_test.go`, `go/internal/web/ai/leon_handlers.go`, `go/internal/web/ai/leon_templates/leon_setup.tmpl`, `go/internal/web/guest/guide_view.go` and the AI/import sections in `docs/ENVIRONMENT.md`.

## 4. Steps

1. On the owner-confirmed Go SHA with a synthetic eligible property, open Guest guide. Create or edit a card, save it and reopen. Expected: content and guest visibility persist. No app edit. Use §6.
2. Open Leon from the property's visible UI and use its import step. Submit one approved synthetic fixture through the real form. The owner may use an existing mocked provider. Expected: queue acknowledgement, job completion, reviewable draft cards, and no auto-publish. If the UI is absent, record flag eligibility, whether Go owns the route and why the page is gated. Record only on/off/configured, never values.
3. Verify the AI setup preview and guest guide in EN/CS on an authorized guest session. Expected: the published test card is present and a host-only draft is absent. If the claim or PIN gate is present, record which path could be completed. Capture both viewport widths.
4. Record import, AI, and guest-view results separately. If any fail after applying the fixture and flag checks, name one owning handler, status and expected result in the report for an exact-diff follow-up. A bare GET on the import action is evidence about method handling only.

## 5. Do not touch

Application code or configuration, payment state, billing or access gates, provider keys and the guest device policy. No real property listings, account data, or uncontrolled provider calls. No fake GET import page.

## 6. Commands

- From `go/`, using a disposable test database, `go test ./internal/web/ai -run 'TestGuideImportRoute' -count=1 -v 2>&1 | tail -30`. Expect an executed test. Record any unconfigured fixture or skip.
- Chromium on staging. Use the visible guide, Leon and guest controls. Record 390/1280 screenshots in EN/CS.

## 7. Acceptance

- [ ] Manual card persisted.
- [ ] Supported import submitted via the correct form, produced reviewable drafts, and left them unpublished.
- [ ] Leon preview worked for the eligible fixture. Disabled behavior remains clear for the ineligible fixture.
- [ ] Authorized guest saw only intended published content. Screenshots and status evidence exist for each reached page.

## 8. Stop and ask

Stop if the provider, disposable fixture, or approved guest session is missing. Give the owner the exact missing precondition. Also stop on a missing anchor, two failures of the same check, a new dependency, out-of-scope files, or the session cap. Return the next exact action to the owner for credentials, SSH, merge or deploy.

## 9. Report

Write `docs/tasks/2036-report.md` (600 tokens max). Include files, commands and last five lines, acceptance, deviations, questions and owner steps. Use `Status: review` only with completed executor checks. Record any staging checks still pending. Use `Status: blocked` for an unmet dependency or missing acceptance evidence.

## Risk list (for the reviewer)

Guide import POST, Leon eligibility and guest guide access when a follow-up patch is needed.

## Owner steps

1. Confirm a synthetic property is eligible for `leon,guide_import`. Use a test-only provider fixture and an isolated guest session.
2. Give the auditor the Go SHA and visible starting route. Share only non-secret feature states.