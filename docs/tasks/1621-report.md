# 1621 report: Go public pages, product guide and guide (one-big-PR mode)

Status: review

## 1. Files changed
- `fba7c22 1621 step 1`: created `go/internal/web/public/pages_data.go`, `pages_render.go`, `pages_golden_test.go`, `templates/pages/{footer,guide,head_nav,posthog,privacy_first,product}.tmpl` (sha256 verified, 9 of 9 OK).
- `cdbeb9f 1621 step 5`: `go/cmd/ubyhost-web/register_web_public.go`, 2 lines added (the `/jak-to-funguje` and `GuidePattern` mux handles).
- Brief status line only (`Status: todo` to `review`), and this report.

## 2. Commands (last 5 lines)
- Phase 0 anchors: paths printed, counts `7 3 6 1 1` (all as expected).
- `gofmt -l internal/web/public` and `go vet ./internal/web/public/`: no output.
- `go test ./internal/web/public/ -count=1 -v -run 'TestPages|TestGuide|TestSignedIn|TestPyJSON'`: `--- PASS` for TestPagesGolden, TestPagesPostHogOnlyWhenConfigured, TestGuideVietnameseServesEnglish, TestSignedInHostKeepsPublicRouteLanguage, TestPagesHeadHasNoBody, TestPyJSON, TestPagesEveryActionEscapes; `ok ... internal/web/public 0.035s`.
- `go build ./...`: no output.
- `go vet ./internal/web/public/... ./cmd/ubyhost-web/...`: no output.
- `go test ./internal/web/public/... ./cmd/ubyhost-web/... -count=1`: `ok` for both packages.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## 3. Acceptance (§7)
- [x] Step 1: `: OK` for all 9 files.
- [x] TestPagesGolden PASS; both packages `ok`.
- [x] `git log --grep='^1621 step'` lists steps 1 and 5 (step 6 is this report commit).
- [x] Step 5 diff: `register_web_public.go`, 2 insertions.
- [x] No screenshot due here (brief 1622).

## 4. Deviations
- None from the brief. The step 4 edit was applied by a direct Edit, not a sed/heredoc.
- Full `-v` run of `./internal/web/public/... ./cmd/ubyhost-web/...`: 1 SKIP, `TestServeForScreenshots` (`shots_test.go:15`, "PUBLIC_LEGAL_SHOTS_ADDR not set"). It is a pre-existing env-gated screenshot helper, not added by 1621. The 1621 golden tests report no SKIP.

## 5. Questions
- None.

## 6. Owner steps left
- None in this brief. Brief 1622 takes the screenshots and the `UBYHOST_GO_PATHS` switch is written after it.
