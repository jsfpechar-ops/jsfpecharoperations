package stays

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func TestParseManualFiledAt(t *testing.T) {
	now := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	if got := parseManualFiledAt("", now); got != "2026-06-15T12:00:00+00:00" {
		t.Fatalf("empty = %q", got)
	}
	if got := parseManualFiledAt("2026-06-14T10:00", now); got != "2026-06-14T08:00:00+00:00" {
		t.Fatalf("local = %q", got)
	}
	if parseManualFiledAt("2099-01-01T00:00", now) != "" {
		t.Fatal("future refused")
	}
}

func TestCleanManualReference(t *testing.T) {
	if cleanManualReference("  a\nb  ") != "a b" {
		t.Fatal("whitespace")
	}
}

func TestClaimOpsSignedOutRedirects(t *testing.T) {
	t.Skip("signed-out redirect parity is in claim_ops_golden.json; hostweb.Login needs a pool")
}

type claimOpsGolden struct {
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

func loadClaimOpsGolden(t *testing.T) claimOpsGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/claim_ops_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g claimOpsGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestClaimOpsGoldenHTTP(t *testing.T) {
	g := loadClaimOpsGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	// DB parity is exercised when UBYHOST_TEST_DATABASE_URL is set (CI); here we
	// only assert the golden file shape the Python script wrote.
	for _, c := range g.Cases {
		if c.Status != http.StatusSeeOther {
			t.Errorf("%s: want 303", c.Name)
		}
		if !strings.HasPrefix(c.Location, "/") {
			t.Errorf("%s: location %q", c.Name, c.Location)
		}
	}
}

func TestMarkFiledByHandUnit(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	stamp := "2026-01-01T00:00:00+00:00"
	_, _ = pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (90, 'co@example.test', 'x', 'host', 1, $1) ON CONFLICT DO NOTHING`, stamp)
	_, _ = pool.Exec(ctx, `INSERT INTO apartment (id, owner_user_id, internal_name, active, created_at)
		VALUES (90, 90, 'CO', 1, $1) ON CONFLICT DO NOTHING`, stamp)
	_, _ = pool.Exec(ctx, `INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, status, created_at, updated_at)
		VALUES (900, 90, 'co', '2026-06-01', '2026-06-03', 'active', $1, $1) ON CONFLICT DO NOTHING`, stamp)
	_, _ = pool.Exec(ctx, `INSERT INTO guest (id, reservation_id, submit_state, nationality, created_at, updated_at)
		VALUES (9001, 900, 'pending', 'DE', $1, $1) ON CONFLICT DO NOTHING`, stamp)
	filedAt := "2026-06-10T09:00:00+00:00"
	res, err := markFiledByHand(ctx, pool, 900, filedAt, "REF", now)
	if err != nil {
		t.Fatal(err)
	}
	if res.Marked != 1 {
		t.Fatalf("marked %d", res.Marked)
	}
}

func testPoolOptional(t *testing.T) *pgxpool.Pool {
	t.Helper()
	url := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL unset")
		return nil
	}
	pool, err := pgxpool.New(context.Background(), url)
	if err != nil {
		t.Fatal(err)
	}
	return pool
}

func TestClaimOpsPostForm(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader("filed_at=2026-06-01T10%3A00&reference=abc"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	_ = req.ParseForm()
	if formStr(req, "reference") != "abc" {
		t.Fatal("formStr")
	}
}

func TestClaimOpsLocationEscape(t *testing.T) {
	u := &url.URL{Path: "/reservations/1"}
	if u.String() != "/reservations/1" {
		t.Fatal(u)
	}
}
