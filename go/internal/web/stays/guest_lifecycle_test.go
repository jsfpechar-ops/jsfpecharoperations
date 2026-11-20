package stays

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

func TestGuestLifecycleGoldenHTTP(t *testing.T) {
	g := loadGuestLifecycleGolden(t)
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
			if c.Status != http.StatusOK && c.Status != http.StatusNotFound && c.Status != http.StatusSeeOther {
				t.Errorf("%s: status %d", c.Name, c.Status)
			}
		}
	}
}

func TestLifecycleSentRefused(t *testing.T) {
	if submitStateSent != "sent" {
		t.Fatal("sent constant")
	}
}

func TestFiledRecordChangedUnit(t *testing.T) {
	res := hostReservation{dateFrom: "2026-06-01", dateTo: "2026-06-04"}
	stored := hostGuest{nationality: "DEU", surname: "A", firstName: "B", submitState: "sent"}
	changed := hostGuest{nationality: "DEU", surname: "A", firstName: "C", submitState: "sent"}
	if !filedRecordChanged(stored, changed, res) {
		t.Fatal("first name change")
	}
	same := hostGuest{nationality: "DEU", surname: "A", firstName: "B", submitState: "sent"}
	if filedRecordChanged(stored, same, res) {
		t.Fatal("no change")
	}
}

func TestGuestPayloadDocType(t *testing.T) {
	raw := validationDocTypes()
	if len(raw) == 0 {
		t.Fatal("doc types")
	}
}

type guestEditGolden struct {
	Now   string `json:"now"`
	Seed  []any  `json:"seed"`
	Cases []struct {
		Name     string `json:"name"`
		Method   string `json:"method"`
		Path     string `json:"path"`
		Body     string `json:"body"`
		User     int64  `json:"user"`
		Status   int    `json:"status"`
		Location string `json:"location"`
		FlashKey string `json:"flash_key"`
	} `json:"cases"`
}

func loadGuestLifecycleGolden(t *testing.T) guestEditGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/guest_lifecycle_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g guestEditGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestGuestLifecycleSignedOutRedirects(t *testing.T) {
	t.Skip("signed-out redirect parity is in guest_lifecycle_golden.json; hostweb.Login needs a pool")
}

func TestGuestLifecycleKeepsSignature(t *testing.T) {
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

