package signup

import (
	"bytes"
	"compress/zlib"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

// golden is testdata/signup.json, written by App/scripts/signup_golden.py.
type golden struct {
	Secret string            `json:"secret"`
	Now    int64             `json:"now"`
	Env    map[string]string `json:"env"`
	Clean  []struct{ Param, Value, Out string }
	UTM    []struct{ Value, Out string }  `json:"utm"`
	UA     []struct{ Value, Out *string } `json:"user_agent"`
	Sel    []struct {
		Query [][2]string `json:"query"`
		JSON  string      `json:"json"`
	} `json:"selection"`
	Clicks []struct {
		IDs    map[string]string `json:"ids"`
		SeenMS int64             `json:"seen_ms"`
		Token  string            `json:"token"`
		Reads  map[string]struct {
			At int64 `json:"at"`
			OK bool  `json:"ok"`
		} `json:"reads"`
	} `json:"clicks"`
	BadClicks   []string `json:"bad_clicks"`
	Attribution []struct {
		Query [][2]string       `json:"query"`
		Mint  bool              `json:"mint"`
		Out   map[string]string `json:"out"`
	} `json:"attribution"`
	Tokens []struct {
		UID   int64  `json:"uid"`
		Nonce string `json:"nonce"`
		Token string `json:"token"`
	} `json:"tokens"`
	Consent []struct{ Platform, Lang, Text string }
	Source  []struct {
		Stored []string          `json:"stored"`
		Attr   map[string]string `json:"attr"`
		Out    string            `json:"out"`
	} `json:"source"`
	ConversionTime []struct{ Stored, Out string } `json:"conversion_time"`
	CSV            struct {
		Rows []struct {
			ID              int64  `json:"id"`
			Gclid           string `json:"gclid"`
			EmailVerifiedAt string `json:"email_verified_at"`
		} `json:"rows"`
		Body string `json:"body"`
	} `json:"csv"`
	ISOFromMS []struct {
		MS  int64  `json:"ms"`
		Out string `json:"out"`
	} `json:"iso_from_ms"`
	Trial      []struct{ Stamp, First, Last string }
	VerifyLink string `json:"verify_link"`
	Mails      []struct {
		Kind, Lang, Workspace, Campaign string
		Ads, Meta                       bool
		Subject, Text, HTML             string
	} `json:"mails"`
	Payload struct {
		Lang string `json:"lang"`
		JSON string `json:"json"`
	} `json:"payload"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "signup.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Clean) == 0 || len(g.UA) == 0 || len(g.Clicks) == 0 || len(g.Tokens) == 0 || len(g.Consent) == 0 ||
		len(g.Trial) == 0 || len(g.Mails) == 0 || g.CSV.Body == "" || g.Payload.JSON == "" {
		t.Fatal("golden file is incomplete")
	}
	return g
}

func (g golden) getenv(k string) string { return g.Env[k] }

func values(q [][2]string) url.Values {
	v := url.Values{}
	for _, p := range q {
		v.Add(p[0], p[1])
	}
	return v
}

// payloadJSON is the JSON inside a signed value, decompressed.
func payloadJSON(t *testing.T, token string) string {
	t.Helper()
	value := token[:strings.LastIndex(token, ".")]
	if parts := strings.Split(value, "."); len(parts) == 3 && parts[0] == "" {
		value = "." + parts[1] // timed: ".<payload>.<ts>"
	} else if len(parts) == 2 && parts[0] != "" {
		value = parts[0]
	}
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(value, "."))
	if err != nil {
		t.Fatal(err)
	}
	if strings.HasPrefix(value, ".") {
		r, err := zlib.NewReader(bytes.NewReader(raw))
		if err != nil {
			t.Fatal(err)
		}
		if raw, err = io.ReadAll(r); err != nil {
			t.Fatal(err)
		}
	}
	return string(raw)
}

func TestGoldenCleaners(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.Clean {
		if got := CleanClickID(c.Param, c.Value); got != c.Out {
			t.Errorf("clean_click_id(%q, %q) = %q, want %q", c.Param, c.Value, got, c.Out)
		}
	}
	for _, c := range g.UTM {
		if got := CleanUTM(c.Value); got != c.Out {
			t.Errorf("clean_utm(%q) = %q, want %q", c.Value, got, c.Out)
		}
	}
	for _, c := range g.UA {
		want := ""
		if c.Out != nil {
			want = *c.Out
		}
		if got := CleanUserAgent(*c.Value); got != want {
			t.Errorf("clean_user_agent(%q) = %q, want %q", *c.Value, got, want)
		}
	}
	for _, c := range g.Sel {
		if got := selectionJSON(values(c.Query)); got != c.JSON {
			t.Errorf("selection %v = %s, want %s", c.Query, got, c.JSON)
		}
	}
	for _, c := range g.Source {
		if got := SignupSource(c.Stored, c.Attr); got != c.Out {
			t.Errorf("signup_source(%v, %v) = %s, want %s", c.Stored, c.Attr, got, c.Out)
		}
	}
	for _, c := range g.ISOFromMS {
		if got := isoFromMS(c.MS); got != c.Out {
			t.Errorf("_iso_from_ms(%d) = %s, want %s", c.MS, got, c.Out)
		}
	}
}

func TestGoldenClicks(t *testing.T) {
	g := loadGolden(t)
	for i, c := range g.Clicks {
		for name, r := range c.Reads {
			got := ReadClick(g.Secret, c.Token, r.At)
			if (got != nil) != r.OK {
				t.Errorf("click %d %s: ok %v, want %v", i, name, got != nil, r.OK)
			}
			if got != nil && (!reflect.DeepEqual(got.IDs, c.IDs) || got.SeenMS != c.SeenMS) {
				t.Errorf("click %d %s: %+v", i, name, got)
			}
		}
		mine, err := IssueClick(g.Secret, c.IDs, c.SeenMS)
		if err != nil {
			t.Fatal(err)
		}
		if mine != c.Token {
			// zlib output differs between CPython and Go: compare the JSON.
			if payloadJSON(t, mine) != payloadJSON(t, c.Token) || ReadClick(g.Secret, mine, g.Now*1000) == nil {
				t.Errorf("click %d: Go token %s differs from Python %s", i, payloadJSON(t, mine), payloadJSON(t, c.Token))
			}
		}
	}
	for i, tok := range g.BadClicks {
		if ReadClick(g.Secret, tok, g.Now*1000) != nil {
			t.Errorf("bad click %d accepted", i)
		}
	}
	if ReadClick(g.Secret+"x", g.Clicks[0].Token, g.Now*1000) != nil || ReadClick(g.Secret, "", g.Now*1000) != nil {
		t.Error("wrong secret or empty token accepted")
	}
	for i, c := range g.Attribution {
		got := Attribution(g.Secret, values(c.Query), c.Mint, g.Now*1000)
		if got["click"] != "" && got["click"] != c.Out["click"] {
			if payloadJSON(t, got["click"]) != payloadJSON(t, c.Out["click"]) {
				t.Errorf("attribution %d click %s, want %s", i, payloadJSON(t, got["click"]), payloadJSON(t, c.Out["click"]))
			}
			got["click"] = c.Out["click"]
		}
		if !reflect.DeepEqual(got, c.Out) && !(len(got) == 0 && len(c.Out) == 0) {
			t.Errorf("attribution %d = %v, want %v", i, got, c.Out)
		}
	}
}

func TestGoldenTokens(t *testing.T) {
	g := loadGolden(t)
	now := time.Unix(g.Now, 0)
	for _, c := range g.Tokens {
		uid, nonce, ok := readToken(g.Secret, c.Token, now.Add(VerifyMaxAge*time.Second))
		if !ok || uid != c.UID || nonce != c.Nonce {
			t.Errorf("read %d: %d %q %v", c.UID, uid, nonce, ok)
		}
		if _, _, ok := readToken(g.Secret, c.Token, now.Add((VerifyMaxAge+1)*time.Second)); ok {
			t.Errorf("token %d accepted after 24 hours", c.UID)
		}
		mine, err := IssueToken(g.Secret, c.UID, c.Nonce, now)
		if err != nil || mine != c.Token {
			t.Errorf("issue_token(%d) = %s, want %s", c.UID, mine, c.Token)
		}
	}
	if _, _, ok := readToken(g.Secret, g.Clicks[0].Token, now); ok {
		t.Error("a click value read as a verify token")
	}
}

func TestGoldenConsentAndExport(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.Consent {
		if got, err := ConsentText(c.Platform, c.Lang); err != nil || got != c.Text {
			t.Errorf("consent_text(%s, %s) = %q, want %q", c.Platform, c.Lang, got, c.Text)
		}
	}
	if _, err := ConsentText("bing", "en"); err != ErrUnknownPlatform {
		t.Error("unknown platform accepted")
	}
	for _, c := range g.ConversionTime {
		if got, err := ConversionTime(c.Stored); err != nil || got != c.Out {
			t.Errorf("conversion_time(%s) = %s %v, want %s", c.Stored, got, err, c.Out)
		}
	}
	var rows []ExportRow
	for _, r := range g.CSV.Rows {
		rows = append(rows, ExportRow{ID: r.ID, Gclid: r.Gclid, EmailVerifiedAt: r.EmailVerifiedAt})
	}
	if got, err := ConversionsCSV(g.getenv, rows); err != nil || got != g.CSV.Body {
		t.Errorf("conversions_csv = %q, want %q", got, g.CSV.Body)
	}
	for _, c := range g.Trial {
		at, _ := time.Parse(time.RFC3339, c.Stamp)
		if first, last := TrialDates(at); first != c.First || last != c.Last {
			t.Errorf("activation_dates(%s) = %s %s, want %s %s", c.Stamp, first, last, c.First, c.Last)
		}
	}
}

func TestGoldenMails(t *testing.T) {
	g := loadGolden(t)
	env := g.getenv
	if link := publicBase(env) + "/signup/verify?t={{claim_secret}}"; link != g.VerifyLink {
		t.Fatalf("verify link %s, want %s", link, g.VerifyLink)
	}
	for i, m := range g.Mails {
		var c mail.Content
		switch m.Kind {
		case "verify":
			c = mail.BuildSignupVerify(publicBase(env), operatorEmail(env), m.Lang, m.Workspace, "host-ab12", g.VerifyLink)
		case "exists":
			c = mail.BuildSignupExists(publicBase(env), appBase(env), operatorEmail(env), m.Lang)
		case "admin":
			c = mail.BuildSignupAdmin(publicBase(env), appBase(env), operatorEmail(env), m.Workspace, "a@b.cz", "host-ab12", m.Campaign, m.Ads, m.Meta)
		}
		if c.Subject != m.Subject || c.Text != m.Text {
			t.Errorf("mail %d %s %s: subject/text differ:\n%q\n%q", i, m.Kind, m.Lang, c.Text, m.Text)
		}
		if c.HTML != m.HTML {
			n := 0
			for n < len(c.HTML) && n < len(m.HTML) && c.HTML[n] == m.HTML[n] {
				n++
			}
			t.Errorf("mail %d %s %s: html differs at byte %d", i, m.Kind, m.Lang, n)
		}
	}
	first := g.Mails[1]
	if got := pyDumps([][2]string{{"text", first.Text}, {"html", first.HTML}, {"lang", g.Payload.Lang}}); got != g.Payload.JSON {
		t.Errorf("payload json differs from json.dumps")
	}
}
