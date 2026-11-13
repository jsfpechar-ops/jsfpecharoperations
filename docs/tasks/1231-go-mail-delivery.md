# 1231: Go mail delivery, part 1: config, markers, attachments, MIME, SES v2 client

Status: todo
Depends on: 1230 (plan, this branch) | Base commit: 902bc51 | Branch: task/1230-track-a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (code is copied by a script; do not read the code blocks)

## 1. Objective

Add the first half of the Go port of App/app/mail.py's delivery as four new files in `go/internal/mail/`: mail config and env checks, the send-time markers and attachments, the MIME builder and a stdlib SES v2 client with SigV4. Parts 1231b and 1231c add the drain loop, the Python golden and the tests on the same branch.

## 2. Context

Plan [go-mail-job](../plans/go-mail-job.md) step 1231, tier B. This port is three briefs run in order on one branch, one PR: **1231** (this: config, markers and attachments, MIME, SES client), **1231b** (Drain, SendNow, Purge, the golden script and fixtures), **1231c** (the Go tests). Nothing calls the code until brief 1236.

- Python source (read-only, ported): `App/app/mail.py` 201-273 (normalise, mask, validate_mail_env), 343-520 (markers, attachments, `_raw_message`), 542-600 (`_send_console`, `_log_staging_link`), 629-735 (`list_unsubscribe_headers`, `display_from`, `_send_ses`), 737-845 (`drain`, `_deliver`, `send_now`, `purge_old`); `App/app/alerts.py` 440-520 (`raise_alert`).
- `go/internal/mail` is imported by `go/internal/ubyport`, so it cannot import ubyport: the `mail_failed` alert write is ported in 1231b (same SQL shape as `ubyport.RaiseAlert`). `payments.qrPNGBytes` is unexported, so `obQRPNG` repeats its two lines (same library, same bytes as the Go `/payments/qr` route).
- Existing files in `go/internal/mail/` do not change. Unexported names in the new files start with `ob` or `ses`.

Behaviour decisions (for the reviewer; the code already does this):
- Timestamps: `updated_at`/`sent_at`/alert `created_at` = `db.utcnow()` form `2026-11-13T10:00:00+00:00`; `next_attempt_at` = `2026-11-13T14:16:00Z` (naive isoformat + `Z`, as `_deliver`); Purge cutoff = Prague wall clock `isoformat()` (microseconds only when non-zero), compared as text like Python.
- Back-off `min(6 h, 60 s * 2^min(attempts, 8))`; attempt 8 -> `failed` + alert `warning`/`mail_failed`, dedupe `mail_failed:<id>`, params `error`, `kind`, `to` sorted like `json.dumps(sort_keys=True)`. The 6 h cap is never reached (max 4 h 16 min), same as Python.
- `last_error`, alert detail and params use the error text with any e-mail address replaced by `[address]`, cut to 400 characters (Python puts `str(exc)` uncut into the alert; Go errors never carry addresses or bodies).
- `SendNow(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, outboxID int64) error`: id <= 0, mail disabled, row missing or not queued, claim lost -> nil. A failed delivery -> nil (row queued with back-off). Error only for an invalid mail env or DB trouble.
- SES: always v2 (`POST https://email.<region>.amazonaws.com/v2/email/outbound-emails`, SigV4 service `ses`). Python sends plain mails over v1; v2 `Simple` delivers the same message under the same IAM action `ses:SendEmail`. `Raw` (MIME) when there are attachments, Reply-To then in the MIME headers. Raw MIME is compared with Python by decoded structure (headers, content types, filenames, cids, part hashes), not bytes (boundaries are random in both).
- QR PNG: not byte-identical to Python (go-qrcode picks another mask than Python's qrcode; both encode the same SPAYD at 246x246). The golden compares its size only.
- `{{guest_details}}` / `{{receipt_details}}`: the renderer (port of `mail_notify.render_guest_details` / `render_receipt_details`) is a later brief that sets `obDefaultDetails`. Until then a row with those markers is put back to `queued` without an attempt, and Drain/SendNow return `ErrNoDetailsRenderer`: never sent with a marker, never failed.
- Logs and errors carry masked addresses only; the staging login-link log (staging + console + link kinds) logs the link with a masked address, as Python.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/mail/outbox_config.go` | create | Config, ConfigFromEnv (validate_mail_env), DisplayFrom, MaskEmail, address/time helpers |
| `go/internal/mail/outbox_markers.go` | create | send-time markers, DetailsRenderer hook, attachments |
| `go/internal/mail/outbox_mime.go` | create | MIME message for SES v2 Raw (_raw_message) |
| `go/internal/mail/outbox_ses.go` | create | stdlib SES v2 client, SigV4, list_unsubscribe_headers, _send_ses |
| `docs/tasks/1231-go-mail-delivery.md` | edit | `Status:` line only |
| `docs/tasks/1231-report.md` | create | report |

No other file may change.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `task/1230-track-a`; `grep -c '^func LoadDataKeys' go/internal/secure/datakeys.go`, `grep -c '^func LocalNow' go/internal/deadlines/deadlines.go` and `grep -c 'skip2/go-qrcode' go/go.mod` each print 1; `ls go/internal/mail/outbox_config.go go/internal/mail/outbox_markers.go go/internal/mail/outbox_mime.go go/internal/mail/outbox_ses.go 2>&1 | grep -c 'No such file'` prints 4; `git status --short | tail -5` is empty. Any check failing: STOP (§8). Then write the helper that copies code block k of this brief byte for byte:

```bash
cat > /tmp/extract_block.py <<'EOF'
import re, sys
src, k, dest = sys.argv[1], int(sys.argv[2]), sys.argv[3]
text = open(src, encoding='utf-8').read()
blocks = re.findall(r'^```(?:python|go)\n(.*?)^```$', text, re.S | re.M)
open(dest, 'w', encoding='utf-8').write(blocks[k - 1])
EOF
```

1. Create the 4 files in one call (from the repo root):

```bash
B=docs/tasks/1231-go-mail-delivery.md; X="python3 /tmp/extract_block.py $B"
mkdir -p go/internal/mail App/scripts
$X 1 go/internal/mail/outbox_config.go
$X 2 go/internal/mail/outbox_markers.go
$X 3 go/internal/mail/outbox_mime.go
$X 4 go/internal/mail/outbox_ses.go
sha256sum go/internal/mail/outbox_config.go go/internal/mail/outbox_markers.go go/internal/mail/outbox_mime.go go/internal/mail/outbox_ses.go | tail -10
```

   Expected:

   - `3184c56523f18337d77a4c161d6089ec8d4179429b53b398fb1e5ca4a1b0b30e`  `go/internal/mail/outbox_config.go`
   - `eafe5e777f1b993e855340b292757f295e76b865c7e599c23af0bcfe583b555e`  `go/internal/mail/outbox_markers.go`
   - `e9e9765c4cebb9d61913fe936c1123ea474e28a275d9fb533f6b7f6950f8d741`  `go/internal/mail/outbox_mime.go`
   - `b6b68fc10d922a2e108fe1c23bc5b4baa90f3f177582a2dab20254fc1e899fa4`  `go/internal/mail/outbox_ses.go`

   A different hash: re-run that one extract once; still different: STOP (§8).

2. From `go/`: `test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -30` prints nothing (the package compiles; tests come in 1231c). Commit "1231 step 1-2".

3. Write the report (§9), set `Status: review`, commit "1231 step 3".

## 5. Do not touch

`App/app/` (all of it), `App/migrations_pg/`, every existing file in `go/internal/` (incl. the `go/internal/mail/*.go` files that exist on the base commit, `go/internal/ubyport/`, `go/internal/payments/`, `go/internal/secure/`, `go/internal/jobs/`), `go/cmd/`, `go/go.mod`, `go/go.sum`, `docs/context/`, `.github/`. No job kind, env var, route, migration or dependency. Hard rules 2 (no addresses or bodies in logs or errors), 3, 4, 5.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -30`. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The four hashes match.
- [ ] gofmt empty, `go vet ./...` clean.
- [ ] Context lint passes.
- [ ] `git diff --stat 902bc51..HEAD | tail -20` lists only paths of the 1230/1231 briefs' §3.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- a step 0 check fails, or a hash still differs after one re-extract (never edit code by hand);
- `cases.json` differs while the script hash matches (Python behaviour moved: never edit JSON, Python or Go to match);
- a parity test fails (`TestGoldenDelivery`, `TestGoldenAddressHelpers`, `TestSigV4MatchesBotocore`), or any test fails twice;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a file outside §3 needs a change, or a new dependency seems needed;
- you need push, merge, a PR, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1231-report.md` (600 tokens at most) and set `Status: review`. It has: 1. `git diff --stat HEAD~2..HEAD | tail -10`; 2. each command with its last 5 lines; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

- `outbox_ses.go`: SigV4 (1231c checks it against botocore), the v2 Simple/Raw choice, no response body in errors (SES echoes addresses), `MessageId` required.
- `outbox_markers.go`: a marker with no secret or stay -> error; the platform invoice sha256 check; the filing PDF decrypt.
- `outbox_config.go`: `Validate` = validate_mail_env; keys loaded only when mail is on. Known differences: `UBYHOST_SES_REGION=` (set but empty) means the default region in Go (getenv cannot tell unset from empty) where Python reports it missing; `normalise_email` ports the two stored forms, not all of `email.utils.parseaddr` (the golden covers 13 inputs).
- Outbound request (rule 2), for the PR text: SES `SendEmail` to `email.<region>.amazonaws.com`, the same provider, region and credentials Python's boto3 uses today; reason: deliver the transactional mails once the mail job runs on Go.

## Owner steps

None (nothing is wired). Brief 1236 carries the switch; it must not be switched on before the guest/receipt detail renderer brief is merged, or guest-list and receipt mails stay queued.

## Code blocks

### Block 1: `go/internal/mail/outbox_config.go`

```go
package mail

// Delivery half of App/app/mail.py (brief 1231): configuration, address helpers
// and the shared error values. Unexported names start with ob so they cannot
// clash with the message builders in this package.

import (
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Backend names, as UBYHOST_MAIL_BACKEND spells them.
const (
	BackendDisabled = "disabled"
	BackendConsole  = "console"
	BackendSES      = "ses"
)

// Config is everything one drain needs. Now, HTTPClient and SESEndpoint are
// injectable so tests need no clock, network or AWS account.
type Config struct {
	Backend         string
	Deployment      string
	From            string
	SESRegion       string
	AccessKeyID     string
	SecretAccessKey string
	Keys            *secure.MultiFernet
	Now             func() time.Time
	HTTPClient      *http.Client
	// SESEndpoint overrides https://email.<region>.amazonaws.com (tests only).
	SESEndpoint string
	// Details fills {{guest_details}} and {{receipt_details}} at send time.
	// Nil means the package default (obDefaultDetails, set by brief 1231b).
	Details DetailsRenderer
}

// Errors the delivery returns. None of them carries an address or a secret.
var (
	// ErrMailConfig is mail.MailConfigError.
	ErrMailConfig = errors.New("mail configuration error")
	// ErrDecryption is db.DecryptionError.
	ErrDecryption = errors.New("stored value could not be decrypted")
)

func obConfigErr(format string, args ...any) error {
	return fmt.Errorf("%w: %s", ErrMailConfig, fmt.Sprintf(format, args...))
}

// ConfigFromEnv reads the mail environment and applies validate_mail_env:
// an invalid backend, ses outside production or an incomplete ses setup is an
// error. The data keys are loaded only when a backend is on.
func ConfigFromEnv(getenv func(string) string) (Config, error) {
	cfg := Config{
		Backend:         strings.ToLower(strings.TrimSpace(obDefault(getenv("UBYHOST_MAIL_BACKEND"), BackendDisabled))),
		Deployment:      strings.ToLower(strings.TrimSpace(obDefault(getenv("UBYHOST_DEPLOYMENT"), "local"))),
		From:            strings.TrimSpace(getenv("UBYHOST_MAIL_FROM")),
		SESRegion:       strings.TrimSpace(obDefault(getenv("UBYHOST_SES_REGION"), "eu-central-1")),
		AccessKeyID:     strings.TrimSpace(getenv("UBYHOST_AWS_ACCESS_KEY_ID")),
		SecretAccessKey: strings.TrimSpace(getenv("UBYHOST_AWS_SECRET_ACCESS_KEY")),
	}
	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	if cfg.Enabled() {
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return Config{}, fmt.Errorf("mail data keys: %w", err)
		}
		cfg.Keys = keys
	}
	return cfg, nil
}

func obDefault(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}

// Validate is validate_mail_env without the warnings.
func (c Config) Validate() error {
	switch c.Backend {
	case BackendDisabled, BackendConsole, BackendSES:
	default:
		return obConfigErr("UBYHOST_MAIL_BACKEND is invalid (use disabled, console, or ses)")
	}
	if c.Backend == BackendSES && c.Deployment != "production" {
		return obConfigErr("UBYHOST_MAIL_BACKEND=ses is only allowed on production; use console on staging")
	}
	if c.Backend == BackendSES {
		var missing []string
		for _, f := range []struct{ key, value string }{
			{"UBYHOST_SES_REGION", c.SESRegion},
			{"UBYHOST_MAIL_FROM", c.From},
			{"UBYHOST_AWS_ACCESS_KEY_ID", c.AccessKeyID},
			{"UBYHOST_AWS_SECRET_ACCESS_KEY", c.SecretAccessKey},
		} {
			if f.value == "" {
				missing = append(missing, f.key)
			}
		}
		if len(missing) > 0 {
			return obConfigErr("production SES is selected but incomplete: %s", strings.Join(missing, ", "))
		}
	}
	return nil
}

// Enabled is mail_enabled: console or ses.
func (c Config) Enabled() bool { return c.Backend == BackendConsole || c.Backend == BackendSES }

func (c Config) now() time.Time {
	if c.Now != nil {
		return c.Now().UTC()
	}
	return time.Now().UTC()
}

// DisplayFrom is display_from: a readable name in front of a bare address.
func (c Config) DisplayFrom() string { return DisplayFrom(c.From) }

// DisplayFrom is mail.display_from(address).
func DisplayFrom(address string) string {
	value := strings.TrimSpace(address)
	if value == "" || strings.Contains(value, "<") || !strings.Contains(value, "@") {
		return value
	}
	return "UbyHost <" + value + ">"
}

var obEmailRE = regexp.MustCompile(`^[^@\s]+@[^@\s]+\.[^@\s]+$`)

// obNormaliseEmail is mail.normalise_email for the two forms the app stores,
// a plain address or "Name <addr>" (the same rule as ubyport.NormaliseEmail,
// which this package cannot import).
func obNormaliseEmail(raw string) string {
	s := strings.TrimSpace(raw)
	if strings.ContainsAny(s, ",\"") || strings.Count(s, "<") > 1 || strings.Count(s, ">") > 1 {
		return ""
	}
	addr := s
	if i := strings.Index(s, "<"); i >= 0 {
		j := strings.Index(s, ">")
		if j < i || strings.TrimSpace(s[j+1:]) != "" {
			return ""
		}
		addr = s[i+1 : j]
	}
	addr = strings.ToLower(strings.TrimSpace(addr))
	if addr == "" || len(addr) > 254 || !obEmailRE.MatchString(addr) {
		return ""
	}
	return addr
}

// MaskEmail is mail.mask_email. A host part that is empty gives "" (Python
// raises IndexError there).
func MaskEmail(addr string) string {
	addr = strings.ToLower(strings.TrimSpace(addr))
	local, domain, ok := strings.Cut(addr, "@")
	if !ok || local == "" || domain == "" {
		return ""
	}
	lr := []rune(local)
	stars := len(lr) - 1
	if stars > 8 {
		stars = 8
	}
	if stars < 3 {
		stars = 3
	}
	parts := strings.Split(domain, ".")
	host := []rune(parts[0])
	if len(host) == 0 {
		return ""
	}
	rest := strings.Join(parts[1:], ".")
	hostStars := len(host) - 1
	if hostStars < 3 {
		hostStars = 3
	}
	out := string(lr[0]) + strings.Repeat("*", stars) + "@" + string(host[0]) + strings.Repeat("*", hostStars)
	if rest != "" {
		out += "." + rest
	}
	return out
}

var obAddrInText = regexp.MustCompile(`[^\s@<>"',;()]+@[^\s@<>"',;()]+`)

// obSafeError turns an error into the text kept in last_error and alerts: no
// address, cut to 400 characters.
func obSafeError(err error) string {
	text := obAddrInText.ReplaceAllString(err.Error(), "[address]")
	r := []rune(text)
	if len(r) > 400 {
		r = r[:400]
	}
	return string(r)
}

// obStamp is db.utcnow(): second precision, +00:00.
func obStamp(t time.Time) string { return t.UTC().Format("2006-01-02T15:04:05") + "+00:00" }

// obIsoNaive is datetime.isoformat() of a naive datetime: microseconds only
// when they are not zero.
func obIsoNaive(t time.Time) string {
	if t.Nanosecond()/1000 != 0 {
		return t.Format("2006-01-02T15:04:05.000000")
	}
	return t.Format("2006-01-02T15:04:05")
}

// obRow is the part of an email_outbox row delivery needs.
type obRow struct {
	ID            int64
	Kind          string
	ApartmentID   *int64
	ReservationID *int64
	To, CC        string
	CCRaw         *string
	Subject       string
	Payload       string
	Attempts      int64
}

// obRowColumns is the column list obRow.dest scans.
const obRowColumns = `id, kind, apartment_id, reservation_id, COALESCE(to_email, ''), COALESCE(cc_email, ''),
	COALESCE(subject, ''), COALESCE(payload, ''), attempts, cc_email`

func (r *obRow) dest() []any {
	return []any{&r.ID, &r.Kind, &r.ApartmentID, &r.ReservationID, &r.To, &r.CC, &r.Subject, &r.Payload, &r.Attempts, &r.CCRaw}
}
```

### Block 2: `go/internal/mail/outbox_markers.go`

```go
package mail

// Send-time markers and the attachments built from payload references
// (mail.delivery_body, delivery_html, attachments).

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/skip2/go-qrcode"
)

// The markers a stored body carries and the payload keys that go with them.
const (
	ClaimSecretMarker    = "{{claim_secret}}"
	DoorCodeMarker       = "{{door_code}}"
	GuestDetailsMarker   = "{{guest_details}}"
	ReceiptDetailsMarker = "{{receipt_details}}"

	claimSecretKey    = "claim_secret_enc"
	doorCodeKey       = "door_code_enc"
	guestDetailsKey   = "guest_details_reservation_id"
	receiptDetailsKey = "receipt_details_reservation_id"
	stayFeeFilingKey  = "stay_fee_filing_id"
	qrSpaydKey        = "qr_spayd"
	platformInvoiceID = "platform_invoice_id"

	// QRContentID is the cid the QR image is referenced by in the HTML.
	QRContentID = "stayfeeqr"
)

// DetailsRenderer fills {{guest_details}} and {{receipt_details}} from the
// database when the mail is sent (mail_notify.render_guest_details and
// render_receipt_details).
type DetailsRenderer interface {
	GuestDetails(ctx context.Context, pool *pgxpool.Pool, reservationID int64, lang string, asHTML bool) (string, error)
	ReceiptDetails(ctx context.Context, pool *pgxpool.Pool, reservationID int64, lang string, asHTML bool) (string, error)
}

// obDefaultDetails is the renderer used when Config.Details is nil. Brief
// 1231b sets it (the port of mail_notify.render_guest_details and
// render_receipt_details); until then such rows are put back untouched.
var obDefaultDetails DetailsRenderer

// ErrNoDetailsRenderer means a body carries {{guest_details}} or
// {{receipt_details}} and no renderer is set. It is a setup problem, not a
// failed send: the row goes back to queued without an attempt counted.
var ErrNoDetailsRenderer = errors.New("mail: no renderer for a send-time guest block")

// obPayload is the decoded outbox payload JSON object.
type obPayload map[string]any

func obParsePayload(raw string) (obPayload, error) {
	if strings.TrimSpace(raw) == "" {
		return obPayload{}, nil
	}
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.UseNumber()
	var p obPayload
	if err := dec.Decode(&p); err != nil || p == nil {
		return nil, errors.New("outbox payload is not a JSON object")
	}
	return p, nil
}

// str is str(payload.get(key) or ""): empty for a missing or falsy value.
func (p obPayload) str(key string) string {
	switch v := p[key].(type) {
	case nil:
		return ""
	case string:
		return v
	case json.Number:
		if v.String() == "0" {
			return ""
		}
		return v.String()
	case bool:
		if v {
			return "True"
		}
		return ""
	default:
		return fmt.Sprint(v)
	}
}

// int is int(payload.get(key)) for a truthy value; ok is false when the key is
// missing or falsy, an error when it is not a whole number.
func (p obPayload) int(key string) (n int64, ok bool, err error) {
	s := p.str(key)
	if s == "" {
		return 0, false, nil
	}
	n, err = strconv.ParseInt(strings.TrimSpace(s), 10, 64)
	if err != nil {
		return 0, true, errors.New("outbox payload has an id that is not a number")
	}
	return n, true, nil
}

func (c Config) decrypt(token string) (string, error) {
	if c.Keys == nil {
		return "", fmt.Errorf("%w: no data keys loaded", ErrDecryption)
	}
	plain, err := c.Keys.Decrypt(token, 0, time.Time{})
	if err != nil {
		return "", fmt.Errorf("%w: stored guest document field", ErrDecryption)
	}
	return string(plain), nil
}

func (c Config) withSecret(value string, p obPayload) (string, error) {
	if !strings.Contains(value, ClaimSecretMarker) {
		return value, nil
	}
	token := p.str(claimSecretKey)
	if token == "" {
		return "", fmt.Errorf("%w: outbox payload has a claim link with no secret", ErrDecryption)
	}
	secret, err := c.decrypt(token)
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(value, ClaimSecretMarker, secret), nil
}

// guestPinDisplay is door_codes.guest_pin_display: the digits plus the "#".
func guestPinDisplay(pin string) string {
	pin = strings.TrimSpace(pin)
	if pin == "" || strings.HasSuffix(pin, "#") {
		return pin
	}
	return pin + "#"
}

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

func (c Config) withDetails(ctx context.Context, pool *pgxpool.Pool, value, marker, key string, p obPayload, asHTML, receipt bool) (string, error) {
	if !strings.Contains(value, marker) {
		return value, nil
	}
	id, ok, err := p.int(key)
	if err != nil {
		return "", err
	}
	if !ok {
		return "", fmt.Errorf("%w: outbox payload has a %s with no stay", ErrDecryption, strings.Trim(marker, "{}"))
	}
	details := c.Details
	if details == nil {
		details = obDefaultDetails
	}
	if details == nil {
		return "", fmt.Errorf("%w: %s", ErrNoDetailsRenderer, marker)
	}
	lang := p.str("lang")
	if lang == "" {
		lang = "en"
	}
	var block string
	if receipt {
		block, err = details.ReceiptDetails(ctx, pool, id, lang, asHTML)
	} else {
		block, err = details.GuestDetails(ctx, pool, id, lang, asHTML)
	}
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(value, marker, block), nil
}

func (c Config) delivery(ctx context.Context, pool *pgxpool.Pool, stored string, p obPayload, asHTML bool) (string, error) {
	v, err := c.withSecret(stored, p)
	if err != nil {
		return "", err
	}
	if v, err = c.withDoorCode(v, p); err != nil {
		return "", err
	}
	if v, err = c.withDetails(ctx, pool, v, GuestDetailsMarker, guestDetailsKey, p, asHTML, false); err != nil {
		return "", err
	}
	return c.withDetails(ctx, pool, v, ReceiptDetailsMarker, receiptDetailsKey, p, asHTML, true)
}

// deliveryBody is mail.delivery_body: the text part with every marker filled.
func (c Config) deliveryBody(ctx context.Context, pool *pgxpool.Pool, p obPayload) (string, error) {
	return c.delivery(ctx, pool, p.str("text"), p, false)
}

// deliveryHTML is mail.delivery_html; empty when the mail has no HTML part.
func (c Config) deliveryHTML(ctx context.Context, pool *pgxpool.Pool, p obPayload) (string, error) {
	return c.delivery(ctx, pool, p.str("html"), p, true)
}

// obAttachment is one file: cid set means an inline image.
type obAttachment struct {
	Filename string
	Maintype string
	Subtype  string
	Data     []byte
	CID      string
}

// obQRPNG is payments.qr_png_bytes: medium error correction, 6 px modules, 4
// module border. It is the call payments.qrPNGBytes makes (unexported there).
func obQRPNG(payload string) ([]byte, error) {
	code, err := qrcode.New(payload, qrcode.Medium)
	if err != nil {
		return nil, err
	}
	return code.PNG(-6)
}

// obAttachments is mail.attachments: files built at send time from payload
// references. A file that is gone is an error, so the row retries.
func (c Config) obAttachments(ctx context.Context, pool *pgxpool.Pool, p obPayload) ([]obAttachment, error) {
	var parts []obAttachment
	filingID, ok, err := p.int(stayFeeFilingKey)
	if err != nil {
		return nil, err
	}
	if ok {
		var period string
		var enc []byte
		err := pool.QueryRow(ctx, `SELECT period_key, pdf_enc FROM stay_fee_filing WHERE id = $1`, filingID).Scan(&period, &enc)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return nil, errors.New("stay fee filing could not be read")
		}
		if errors.Is(err, pgx.ErrNoRows) || len(enc) == 0 {
			return nil, obConfigErr("stay fee filing PDF is missing")
		}
		if c.Keys == nil {
			return nil, fmt.Errorf("%w: no data keys loaded", ErrDecryption)
		}
		plain, derr := c.Keys.Decrypt(string(enc), 0, time.Time{})
		if derr != nil {
			return nil, fmt.Errorf("%w: stored attachment", ErrDecryption)
		}
		name := p.str("attachment_name")
		if name == "" {
			name = "poplatek-z-pobytu-" + period + ".pdf"
		}
		parts = append(parts, obAttachment{Filename: name, Maintype: "application", Subtype: "pdf", Data: plain})
	}
	if id, has, err := p.int(platformInvoiceID); err != nil {
		return nil, err
	} else if has {
		var blob []byte
		var sum *string
		err := pool.QueryRow(ctx, `SELECT pdf_blob, pdf_sha256 FROM platform_invoice WHERE id = $1`, id).Scan(&blob, &sum)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return nil, errors.New("platform invoice could not be read")
		}
		if errors.Is(err, pgx.ErrNoRows) || len(blob) == 0 {
			return nil, errors.New("platform_invoice_pdf_missing")
		}
		h := sha256.Sum256(blob)
		if sum == nil || hex.EncodeToString(h[:]) != *sum {
			return nil, errors.New("platform_invoice_pdf_changed")
		}
		name := p.str("attachment_name")
		if name == "" {
			name = "faktura-" + p.str(platformInvoiceID) + ".pdf"
		}
		parts = append(parts, obAttachment{Filename: name, Maintype: "application", Subtype: "pdf", Data: bytes.Clone(blob)})
	}
	if spayd := p.str(qrSpaydKey); spayd != "" {
		png, err := obQRPNG(spayd)
		if err != nil {
			return nil, errors.New("QR code could not be made")
		}
		parts = append(parts, obAttachment{Filename: "qr-platba.png", Maintype: "image", Subtype: "png", Data: png, CID: QRContentID})
	}
	return parts, nil
}
```

### Block 3: `go/internal/mail/outbox_mime.go`

```go
package mail

// The MIME message for SES v2 Raw, shaped like mail._raw_message: text and
// HTML as multipart/alternative, inline cid images next to the HTML in a
// multipart/related, files after that in a multipart/mixed.

import (
	"bytes"
	"encoding/base64"
	"errors"
	"mime"
	"mime/multipart"
	"mime/quotedprintable"
	netmail "net/mail"
	"net/textproto"
	"strings"
)

// obHeader is one extra header (List-Unsubscribe).
type obHeader struct {
	Name  string `json:"Name"`
	Value string `json:"Value"`
}

type obNode struct {
	ctype    string
	header   textproto.MIMEHeader
	body     []byte
	children []*obNode
}

// obSplitLines is bytes.splitlines(): only \n, \r and \r\n end a line.
func obSplitLines(s string) []string {
	s = strings.ReplaceAll(s, "\r\n", "\n")
	s = strings.ReplaceAll(s, "\r", "\n")
	lines := strings.Split(s, "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	return lines
}

// obTextNode is one text part. Like EmailMessage.set_content, the text ends
// with exactly one added line break.
func obTextNode(subtype, text string) *obNode {
	body := strings.Join(obSplitLines(text), "\r\n") + "\r\n"
	var buf bytes.Buffer
	w := quotedprintable.NewWriter(&buf)
	_, _ = w.Write([]byte(body))
	_ = w.Close()
	return &obNode{
		ctype: "text/" + subtype,
		header: textproto.MIMEHeader{
			"Content-Type":              {"text/" + subtype + `; charset="utf-8"`},
			"Content-Transfer-Encoding": {"quoted-printable"},
		},
		body: buf.Bytes(),
	}
}

func obFileNode(a obAttachment) *obNode {
	ctype := a.Maintype + "/" + a.Subtype
	enc := base64.StdEncoding.EncodeToString(a.Data)
	var buf bytes.Buffer
	for len(enc) > 76 {
		buf.WriteString(enc[:76] + "\r\n")
		enc = enc[76:]
	}
	buf.WriteString(enc + "\r\n")
	h := textproto.MIMEHeader{
		"Content-Type":              {ctype},
		"Content-Transfer-Encoding": {"base64"},
		"Content-Disposition":       {mime.FormatMediaType("attachment", map[string]string{"filename": a.Filename})},
	}
	if a.CID != "" {
		h["Content-Id"] = []string{"<" + a.CID + ">"}
	}
	return &obNode{ctype: ctype, header: h, body: buf.Bytes()}
}

// render returns the headers and the body of a node; a multipart node gets its
// boundary here.
func (n *obNode) render() (textproto.MIMEHeader, []byte) {
	if len(n.children) == 0 {
		return n.header, n.body
	}
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	for _, child := range n.children {
		h, b := child.render()
		pw, _ := mw.CreatePart(h)
		_, _ = pw.Write(b)
	}
	_ = mw.Close()
	return textproto.MIMEHeader{"Content-Type": {n.ctype + "; boundary=\"" + mw.Boundary() + "\""}}, buf.Bytes()
}

var obAddressHeaders = map[string]bool{"From": true, "To": true, "Cc": true, "Reply-To": true}

// obHeaderValue encodes one header value. An address header keeps its address
// readable: only a non-ASCII display name becomes an encoded word.
func obHeaderValue(name, value string) (string, error) {
	if strings.ContainsAny(value, "\r\n") {
		return "", errors.New("mail header has a line break")
	}
	if obAddressHeaders[name] && obNonASCII(value) {
		a, err := netmail.ParseAddress(value)
		if err != nil {
			return "", errors.New("mail address header could not be encoded")
		}
		return a.String(), nil
	}
	return mime.QEncoding.Encode("utf-8", value), nil
}

func obNonASCII(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] >= 0x80 {
			return true
		}
	}
	return false
}

// obRawMessage builds the whole message. from is the display From.
func obRawMessage(from, to, cc, subject, replyTo string, headers []obHeader, body, html string, parts []obAttachment) ([]byte, error) {
	root := obTextNode("plain", body)
	if html != "" {
		htmlNode := obTextNode("html", html)
		var inline []*obNode
		for _, p := range parts {
			if p.CID != "" {
				inline = append(inline, obFileNode(p))
			}
		}
		if len(inline) > 0 {
			htmlNode = &obNode{ctype: "multipart/related", children: append([]*obNode{htmlNode}, inline...)}
		}
		root = &obNode{ctype: "multipart/alternative", children: []*obNode{root, htmlNode}}
	}
	var files []*obNode
	for _, p := range parts {
		if p.CID == "" {
			files = append(files, obFileNode(p))
		}
	}
	if len(files) > 0 {
		root = &obNode{ctype: "multipart/mixed", children: append([]*obNode{root}, files...)}
	}
	rootHeader, rootBody := root.render()

	var out bytes.Buffer
	add := func(name, value string) error {
		v, err := obHeaderValue(name, value)
		if err != nil {
			return err
		}
		out.WriteString(name + ": " + v + "\r\n")
		return nil
	}
	fields := [][2]string{{"From", from}, {"To", to}}
	if cc != "" {
		fields = append(fields, [2]string{"Cc", cc})
	}
	fields = append(fields, [2]string{"Subject", subject})
	if replyTo != "" {
		fields = append(fields, [2]string{"Reply-To", replyTo})
	}
	for _, h := range headers {
		fields = append(fields, [2]string{h.Name, h.Value})
	}
	for _, f := range fields {
		if err := add(f[0], f[1]); err != nil {
			return nil, err
		}
	}
	out.WriteString("MIME-Version: 1.0\r\n")
	for _, name := range []string{"Content-Type", "Content-Transfer-Encoding"} {
		if v := rootHeader.Get(name); v != "" {
			out.WriteString(name + ": " + v + "\r\n")
		}
	}
	out.WriteString("\r\n")
	out.Write(rootBody)
	return out.Bytes(), nil
}
```

### Block 4: `go/internal/mail/outbox_ses.go`

```go
package mail

// A stdlib client for SES API v2 SendEmail with AWS Signature Version 4.
// No AWS SDK: the request is one JSON POST and the signature is HMAC-SHA256.

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	sesPath        = "/v2/email/outbound-emails"
	sesContentType = "application/json"
)

type sesData struct {
	Data    string `json:"Data"`
	Charset string `json:"Charset"`
}

type sesBody struct {
	Text sesData  `json:"Text"`
	Html *sesData `json:"Html,omitempty"`
}

type sesSimple struct {
	Subject sesData    `json:"Subject"`
	Body    sesBody    `json:"Body"`
	Headers []obHeader `json:"Headers,omitempty"`
}

type sesRaw struct {
	Data string `json:"Data"`
}

type sesContent struct {
	Simple *sesSimple `json:"Simple,omitempty"`
	Raw    *sesRaw    `json:"Raw,omitempty"`
}

type sesDestination struct {
	ToAddresses []string `json:"ToAddresses"`
	CcAddresses []string `json:"CcAddresses,omitempty"`
}

type sesRequest struct {
	FromEmailAddress string         `json:"FromEmailAddress"`
	Destination      sesDestination `json:"Destination"`
	ReplyToAddresses []string       `json:"ReplyToAddresses,omitempty"`
	Content          sesContent     `json:"Content"`
}

func obHMAC(key []byte, msg string) []byte {
	m := hmac.New(sha256.New, key)
	m.Write([]byte(msg))
	return m.Sum(nil)
}

// obSignV4 returns the X-Amz-Date and Authorization values for a POST with a
// JSON body: the signed headers are content-type, host and x-amz-date.
func obSignV4(host, path, region, service, accessKey, secretKey string, now time.Time, body []byte) (amzDate, authorization string) {
	now = now.UTC()
	amzDate = now.Format("20060102T150405Z")
	day := now.Format("20060102")
	payloadHash := sha256.Sum256(body)
	canonicalHeaders := "content-type:" + sesContentType + "\nhost:" + host + "\nx-amz-date:" + amzDate + "\n"
	signedHeaders := "content-type;host;x-amz-date"
	canonical := strings.Join([]string{"POST", path, "", canonicalHeaders, signedHeaders, hex.EncodeToString(payloadHash[:])}, "\n")
	scope := day + "/" + region + "/" + service + "/aws4_request"
	canonicalHash := sha256.Sum256([]byte(canonical))
	toSign := "AWS4-HMAC-SHA256\n" + amzDate + "\n" + scope + "\n" + hex.EncodeToString(canonicalHash[:])
	key := obHMAC([]byte("AWS4"+secretKey), day)
	key = obHMAC(key, region)
	key = obHMAC(key, service)
	key = obHMAC(key, "aws4_request")
	sig := hex.EncodeToString(obHMAC(key, toSign))
	authorization = "AWS4-HMAC-SHA256 Credential=" + accessKey + "/" + scope +
		", SignedHeaders=" + signedHeaders + ", Signature=" + sig
	return amzDate, authorization
}

func (c Config) sesEndpoint() string {
	if c.SESEndpoint != "" {
		return strings.TrimRight(c.SESEndpoint, "/")
	}
	region := c.SESRegion
	if region == "" {
		region = "eu-central-1"
	}
	return "https://email." + region + ".amazonaws.com"
}

// sesSend posts one message and returns the MessageId. Errors carry the HTTP
// status and the AWS error type only: the response text can echo addresses.
func (c Config) sesSend(ctx context.Context, req sesRequest) (string, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(req); err != nil {
		return "", errors.New("SES request could not be encoded")
	}
	body := bytes.TrimRight(buf.Bytes(), "\n")
	target, err := url.Parse(c.sesEndpoint() + sesPath)
	if err != nil {
		return "", obConfigErr("SES endpoint is not a URL")
	}
	region := c.SESRegion
	if region == "" {
		region = "eu-central-1"
	}
	amzDate, auth := obSignV4(target.Host, target.Path, region, "ses", c.AccessKeyID, c.SecretAccessKey, c.now(), body)
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, target.String(), bytes.NewReader(body))
	if err != nil {
		return "", errors.New("SES request could not be built")
	}
	httpReq.Header.Set("Content-Type", sesContentType)
	httpReq.Header.Set("X-Amz-Date", amzDate)
	httpReq.Header.Set("Authorization", auth)
	client := c.HTTPClient
	if client == nil {
		client = &http.Client{Timeout: 30 * time.Second}
	}
	resp, err := client.Do(httpReq)
	if err != nil {
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		return "", errors.New("SES SendEmail request failed")
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		kind := resp.Header.Get("X-Amzn-Errortype")
		if i := strings.IndexByte(kind, ':'); i >= 0 {
			kind = kind[:i]
		}
		if kind == "" {
			kind = "unknown"
		}
		return "", fmt.Errorf("SES SendEmail failed: HTTP %d (%s)", resp.StatusCode, kind)
	}
	var out struct {
		MessageID string `json:"MessageId"`
	}
	_ = json.Unmarshal(raw, &out)
	if out.MessageID == "" {
		return "", obConfigErr("SES SendEmail returned no MessageId.")
	}
	return out.MessageID, nil
}

// obListUnsubscribeHeaders is mail.list_unsubscribe_headers: lifecycle kinds
// only, https only, printable ASCII, at most 995 characters.
func obListUnsubscribeHeaders(kind string, p obPayload) []obHeader {
	url := p.str("list_unsubscribe")
	if !obLifecycleKinds[kind] || !strings.HasPrefix(url, "https://") {
		return nil
	}
	value := "<" + url + ">"
	if len([]rune(value)) > 995 {
		return nil
	}
	for _, r := range value {
		if r < 32 || r >= 127 {
			return nil
		}
	}
	return []obHeader{
		{Name: "List-Unsubscribe", Value: value},
		{Name: "List-Unsubscribe-Post", Value: "List-Unsubscribe=One-Click"},
	}
}

var obLifecycleKinds = map[string]bool{
	"lifecycle_no_property": true,
	"lifecycle_no_calendar": true,
	"lifecycle_no_guest":    true,
}

// obSendSES is mail._send_ses over SES v2: Simple for plain mail, Raw when
// there are files.
func (c Config) obSendSES(ctx context.Context, row obRow, p obPayload, body, html string, parts []obAttachment) (string, error) {
	if c.Backend != BackendSES {
		return "", obConfigErr("SES sender invoked while UBYHOST_MAIL_BACKEND is not ses.")
	}
	if c.From == "" {
		return "", obConfigErr("UBYHOST_MAIL_FROM is required for SES sending.")
	}
	req, err := c.obBuildSESRequest(row, p, body, html, parts)
	if err != nil {
		return "", err
	}
	return c.sesSend(ctx, req)
}

// obBuildSESRequest is the SendEmail v2 request _send_ses makes: Raw with the
// MIME message when there are files, else Simple with Reply-To and headers.
func (c Config) obBuildSESRequest(row obRow, p obPayload, body, html string, parts []obAttachment) (sesRequest, error) {
	replyTo := obNormaliseEmail(p.str("reply_to"))
	cc := obNormaliseEmail(row.CC)
	headers := obListUnsubscribeHeaders(row.Kind, p)
	req := sesRequest{
		FromEmailAddress: c.DisplayFrom(),
		Destination:      sesDestination{ToAddresses: []string{row.To}},
	}
	if cc != "" {
		req.Destination.CcAddresses = []string{cc}
	}
	if len(parts) > 0 {
		raw, err := obRawMessage(c.DisplayFrom(), row.To, cc, row.Subject, replyTo, headers, body, html, parts)
		if err != nil {
			return sesRequest{}, err
		}
		req.Content.Raw = &sesRaw{Data: base64.StdEncoding.EncodeToString(raw)}
	} else {
		simple := &sesSimple{
			Subject: sesData{Data: row.Subject, Charset: "UTF-8"},
			Body:    sesBody{Text: sesData{Data: body, Charset: "UTF-8"}},
			Headers: headers,
		}
		if html != "" {
			simple.Body.Html = &sesData{Data: html, Charset: "UTF-8"}
		}
		req.Content.Simple = simple
		if replyTo != "" {
			req.ReplyToAddresses = []string{replyTo}
		}
	}
	return req, nil
}
```

