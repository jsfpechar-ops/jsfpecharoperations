# 2026: `/guests/{id}` stops showing errors to a guest who did nothing wrong

Status: todo | Depends on: 2027 | Branch: task/2026-guest-detail-form
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: **B+** (guest personal data — read the privacy row first)

## 1. Objective — measured on the Go stack, 2026-11-22

Source: `docs/tasks/2019-ux-gate-2011-2018.md`, the `/guests/{id}` row (verdict **FAIL**), screenshots in `/tmp/ux-2011-2018/` (regenerate; never commit guest images, rule 3).

1. **A field marked "(optional)" reports "required".** This is the worst of the five findings: the form contradicts itself.
2. **Red validation errors, including a signature error, render on a clean GET** — a guest who has just opened the page is shown a list of failures.
3. **Five helper lines** stack up, so the field group reads as a wall of fine print.
4. **A 12 × 12 input** — an unclickable checkbox/radio, far under the 44 px of design-system §1 rule 8.

**Priority**: items 1 and 2 are correctness, not polish. If the clean GET emits errors because the Go form applies Python's *filled* form validation to an *empty* one, that is a bug other pages may share — say so in the report even if you only fix it here.

**Parity tension.** The page is DOM-identical to Python (`10851/10851`), so a Go-only fix breaks `docs/plans/staging-prod-identical.md`. Per [go-first](docs/context/go-first.md), fix in Go; the **owner step in §4.6** adds the path to prod `UBYHOST_GO_PATHS` (`docs/ENVIRONMENT.md:190`). Do not edit Python to match. **Never** change guest field semantics — [UBYPORT_CORE](docs/UBYPORT_CORE.md) forbids it; this brief touches labels, validation display and target size only.

## 2. Context

- **Read first**: `docs/privacy/RETENTION.md` and `docs/context/rules.md#personal-data`. The page shows a guest's personal data; a screenshot in the report must be of the **seed** guest, never a real one.
- `docs/design/design-system.md` §1 rule 8 (44 px), §4 copy (rule 9 in AGENTS.md: one explanation lives in one place; no sentence the button already says).
- Go: `go/internal/web/stays/guest_edit.go`, `templates/guest_form_admin.tmpl`, `go/internal/web/stays/tpl.go` + `i18n.json`/`i18n_keys.txt` (regenerated with `App/scripts/go_host_i18n.py`).
- Python reference (read-only): `App/app/templates/guest_edit.html`, and the validator behind it — check whether Python shows errors on a clean GET. If Python does **not**, this is a Go bug introduced by the port and the fix is a parity fix, not a design change.
- 2015's report flagged that `validation_message(...)` has no Go counterpart; do not try to solve localisation here.

## 3. Files

- `go/internal/web/stays/guest_edit.go`, `go/internal/web/stays/templates/guest_form_admin.tmpl`, `go/internal/web/stays/i18n.json` + `i18n_keys.txt` (regenerated), their tests.
- Read-only reference: `App/app/templates/guest_edit.html`, `App/app/guest.py`.

## 4. Steps

1. Reproduce at 390/768/1280 as host. Capture the clean-GET error list **verbatim** into the report.
2. Find why a clean GET validates at all. Compare with Python. Fix the cause, not the symptom (do not hide a block that is wrongly populated).
3. The "(optional)" field: the marker and the validator must agree. Whichever is wrong, say which.
4. Collapse the five helper lines: one explanation in one place (rule 9); keep the legal/filing sentences that must stay.
5. Raise the 12 × 12 input to ≥44 px hit area without inflating the visual box if the design needs it small.
6. Owner step: add `/guests/*` to prod `UBYHOST_GO_PATHS`.
7. Tests: a render test that a clean GET contains **no** validation error for a valid seed guest, and that every labelled field's required/optional marker matches its validator.

## 5. Do not touch

`App/app/` (unless §2 proves a Python parity defect, in which case say which go-first exception applies and stop), guest **field names or meanings**, other pages, Caddy, deploy files, secrets, `UBYHOST_GO_PATHS` itself (owner step). No new dependency. Light mode only.

## 6. Commands

```bash
cd go && go build ./... && gofmt -l ./internal ./cmd 2>&1 | tail -30
cd go && go test ./internal/web/stays/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -10
cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
```

## 7. Acceptance

- A clean GET shows **zero** validation errors; the "(optional)" marker and its validator agree.
- 390/768/1280 screenshots (seed guest only) in the report, opened, one sentence per width (rule 10).
- All targets ≥44 px; helper text collapsed; `go_host_i18n.py --check` clean; lint green, 0 skipped.
- The `/guests/1` audit row does not regress below fail 0.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if the clean-GET errors come from shared validation used by other pages; if a fix would change guest field semantics or the UbyPort payload (UBYPORT_CORE stop); if the cause is in Python and would need a Python change.

## 9. Report

`docs/tasks/2026-report.md`, ≤600 tokens: the verbatim error list before, the root cause, which marker was wrong, before/after per width, the owner step, deviations.
