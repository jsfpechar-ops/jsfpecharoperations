package submissions

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

type readGolden struct {
	Now   string `json:"now"`
	Cases []struct {
		Name  string   `json:"name"`
		Lang  string   `json:"lang"`
		Path  string   `json:"path"`
		Kind  string   `json:"kind"`
		Lines []string `json:"lines"`
	} `json:"cases"`
}

func loadReadGolden(t *testing.T) readGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/submissions_read_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g readGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func seedParityWorld(t *testing.T, pool *pgxpool.Pool, now time.Time) (ownerID, okID, errID int64) {
	t.Helper()
	ctx := t.Context()
	stamp := now.UTC().Format(time.RFC3339)
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email)
		VALUES ('reports-parity', 'x', 'host', 1, 1, $1, 'reports-parity@example.test') RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, now)
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at) VALUES ($1,'Entity',$2) RETURNING id`,
		ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Chrome Flat','tokreports','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var resID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		VALUES ($1,'uid-parity-stay','2026-06-15','2026-06-17','active','manual',$2,$2) RETURNING id`, aptID, stamp).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	var guestID int64
	if err := pool.QueryRow(ctx, `INSERT INTO guest (reservation_id, first_name, surname, nationality, doc_number, is_lead, entered_by, created_at, updated_at)
		VALUES ($1,'Lead','Guest','CZE','AB123456',1,'guest',$2,$2) RETURNING id`, resID, stamp).Scan(&guestID); err != nil {
		t.Fatal(err)
	}
	guestJSON := fmt.Sprintf("[%d]", guestID)
	states := []string{"ok", "ok_duplicate", "partial", "error", "failed", "transport_error", "outcome_unknown", "not_configured", "running", "noop"}
	for i, state := range states {
		var pseudo, header, errText, receipt *string
		rec := `[""]`
		if state == "error" {
			h := "112;"
			header = &h
			rec = `["112;"]`
		}
		if state == "transport_error" {
			e := "smtp timeout"
			errText = &e
		}
		if state == "ok" || state == "ok_duplicate" || state == "partial" {
			p := fmt.Sprintf("ST%02d", i)
			pseudo = &p
			rc := "e=="
			receipt = &rc
		}
		var id int64
		if err := pool.QueryRow(ctx, `INSERT INTO submission (apartment_id, created_at, mode, guest_ids, state)
			VALUES ($1,$2,'manual',$3,'running') RETURNING id`,
			aptID, stamp, guestJSON).Scan(&id); err != nil {
			t.Fatal(err)
		}
		if state != "running" {
			if _, err := pool.Exec(ctx, `UPDATE submission SET state=$1, pseudo_stamp=$2, header_errors=$3, record_errors=$4::jsonb,
				finished_at=$5, error_text=$6, receipt_pdf=$7 WHERE id=$8`,
				state, pseudo, header, rec, stamp, errText, receipt, id); err != nil {
				t.Fatal(err)
			}
		}
		if i == 0 {
			okID = id
		}
		if i == 4 {
			errID = id
		}
	}
	return ownerID, okID, errID
}

func signedGET(t *testing.T, mux http.Handler, now time.Time, ownerID int64, path, lang string) string {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, map[string]any{
		"uid": ownerID, "sv": 1,
	}, now)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("%s: status %d", path, rec.Code)
	}
	return rec.Body.String()
}

func TestReadPagesMatchPythonGolden(t *testing.T) {
	pool := dbPool(t)
	g := loadReadGolden(t)
	now, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	ownerID, okID, errID := seedParityWorld(t, pool, now)
	mux := http.NewServeMux()
	Register(mux, pool, testGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	for _, c := range g.Cases {
		if c.Kind == "stay" {
			continue
		}
		path := c.Path
		switch c.Name {
		case "detail ok en":
			path = "/submissions/" + strconv.FormatInt(okID, 10) + "?lang=en"
		case "detail error en":
			path = "/submissions/" + strconv.FormatInt(errID, 10) + "?lang=en"
		}
		html := signedGET(t, mux, now, ownerID, path, c.Lang)
		var got []string
		switch c.Kind {
		case "list":
			got = submissionsVisibleLines(html)
		case "detail":
			got = submissionDetailVisibleLines(html)
		default:
			t.Fatalf("unknown kind %q", c.Kind)
		}
		for i := 0; i < len(got) || i < len(c.Lines); i++ {
			var have, want string
			if i < len(got) {
				have = got[i]
			}
			if i < len(c.Lines) {
				want = c.Lines[i]
			}
			if have != want {
				t.Fatalf("%s line %d: got %q want %q", c.Name, i, have, want)
			}
		}
	}
}
