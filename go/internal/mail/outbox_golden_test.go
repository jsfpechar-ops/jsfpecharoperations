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
