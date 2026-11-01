# 0555 report: Go guest and apartment validation

Status: review (committed locally on claude/project-thread-dwlrdj, not pushed)

## Files changed
- `go/internal/validation/validation.go`: port of validate_guest, validate_birth_date, validate_residence, signature check, guest_issues / guest_is_complete path, validate_apartment, errors_only, parse_iso_date.
- `go/internal/validation/validation_test.go`: embeds golden.json, compares every guest and apartment case (message, field, severity, order, completeness).
- `go/internal/validation/testdata/golden.json`: 95 guest cases, 43 apartment cases.
- `App/scripts/validation_golden.py`: writes the golden file from the real Python functions, clock pinned to 2026-11-01.
- `docs/tasks/0555-report.md`: this report.

## Commands (last lines)
- `.venv/bin/python scripts/validation_golden.py` (from App/): `guest cases 95, apartment cases 43` / `wrote go/internal/validation/testdata/golden.json`. Rerun gives an identical sha256.
- `gofmt -l .` empty, `go vet ./internal/validation/` clean.
- `go test ./internal/validation/ -count=1 -v`: 140 `--- PASS`, 0 FAIL, 0 SKIP (95 + 43 + 2 parents).
- `go test ./internal/validation/ -count=1`: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation`.
- `python3 scripts/context_lint.py`: not run (budget).

## Deviations
- `today` is a parameter of GuestIssues, GuestIsComplete and birth-date checks (Python reads date.today()). Brief section 2 asks for this.
- Not ported: the normalisers (NFKD folding, strip_forbidden, normalise_* ). validate_guest takes stored values, so they are not needed. This means no `golang.org/x/text` use and go.mod is unchanged.
- Not ported: the "Home address is too long" branch. Python's compose_residence truncates to 255 first, so the branch cannot fire.
- Known small gaps: Python isdigit() accepts superscript digits, Go uses unicode.IsDigit (Nd) or ASCII (birth date). Not covered by golden.
- The NON_LATIN_MESSAGE branch is covered through an unexported raw-input path in validateGuest (test only). GuestIssues never passes raw, matching reporting.guest_issues.
- Stored values are strings; a Python int 0 for legal_entity_id would be truthy in Go. Golden uses strings only.
- Venv created at App/.venv (git-ignored) with requirements.txt.

- Follow-up (orchestrator decision): countries.json moved to `go/internal/countries/` with `countries.Name`; ubyport.CountryName delegates to it; validation imports `countries`, not `ubyport`, so no cycle when 0558 lands.

## Questions (stop-and-ask)
1. Country membership (nationality, res_country) uses `ubyport.CountryName(code, "en") != code`, which imports `go/internal/ubyport` from the new package. go:embed cannot reach countries.json from a sibling package, and copying the file is forbidden. Owner decision needed: accept this import (risk: a future ubyport -> validation import would be a cycle), or move countries.json into a shared package.

## Owner steps left
- None for production. Push and open the PR yourself (executor did not push, per the brief).
