# 2067: Go mail send-time renderer, part 1: `{{receipt_details}}` and the wiring

Status: todo
Depends on: 1231b (applied), 2065 (applied) | Executor: Haiku 5.5, 30 tool calls | Part 2: [2068](2068-go-mail-guest-details-renderer.md)
Trailers on every commit: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf`

## 1. Objective

The Go mail drain fills `{{receipt_details}}` and `{{guest_details}}` through `mail.DetailsRenderer`, and nothing sets it. `go/internal/mail/outbox_drain.go:168` puts such a row back to `queued` forever, so after the all-Go deploy no completion receipt (2065) and no guest-details host mail is ever sent. This brief writes the receipt renderer, wires one package default at startup (so every drain, `SendNow` and `Drain` caller is covered), and proves the drain sends the row. 2068 adds the guest list.

## 2. Context (paste, do not re-derive)

Python `App/app/mail.py:377-410`: `_with_guest_details` / `_with_receipt_details` (marker `{{receipt_details}}`, payload key `receipt_details_reservation_id`, `lang` from payload, default `en`). Go side already matches: `go/internal/mail/outbox_markers.go:79-95` (interface, `obDefaultDetails`, `ErrNoDetailsRenderer`) and `:225-250` `withDetails`. Only the renderer is missing. `go/internal/mail/outbox_config.go:41` `Config.Details` (nil means `obDefaultDetails`).

Python renderer `App/app/mail_notify.py:2093` `render_receipt_details(reservation_id, *, lang, as_html)`:
- title = guest text `mail_completion_sent_title` (en "What you sent"; other keys `mail_completion_sent_doc_label` "Document number", `mail_completion_sent_unnamed` "Guest"; catalogue `App/app/i18n.py` ~669-671, all languages).
- `claimed_at` from `reservation_claim` where `reservation_id = ?` (empty string when no row).
- guests: `SELECT id, first_name, surname, doc_number, doc_number_enc, entered_by, created_at FROM guest WHERE reservation_id = ? AND archived_at IS NULL ORDER BY is_lead DESC, id`. Python's `db.query` hydrates `doc_number` from `doc_number_enc` (`App/app/db.py:~1990-2007`, `decrypt_field`: no token gives the plain column; a token that fails to decrypt is an error, never empty).
- per guest: `line` = `first_name` and `surname` (each stripped, joined with one space, empty parts dropped) or the "unnamed" text. `typed_here` = `entered_by == "guest"` AND `since != ""` AND `str(created_at) >= since` (string comparison). When `typed_here`, `masked = mask_document_number(doc_number)`; if non-empty `line = f"{line} – {doc_label}: {masked}"` (en dash U+2013).
- `mask_document_number` (`mail_notify.py:1894`): remove all whitespace; empty gives ""; shorter than 5 characters gives `••••`; else `•••• ` + last four characters.
- no lines (no guests, also a deleted stay): return "" (the marker is replaced by an empty string; the mail still goes).
- text: `"\n".join([title, *lines])`. HTML: `_block_section(title, lines[0]) + "".join(_block_paragraph(l) for l in lines[1:])`. The Go equivalents are `mailnotify.BlockSection(label, body)` and `mailnotify.BlockParagraph(text, false)` (`go/internal/mailnotify/shell.go:255,277`).
- Python raises nothing for a missing stay; Go must match (no error, empty string).

Decrypt in Go: `go/internal/secure/fieldcrypto.go:20` `(*MultiFernet).DecryptField(token, now)`; `mail.Config.Keys` is the `*secure.MultiFernet` the drain already holds. Rule: token empty means use the plain column; token present and undecryptable returns an error wrapping `mail.ErrDecryption` (the drain then counts a failed attempt, as Python does). Reuse the same rule as `go/internal/ubyport/collect.go:269` `decryptOrPlain`; copy its three lines into the new package instead of importing an unexported helper.

Import direction: `go/internal/mail` imports `go/internal/mailnotify`, and `mailnotify` must not import `mail`. So the renderer goes in a NEW package `go/internal/maildetails` that imports `mail`, `mailnotify` and `secure`. The renderer needs the guest catalogue keys above: check `grep -c completion_sent go/internal/mailnotify/*_strings.json`; if 0 (expected), add the three keys for every language via the existing generator `App/scripts/go_mailnotify_completion_i18n.py` (read its first 30 lines; it writes `completion_i18n_strings.json`). Then `GuestText(lang, key, args)` from `mailnotify/i18n.go:103` works for them.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/go_mailnotify_completion_i18n.py` | edit | add the 3 `mail_completion_sent_*` keys to its list |
| `go/internal/mailnotify/completion_i18n_strings.json` | regenerate | by the script, not by hand |
| `go/internal/maildetails/details.go` | create | `Renderer{}` implementing `mail.DetailsRenderer`; `ReceiptDetails` real; `GuestDetails` returns `mail.ErrNoDetailsRenderer` until 2068 |
| `go/internal/mail/outbox_markers.go` | edit | add `func SetDefaultDetails(d DetailsRenderer) { obDefaultDetails = d }` right under the `obDefaultDetails` var |
| `go/cmd/ubyhost-web/main.go` (or the file with `func main`; find with `grep -ln 'func main' go/cmd/ubyhost-web/*.go`) | edit | one line before routes and jobs start: `mail.SetDefaultDetails(maildetails.Renderer{})` |
| `go/internal/maildetails/details_test.go` | create | unit + golden tests (step 4) |
| `App/scripts/mail_details_golden.py` | create | Python oracle (step 3) |
| `go/internal/maildetails/testdata/receipt_golden.json` | create | generated by the script |
| `go/internal/maildetails/details_db_test.go` | create | DB-backed drain tests (step 5) |
| `docs/tasks/2067-go-mail-details-renderer.md` | edit | `Status:` line only |
| `docs/tasks/2067-report.md` | create | report |

No other file may change. Every drain is built from `mail.ConfigFromEnv` in `register_job_mail.go`, `door_codes_wire.go`, `stays/claim_ops.go`, `stays/claim_seed.go`, `web/auth` and `doorcodes/wire`; the package default covers them all, so do not touch those.

## 4. Steps

0. Checks (one call, repo root): `git branch --show-current`; `grep -c 'obDefaultDetails' go/internal/mail/outbox_markers.go` is at least 3; `ls go/internal/maildetails 2>&1 | grep -c 'No such'` prints 1; `git status --short | tail -5` empty; `grep -rn 'SetDefaultDetails\|obDefaultDetails *=' go --include=*.go | grep -v _test | tail -5` prints nothing. A check failing: STOP.
1. Catalogue: edit `go_mailnotify_completion_i18n.py` to add the 3 keys, run it from `App/` (`/var/tmp/ubyvenv/bin/python scripts/go_mailnotify_completion_i18n.py 2>&1 | tail -5`, else `.venv/bin/python`), then `grep -c completion_sent go/internal/mailnotify/completion_i18n_strings.json` is at least 3 and `git diff --stat go | tail -5` shows only that JSON. Commit "2067 step 1".
2. Write `maildetails/details.go` and the `SetDefaultDetails` line and the `main` line. `ReceiptDetails(ctx, pool, id, lang, asHTML)`: query the claim row and the guests with the SQL above through pgx (`$1` params, `COALESCE` text columns to `''`; `created_at` and `claimed_at` compared as the stored text, so select them cast `::text`; check how the existing Go code in `go/internal/mail/outbox_drain.go` reads timestamps and copy that cast). Decrypt `doc_number_enc` with `Keys.DecryptField(token, now)` only when `typed_here` (Python decrypts all, but a failing token for a non-typed guest must still error: decrypt every guest, mask only when `typed_here`). Build text and HTML exactly as in §2. The renderer needs `Keys`; get them from a field `Keys *secure.MultiFernet` on `Renderer`, set in `main` from the same source `mail.ConfigFromEnv` uses (grep `Keys` in `go/internal/mail/outbox_config.go`; if `ConfigFromEnv` loads keys itself, instead add `Keys` to the `DetailsRenderer` call by reading it from `c.Keys` is NOT possible because the interface has no config: so let `Renderer` build the keys lazily with the same loader function `ConfigFromEnv` calls, and name it in the report). `go build ./... 2>&1 | tail -30` clean. Commit "2067 step 2".
3. `App/scripts/mail_details_golden.py`: follow the pattern of `App/scripts/mail_drain_golden.py` (read its first 60 lines for the DB bootstrap). Insert invented rows (all names and e-mails invented, `@example.test`) into a scratch DB, call the real `mail_notify.render_receipt_details(rid, lang=..., as_html=...)`, write `go/internal/maildetails/testdata/receipt_golden.json` with the inputs (guest rows, `claimed_at`) and both outputs. Cases: (a) two guests, lead typed here with a 9-character document number (masked with last four); (b) typed here, number of 3 characters (mask only); (c) host-entered guest (name only); (d) typed before `claimed_at` (name only); (e) no claim row (nobody is typed here); (f) unnamed guest (catalogue "Guest"); (g) no guests, and an id that does not exist (both ""); (h) lang `cs` and `de` for case (a); (i) a name containing `<` and `&` (HTML escaping). Run it twice, same hash. Commit "2067 step 3".
4. `details_test.go`: load the JSON, seed each case into a Postgres test DB (`UBYHOST_TEST_DATABASE_URL`; copy the seeding helpers from `go/cmd/ubyhost-web/completion_hooks_db_test.go`), call `Renderer.ReceiptDetails` and compare byte for byte, text and HTML. Plus: a token that does not decrypt returns an error that `errors.Is(err, mail.ErrDecryption)`. Run `cd go && go test ./internal/maildetails/... -count=1 2>&1 | tail -30`. Commit "2067 step 4".
5. `details_db_test.go` (package `maildetails_test`, real `mail.Config` with the console backend, same helper style as `go/internal/mail/outbox_drain_test.go:322-345`):
   - a queued `kind='completion'` outbox row made by the real 2065 path (call `mailnotify`/`guest` completion hook exactly as `go/cmd/ubyhost-web/completion_hooks_db_test.go` case 1 does) with `{{receipt_details}}` in the stored text and html: after `mail.Drain`, row `state = 'sent'`, and the sent text and html contain the block for the seeded guests (compare with `Renderer.ReceiptDetails` output) and no `{{`.
   - a row whose reservation was deleted (payload id points to no stay): `state = 'sent'` with the marker replaced by "" (Python behaviour), no error.
   - a row with the marker and no `receipt_details_reservation_id` in the payload: stays not sent, attempt counted as a decryption failure, same as `go/internal/mail/outbox_drain_test.go` already asserts for other markers (read that test, mirror it).
   - a `{{guest_details}}` row still hits `ErrNoDetailsRenderer` here (2068 flips this; write the assertion with the comment `2068 replaces this`).
   Run `cd go && UBYHOST_TEST_DATABASE_URL=<given url> go test ./internal/maildetails/... ./internal/mail/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30`. The existing `TestNoDetailsRendererPutsRowBack` sets `obDefaultDetails = nil` itself, so it must still pass. Commit "2067 step 5".
6. Context lint, report, `Status: review`, commit "2067 step 6".

## 5. Do not touch

`{{guest_details}}` (2068). Any other marker: audited, nothing else is missing: Python fills `{{claim_secret}}`, `{{door_code}}`, `{{guest_details}}`, `{{receipt_details}}` in `mail.py:188-200`; Go already has the first two and the entry codes (`outbox_markers.go:26-34`). The Go side does not yet enqueue `guest_details_host` at all (Python `mail_notify.build_host_guest_details`); that is a separate port, state it in the report.

## 6. Commands

`gofmt -l .` empty; `go vet ./internal/maildetails/... ./internal/mail/... 2>&1 | tail -30`; the two `go test` lines in steps 4 and 5. 0 new skips (name every SKIP you see). Python: `python3 scripts/context_lint.py 2>&1 | tail -3` from the repo root.

## 7. Acceptance

- [ ] Golden fixture compares equal for all cases, text and HTML.
- [ ] A queued completion row with `{{receipt_details}}` is `sent` after `mail.Drain`, block filled.
- [ ] Deleted-stay row is sent with an empty block.
- [ ] `grep -rn 'SetDefaultDetails' go --include=*.go | grep -v _test | tail -5` shows the definition and exactly one call in `main`.
- [ ] No personal data in fixtures or the report (invented names only).

## 8. Stop and ask

Anchor not found; import cycle between `maildetails` and `mail`; `ConfigFromEnv` gives no way to build the same keys; the golden script needs a dependency; a test fails twice.

## 9. Report

Write `docs/tasks/2067-report.md` (600 tokens at most). Owner steps: none. After merge the owner checks nothing; deploy is automatic.

