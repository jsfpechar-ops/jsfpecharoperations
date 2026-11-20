# 1428: Go mail — `BuildInvoiceIssued` (guest invoice e-mail)

Status: todo
Depends on: 1231 (mail package shell) | Base commit: current `origin/main` | Branch: `cursor/1428-go-mail-invoice-issued-dff7`
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (guest mail)

## 1. Objective

Port `mail_notify.build_invoice_issued` to `go/internal/mail` as `BuildInvoiceIssued`, golden-tested against Python. Export `ClaimSecretPayloadKey` for the invoice send route (brief 1429). No web route and no `UBYHOST_GO_PATHS` change.

## 2. Context

**Python source:** `App/app/mail_notify.py` `build_invoice_issued` (lines 2192–2247); guest catalogue keys listed in brief 1429 §2.

**Parity method (go-first mail pattern):** `App/scripts/go_invoice_issued_golden.py` calls the real Python builder; `go/internal/mail/invoice_issued_test.go` replays each case byte for byte. `App/scripts/go_mail_invoice_issued_i18n.py` writes `guest_i18n_strings.json` (go:embed), same idea as `go_mailnotify_i18n.py`.

**Markers:** `mail.ClaimSecretMarker` is already exported. Payload encryption uses `mail.ClaimSecretPayloadKey` (`claim_secret_enc`).

**Sidecars:** `docs/tasks/1428-files/<repo path>.txt`. Step 1 copies them; never retype. Manifest: `docs/tasks/1428-files/MANIFEST.sha256`.

| sha256 | file |
|---|---|
| `25006a6dd3a43e8038ed92b5c63c43ca3251cd7885c6c780f9d33a64d2aa5324` | `App/scripts/go_invoice_issued_golden.py` |
| `9729ed168cdf21025bf41940c9f640a166292c717b6e9a693649dc52c6108db0` | `App/scripts/go_mail_invoice_issued_i18n.py` |
| `1b49921a9d701b53eca3fa672f7caa1fd673aa70db930833fc7a9ce1082de59e` | `App/tests/test_go_invoice_issued_golden.py` |
| `16299360aefef8e5024560befb930ffd20af7eaf18fe1f0336442ace3ec1a73e` | `go/internal/mail/guest_footer.go` |
| `15b8de0ed12b25036d01427e9632bc0ca456fc58fb05bf2e61a27bf49ea1aa30` | `go/internal/mail/guest_i18n.go` |
| `709a081cbb951194cfbe8203407435ffb075f67a21d2013fa5791227a462719a` | `go/internal/mail/guest_i18n_strings.json` |
| `9d0cfc929b1dc1f7877274e954417f93a07bcf7f60a8dc4dc398b605f3c4a425` | `go/internal/mail/guest_shell.go` |
| `561581fd0ee1bc00fe5971b1cdcf479995ae137fa10dc37c91d35a29d6ba661e` | `go/internal/mail/invoice_issued.go` |
| `2551301e8e24d10112e243d3cf549e58dd5f078b8ba3b5b2f678132737338c1b` | `go/internal/mail/invoice_issued_test.go` |
| `6fae4279e60eb5d331ca9520a6e2e2d8c25af2a2071748cec83727ec299c2f27` | `go/internal/mail/outbox_markers.go` |
| `03a7d8352071d1b488f095d6c81a2e115ea92406a402a64c42e4e6e607199caa` | `go/internal/mail/testdata/invoice_issued_golden.json` |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/mail/invoice_issued.go` | create | `BuildInvoiceIssued` |
| `go/internal/mail/invoice_issued_test.go` | create | golden replay |
| `go/internal/mail/guest_i18n.go` | create | guest catalogue lookup |
| `go/internal/mail/guest_i18n_strings.json` | create | embedded strings |
| `go/internal/mail/guest_footer.go` | create | `HostDetails`, guest footer |
| `go/internal/mail/guest_shell.go` | create | guest `_shell` / `_block_panel` |
| `go/internal/mail/outbox_markers.go` | edit | export `ClaimSecretPayloadKey` |
| `go/internal/mail/testdata/invoice_issued_golden.json` | create | golden fixture |
| `App/scripts/go_invoice_issued_golden.py` | create | golden generator |
| `App/scripts/go_mail_invoice_issued_i18n.py` | create | i18n generator |
| `App/tests/test_go_invoice_issued_golden.py` | create | `--check` freshness |
| `docs/tasks/1428-files/**` | keep | exact-diff sidecars |
| `docs/tasks/1428-report.md` | create | report (§9) |

No other file may change.

## 4. Steps

0. Anchors (repo root; each prints `1` or STOP §8):
   - `grep -cF 'func BuildInvoiceIssued(' go/internal/mail/invoice_issued.go | tail -1`
   - `grep -cF 'ClaimSecretPayloadKey' go/internal/mail/outbox_markers.go | tail -1`
   - `find docs/tasks/1428-files -name '*.txt' ! -name 'MANIFEST.sha256' | wc -l | tail -1` → `11`

1. Copy sidecars and verify:

   ```bash
   S=docs/tasks/1428-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'MANIFEST.sha256' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 11 lines ending `: OK`. Commit `1428 step 1`.

2. Regenerate goldens (App venv):

   ```bash
   cd App && .venv/bin/python scripts/go_mail_invoice_issued_i18n.py && .venv/bin/python scripts/go_invoice_issued_golden.py 2>&1 | tail -5
   ```

   Commit only if bytes changed (`1428 step 2`).

3. Run §6; write report.

## 5. Do not touch

`UBYHOST_GO_PATHS`, any `register_web_*.go`, `go/internal/web/invoices/send.go` (brief 1429), `App/app/`.

## 6. Commands

From `go/`: `gofmt -l internal/mail/ 2>&1 | tail -5` (empty)
From `go/`: `go vet ./internal/mail/... 2>&1 | tail -10`
From `go/`: `go test ./internal/mail/... -count=1 2>&1 | tail -30`
From `App/`: `.venv/bin/python -m pytest tests/test_go_invoice_issued_golden.py -q --tb=short -x 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Six golden cases: subject, text and html match Python byte for byte.
- [ ] `ClaimSecretPayloadKey` exported; existing mail tests still green.
- [ ] No route registration; diff limited to §3.

## 8. Stop and ask

Stop when: anchor missing; golden drift not fixable by re-running scripts; file outside §3 needed; 25 tool calls.

## 9. Report

`docs/tasks/1428-report.md`, `Status: review`, one PR.

## Risk list (for the reviewer)

Guest footer carries host contact e-mail/phone (expected). Download URL in goldens uses `{{claim_secret}}`, never a real token.

## Owner steps

None.