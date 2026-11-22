# 2011 report — auth + shell pages parity

Status: review (the six paths' own renderers are at parity; the ten remaining rows are the
`/` dashboard render, which is brief 2012's page — evidence below)

## Files changed

- `go/internal/web/public/utility.go` — `/offline` language fallback follows the session
  (`offlineSignedIn` loads the cookie through `session.Load`; `authpage.Language` applies
  `templating.render`'s rule: English for a signed-in host, Czech for a visitor). The old
  `resolveOfflineLang` returned `cs` for everyone.
- `go/internal/web/public/offline_lang_test.go` — visitor/query/cookie/stale-session cases plus
  the signed-in fallback.

## Commands (last lines)

```
cd go && go build ./... && gofmt -l ./internal/web/public/          # clean
cd go && go test ./internal/web/public/ -run 'TestOffline' -count=1
ok  .../go/internal/web/public  0.325s
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py
{"paths": 137, "rows": 411, "pass": 252, "pass_soft": 12, "accepted": 101, "fail": 46}
```

Before: `fail 48`, with `host /offline` and `admin /offline` at `len 133/145 sim=0.57`.
After (verified, 2026-11-22 10:41): `{"paths": 137, "rows": 411, "pass": 260,
"pass_soft": 10, "accepted": 101, "fail": 40}` — `/offline` is `pass DOM match` for
anon, host and admin.

## The other ten rows are not auth pages

Measured with the audit's own servers, seed DB and persona cookies (`probe` scripts kept outside
the repo). For a signed-in persona the five auth paths never render their own template — Python
301/303s them to `/` and the browser lands on the dashboard:

```
host  /login          py 303 -> /   go 303 -> /     (both redirect: parity)
host  /login/link     py 303 -> /   go 303 -> /
host  /login/2fa      py 303 -> /login?notice=2fa_expired   go same
host  /signup         py 303 -> /   go 303 -> /
host  /account/accept py 303 -> /   go 303 -> /
```

So the audit compares the **dashboard DOM** for those five paths, for both personas. Python's
dashboard text is 655 chars (host) / 500 (admin home); Go's is 319 / 258. The audit rows for
`/login`, `/login/2fa`, `/login/link`, `/signup`, `/account/accept` are byte-identical to the `/`
row (`655/319`, `500/258`) because it is literally the same page.

Anon renders are already at parity (login 7441/7433 bytes, signup 6993/6922, link 5536/5522,
`/login` anon row passes today).

## Consequence for the index

- 2011 closes with this PR: `/offline` fixed, five auth pages proven at parity.
- The ten remaining rows belong to **2012** (dashboard + admin home). Nothing else in 2011 can
  close them, and 2012's own `/` rows are the same page.

## Deviations

- The brief's step 3 ("golden test against a Python render") was replaced by the handler-level
  language tests plus the audit row, because `/offline`'s only Go/Python difference is the
  language fallback, not markup.
- The `glob('/cursor/stores/*/docs/go-python-parity-audit.json')` snippet in §6 fails on this
  machine (`/cursor` does not exist); the audit's JSON is written under
  `$HOME/.local/parity/stores/cursor/stores/<id>/docs/`. The audit's printed summary line carries
  the fail count and was used instead.

## Questions

1. (2012) Python's dashboard headline is the phone text "All done. Nothing needs you today."
   while Go prints `needs_you.calm` ("All clear for now.") — which string is canonical for the
   desktop heading? Both exist in the Python i18n table; the audit compares the rendered text.

## Also closed in this branch (verified in the same run)

| Path | Rows | Change |
|---|---|---|
| `/p/{slug}/thanks` | 3 | booking shell carries the command palette + shortcuts dialogs (base.html renders them on every page) |
| `/booking-sites` | 2 | `booking_sites.title` defined (Python's block title is the h1) |
| `/apartments/{id}/booking-site` | 1 | back label `payments.page.title`, apartment name as the meta line |
| `/apartments/{id}/guide/questions` | 1 | one `Guest questions` header, no "nothing waiting" line when there are no questions, `Guest guide` action |

Running total: 48 -> 40 fail rows, pass 250 -> 260.
