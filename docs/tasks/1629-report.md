# 1629 report

Status: review

## Summary

Copied brief 1629 sidecars, removed `RegisterGuideView` 501 stubs from `wave_routes.go` (handlers live in `guide_view.go`). Dropped redundant `lang.go`; guide handlers use `shell.Language(r)` instead of conflicting `GuestLanguage`.

## Commits

- `1629 step 1` — sidecars + wave stub removal + lang integration

## Commands

- `sha256sum -c docs/tasks/1629-files/MANIFEST.sha256` — all OK except `lang.go` removed on purpose
- `cd go && go build ./...` — OK
- `cd go && go test ./internal/web/guest/... -count=1` — ok
- `cd App && .venv/bin/python scripts/go_guest_guide_view_golden.py --check` — OK
- `cd App && .venv/bin/python -m pytest tests/test_go_guest_guide_view_golden.py -q` — 1 passed
- `python3 scripts/context_lint.py` — OK

## §7

- [x] Headers wired in guide_view (hardenedHeaders / photoHeaders)
- [x] QR rate limit 120 via rate.go
- [x] BookedLevel golden test
- [x] Stay gate uses guide_gate_stub until 1721 full gate
- [ ] Browser `test_guest_guide_view.py` — not run (needs DB; wave G / 1728 cutover)

## Deviations

- Removed `lang.go`: duplicates `shell.Language`; kept manifest files except this one.
- `guide_view.go` / `guide_gate_stub.go`: `Language(r)` not `GuestLanguage(r)`.

## guide_translate.fill

Not ported; Leon cards read from DB only (no outbound fill in this PR).

## Questions

None.

## Owner

None until brief 1728 adds guide paths to `UBYHOST_GO_PATHS`.