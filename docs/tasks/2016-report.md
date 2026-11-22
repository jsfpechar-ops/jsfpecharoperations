# 2016 report — guest link hub `/l/{token}...`

Status: review (21 audit rows closed at character-for-character DOM equality)

## Rows closed (measured with the audit's servers, seed DB and persona cookies)

Probe = `probe_l.py` (out of repo, imports `scripts/e2e/page_parity_audit.py`, Playwright,
`norm_dom`). Before → after, `py/go` normalised-text length and status:

| Path | anon | host | admin |
|---|---|---|---|
| `/l/{token}` | 581/613 → **581/581** | 670/613 → **670/670** | 581/613 → **581/581** |
| `/l/{token}/1` | 1480/5 → **1480/1480** | 10065/5 → **10065/10065** | 1480/5 → **1480/1480** |
| `/claim` | 455/7 → **455/455** | 455/7 → **455/455** | 455/7 → **455/455** |
| `/guide` | 1480/5 → **1480/1480** | 475/5 → **475/475** | 1480/5 → **1480/1480** |
| `/guide/photos/1/1` | 1480/5 → **1480/1480** | **404/200** → **404/404** (488/488) | 1480/5 → **1480/1480** |
| `/new` | 1480/9916 → **1480/1480** | 10065/9916 → **10065/10065** | 1480/9916 → **1480/1480** |
| `/edit/1` | **200/403** → **200/200** (1480/1480) | 617/384 → **617/617** | **200/403** → **200/200** (1480/1480) |
| `/remove/1` | **200/403** → **200/200** (1480/1480) | 599/384 → **599/599** | **200/403** → **200/200** (1480/1480) |

Rows left: none for `/l/`. Not ported on purpose: `guest/stay.html` (the hub after a
form is sent — no audit row reaches it here), `assigned.html`, the live-guide card list
(topic kicker left out rather than guessed) and `guest_remove.html`'s template (still Go's
form shell).

## Security note on the 200s (measure, do not "fix")

`UBYHOST_GUEST_PIN=0` in the audit env (`scripts/e2e/page_parity_audit.py` `ENV`), so
`config.GUEST_PIN_REQUIRED` (`app/config.py:441`) is off and `_require_pin`
(`app/routes/guest.py:755`) returns None: **no PIN page appears in these rows**. The
200 on `/edit/{id}` and `/remove/{id}` for anon and admin is the **claim ask**:
`_require_claim_session` (`guest.py:1242-1256`) 303-redirects a device that does not hold
the claim to `/l/{token}/{res}`, and `stay_overview` renders `guest/claim.html` with 200
(`guest.py:1526-1527`). Go now does the same (`formPagesRequireClaim` 303 →
`stayOverview` → `claim.tmpl`); the ownership rule itself is unchanged — a guest id not in
`ubyhost_owned` still gets `not_yours` 403, as the host row shows.

The host 404 on `/guide/photos/1/1` is `guest_guide_view._photo:134` returning None for a
photo whose card is not in the level's list, answered by `_not_found` (`:194`). Go's
`serveGuidePhoto` applies the same rule and the page is now the bare `bad_link` 404.

## Files changed

`go/internal/web/guest/`: `page_shell.go`, `pages.go` (new), `templates/{claim,confirm,guide}.tmpl`
(new), `templates/{base,unavailable}.tmpl`, `shell.go`, `pick.go`, `stay_claim.go`,
`form_pages.go`, `form_pages_fill.go`, `guide_gate_stub.go`, `guide_page.go`, `guide_view.go`,
`i18n.json` + `i18n_keys.txt` (55 keys the pages print, merged from `app/i18n.py`).

## Commands

```
cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/...   # ok guest 0.311s, main 1.965s
cd go && gofmt -l ./internal/web/guest/ ./cmd/ubyhost-web/        # prints nothing
```

## Deviations

- No DB golden test in the repo (brief step 3): parity is verified with the probe above, as
  2011 did; the existing handler tests stay green.
- 1820 §6 screenshots not taken: the tool writes under `/cursor/stores/...`, which does not
  exist on this machine (same as 2011's note).
- `_host_link_note` uses the guest catalog's `workflow.link.host_note*` (same host copy,
  both catalogs generated from `host_i18n.py`).
- While regenerating the guest catalog the repo's `App/scripts/go_host_i18n.py` also rewrote
  `go/internal/web/booking/i18n.json`; that was reverted untouched.

## Questions

1. Is `GUEST_PIN_REQUIRED` meant to be off in the audit env? If a PIN row should be compared
   too, the audit needs a third seed with `UBYHOST_GUEST_PIN=1`.
