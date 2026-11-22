# 2011: Auth + shell pages to exact Python DOM (/login, /login/2fa, /login/link, /signup, /account/accept, /offline)

Status: todo | Depends on: none | Branch: task/2011-go-parity-auth-shell
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B (auth pages; rule 6: forms work without JS)

## 1. Objective — failing audit rows (2026-11-21)

| Personas | Path | py/go | Note |
|---|---|---|---|
| admin, host | `/login`, `/login/2fa`, `/login/link`, `/signup` | 200/200 | len 500-655 vs 258-319, sim 0.01-0.05 |
| admin, host | `/account/accept` | 200/200 | len 502/658 vs 258/319 |
| admin, host | `/offline` | 200/200 | len 133 vs 145, sim 0.57 |

Go renders a bare shell. Python adds: flash blocks, Turnstile container (no-JS still works), footer privacy line ("no tracking cookies", rule 9), lang links.

## 2. Context

- Python (read-only): `App/app/templates/auth_base.html`, `login.html`, `two_factor_login.html`, `login_link.html`, `login_sent.html`, `signup.html`, `signup_sent.html`, `signup_verify.html`, `account_accept.html`, `offline.html`. Anchors: `grep -n 'flash\|turnstile\|no tracking\|lang' App/app/templates/auth_base.html | head -20`.
- Go: `go/internal/web/auth/` (`acct_templates/shell.tmpl`, `account_accept.tmpl`, `templates/signup/*`), `go/internal/web/public/utility.go` (`/offline`), route tests in `go/cmd/ubyhost-web/register_web_auth_*.go`.
- DOM to match: normalised DOM (see `norm_dom` in `scripts/e2e/page_parity_audit.py`) equal to Python: same flash container, identical `name=` attrs, Turnstile div, footer line, offline PWA meta.

## 3. Files

- The Go auth/public templates + handlers named above; matching `*_test.go` files.

## 4. Steps

0. Anchors per route: `grep -rn 'login\|signup\|offline\|account/accept' go/cmd/ubyhost-web --include='*.go' | grep Handle | head`.
1. Port each template block-by-block; class names, `name=`, ids byte-for-byte; whitespace normalisation only.
2. Handler statuses/redirects identical to Python (logged-in vs anon on `/account/accept`).
3. Unit test per page: render fixture, compare normalised HTML to a Python golden generated once via the audit seed DB.

## 5. Do not touch

`App/`, other pages, Caddy, `UBYHOST_GO_PATHS`, deploy files.

## 6. Commands

```bash
cd go && go test ./internal/web/auth/... ./internal/web/public/... ./cmd/ubyhost-web/... 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_login_*.py tests/test_auth_*.py tests/test_two_factor_*.py tests/test_passkeys.py tests/test_remember_me_reissue.py tests/test_security*.py tests/test_app_domain.py tests/test_env_guard.py tests/test_pwa.py -q --tb=short -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
python3 - <<'PY' 2>&1 | tail -15
import json, glob
p = sorted(glob.glob('/cursor/stores/*/docs/go-python-parity-audit.json'))[-1]
bad = [r for r in json.load(open(p))['rows'] if r['path'] in ('/login','/login/2fa','/login/link','/signup','/account/accept','/offline') and r['verdict'].startswith('fail')]
print('remaining fail rows:', len(bad))
[print(r['persona'], r['path'], r['verdict'], r.get('cause')) for r in bad]
PY
```

## 7. Acceptance

Go tests green; test-map rows green with 0 skipped; audit shows 0 fail rows for the six paths; run the §6 block of `docs/tasks/1820-go-page-screenshot-parity-tool.md` (390/768/1280) and attach shots.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if a Python block has no Go layout equivalent; if a status differs from Python for a reason not in the audit.

## 9. Report

`docs/tasks/2011-report.md`, <=600 tokens: files changed, command tails, screenshots, deviations.
