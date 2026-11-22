# 2011 report — auth + shell pages parity

Status: blocked (25-call checkpoint reached; no code changed)

## Files changed

- `docs/tasks/2011-report.md` only.

## What the audit says now (rerun, not the brief's 2026-11-21 table)

Command: `cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py`

```
{"paths": 137, "rows": 411, "pass": 250, "pass_soft": 12, "accepted": 101, "fail": 48}
```

So 48 fail rows exist, but **which of them are the six paths could not be read**:
§6's filter snippet globs `/cursor/stores/*/docs/go-python-parity-audit.json`, the
audit writes it (`STORE_DOC`, script line 22/401-403), yet the file is absent
afterwards (`glob` empty → `IndexError`; `/cursor` does not exist for this shell).
The run itself exits 0, so the store write is being discarded, not failing.

## Anchors (step 0)

`grep -rn 'login|signup|offline|account/accept' go/cmd/ubyhost-web --include='*.go' | grep -i handle`
returns nothing (routes are registered from the packages, not in `cmd/`):

- `go/internal/web/auth/auth.go:65-82` — `GET /login`, `POST /login`, `GET|POST /login/link`,
  `GET|POST /login/2fa`, `GET|POST /account/accept`, `GET|POST /signup`.
- `go/internal/web/public/utility.go:61` — `GET /offline`.

The full port already exists and is wired: `go/internal/web/auth/authpage/`
(`base.html` 102 lines, `login.html` 97, `login_link.html` 20, `login_sent.html` 29,
`two_factor_login.html` 38) is rendered by `login.go` via `authpage.Render`, plus
`acct_templates/shell.tmpl` + `account_accept.tmpl` and `templates/signup/*`.
The brief's "Go renders a bare shell" (len 258-319) is therefore stale for `/login`,
`/login/2fa`, `/login/link`; those pages need a DOM diff, not a rewrite.

## `/offline` — analysed root cause (not applied)

Python's language fallback depends on the session (`App/app/templating.py:713-718`):
`DEFAULT_LANGUAGE` ("en") when `current_user` is set, `PUBLIC_DEFAULT_LANGUAGE`
("cs") for a visitor. Go's `resolveOfflineLang` (`utility.go:165`) returns `"cs"`
unconditionally, so a signed-in host gets a Czech page from Go and an English one
from Python — consistent with the row's `len 133/145 sim=0.57`. Go already has the
matching helper: `authpage.Language(r, host != nil)`.

## Deviations

- Done: step 0 (anchors), the §6 audit rerun. Left: steps 1, 2, 3 (§7 shots too).
- `/cursor` store is not usable locally, so §6's last snippet cannot pass here.

## Questions

1. Where must the audit write its JSON so §6's filter works on this machine?
2. For `/offline`: reach the session in `public.DepsUtility` and use
   `authpage.Language(r, host != nil)`, or extend `resolveOfflineLang`? Confirm before editing.

## Owner steps left

None (no deploy, no merge).
