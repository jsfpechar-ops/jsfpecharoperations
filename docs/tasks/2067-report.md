# 2067 report (partial)

Status: blocked (steps 3-6 not done; executor tool-call budget reached)

## Done

- Step 1 (commit "2067 step 1"): added `mail_completion_sent_title`, `mail_completion_sent_doc_label`, `mail_completion_sent_unnamed` to `App/scripts/go_mailnotify_completion_i18n.py`; regenerated `go/internal/mailnotify/completion_i18n_strings.json` (18 new lines, 3 keys x 6 languages; "guest keys missing per language: {}").
- Step 2 (commit "2067 step 2"):
  - `go/internal/maildetails/details.go` (new): `Renderer` implements `mail.DetailsRenderer`. `ReceiptDetails` ports `render_receipt_details` (claim row, guest query, decrypt-every-guest, mask only for typed-here guests, text and HTML output, empty string when no lines). `GuestDetails` returns `mail.ErrNoDetailsRenderer` (2068).
  - `go/internal/mail/outbox_markers.go`: `SetDefaultDetails(d DetailsRenderer)`.
  - `go/cmd/ubyhost-web/main.go`: imports `mail` and `maildetails`; `mail.SetDefaultDetails(maildetails.Renderer{})` is the first statement of `run()`.
  - `go build ./...` clean; `gofmt -l` empty on the touched packages.

## Not done

- Step 3: `App/scripts/mail_details_golden.py` and `go/internal/maildetails/testdata/receipt_golden.json` not written. No golden comparison against Python has been run.
- Step 4: `details_test.go` not written; no unit test run.
- Step 5: `details_db_test.go` not written; drain behaviour (sent with block filled, deleted stay, decryption failure, guest_details still ErrNoDetailsRenderer) not verified.
- Step 6: context lint not run; `Status:` line in the brief not edited.
- No `go test` run at all.

## Deviations

- Key source: `Renderer` has a `Getenv func(string) string` field (nil means `os.Getenv`) and calls `secure.LoadDataKeys` on first need, instead of receiving `Config.Keys`. `DetailsRenderer` has no config argument, so this matches the brief's fallback option.
- `SetDefaultDetails` call is at the top of `run()`, not a separate line before routes. Nothing else in `run()` runs before it.
- Trailers use Claude Opus 5.5 as instructed for this run. No PR opened, no push.

## Owner steps

None.
