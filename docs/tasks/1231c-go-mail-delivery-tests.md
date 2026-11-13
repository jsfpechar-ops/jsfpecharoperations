# 1231c: Go mail delivery, part 3: parity and database tests

Status: todo
Depends on: 1231b (this branch) | Base commit: 902bc51 | Branch: task/1230-track-a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (code is copied by a script; do not read the code blocks)

## 1. Objective

Add the Go tests for 1231 and 1231b: the golden comparison against the Python fixtures and the PostgreSQL tests of Drain, SendNow, back-off, the mail_failed alert and Purge. This proves the Go delivery matches Python before brief 1236 wires the job.

## 2. Context

Part 3 of 3 (1231, 1231b, 1231c; one branch, one PR). Behaviour decisions: [1231 §2](1231-go-mail-delivery.md). The tests read `go/internal/mail/testdata/drain/cases.json` (1231b) and create their own database per test from `App/migrations_pg/`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/mail/outbox_golden_test.go` | create | golden parity tests, SigV4 vs botocore, ConfigFromEnv, markers, MIME |
| `go/internal/mail/outbox_drain_test.go` | create | PostgreSQL tests: Drain, SendNow, back-off, alert, stale reset, SES HTTP, Purge |
| `docs/tasks/1231c-go-mail-delivery-tests.md` | edit | `Status:` line only |
| `docs/tasks/1231c-report.md` | create | report |

No other file may change.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `task/1230-track-a`; `grep -c '^func SendNow' go/internal/mail/outbox_drain.go` prints 1 and `sha256sum go/internal/mail/testdata/drain/cases.json` prints `84faacbe05b15a3bf285b75e752cd59650ee55ea4ed9af5e833d6654396999b0` (1231b is applied); `ls go/internal/mail/outbox_golden_test.go go/internal/mail/outbox_drain_test.go 2>&1 | grep -c 'No such file'` prints 2; `git status --short | tail -5` is empty. Any check failing: STOP (§8). Then write the helper that copies code block k of this brief byte for byte:

```bash
cat > /tmp/extract_block.py <<'EOF'
import re, sys
src, k, dest = sys.argv[1], int(sys.argv[2]), sys.argv[3]
text = open(src, encoding='utf-8').read()
blocks = re.findall(r'^```(?:python|go)\n(.*?)^```$', text, re.S | re.M)
open(dest, 'w', encoding='utf-8').write(blocks[k - 1])
EOF
```

1. Create the 2 files in one call (from the repo root):

```bash
B=docs/tasks/1231c-go-mail-delivery-tests.md; X="python3 /tmp/extract_block.py $B"
mkdir -p go/internal/mail App/scripts
$X 1 go/internal/mail/outbox_golden_test.go
$X 2 go/internal/mail/outbox_drain_test.go
sha256sum go/internal/mail/outbox_golden_test.go go/internal/mail/outbox_drain_test.go | tail -10
```

   Expected:

   - `b28cded804dce01ce21dbdb37711f76bb2bd0608e761a0a559e7a5b7934c9468`  `go/internal/mail/outbox_golden_test.go`
   - `850985f61646cc11fce0f4fa6ab328dc049ceb3211933ef0f3f94fc73eb089c5`  `go/internal/mail/outbox_drain_test.go`

   A different hash: re-run that one extract once; still different: STOP (§8).

2. From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/mail/ -count=1 2>&1 | tail -30` ends `ok` (DB tests skip without a database). Commit "1231c step 1-2".

3. Go DB tests locally (2 calls at most; if PostgreSQL cannot start, write "CI only" and the reason in the report). As root with PostgreSQL 16:

```bash
P=/var/tmp/pg1231 && mkdir -p $P && chown postgres $P && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $P/data -A trust -U postgres" >/dev/null && su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $P/data -o '-p 55431 -k $P -c listen_addresses=127.0.0.1' -l $P/log -w start" 2>&1 | tail -3
```

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55431/postgres go test ./internal/mail/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

   Expected: `--- PASS` for TestDrainConsole, TestDrainTerminalFailureRaisesAlert, TestDrainResetsStaleSending, TestDrainSESRequest, TestDrainSESErrorsDoNotLeakAddresses, TestPurge, TestSendNow, TestNoDetailsRendererPutsRowBack, TestGoldenDelivery, TestGoldenAddressHelpers, TestSigV4MatchesBotocore, TestConfigFromEnv, TestDetailsMarkers, TestRawMessageNonASCIIAddressName, then `ok`. No `--- SKIP`. A FAIL: STOP (§8), paste its first 20 lines into the report.

4. Write the report (§9), set `Status: review`, commit "1231c step 4".

## 5. Do not touch

`App/app/` (all of it), `App/migrations_pg/`, every existing file in `go/internal/` (incl. the `go/internal/mail/*.go` files that exist on the base commit, `go/internal/ubyport/`, `go/internal/payments/`, `go/internal/secure/`, `go/internal/jobs/`), `go/cmd/`, `go/go.mod`, `go/go.sum`, `docs/context/`, `.github/`. No job kind, env var, route, migration or dependency. Hard rules 2 (no addresses or bodies in logs or errors), 3, 4, 5.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/mail/ -count=1 2>&1 | tail -30`. Step 3 (DB tests). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The two hashes match.
- [ ] gofmt empty, vet clean, `go test ./internal/mail/` ok.
- [ ] Step 3: the 14 tests PASS on local PostgreSQL, or "CI only" with the reason.
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

Write `docs/tasks/1231c-report.md` (600 tokens at most) and set `Status: review`. It has: 1. `git diff --stat HEAD~2..HEAD | tail -10`; 2. each command with its last 5 lines; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

- `outbox_golden_test.go`: every golden case is compared (body, HTML, Reply-To, Cc, List-Unsubscribe headers, attachments by sha256 or PNG size, the v2 Simple request JSON, the Raw MIME tree); error cases must error in Go too.
- `outbox_drain_test.go`: the DB tests must PASS in CI, not skip (`--- PASS: TestDrainConsole` in the Go job log).
- After this brief: the orchestrator pushes and opens the draft PR for 1230-1231c; the PR text names the outbound request (see [1231 risk list](1231-go-mail-delivery.md)).

## Owner steps

None (nothing is wired). Brief 1236 carries the switch; it must not be switched on before the guest/receipt detail renderer brief is merged, or guest-list and receipt mails stay queued.

## Code blocks

### Block 1: `go/internal/mail/outbox_golden_test.go`

```go
package mail

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"image/png"
	"io"
	"mime"
	"mime/multipart"
	"mime/quotedprintable"
	netmail "net/mail"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// ---- fixtures written by App/scripts/mail_drain_golden.py ----

type obNodeJSON struct {
	Type        string       `json:"type"`
	Filename    string       `json:"filename"`
	CID         string       `json:"cid"`
	Disposition string       `json:"disposition"`
	Parts       []obNodeJSON `json:"parts"`
	SHA256      string       `json:"sha256"`
	PNGSize     string       `json:"png_size"`
}

type obGoldenCase struct {
	Name    string         `json:"name"`
	Kind    string         `json:"kind"`
	To      string         `json:"to"`
	CC      *string        `json:"cc"`
	Subject string         `json:"subject"`
	Payload map[string]any `json:"payload"`
	Error   string         `json:"error"`
	Body    string         `json:"body"`
	HTML    string         `json:"html"`
	Headers []obHeader     `json:"headers"`
	ReplyTo string         `json:"reply_to"`
	CCNorm  string         `json:"cc_normalised"`
	Attach  []struct {
		Filename string  `json:"filename"`
		Maintype string  `json:"maintype"`
		Subtype  string  `json:"subtype"`
		CID      *string `json:"cid"`
		SHA256   string  `json:"sha256"`
		PNGSize  string  `json:"png_size"`
	} `json:"attachments"`
	SentAs   string          `json:"sent_as"`
	V2Simple json.RawMessage `json:"v2_simple"`
	Raw      *struct {
		Headers map[string]string `json:"headers"`
		Tree    obNodeJSON        `json:"tree"`
	} `json:"raw"`
}

type obGolden struct {
	FernetKey    string         `json:"fernet_key"`
	FilingPDFEnc string         `json:"filing_pdf_enc"`
	FilingPeriod string         `json:"filing_period"`
	InvoicePDF   string         `json:"invoice_pdf_b64"`
	Cases        []obGoldenCase `json:"cases"`
	Staging      []struct {
		Kind   string `json:"kind"`
		Text   string `json:"text"`
		Want   string `json:"want"`
		Logged bool   `json:"logged"`
	} `json:"staging_links"`
	Normalise []struct{ In, Out string } `json:"normalise"`
	Mask      []struct{ In, Out string } `json:"mask"`
	From      []struct{ In, Out string } `json:"display_from"`
	Backoff   []struct {
		Attempts int  `json:"attempts"`
		Delay    int  `json:"delay"`
		Terminal bool `json:"terminal"`
	} `json:"backoff"`
	SigV4 struct {
		URL, Body, Date, Authorization, Region string
		AccessKey                              string `json:"access_key"`
		SecretKey                              string `json:"secret_key"`
	} `json:"sigv4"`
}

func obLoadGolden(t *testing.T) obGolden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "drain", "cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g obGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func obTestConfig(t *testing.T, g obGolden) Config {
	t.Helper()
	keys, err := secure.NewMultiFernet([]byte(g.FernetKey))
	if err != nil {
		t.Fatal(err)
	}
	return Config{
		Backend: BackendSES, Deployment: "production", From: "noreply@mail.example.test",
		SESRegion: "eu-central-1", AccessKeyID: "AKIDEXAMPLE", SecretAccessKey: "secret",
		Keys: keys, Now: func() time.Time { return time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC) },
	}
}

// ---- database helper (own copy, like every package) ----

func obTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_mail_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}

func obSeedFiles(t *testing.T, pool *pgxpool.Pool, g obGolden) []byte {
	t.Helper()
	ctx := context.Background()
	for _, q := range []string{
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'owner@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at) VALUES (1, 1, 'Byt', 'Brno', 'UBY', 'tok1', '2026-01-01')`,
	} {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO stay_fee_filing (id, apartment_id, period_key, version, cadence, rate_czk, liable_days, exempt_days,
		   total_due_czk, total_collected_czk, pdf_enc, created_at)
		 VALUES (7, 1, $1, 1, 'monthly', 50, 1, 0, 50, 50, $2, '2026-11-01T00:00:00+00:00')`,
		g.FilingPeriod, []byte(g.FilingPDFEnc)); err != nil {
		t.Fatal(err)
	}
	pdf, err := base64.StdEncoding.DecodeString(g.InvoicePDF)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(pdf)
	for _, row := range []struct {
		id  int
		sha string
	}{{9, hex.EncodeToString(sum[:])}, {10, strings.Repeat("0", 64)}} {
		if _, err := pool.Exec(ctx,
			`INSERT INTO platform_invoice (id, kind, seq_year, seq_no, number, vs, issue_date, due_date, period_from, period_to,
			   total_haler, snapshot_json, created_at, pdf_blob, pdf_sha256)
			 VALUES ($1::bigint, 'invoice', 2026, $1::bigint, 'N-'||$1::text, 'VS'||$1::text, '2026-11-01', '2026-11-15', '2026-10-01', '2026-10-31',
			   100, '{}', '2026-11-01T00:00:00+00:00', $2, $3)`, row.id, pdf, row.sha); err != nil {
			t.Fatal(err)
		}
	}
	return pdf
}

// ---- MIME tree of Go's own raw message, same shape as the Python oracle ----

func obDecode(h textprotoGetter, body []byte) []byte {
	switch strings.ToLower(h.Get("Content-Transfer-Encoding")) {
	case "quoted-printable":
		out, _ := io.ReadAll(quotedprintable.NewReader(bytes.NewReader(body)))
		return out
	case "base64":
		out, _ := base64.StdEncoding.DecodeString(strings.NewReplacer("\r", "", "\n", "").Replace(string(body)))
		return out
	}
	return body
}

type textprotoGetter interface{ Get(string) string }

func obTree(t *testing.T, h textprotoGetter, body []byte) obNodeJSON {
	t.Helper()
	ctype, params, err := mime.ParseMediaType(h.Get("Content-Type"))
	if err != nil {
		t.Fatalf("content type: %v", err)
	}
	node := obNodeJSON{Type: ctype}
	if d := h.Get("Content-Disposition"); d != "" {
		disp, dp, _ := mime.ParseMediaType(d)
		node.Disposition = disp
		node.Filename = dp["filename"]
	}
	node.CID = h.Get("Content-Id")
	if strings.HasPrefix(ctype, "multipart/") {
		mr := multipart.NewReader(bytes.NewReader(body), params["boundary"])
		for {
			part, err := mr.NextRawPart()
			if err == io.EOF {
				break
			}
			if err != nil {
				t.Fatal(err)
			}
			pb, _ := io.ReadAll(part)
			node.Parts = append(node.Parts, obTree(t, part.Header, pb))
		}
		return node
	}
	data := obDecode(h, body)
	if strings.HasPrefix(ctype, "image/") {
		node.PNGSize = obPNGSize(t, data)
		return node
	}
	if strings.HasPrefix(ctype, "text/") {
		data = bytes.ReplaceAll(data, []byte("\r\n"), []byte("\n"))
	}
	sum := sha256.Sum256(data)
	node.SHA256 = hex.EncodeToString(sum[:])
	return node
}

// obPNGSize is the oracle's png_size: the QR image is compared by size only
// (go-qrcode picks another mask than Python's qrcode, so the bytes differ).
func obPNGSize(t *testing.T, data []byte) string {
	t.Helper()
	cfg, err := png.DecodeConfig(bytes.NewReader(data))
	if err != nil {
		t.Fatalf("not a PNG: %v", err)
	}
	return fmt.Sprintf("%dx%d", cfg.Width, cfg.Height)
}

func obRawHeaders(m *netmail.Message) map[string]string {
	out := map[string]string{}
	dec := new(mime.WordDecoder)
	for _, name := range []string{"From", "To", "Cc", "Subject", "Reply-To", "List-Unsubscribe", "List-Unsubscribe-Post"} {
		if v := m.Header.Get(name); v != "" {
			d, err := dec.DecodeHeader(v)
			if err != nil {
				d = v
			}
			out[name] = d
		}
	}
	return out
}

// ---- tests ----

func TestGoldenDelivery(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	obSeedFiles(t, pool, g)
	ctx := context.Background()
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			payloadJSON, _ := json.Marshal(c.Payload)
			p, err := obParsePayload(string(payloadJSON))
			if err != nil {
				t.Fatal(err)
			}
			body, errBody := cfg.deliveryBody(ctx, pool, p)
			html, errHTML := cfg.deliveryHTML(ctx, pool, p)
			parts, errParts := cfg.obAttachments(ctx, pool, p)
			if c.Error != "" {
				if errBody == nil && errHTML == nil && errParts == nil {
					t.Fatalf("expected the oracle's %s as an error, got none", c.Error)
				}
				return
			}
			if errBody != nil || errHTML != nil || errParts != nil {
				t.Fatalf("unexpected errors: %v %v %v", errBody, errHTML, errParts)
			}
			if body != c.Body || html != c.HTML {
				t.Fatalf("body or html differs\n got %q / %q\nwant %q / %q", body, html, c.Body, c.HTML)
			}
			cc := ""
			if c.CC != nil {
				cc = *c.CC
			}
			if got := obNormaliseEmail(cc); got != c.CCNorm {
				t.Fatalf("cc %q want %q", got, c.CCNorm)
			}
			replyTo := obNormaliseEmail(p.str("reply_to"))
			if replyTo != c.ReplyTo {
				t.Fatalf("reply_to %q want %q", replyTo, c.ReplyTo)
			}
			headers := obListUnsubscribeHeaders(c.Kind, p)
			if !reflect.DeepEqual(headers, c.Headers) && !(len(headers) == 0 && len(c.Headers) == 0) {
				t.Fatalf("headers %v want %v", headers, c.Headers)
			}
			if len(parts) != len(c.Attach) {
				t.Fatalf("attachments %d want %d", len(parts), len(c.Attach))
			}
			for i, want := range c.Attach {
				got := parts[i]
				sum := sha256.Sum256(got.Data)
				cid := ""
				if want.CID != nil {
					cid = *want.CID
				}
				same := hex.EncodeToString(sum[:]) == want.SHA256
				if got.Maintype == "image" {
					same = want.SHA256 == "" && obPNGSize(t, got.Data) == want.PNGSize
				}
				if got.Filename != want.Filename || got.Maintype != want.Maintype || got.Subtype != want.Subtype ||
					got.CID != cid || !same {
					t.Fatalf("attachment %d differs: %s %s/%s cid=%q sha=%x", i, got.Filename, got.Maintype, got.Subtype, got.CID, sum)
				}
			}
			if len(c.V2Simple) > 0 {
				req, err := cfg.obBuildSESRequest(obRow{Kind: c.Kind, To: c.To, CC: cc, Subject: c.Subject}, p, body, html, parts)
				if err != nil {
					t.Fatal(err)
				}
				gotJSON, _ := json.Marshal(req)
				var got, want any
				_ = json.Unmarshal(gotJSON, &got)
				_ = json.Unmarshal(c.V2Simple, &want)
				if !reflect.DeepEqual(got, want) {
					t.Fatalf("SES v2 Simple request differs\n got %s\nwant %s", gotJSON, c.V2Simple)
				}
			}
			wantRaw := c.SentAs == "raw"
			if wantRaw != (len(parts) > 0) {
				t.Fatalf("sent_as %q but %d attachments", c.SentAs, len(parts))
			}
			if !wantRaw {
				return
			}
			raw, err := obRawMessage(cfg.DisplayFrom(), c.To, replyToCC(cc), c.Subject, replyTo, headers, body, html, parts)
			if err != nil {
				t.Fatal(err)
			}
			msg, err := netmail.ReadMessage(bytes.NewReader(raw))
			if err != nil {
				t.Fatal(err)
			}
			rest, _ := io.ReadAll(msg.Body)
			if got := obRawHeaders(msg); !reflect.DeepEqual(got, c.Raw.Headers) {
				t.Fatalf("raw headers %v want %v", got, c.Raw.Headers)
			}
			tree := obTree(t, msg.Header, rest)
			if !reflect.DeepEqual(tree, c.Raw.Tree) {
				gotJSON, _ := json.MarshalIndent(tree, "", " ")
				wantJSON, _ := json.MarshalIndent(c.Raw.Tree, "", " ")
				t.Fatalf("mime tree differs\n got %s\nwant %s", gotJSON, wantJSON)
			}
		})
	}
}

func replyToCC(cc string) string { return obNormaliseEmail(cc) }

func TestGoldenAddressHelpers(t *testing.T) {
	g := obLoadGolden(t)
	for _, c := range g.Normalise {
		if got := obNormaliseEmail(c.In); got != c.Out {
			t.Errorf("normalise %q = %q want %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Mask {
		if got := MaskEmail(c.In); got != c.Out {
			t.Errorf("mask %q = %q want %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.From {
		if got := DisplayFrom(c.In); got != c.Out {
			t.Errorf("display_from %q = %q want %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Backoff {
		if got := ObBackoff(c.Attempts); got != time.Duration(c.Delay)*time.Second {
			t.Errorf("backoff %d = %v want %ds", c.Attempts, got, c.Delay)
		}
		if (c.Attempts >= obMaxAttempts) != c.Terminal {
			t.Errorf("terminal %d", c.Attempts)
		}
	}
	for _, c := range g.Staging {
		got := obStagingLink("staging", c.Kind, c.Text)
		if got != c.Want || (got != "") != c.Logged {
			t.Errorf("staging link %q = %q want %q", c.Text, got, c.Want)
		}
		if obStagingLink("production", c.Kind, c.Text) != "" {
			t.Errorf("production must never log a link")
		}
	}
}

func TestSigV4MatchesBotocore(t *testing.T) {
	g := obLoadGolden(t)
	v := g.SigV4
	when := time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)
	date, auth := obSignV4("email.eu-central-1.amazonaws.com", "/v2/email/outbound-emails", v.Region, "ses",
		v.AccessKey, v.SecretKey, when, []byte(v.Body))
	if date != v.Date || auth != v.Authorization {
		t.Fatalf("signature differs from botocore\n got %s %s\nwant %s %s", date, auth, v.Date, v.Authorization)
	}
}

func TestConfigFromEnv(t *testing.T) {
	g := obLoadGolden(t)
	env := func(m map[string]string) func(string) string { return func(k string) string { return m[k] } }
	base := map[string]string{"UBYHOST_DATA_KEYS": g.FernetKey, "UBYHOST_DATA_KEY_LEGACY": "0"}
	with := func(extra map[string]string) map[string]string {
		m := map[string]string{}
		for k, v := range base {
			m[k] = v
		}
		for k, v := range extra {
			m[k] = v
		}
		return m
	}
	if cfg, err := ConfigFromEnv(env(map[string]string{})); err != nil || cfg.Enabled() || cfg.Keys != nil {
		t.Fatalf("disabled by default: %+v %v", cfg, err)
	}
	if _, err := ConfigFromEnv(env(with(map[string]string{"UBYHOST_MAIL_BACKEND": "smtp"}))); err == nil {
		t.Fatal("invalid backend must fail")
	}
	if _, err := ConfigFromEnv(env(with(map[string]string{"UBYHOST_MAIL_BACKEND": "ses", "UBYHOST_DEPLOYMENT": "staging"}))); err == nil {
		t.Fatal("ses outside production must fail")
	}
	if _, err := ConfigFromEnv(env(with(map[string]string{"UBYHOST_MAIL_BACKEND": "ses", "UBYHOST_DEPLOYMENT": "production"}))); err == nil ||
		!strings.Contains(err.Error(), "UBYHOST_MAIL_FROM") {
		t.Fatalf("incomplete ses must name the missing keys: %v", err)
	}
	cfg, err := ConfigFromEnv(env(with(map[string]string{
		"UBYHOST_MAIL_BACKEND": " SES ", "UBYHOST_DEPLOYMENT": "production", "UBYHOST_MAIL_FROM": "a@b.test",
		"UBYHOST_AWS_ACCESS_KEY_ID": "k", "UBYHOST_AWS_SECRET_ACCESS_KEY": "s"})))
	if err != nil || cfg.Backend != BackendSES || cfg.SESRegion != "eu-central-1" || cfg.Keys == nil {
		t.Fatalf("good ses config: %+v %v", cfg, err)
	}
	if cfg, err := ConfigFromEnv(env(with(map[string]string{"UBYHOST_MAIL_BACKEND": "console"}))); err != nil || !cfg.Enabled() {
		t.Fatalf("console: %v", err)
	}
}

type obFakeDetails struct{}

func (obFakeDetails) GuestDetails(_ context.Context, _ *pgxpool.Pool, id int64, lang string, asHTML bool) (string, error) {
	return fmt.Sprintf("guests:%d:%s:%v", id, lang, asHTML), nil
}

func (obFakeDetails) ReceiptDetails(_ context.Context, _ *pgxpool.Pool, id int64, lang string, asHTML bool) (string, error) {
	return fmt.Sprintf("receipt:%d:%s:%v", id, lang, asHTML), nil
}

func TestDetailsMarkers(t *testing.T) {
	g := obLoadGolden(t)
	cfg := obTestConfig(t, g)
	ctx := context.Background()
	p, _ := obParsePayload(`{"text":"A {{guest_details}} B {{receipt_details}}","html":"<i>{{guest_details}}</i>","guest_details_reservation_id":12,"receipt_details_reservation_id":"13","lang":"cs"}`)
	if _, err := cfg.deliveryBody(ctx, nil, p); err == nil {
		t.Fatal("a marker with no renderer must be an error, never sent as it is")
	}
	cfg.Details = obFakeDetails{}
	body, err := cfg.deliveryBody(ctx, nil, p)
	if err != nil || body != "A guests:12:cs:false B receipt:13:cs:false" {
		t.Fatalf("body %q %v", body, err)
	}
	html, err := cfg.deliveryHTML(ctx, nil, p)
	if err != nil || html != "<i>guests:12:cs:true</i>" {
		t.Fatalf("html %q %v", html, err)
	}
	p, _ = obParsePayload(`{"text":"{{guest_details}}"}`)
	if _, err := cfg.deliveryBody(ctx, nil, p); err == nil {
		t.Fatal("a marker with no stay id must be an error")
	}
}

func TestRawMessageNonASCIIAddressName(t *testing.T) {
	raw, err := obRawMessage("Jméno Příjmení <n@x.test>", "a@b.test", "", "Účet", "", nil, "ahoj", "",
		[]obAttachment{{Filename: "f.pdf", Maintype: "application", Subtype: "pdf", Data: []byte("x")}})
	if err != nil {
		t.Fatal(err)
	}
	msg, err := netmail.ReadMessage(bytes.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}
	from, err := msg.Header.AddressList("From")
	if err != nil || len(from) != 1 || from[0].Name != "Jméno Příjmení" || from[0].Address != "n@x.test" {
		t.Fatalf("from %v %v", from, err)
	}
	if got := obRawHeaders(msg)["Subject"]; got != "Účet" {
		t.Fatalf("subject %q", got)
	}
}
```

### Block 2: `go/internal/mail/outbox_drain_test.go`

```go
package mail

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Database tests for Drain, SendNow and Purge (brief 1231).

func obQueue(t *testing.T, pool *pgxpool.Pool, key, kind, to string, payload map[string]any, attempts int, next string) int64 {
	t.Helper()
	raw, _ := json.Marshal(payload)
	var id int64
	err := pool.QueryRow(context.Background(),
		`INSERT INTO email_outbox (idempotency_key, kind, to_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		 VALUES ($1, $2, $3, 'Subject', $4, 'queued', $5, $6, '2026-11-13T09:00:00+00:00', '2026-11-13T09:00:00+00:00')
		 RETURNING id`, key, kind, to, string(raw), attempts, next).Scan(&id)
	if err != nil {
		t.Fatal(err)
	}
	return id
}

func obRowState(t *testing.T, pool *pgxpool.Pool, id int64) (state string, attempts int, lastErr, provider, next *string) {
	t.Helper()
	err := pool.QueryRow(context.Background(),
		`SELECT state, attempts, last_error, provider_id, next_attempt_at FROM email_outbox WHERE id = $1`, id).
		Scan(&state, &attempts, &lastErr, &provider, &next)
	if err != nil {
		t.Fatal(err)
	}
	return
}

func TestDrainConsole(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	cfg.Backend = BackendConsole
	cfg.Deployment = "staging"
	obSeedFiles(t, pool, g)
	ctx := context.Background()
	due := "2026-11-13T09:59:59Z" // before 10:00:00+00:00 as text
	ok := obQueue(t, pool, "k1", "completion", "guest@example.test", map[string]any{"text": "hello", "html": "<p>hello</p>", "stay_fee_filing_id": 7}, 0, due)
	bad := obQueue(t, pool, "k2", "claim", "guest@example.test", map[string]any{"text": "{{claim_secret}}"}, 0, due)
	later := obQueue(t, pool, "k3", "completion", "guest@example.test", map[string]any{"text": "later"}, 0, "2026-11-13T11:00:00Z")
	sum, err := Drain(ctx, pool, cfg, 8)
	if err != nil {
		t.Fatal(err)
	}
	if sum != (Summary{Sent: 1, Skipped: 1}) {
		t.Fatalf("summary %+v", sum)
	}
	state, attempts, lastErr, provider, _ := obRowState(t, pool, ok)
	if state != "sent" || attempts != 1 || lastErr != nil || provider == nil || *provider != fmt.Sprintf("console:%d", ok) {
		t.Fatalf("sent row: %s %d %v %v", state, attempts, lastErr, provider)
	}
	var text string
	var htmlCol *string
	if err := pool.QueryRow(ctx, `SELECT body_text, body_html FROM console_mail_log WHERE outbox_id = $1`, ok).Scan(&text, &htmlCol); err != nil {
		t.Fatal(err)
	}
	if text != "hello\n\n[Attachments: poplatek-z-pobytu-2026-10.pdf]" || htmlCol == nil || *htmlCol != "<p>hello</p>" {
		t.Fatalf("console log %q %v", text, htmlCol)
	}
	state, attempts, lastErr, _, next := obRowState(t, pool, bad)
	if state != "queued" || attempts != 1 || lastErr == nil || strings.Contains(*lastErr, "@") || next == nil || *next != "2026-11-13T10:02:00Z" {
		t.Fatalf("failed row: %s %d %v %v", state, attempts, lastErr, next)
	}
	if state, _, _, _, _ := obRowState(t, pool, later); state != "queued" {
		t.Fatalf("not yet due row was touched: %s", state)
	}
	var logs int
	_ = pool.QueryRow(ctx, `SELECT count(*) FROM console_mail_log`).Scan(&logs)
	if logs != 1 {
		t.Fatalf("console log rows %d", logs)
	}
}

func TestDrainTerminalFailureRaisesAlert(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	cfg.Backend = BackendConsole
	ctx := context.Background()
	id := obQueue(t, pool, "k1", "claim", "jan.novak@example.test", map[string]any{"text": "{{claim_secret}}"}, 7, "2026-11-13T09:00:00Z")
	sum, err := Drain(ctx, pool, cfg, 8)
	if err != nil || sum.Failed != 1 {
		t.Fatalf("%+v %v", sum, err)
	}
	state, attempts, lastErr, _, next := obRowState(t, pool, id)
	if state != "failed" || attempts != 8 || lastErr == nil || next == nil || *next != "2026-11-13T14:16:00Z" {
		t.Fatalf("terminal row: %s %d %v %v", state, attempts, lastErr, next)
	}
	var level, kind, key, message, detail, params string
	err = pool.QueryRow(ctx, `SELECT level, kind, dedupe_key, message, detail, params FROM alert WHERE dedupe_key = $1`,
		fmt.Sprintf("mail_failed:%d", id)).Scan(&level, &kind, &key, &message, &detail, &params)
	if err != nil {
		t.Fatal(err)
	}
	if level != "warning" || kind != "mail_failed" || message != "E-mail could not be sent (claim)." {
		t.Fatalf("alert %s %s %s", level, kind, message)
	}
	if !strings.HasPrefix(detail, "To j********@e******.test: ") || strings.Contains(detail+params, "jan.novak") {
		t.Fatalf("alert leaks the address or has the wrong shape: %q %q", detail, params)
	}
	wantParams := `{"error": "` + *lastErr + `", "kind": "claim", "to": "j********@e******.test"}`
	if params != wantParams {
		t.Fatalf("params %q want %q", params, wantParams)
	}
}

func TestDrainResetsStaleSending(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	cfg.Backend = BackendConsole
	ctx := context.Background()
	id := obQueue(t, pool, "k1", "completion", "guest@example.test", map[string]any{"text": "hi"}, 0, "2026-11-13T09:00:00Z")
	fresh := obQueue(t, pool, "k2", "completion", "guest@example.test", map[string]any{"text": "hi"}, 0, "2026-11-13T09:00:00Z")
	for _, r := range []struct {
		id      int64
		updated string
	}{{id, "2026-11-13T09:49:00+00:00"}, {fresh, "2026-11-13T09:51:00+00:00"}} {
		if _, err := pool.Exec(ctx, `UPDATE email_outbox SET state = 'sending', updated_at = $1 WHERE id = $2`, r.updated, r.id); err != nil {
			t.Fatal(err)
		}
	}
	sum, err := Drain(ctx, pool, cfg, 8)
	if err != nil || sum.Sent != 1 {
		t.Fatalf("%+v %v", sum, err)
	}
	if state, _, _, _, _ := obRowState(t, pool, id); state != "sent" {
		t.Fatalf("stale row %s", state)
	}
	if state, _, _, _, _ := obRowState(t, pool, fresh); state != "sending" {
		t.Fatalf("fresh sending row must be left alone, got %s", state)
	}
}

func TestDrainSESRequest(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	var gotPath, gotAuth, gotDate, gotType string
	var gotBody map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath, gotAuth, gotDate, gotType = r.URL.Path, r.Header.Get("Authorization"), r.Header.Get("X-Amz-Date"), r.Header.Get("Content-Type")
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &gotBody)
		// the signature must verify against the request as received
		date, auth := obSignV4(r.Host, r.URL.Path, "eu-central-1", "ses", "AKIDEXAMPLE", "secret", cfg.now(), raw)
		if date != gotDate || auth != gotAuth {
			http.Error(w, "bad signature", 403)
			return
		}
		_, _ = w.Write([]byte(`{"MessageId":"0100abc"}`))
	}))
	defer srv.Close()
	cfg.SESEndpoint = srv.URL
	cfg.HTTPClient = srv.Client()
	ctx := context.Background()
	id := obQueue(t, pool, "k1", "lifecycle_no_guest", "host@example.test",
		map[string]any{"text": "tip", "html": "<p>tip</p>", "reply_to": "r@example.test", "list_unsubscribe": "https://app.example.test/u/1"},
		0, "2026-11-13T09:00:00Z")
	sum, err := Drain(ctx, pool, cfg, 8)
	if err != nil || sum.Sent != 1 {
		t.Fatalf("%+v %v", sum, err)
	}
	state, _, _, provider, _ := obRowState(t, pool, id)
	if state != "sent" || provider == nil || *provider != "0100abc" {
		t.Fatalf("row %s %v", state, provider)
	}
	if gotPath != "/v2/email/outbound-emails" || gotType != "application/json" || !strings.HasPrefix(gotAuth, "AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20261113/eu-central-1/ses/aws4_request") {
		t.Fatalf("request %s %s %s", gotPath, gotType, gotAuth)
	}
	simple := gotBody["Content"].(map[string]any)["Simple"].(map[string]any)
	body := simple["Body"].(map[string]any)
	if gotBody["FromEmailAddress"] != "UbyHost <noreply@mail.example.test>" ||
		simple["Subject"].(map[string]any)["Data"] != "Subject" ||
		body["Text"].(map[string]any)["Data"] != "tip" || body["Html"].(map[string]any)["Data"] != "<p>tip</p>" ||
		gotBody["ReplyToAddresses"].([]any)[0] != "r@example.test" ||
		gotBody["Destination"].(map[string]any)["ToAddresses"].([]any)[0] != "host@example.test" {
		t.Fatalf("body %v", gotBody)
	}
	headers := simple["Headers"].([]any)
	if len(headers) != 2 || headers[0].(map[string]any)["Name"] != "List-Unsubscribe" {
		t.Fatalf("headers %v", headers)
	}
}

func TestDrainSESErrorsDoNotLeakAddresses(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Amzn-ErrorType", "MessageRejected:http://internal.amazon.com/coral/")
		w.WriteHeader(400)
		_, _ = w.Write([]byte(`{"message":"Email address is not verified: guest@example.test"}`))
	}))
	defer srv.Close()
	cfg.SESEndpoint = srv.URL
	cfg.HTTPClient = srv.Client()
	id := obQueue(t, pool, "k1", "completion", "guest@example.test", map[string]any{"text": "x"}, 0, "2026-11-13T09:00:00Z")
	if sum, err := Drain(context.Background(), pool, cfg, 8); err != nil || sum.Skipped != 1 {
		t.Fatalf("%+v %v", sum, err)
	}
	_, _, lastErr, _, _ := obRowState(t, pool, id)
	if lastErr == nil || *lastErr != "SES SendEmail failed: HTTP 400 (MessageRejected)" {
		t.Fatalf("last_error %v", lastErr)
	}
	// a response without a MessageId is an error too
	srv2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(`{}`)) }))
	defer srv2.Close()
	cfg.SESEndpoint = srv2.URL
	if _, err := cfg.sesSend(context.Background(), sesRequest{}); err == nil || !strings.Contains(err.Error(), "MessageId") {
		t.Fatalf("no message id: %v", err)
	}
}

func TestPurge(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	ctx := context.Background()
	_ = g
	now := time.Date(2026, 11, 13, 10, 0, 0, 123456000, time.UTC) // 11:00 in Prague
	// cutoff = 2026-10-30T11:00:00.123456 (Prague wall clock, microseconds kept)
	ins := func(key, state, updated string) {
		if _, err := pool.Exec(ctx,
			`INSERT INTO email_outbox (idempotency_key, kind, to_email, state, created_at, updated_at) VALUES ($1, 'completion', 'a@b.test', $2, $3, $3)`,
			key, state, updated); err != nil {
			t.Fatal(err)
		}
	}
	ins("old-sent", "sent", "2026-10-30T10:00:00+00:00")
	ins("old-failed", "failed", "2026-10-01T10:00:00+00:00")
	ins("old-queued", "queued", "2026-10-01T10:00:00+00:00")
	ins("new-sent", "sent", "2026-11-12T10:00:00+00:00")
	for i, at := range []string{"2026-10-29T10:00:00+00:00", "2026-11-12T10:00:00+00:00"} {
		if _, err := pool.Exec(ctx, `INSERT INTO console_mail_log (outbox_id, created_at) VALUES ($1, $2)`, i, at); err != nil {
			t.Fatal(err)
		}
	}
	n, err := Purge(ctx, pool, now, 14)
	if err != nil || n != 2 {
		t.Fatalf("purged %d %v", n, err)
	}
	var left, logs int
	_ = pool.QueryRow(ctx, `SELECT count(*) FROM email_outbox`).Scan(&left)
	_ = pool.QueryRow(ctx, `SELECT count(*) FROM console_mail_log`).Scan(&logs)
	if left != 2 || logs != 1 {
		t.Fatalf("left %d logs %d", left, logs)
	}
	if got := obIsoNaive(time.Date(2026, 10, 30, 11, 0, 0, 123456000, time.UTC)); got != "2026-10-30T11:00:00.123456" {
		t.Fatalf("iso %s", got)
	}
	if got := obIsoNaive(time.Date(2026, 10, 30, 11, 0, 0, 0, time.UTC)); got != "2026-10-30T11:00:00" {
		t.Fatalf("iso %s", got)
	}
}

func TestSendNow(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	ctx := context.Background()
	env := map[string]string{"UBYHOST_MAIL_BACKEND": "console", "UBYHOST_DATA_KEYS": g.FernetKey, "UBYHOST_DATA_KEY_LEGACY": "0"}
	getenv := func(k string) string { return env[k] }
	due := "2026-11-13T09:00:00Z"
	ok := obQueue(t, pool, "k1", "login_link", "guest@example.test", map[string]any{"text": "hi"}, 0, due)
	bad := obQueue(t, pool, "k2", "claim", "guest@example.test", map[string]any{"text": "{{claim_secret}}"}, 2, due)
	if err := SendNow(ctx, pool, getenv, 0); err != nil {
		t.Fatalf("id 0: %v", err)
	}
	if err := SendNow(ctx, pool, getenv, 999999); err != nil {
		t.Fatalf("missing row: %v", err)
	}
	env["UBYHOST_MAIL_BACKEND"] = "disabled"
	if err := SendNow(ctx, pool, getenv, ok); err != nil {
		t.Fatalf("disabled: %v", err)
	}
	if state, _, _, _, _ := obRowState(t, pool, ok); state != "queued" {
		t.Fatalf("disabled mail must not touch the row: %s", state)
	}
	env["UBYHOST_MAIL_BACKEND"] = "smtp"
	if err := SendNow(ctx, pool, getenv, ok); err == nil {
		t.Fatal("an invalid backend is a config error")
	}
	env["UBYHOST_MAIL_BACKEND"] = "console"
	if err := SendNow(ctx, pool, getenv, ok); err != nil {
		t.Fatal(err)
	}
	if state, attempts, _, provider, _ := obRowState(t, pool, ok); state != "sent" || attempts != 1 || provider == nil || *provider != fmt.Sprintf("console:%d", ok) {
		t.Fatalf("sent: %s %d %v", state, attempts, provider)
	}
	if err := SendNow(ctx, pool, getenv, ok); err != nil {
		t.Fatalf("a sent row is left alone: %v", err)
	}
	var logs int
	_ = pool.QueryRow(ctx, `SELECT count(*) FROM console_mail_log WHERE outbox_id = $1`, ok).Scan(&logs)
	if logs != 1 {
		t.Fatalf("sent twice: %d log rows", logs)
	}
	// a failed delivery is not an error: the row stays queued with back-off
	if err := SendNow(ctx, pool, getenv, bad); err != nil {
		t.Fatalf("failed delivery must not be an error: %v", err)
	}
	if state, attempts, lastErr, _, next := obRowState(t, pool, bad); state != "queued" || attempts != 3 || lastErr == nil || next == nil || *next == due {
		t.Fatalf("failed row: %s %d %v %v", state, attempts, lastErr, next)
	}
}

func TestNoDetailsRendererPutsRowBack(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	cfg.Backend = BackendConsole
	ctx := context.Background()
	saved := obDefaultDetails
	obDefaultDetails = nil
	defer func() { obDefaultDetails = saved }()
	id := obQueue(t, pool, "k1", "guest_details_host", "host@example.test",
		map[string]any{"text": "{{guest_details}}", "guest_details_reservation_id": 5}, 0, "2026-11-13T09:00:00Z")
	if _, err := Drain(ctx, pool, cfg, 8); !errors.Is(err, ErrNoDetailsRenderer) {
		t.Fatalf("drain: %v", err)
	}
	if err := cfg.sendNow(ctx, pool, id); !errors.Is(err, ErrNoDetailsRenderer) {
		t.Fatalf("send_now: %v", err)
	}
	if state, attempts, lastErr, _, _ := obRowState(t, pool, id); state != "queued" || attempts != 0 || lastErr != nil {
		t.Fatalf("row must be put back untouched: %s %d %v", state, attempts, lastErr)
	}
	cfg.Details = obFakeDetails{}
	if sum, err := Drain(ctx, pool, cfg, 8); err != nil || sum.Sent != 1 {
		t.Fatalf("with a renderer: %+v %v", sum, err)
	}
}
```

