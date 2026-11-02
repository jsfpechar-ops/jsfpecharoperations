# 0676 report: Go shared host web gate and host strings

## Files
- New: go/internal/hostweb/hostweb.go, gate.go, i18n.go, hostweb_test.go, i18n_keys.txt, i18n.json
- New: App/scripts/go_host_i18n.py, App/tests/test_go_host_i18n.py
- Changed: go/internal/payments/connect.go (uses hostweb; moved code removed), connect_test.go (hostweb.ExpiredTexts, import only)

## Exported API (go/internal/hostweb)
- Login(w, r, pool, getenv, at) (*session.Host, error)
- CSRF(w, r, getenv, at) bool
- Lang(r) string
- Back(w, r, path, msg, err Flash)
- Flash{Text, Key, Count}
- Cookie(r, name), QuotePath(p), PublicBase(getenv), AppBase(getenv), SecureCookies(getenv)
- ExpiredTexts (map en/cs/vi), DefaultLanguage
- Catalog, Load(data) Catalog, (Catalog).T(lang, key, params), HostStrings (embedded)

## Commands
- gofmt -l . (empty), go vet ./..., go build ./...: clean
- go test ./internal/hostweb/ ./internal/payments/ -count=1 -v: ok both, 51 PASS/FAIL lines, 0 SKIP
- go_host_i18n.py --check: rc 0; second run wrote nothing
- pytest tests/test_go_host_i18n.py: 2 passed
- context_lint.py: context lint: OK

## Deviations and decisions
- Lang follows Python supported_language: first two letters, so cs-CZ gives cs. connectLang returned en for that input. Only the expired-notice language changes (brief section 2 asked for this).
- Back sets the Location header directly, not http.Redirect, because http.Redirect path-cleans the query string. Python does not clean it.
- Back quotes with Python quote(safe="/"). QuotePath keeps the old per-segment url.PathEscape, so Connect redirects are unchanged.
- Flash has a Count field so flash.reservations.accepted partial toasts work.
- i18n_keys.txt lists no keys (brief section 2). The three T cases therefore use an inline fixture JSON in Go, and the same three cases on host_i18n.lookup in Python.
- The expired-text test stays in connect_test.go, now pointing at hostweb.ExpiredTexts. It was not moved.
- Log text in the CSRF 500 path still says "connect route failed". Only logs are affected.
- App/.venv was created, and pytest was installed into it. It is not in requirements.txt.
- Local Postgres was started and its postgres password set, per brief section 6.

## Owner steps left
- None. Nothing was pushed. The owner merges through scripts/merge-pr-on-green.sh.
