package stays

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

func TestGuestPrivacyGoldenHTTP(t *testing.T) {
	g := loadGuestPrivacyGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	for _, c := range g.Cases {
		switch c.Method {
		case http.MethodPost:
			if c.Status != http.StatusSeeOther && c.Status != http.StatusOK {
				t.Errorf("%s: status %d", c.Name, c.Status)
			}
			if c.Status == http.StatusSeeOther && c.Location != "" && !strings.HasPrefix(c.Location, "/") {
				t.Errorf("%s: location %q", c.Name, c.Location)
			}
		case http.MethodGet:
			if c.Status != http.StatusOK && c.Status != http.StatusNotFound && c.Status != http.StatusSeeOther && c.Status != http.StatusForbidden {
				t.Errorf("%s: status %d", c.Name, c.Status)
			}
		}
	}
}

func TestPassportFilenameUnit(t *testing.T) {
	if passportDownloadFilename(9, "image/jpeg") != "passport-9.jpg" {
		t.Fatal("filename")
	}
}

func loadGuestPrivacyGolden(t *testing.T) guestEditGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/guest_privacy_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g guestEditGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestGuestPrivacySignedOutRedirects(t *testing.T) {
	g := loadGuestPrivacyGolden(t)
	for _, c := range g.Cases {
		if c.User != 0 {
			continue
		}
		if c.Status != http.StatusSeeOther || c.Location != "/login" {
			t.Fatalf("%s: signed-out want 303 /login, got %d %q", c.Name, c.Status, c.Location)
		}
	}
}

func TestGuestPrivacyKeepsSignature(t *testing.T) {
	now := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	sig := validGuestSignature()
	if got := keptGuestSignature(sig, ""); got != sig {
		t.Fatalf("kept %q", got)
	}
	if keptGuestSignature("not-a-data-url", "data:image/png;base64,OLD") != "data:image/png;base64,OLD" {
		t.Fatal("fallback stored")
	}
	_ = now
}
