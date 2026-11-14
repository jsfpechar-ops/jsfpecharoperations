package mail

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

type accountGolden struct {
	Env       map[string]string `json:"env"`
	AppBase   string            `json:"app_base"`
	MaskedNew string            `json:"masked_new"`
	Mails     []struct {
		Builder string `json:"builder"`
		Kind    string `json:"kind"`
		Link    string `json:"link"`
		Minutes int    `json:"minutes"`
		Lang    string `json:"lang"`
		Side    string `json:"side"`
		By      string `json:"by"`
		Masked  string `json:"masked"`
		Name    string `json:"name"`
		Stage   string `json:"stage"`
		Date    string `json:"date"`
		Subject string `json:"subject"`
		Text    string `json:"text"`
		HTML    string `json:"html"`
	} `json:"mails"`
	Payloads struct {
		Link struct {
			Lang string `json:"lang"`
			JSON string `json:"json"`
		} `json:"link"`
		Notice       string `json:"notice"`
		LinkKeyToken string `json:"link_key_token"`
		LinkKey      string `json:"link_key"`
	} `json:"payloads"`
	Dates []struct {
		In  string `json:"in"`
		Out string `json:"out"`
	} `json:"dates"`
}

func loadAccountGolden(t *testing.T) accountGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/auth_mail.json")
	if err != nil {
		t.Fatal(err)
	}
	var g accountGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Mails) < 150 || len(g.Dates) == 0 {
		t.Fatalf("golden too small: %d mails", len(g.Mails))
	}
	return g
}

func (g accountGolden) getenv(k string) string { return g.Env[k] }

// TestAccountMailsMatchPython compares subject, text and HTML of every
// account mail Python built (App/scripts/auth_shared_golden.py) byte for byte.
func TestAccountMailsMatchPython(t *testing.T) {
	g := loadAccountGolden(t)
	public, operator := accountPublicBase(g.getenv), accountOperatorEmail(g.getenv)
	if accountAppBase(g.getenv) != g.AppBase || MaskEmail("new.address@example.cz") != g.MaskedNew {
		t.Fatalf("app base or mask differ")
	}
	seen := map[string]int{}
	for i, m := range g.Mails {
		var c Content
		var err error
		switch m.Builder {
		case "link":
			c, err = BuildLinkMail(public, operator, m.Kind, m.Link, m.Minutes, m.Lang)
		case "email_changed":
			c, err = BuildEmailChanged(public, operator, m.Side, m.Masked, m.Lang, m.By)
		case "passkey_added":
			c = BuildPasskeyAdded(public, operator, m.Name, m.Lang)
		case "workspace_deletion":
			c, err = BuildWorkspaceDeletion(public, operator, m.Stage, m.Date, m.Lang)
		default:
			t.Fatalf("unknown builder %q", m.Builder)
		}
		if err != nil {
			t.Fatalf("mail %d: %v", i, err)
		}
		seen[m.Builder]++
		if c.Subject != m.Subject {
			t.Errorf("mail %d (%s %s %s): subject %q, want %q", i, m.Builder, m.Kind, m.Lang, c.Subject, m.Subject)
		}
		if c.Text != m.Text {
			t.Errorf("mail %d (%s %s %s): text differs\n got: %q\nwant: %q", i, m.Builder, m.Kind, m.Lang, c.Text, m.Text)
		}
		if c.HTML != m.HTML {
			t.Errorf("mail %d (%s %s %s): html differs", i, m.Builder, m.Kind, m.Lang)
		}
	}
	for _, b := range []string{"link", "email_changed", "passkey_added", "workspace_deletion"} {
		if seen[b] == 0 {
			t.Errorf("no %s case", b)
		}
	}
}

func TestUnknownVariants(t *testing.T) {
	if _, err := BuildLinkMail("", "", "password_reset", "x", 15, "en"); err != ErrUnknownMail {
		t.Errorf("link kind: %v", err)
	}
	if _, err := BuildEmailChanged("", "", "both", "x", "en", "self"); err != ErrUnknownMail {
		t.Errorf("side: %v", err)
	}
	if _, err := BuildWorkspaceDeletion("", "", "now", "x", "en"); err != ErrUnknownMail {
		t.Errorf("stage: %v", err)
	}
}

// TestAccountPayloadsMatchPython: the payload column is json.dumps(payload)
// in Python's key order (claim_secret_enc stands in as "ENC"), and the link
// key is kind:user:sha256(token)[:24].
func TestAccountPayloadsMatchPython(t *testing.T) {
	g := loadAccountGolden(t)
	var link, notice *struct{ text, html string }
	for _, m := range g.Mails {
		if link == nil && m.Builder == "link" && m.Lang == "CS-cz" {
			link = &struct{ text, html string }{m.Text, m.HTML}
		}
		if notice == nil && m.Builder == "passkey_added" {
			notice = &struct{ text, html string }{m.Text, m.HTML}
		}
	}
	if link == nil || notice == nil {
		t.Fatal("golden lacks the payload mails")
	}
	got := accountPayloadJSON([]payloadField{{"text", strPtr(link.text)}, {"html", strPtr(link.html)},
		{"lang", strPtr(authLanguage("CS-cz"))}, {claimSecretKey, strPtr("ENC")}})
	if got != g.Payloads.Link.JSON || authLanguage("CS-cz") != g.Payloads.Link.Lang {
		t.Errorf("link payload differs")
	}
	got = accountPayloadJSON(noticePayload(Content{Text: notice.text, HTML: notice.html}, g.getenv))
	if got != g.Payloads.Notice {
		t.Errorf("notice payload differs")
	}
	if KindLoginLink+":7:"+linkKeyPart(g.Payloads.LinkKeyToken) != g.Payloads.LinkKey {
		t.Errorf("link key differs")
	}
	if accountPayloadJSON([]payloadField{{"a", nil}, {"b", strPtr("\U0001F600\x7f\"\\\n")}}) !=
		`{"a": null, "b": "\ud83d\ude00\u007f\"\\\n"}` {
		t.Errorf("ensure_ascii escaping differs")
	}
}

// TestFmtDateMatchesPython is validation.fmt_date(value[:10]).
func TestFmtDateMatchesPython(t *testing.T) {
	g := loadAccountGolden(t)
	for _, d := range g.Dates {
		head := d.In
		if r := []rune(head); len(r) > 10 {
			head = string(r[:10])
		}
		if got := FmtDate(head); got != d.Out {
			t.Errorf("FmtDate(%q) = %q, want %q", d.In, got, d.Out)
		}
	}
	if !strings.Contains(FmtDate("2027-01-05"), "05.01.2027") {
		t.Errorf("plain date")
	}
}
