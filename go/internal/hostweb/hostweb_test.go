package hostweb

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBack(t *testing.T) {
	saved := Flash{Text: "Saved", Key: "flash.guests.saved"}
	cases := []struct {
		name string
		path string
		msg  Flash
		err  Flash
		want string
	}{
		{"msg only", "/a", Flash{Text: "Ok"}, Flash{}, "/a?msg=Ok"},
		{"err only", "/a", Flash{}, Flash{Text: "Bad"}, "/a?err=Bad"},
		{"both", "/a", Flash{Text: "Ok"}, Flash{Text: "Bad"}, "/a?msg=Ok&err=Bad"},
		{"success key", "/a", saved, Flash{}, "/a?msg=Saved&toast_kind=success"},
		{"sticky warning", "/a", Flash{Text: "Saved", Key: "flash.apartments.saved"}, Flash{}, "/a?msg=Saved&toast_kind=warning&toast_sticky=1"},
		{"partial", "/a", Flash{Text: "Some", Key: "flash.reservations.accepted", Count: 2}, Flash{}, "/a?msg=Some&toast_kind=partial&toast_sticky=1"},
		{"zero count is neutral", "/a", Flash{Text: "None", Key: "flash.reservations.accepted"}, Flash{}, "/a?msg=None"},
		{"query in path", "/a?x=1", Flash{Text: "Ok"}, Flash{}, "/a?x=1&msg=Ok"},
		{"fragment", "/a?x=1#top", Flash{Text: "Ok"}, Flash{}, "/a?x=1&msg=Ok#top"},
		{"fragment without query", "/a#top", Flash{Text: "Ok"}, Flash{}, "/a?msg=Ok#top"},
		{"non ascii like quote", "/a", Flash{Text: "Uloženo"}, Flash{}, "/a?msg=Ulo%C5%BEeno"},
		{"slash kept", "/a", Flash{Text: "x/y//z"}, Flash{}, "/a?msg=x/y//z"},
		{"no message", "/a", Flash{}, Flash{}, "/a"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			rec := httptest.NewRecorder()
			req := httptest.NewRequest(http.MethodPost, "/", nil)
			Back(rec, req, c.path, c.msg, c.err)
			if rec.Code != http.StatusSeeOther {
				t.Fatalf("code %d, want 303", rec.Code)
			}
			if got := rec.Header().Get("Location"); got != c.want {
				t.Errorf("location %q, want %q", got, c.want)
			}
		})
	}
}

func TestLang(t *testing.T) {
	cases := []struct {
		name   string
		target string
		cookie string
		want   string
	}{
		{"query beats cookie", "/x?lang=cs", "vi", "cs"},
		{"cookie without query", "/x", "vi", "vi"},
		{"unsupported query falls to cookie", "/x?lang=de", "cs", "cs"},
		{"region code", "/x?lang=cs-CZ", "", "cs"},
		{"nothing set", "/x", "", "en"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, c.target, nil)
			if c.cookie != "" {
				req.AddCookie(&http.Cookie{Name: langCookie, Value: c.cookie})
			}
			if got := Lang(req); got != c.want {
				t.Errorf("lang %q, want %q", got, c.want)
			}
		})
	}
}

func TestCatalogCases(t *testing.T) {
	c := Load([]byte(`{"en":{"plain":"Hi","named":"Hello %(name)s"}}`))
	if got := c.T("en", "plain", nil); got != "Hi" {
		t.Errorf("plain: %q", got)
	}
	if got := c.T("en", "named", map[string]any{"name": "Ana"}); got != "Hello Ana" {
		t.Errorf("named: %q", got)
	}
	if got := c.T("en", "missing", nil); got != "missing" {
		t.Errorf("missing: %q", got)
	}
	if got := c.T("cs", "plain", nil); got != "Hi" {
		t.Errorf("unknown lang falls back to default table: %q", got)
	}
	if got := c.T("en", "named", map[string]any{"other": 1}); got != "Hello %(name)s" {
		t.Errorf("bad params return raw text: %q", got)
	}
}

func TestHostStringsEmbedded(t *testing.T) {
	if _, ok := HostStrings["en"]; !ok {
		t.Fatal("embedded i18n.json has no en table")
	}
}
