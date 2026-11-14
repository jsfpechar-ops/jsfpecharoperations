# 1663: Go mail — `{{entry_code}}` send-time marker

Status: todo
Depends on: none | Base commit: bdfaa4d4 | Branch: task/1663-go-mail-entry-code-marker
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (mail secret)

## 1. Objective

The Go outbox fills a new marker `{{entry_code}}` at send time from the payload key `entry_code_enc` (Fernet ciphertext), exactly like `{{door_code}}`, but with the raw host-typed value (no `guestPinDisplay`), HTML-escaped in the HTML part. A marker with no key fails the send with `ErrDecryption`. Nothing queues the marker yet: the receipt brief 1667 will.

## 2. Context (verified on bdfaa4d4)

Markers and keys, `go/internal/mail/outbox_markers.go:24-35`:

```go
const (
	ClaimSecretMarker    = "{{claim_secret}}"
	DoorCodeMarker       = "{{door_code}}"
	GuestDetailsMarker   = "{{guest_details}}"
	ReceiptDetailsMarker = "{{receipt_details}}"

	claimSecretKey    = "claim_secret_enc"
	doorCodeKey       = "door_code_enc"
```

Door-code fill to mirror, `outbox_markers.go:147-160`:

```go
func (c Config) withDoorCode(value string, p obPayload) (string, error) {
	if !strings.Contains(value, DoorCodeMarker) {
		return value, nil
	}
	token := p.str(doorCodeKey)
	if token == "" {
		return "", fmt.Errorf("%w: outbox payload has a door code with no secret", ErrDecryption)
	}
```

Delivery chain, `outbox_markers.go:196-203`:

```go
func (c Config) delivery(ctx context.Context, pool *pgxpool.Pool, stored string, p obPayload, asHTML bool) (string, error) {
	v, err := c.withSecret(stored, p)
	if err != nil {
		return "", err
	}
	if v, err = c.withDoorCode(v, p); err != nil {
		return "", err
	}
```

Rules (`docs/context/rules.md` §Mail, owner 2026-11-14): the outbox never stores a secret in clear; a missing secret fails the send; the entry code is never logged (no value in any error text). The Go `mail` job is not live (`docs/plans/go-mail-job.md`; status: Python runs `mail`), so this is dormant until `mail` joins `UBYHOST_GO_JOB_KINDS`. Python `App/app/mail.py` is not changed (no go-first exception applies): the receipt that uses the marker is built in Go after the guest pages port (1667).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/mail/outbox_markers.go` | edit | constants, `withEntryCode`, one call in `delivery` |
| `go/internal/mail/outbox_entry_code_test.go` | new | the tests of step 3 |

No other file may change.

## 4. Steps

1. Constants: add `EntryCodeMarker      = "{{entry_code}}"` after the `DoorCodeMarker` line and `entryCodeKey      = "entry_code_enc"` after the `doorCodeKey` line (gofmt aligns).
2. After `withDoorCode`, add:

```go
// withEntryCode fills the building entry code: the host-typed value as stored,
// escaped in the HTML part. Never log the value.
func (c Config) withEntryCode(value string, p obPayload, asHTML bool) (string, error) {
	if !strings.Contains(value, EntryCodeMarker) {
		return value, nil
	}
	token := p.str(entryCodeKey)
	if token == "" {
		return "", fmt.Errorf("%w: outbox payload has an entry code with no secret", ErrDecryption)
	}
	code, err := c.decrypt(token)
	if err != nil {
		return "", err
	}
	if asHTML {
		code = html.EscapeString(code)
	}
	return strings.ReplaceAll(value, EntryCodeMarker, code), nil
}
```

   Add `"html"` to the imports if missing. In `delivery`, right after the `withDoorCode` block: `if v, err = c.withEntryCode(v, p, asHTML); err != nil { return "", err }` (three lines, same style).
3. Tests in `outbox_entry_code_test.go` (build a `Config` with a data key the way `outbox_golden_test.go` does: `grep -n "Config{" go/internal/mail/*_test.go | head`): (a) text part: marker replaced by the decrypted `A1#-*`; (b) HTML part: `<b>` in a code comes out as `&lt;b&gt;`; (c) marker with no key → `errors.Is(err, ErrDecryption)` and the error text has no code; (d) key with no marker → body unchanged; (e) a door code and an entry code in one body both filled.
4. Run §6, commit per step (`1663 step k`).

## 5. Do not touch

`App/app/mail.py`, `mail_notify.py`, `claim.py` (Python is not changed), other markers, `outbox_golden_test.go` fixtures (`App/scripts/mail_drain_golden.py` output), `obAttachments`.

## 6. Commands

From `go/`: `gofmt -l internal/mail/ 2>&1 | tail -5` (prints nothing)
From `go/`: `go vet ./internal/mail/ 2>&1 | tail -10`
From `go/`: `go test ./internal/mail/... 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Five tests of step 3 green; existing mail tests (golden included) unchanged and green.
- [ ] No error text or log line contains a code value.
- [ ] `git diff --stat origin/main` lists only the two files of §3 (plus the report).

## 8. Stop and ask

Stop if: an excerpt is not found; a mail golden changes; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/1663-report.md` (≤600 tokens), `Status: review`, one PR.

## Risk list (for the reviewer)

`go/internal/mail/outbox_markers.go` `delivery` (every Go-sent mail passes through it).

## Owner steps

None: dormant until the Go `mail` job is switched on (`docs/plans/go-mail-job.md` §5).
