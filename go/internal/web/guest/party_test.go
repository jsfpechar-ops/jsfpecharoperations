package guest

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

func TestPartyGoldenHTTP(t *testing.T) {
	g := loadPartyGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	for _, c := range g.Cases {
		switch c.Method {
		case http.MethodPost:
			if c.Status != http.StatusSeeOther && c.Status != http.StatusNotFound {
				t.Errorf("%s: status %d", c.Name, c.Status)
			}
			if c.Status == http.StatusSeeOther && c.Location != "" && !strings.HasPrefix(c.Location, "/l/") {
				t.Errorf("%s: location %q", c.Name, c.Location)
			}
		}
	}
}

type partyGolden struct {
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

func loadPartyGolden(t *testing.T) partyGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/party_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g partyGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestHeadcountLeadLiveEnv(t *testing.T) {
	if headcountLeadLive(func(string) string { return "" }) {
		t.Fatal("empty off")
	}
	if !headcountLeadLive(func(k string) string {
		if k == "UBYHOST_HEADCOUNT_LEAD_LIVE" {
			return "1"
		}
		return ""
	}) {
		t.Fatal("1 on")
	}
}

func TestLeadCutoffPrague(t *testing.T) {
	c := leadCutoff("2026-06-10", "14")
	if c.IsZero() {
		t.Fatal("cutoff")
	}
	now := time.Date(2026, 6, 10, 8, 0, 0, 0, time.UTC)
	if cutoffPassed("2026-06-10", "14", now) {
		t.Fatal("before check-in")
	}
}

func TestApplyDeclaredUnit(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	stamp := "2026-01-01T00:00:00Z"
	_, _ = pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (72, 'gp@example.test', 'x', 'host', 1, $1) ON CONFLICT DO NOTHING`, stamp)
	_, _ = pool.Exec(ctx, `INSERT INTO apartment (id, owner_user_id, internal_name, active, permalink_token, created_at)
		VALUES (72, 72, 'GP', 1, 'tok1722', $1) ON CONFLICT DO NOTHING`, stamp)
	_, _ = pool.Exec(ctx, `INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, status, created_at, updated_at)
		VALUES (1722, 72, 'gp', '2026-06-20', '2026-06-22', 'active', $1, $1) ON CONFLICT DO NOTHING`, stamp)
	d := partyDeps{pool: pool, getenv: func(string) string { return "" }, now: func() time.Time { return now }}
	code, err := d.applyDeclared(ctx, 1722, 3)
	if err != nil {
		t.Fatal(err)
	}
	if code != codeSaved {
		t.Fatalf("code %q", code)
	}
}
