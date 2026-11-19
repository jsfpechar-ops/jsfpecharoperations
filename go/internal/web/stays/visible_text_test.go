package stays

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

type staysVisibleGolden struct {
	Cases []struct {
		Name  string   `json:"name"`
		Lang  string   `json:"lang"`
		Path  string   `json:"path"`
		Lines []string `json:"lines"`
	} `json:"cases"`
}

func loadStaysVisibleGolden(t *testing.T) staysVisibleGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/stays_visible_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g staysVisibleGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 1 {
		t.Fatal("stays visible golden is empty")
	}
	return g
}

func seedStaysVisibleParityWorld(t *testing.T, pool *pgxpool.Pool, now time.Time) int64 {
	t.Helper()
	ctx := t.Context()
	stamp := isoStamp(now)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('stays-parity', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, now)
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Chrome Flat','tokparity','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	type spec struct {
		from, to, source, status string
		gn, sn                   string
	}
	specs := []spec{
		{"2026-06-10", "2026-06-12", "airbnb", "active", "Sofia", "Costa"},
		{"2026-06-13", "2026-06-14", "booking", "active", "", ""},
		{"2026-06-15", "2026-06-17", "manual", "active", "Lead", "Three"},
		{"2026-06-18", "2026-06-20", "manual", "active", "Lead", "Four"},
		{"2026-06-21", "2026-06-23", "manual", "active", "Lead", "Five"},
		{"2026-06-24", "2026-06-26", "manual", "cancelled", "", ""},
	}
	for i, s := range specs {
		var resID int64
		err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$7) RETURNING id`,
			aptID, fmt.Sprintf("uid-%d", i), s.from, s.to, s.status, s.source, stamp).Scan(&resID)
		if err != nil {
			t.Fatal(err)
		}
		if s.gn != "" {
			if _, err := pool.Exec(ctx, `INSERT INTO guest (reservation_id, first_name, surname, is_lead, entered_by, created_at, updated_at)
				VALUES ($1,$2,$3,1,'guest',$4,$4)`, resID, s.gn, s.sn, stamp); err != nil {
				t.Fatal(err)
			}
		}
	}
	return ownerID
}

func staysListGET(t *testing.T, mux http.Handler, now time.Time, ownerID int64, path, lang string) string {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(createTestSecret, map[string]any{
		"uid": ownerID, "sv": 1,
	}, now)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("%s: status %d", path, rec.Code)
	}
	return rec.Body.String()
}

func TestStaysListVisibleTextMatchesPython(t *testing.T) {
	pool := dbPool(t)
	now := fixedToday()
	ownerID := seedStaysVisibleParityWorld(t, pool, now)
	mux := http.NewServeMux()
	Register(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	g := loadStaysVisibleGolden(t)
	for _, c := range g.Cases {
		html := staysListGET(t, mux, now, ownerID, c.Path, c.Lang)
		got := staysVisibleLines(html)
		for i := 0; i < len(got) || i < len(c.Lines); i++ {
			var have, want string
			if i < len(got) {
				have = got[i]
			}
			if i < len(c.Lines) {
				want = c.Lines[i]
			}
			if have != want {
				t.Fatalf("%s: line %d got %q want %q", c.Name, i, have, want)
			}
		}
	}
}

func TestStaysListVisibleTextNoRawI18nKeys(t *testing.T) {
	cases := []struct {
		name string
		data listPage
	}{
		{"page1", parityFixture(fixedToday(), 1, "")},
		{"page2", parityFixture(fixedToday(), 2, "")},
		{"report_failed", parityFixture(fixedToday(), 1, "failed")},
	}
	for _, tc := range cases {
		html := renderStaysHTML(t, tc.data)
		lines := staysVisibleLines(html)
		if bad := rawI18nKeysInText(lines); len(bad) > 0 {
			t.Fatalf("%s: raw catalog keys in visible text: %v", tc.name, bad)
		}
	}
	data := parityFixture(fixedToday(), 1, "")
	rows := parityRows(fixedToday())
	rows[0].Reservation.Source = "airbnb"
	rows[1].Reservation.Source = "booking"
	data.View.Rows = rows[:3]
	data.Groups = groupRows(data.View.Rows, data.Today)
	html := renderStaysHTML(t, data)
	lines := staysVisibleLines(html)
	for _, label := range []string{"Airbnb", "Booking.com", "Direct booking"} {
		if !strings.Contains(html, label) {
			t.Fatalf("missing label %q in HTML", label)
		}
	}
	if bad := rawI18nKeysInText(lines); len(bad) > 0 {
		t.Fatalf("portal sources case: raw keys %v", bad)
	}
}
