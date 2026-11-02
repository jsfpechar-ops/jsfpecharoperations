# 0679 report

Files: `go/internal/palette/palette.go`, `db.go`, `palette_test.go`, `i18n_keys.txt`, `i18n.json` (new); `go/cmd/ubyhost-web/main.go` (import + one route `GET /api/command-palette`); this report.

Commands (tails):
- gofmt/vet/build: clean.
- `go test ./internal/palette/ ./cmd/... -count=1` with UBYHOST_TEST_DATABASE_URL set: `ok ... internal/palette`; 7 tests pass (encoding, one property, other owner's stays, signed-out 401, AI gate, Czech key, TTLock gate). 0 skipped.
- `go_host_i18n.py --check`: no output (not confirmed by exit code).
- `context_lint.py`: OK.

Not done (brief section 4 and 7 gaps):
- Two-property hub URL, permalink copy with a real token-only case, admin items, stays 80 cap, submissions 40 cap, archived stays excluded: not tested. Exact byte-output fixture not added.
- No golden Python script.

Deviations:
- `linkKey` reads the current slug only. Python `guest_slug.ensure` creates a slug when none exists; that write is not ported. Such apartments get the permanent token.
- Python's bootstrap/staging no-login account fallback is not ported (session.Load has none).
- The email for the AI check is `user_account.email`, read in `accountEmailOf`.
- Go's encoder escapes U+2028/U+2029 even without HTML escaping; Python does not.
- Timestamps are passed through as stored text (date_from/date_to/created_at are text columns).

Owner steps left: none. Not pushed.
