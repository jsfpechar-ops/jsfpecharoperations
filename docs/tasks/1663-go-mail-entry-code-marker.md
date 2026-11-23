# 1663: Go mail — `{{entry_code_1}}` to `{{entry_code_3}}` send-time markers

Status: todo (runnable now)
Depends on: none | Base commit: fill from `git rev-parse --short HEAD` | Branch: task/1663-go-mail-entry-code-marker
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (mail secret)

## 1. Objective

Owner D1 (2026-11-22): up to 3 extra entry codes per apartment. The Go outbox fills three indexed markers `{{entry_code_1}}`, `{{entry_code_2}}`, `{{entry_code_3}}` at send time from the payload keys `entry_code_enc_1`, `entry_code_enc_2`, `entry_code_enc_3` (Fernet ciphertext, one per position), like `{{door_code}}` but with the raw host-typed value (no `guestPinDisplay`), HTML-escaped in the HTML part. A marker whose key is missing or empty fails the send with `ErrDecryption`; a key with no marker changes nothing; a row that gets no key gets no marker. Which codes appear and in what order is decided when the receipt is queued (1667, arrival order D5 via `entryCodeGuestOrder`); the mail job only fills what the body names. Nothing queues the markers yet.

## 2. Context (re-verified on the current checkout)

Markers and keys, `go/internal/mail/outbox_markers.go:24-36`:

```go
const (
	ClaimSecretMarker = "{{claim_secret}}"
	// ClaimSecretPayloadKey is the outbox payload field for an encrypted claim token.
	ClaimSecretPayloadKey = "claim_secret_enc"
	DoorCodeMarker        = "{{door_code}}"
	GuestDetailsMarker    = "{{guest_details}}"
	ReceiptDetailsMarker  = "{{receipt_details}}"

	claimSecretKey    = ClaimSecretPayloadKey
	doorCodeKey       = "door_code_enc"
```

Door-code fill to mirror, `outbox_markers.go:149-162`:

```go
func (c Config) withDoorCode(value string, p obPayload) (string, error) {
	if !strings.Contains(value, DoorCodeMarker) {
		return value, nil
	}
	token := p.str(doorCodeKey)
	if token == "" {
		return "", fmt.Errorf("%w: outbox payload has a door code with no secret", ErrDecryption)
	}
	pin, err := c.decrypt(token)
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(value, DoorCodeMarker, guestPinDisplay(pin)), nil
}
```
`decrypt` (`:114`) wraps every failure in `ErrDecryption` without any value in the text.

Delivery chain, `outbox_markers.go:198-205`:

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

Rules (`docs/context/rules.md` §Mail, owner 2026-11-14): the outbox never stores a secret in clear; a missing secret fails the send; no entry code is ever logged (no value in any error text). The Go `mail` job is not live (`docs/plans/go-mail-job.md`; status: Python runs `mail`), so this is dormant until `mail` joins `UBYHOST_GO_JOB_KINDS`. Python `App/app/mail.py` is not changed (no go-first exception applies): the receipt that uses the markers is built in Go after the guest pages port (1667, whose §2 uses the same marker and key names). `grep -rn entry_code go/internal/mail/` finds nothing today. Imports of `outbox_markers.go` (`:7-21`) do not include `html`; the test config pattern is `obTestConfig` (`outbox_golden_test.go:112-123`, `secure.NewMultiFernet([]byte(key))`, ciphertext via `Keys.Encrypt` / `EncryptString` in `go/internal/secure/fernet.go:156`, `datakeys.go:49`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/mail/outbox_markers.go` | edit | constants, two helpers, `withEntryCodes`, one call in `delivery` |
| `go/internal/mail/outbox_entry_code_test.go` | new | the tests of step 3 |

No other file may change.

## 4. Steps

1. Constants: in the exported `const` block add `EntryCodeMarker1 = "{{entry_code_1}}"`, `EntryCodeMarker2 = "{{entry_code_2}}"`, `EntryCodeMarker3 = "{{entry_code_3}}"` after the `DoorCodeMarker` line, and `entryCodeKey1 = "entry_code_enc_1"`, `entryCodeKey2`, `entryCodeKey3` after `doorCodeKey` (gofmt aligns). Add `EntryCodePayloadKey(position int) string` (exported, returns `entry_code_enc_<n>`) and `EntryCodeMarker(position int) string` (returns `{{entry_code_<n>}}`) so 1667 never builds the strings by hand; positions outside 1..3 return the empty string.
2. After `withDoorCode`, add one function and loop over the three positions:

```go
// withEntryCodes fills the extra entry codes: the host-typed value as stored,
// escaped in the HTML part. A marker without its key fails the send. Never log a value.
func (c Config) withEntryCodes(value string, p obPayload, asHTML bool) (string, error) {
	for position := 1; position <= 3; position++ {
		marker := EntryCodeMarker(position)
		if !strings.Contains(value, marker) {
			continue
		}
		token := p.str(EntryCodePayloadKey(position))
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
		value = strings.ReplaceAll(value, marker, code)
	}
	return value, nil
}
```

   Add `"html"` to the imports (between `"fmt"` and `"strconv"`). In `delivery` (`:198`), right after the `withDoorCode` block, add `if v, err = c.withEntryCodes(v, p, asHTML); err != nil { return "", err }` (three lines, same style). The error text names no position and no value.
3. Tests in `go/internal/mail/outbox_entry_code_test.go` (config as `obTestConfig`; read how `outbox_golden_test.go` builds `obGolden`/keys first, or build `Config{Keys: keys}` directly; encrypt fixtures with the same `keys`; `delivery` needs a pool only for the details markers, so call `Config.withEntryCodes` directly for the unit cases and `deliveryBody`/`deliveryHTML` only if a DB is set): (a) text part: `{{entry_code_1}}` replaced by the decrypted `A1#-*`; (b) HTML part: a code `<b>&` comes out as `&lt;b&gt;&amp;`; (c) marker 2 present with no `entry_code_enc_2` key (and with an empty string key) → `errors.Is(err, ErrDecryption)` and the error text contains no code; (d) keys 1 to 3 present but no markers → body unchanged; (e) all three markers and the door code in one body, each filled with its own value, order preserved; (f) a key for position 2 only and a marker for position 1 → ErrDecryption (no cross-position fill); (g) `EntryCodeMarker(0)`, `EntryCodeMarker(4)` and `EntryCodePayloadKey(4)` return the empty string; (h) a garbage ciphertext → `ErrDecryption`, text without the token.
4. Run §6, commit per step (`1663 step k`).

## 5. Do not touch

`App/app/mail.py`, `mail_notify.py`, `claim.py` (Python is not changed), other markers, `outbox_golden_test.go` fixtures (`App/scripts/mail_drain_golden.py` output), `obAttachments`.

## 6. Commands

From `go/`: `gofmt -l internal/mail/ 2>&1 | tail -5` (prints nothing)
From `go/`: `go vet ./internal/mail/ 2>&1 | tail -10`
From `go/`: `go test ./internal/mail/... 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] The eight cases of step 3 green; existing mail tests (golden included) unchanged and green.
- [ ] No error text or log line contains a code value.
- [ ] `git diff --stat origin/main` lists only the two files of §3 (plus the report).

## 8. Stop and ask

Stop if: an excerpt is not found; a mail golden changes; the payload key names or marker names differ from 1667 §2; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/1663-report.md` (≤600 tokens), `Status: review`, one PR.

## Risk list (for the reviewer)

`go/internal/mail/outbox_markers.go` `delivery` (every Go-sent mail passes through it): a body with no `{{entry_code_n}}` must come out byte for byte as before; the golden tests prove it.

## Owner steps

None: dormant until the Go `mail` job is switched on (`docs/plans/go-mail-job.md` §5).
