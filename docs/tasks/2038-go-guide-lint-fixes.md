# 2038: Go guide pages — fix the two 1668 layout-lint findings

Status: review
Depends on: 1668 (same branch) | Base commit: branch `cursor/1668-go-layout-lint-harness-992e` | Branch: same
Executor: one session | Tier B (host UI, Go only)

## 1. Objective

`test_go_pages_layout_lint_browser.py` (1668) reports 6 findings on Go host pages. Fix both in Go templates/handlers so the test passes with 0 findings and 0 skipped. No allow-list (AGENTS rule 10). Go only; do not edit Python templates (owner 2026-11-22 [parity/ux]: a UX fix stays Go-only).

## 2. Context (verified on the branch)

- `help-stranded` on `guide` at 390/768/1280: `go/internal/web/ai/guide/templates/guide_index.tmpl:57-58` opens the Leon section with an empty tip, then prints `{{help_tip "guide-leon-help" ...}}` on its own line. `guide_section_open(id, title, tip)` (`go/internal/web/ai/guide_common.go:66`) already takes the tip as its third argument; line 5 of the same template shows the pattern.
- `multiple-save-in-form` on `guide-card-wifi` at 390/768/1280: `go/internal/web/ai/guide/templates/guide_card.tmpl:46-49` renders two submits, "Save and next card" (`name="then" value="next"`) and "Save". `cardSave` (`go/internal/web/ai/guide_cards.go:181-191`) and `leonAfterSave` (`:103-115`) already fall back to the guide index (or Leon setup) when `nextOpen` (`guide_data.go:460`) returns 0.

## 3. Files

| File | Change |
|---|---|
| `go/internal/web/ai/guide/templates/guide_index.tmpl` | tip moves into `guide_section_open`; drop the separate line |
| `go/internal/web/ai/guide/templates/guide_card.tmpl` | one submit only |
| `go/internal/web/ai/guide_cards.go` | `guideCardData.HasNext bool`, filled in `card()` from `s.nextOpen(ctx, a.ID, item.ID) != 0` |
| `go/internal/web/ai/guide_cards_test.go` (or the existing card test file) | tests below |

## 4. Steps

1. `guide_index.tmpl`: `{{guide_section_open "leon" (t "guest_guide.leon.title") (help_tip "guide-leon-help" (t "guest_guide.leon.help"))}}`; delete line 58.
2. `guide_cards.go`: add `HasNext bool` to `guideCardData`; in `card()` set it from `nextOpen` (on error: `false`, render continues; never log card text).
3. `guide_card.tmpl` actions: `{{if .HasNext}}` one primary submit `guest_guide.save_next` with `name="then" value="next"`; `{{else}}` one primary submit `guest_guide.save`. No second save button. Keep `.ui-form-actions`.
4. Tests (Go, existing guide test world helpers): card page with another open card renders exactly one `type="submit"` save button with `value="next"`; last open card renders exactly one, labelled Save, without `then`; guide index renders `guide-leon-help` inside the Leon section heading element.

## 5. Do not touch

Python templates, `layout_lint.js`, the harness, i18n keys (reuse existing ones), handlers other than `card()`.

## 6. Commands

From `go/`: `gofmt -l internal/web/ai/ && go vet ./internal/web/ai/ && go test ./internal/web/ai/ 2>&1 | tail -30` (with `UBYHOST_TEST_DATABASE_URL`). From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots UBYHOST_TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -rs 2>&1 | tail -30`. Repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance

- [ ] Layout lint: 0 findings, 3 passed, 0 skipped.
- [ ] Go tests green; `gofmt` clean.
- [ ] Open `guide-390.png` and `guide-card-wifi-390.png`: the `?` sits beside "Leon (AI) for your guests"; the card form ends in one primary button.

## 8. Stop and ask

Stop if a third finding appears after the fix, if a Go DOM-parity test pins the two buttons, or if `nextOpen` needs a schema change.

## 9. Report

`docs/tasks/2038-report.md` (≤400 tokens) with what the two 390 px screenshots show; `Status: review`.
