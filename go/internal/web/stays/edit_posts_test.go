package stays

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

type editPostsCase struct {
	Name     string            `json:"name"`
	Method   string            `json:"method"`
	Path     string            `json:"path"`
	Fields   map[string]string `json:"fields"`
	Headers  map[string]string `json:"headers"`
	OwnerID  int64             `json:"owner_id"`
	Status   int               `json:"status"`
	Location string            `json:"location_prefix"`
	Body     string            `json:"body"`
}

type editPostsGolden struct {
	Now   string          `json:"now"`
	Cases []editPostsCase `json:"cases"`
}

func loadEditPostsGolden(t *testing.T) editPostsGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/edit_posts_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g editPostsGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func editCSRFPost(t *testing.T, h http.Handler, at time.Time, path, nonce string, ownerID int64, fields map[string]string, hdr map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	form := url.Values{}
	for k, v := range fields {
		form.Set(k, v)
	}
	sum := sha256.Sum256([]byte(nonce))
	token, err := secure.NewTimedSerializer(createTestSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, at)
	if err != nil {
		t.Fatal(err)
	}
	form.Set("_csrf", token)
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: nonce})
	if ownerID != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(createTestSecret, map[string]any{
			"uid": ownerID, "sv": 1,
		}, at)})
	}
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestRegisterEditPostsRoutes(t *testing.T) {
	mux := http.NewServeMux()
	RegisterEditPosts(mux, nil, createGetenv, func() time.Time { return fixedToday() },
		func(_ string, h http.HandlerFunc) http.Handler { return h }, nil)
	for _, p := range []string{
		"/reservations/1/quick-edit",
		"/reservations/1/remove-empty-slot",
		"/reservations/1/archive",
		"/reservations/1/unarchive",
		"/reservations/1/delete-demo",
	} {
		req := httptest.NewRequest(http.MethodPost, p, nil)
		if h, pattern := mux.Handler(req); h == nil || pattern == "" {
			t.Fatalf("no handler for POST %s", p)
		}
	}
}

func TestQuickEditUnknownStayJSON404(t *testing.T) {
	if os.Getenv("UBYHOST_TEST_DATABASE_URL") == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL not set")
	}
	pool := dbPool(t)
	ctx := t.Context()
	now := fixedToday()
	stamp := isoStamp(now)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('qe-miss', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, now)
	mux := http.NewServeMux()
	RegisterEditPosts(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h }, nil)
	rec := editCSRFPost(t, mux, now, "/reservations/99999/quick-edit", "n1", ownerID, map[string]string{"summary": "x"}, nil)
	if rec.Code != http.StatusNotFound || !strings.Contains(rec.Body.String(), `"ok":false`) {
		t.Fatalf("got %d %q", rec.Code, rec.Body.String())
	}
}

func TestEditPostsGoldenParity(t *testing.T) {
	if os.Getenv("UBYHOST_TEST_DATABASE_URL") == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL not set")
	}
	g := loadEditPostsGolden(t)
	pool := dbPool(t)
	editSeedGolden(t, pool, g)
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	mux := http.NewServeMux()
	RegisterEditPosts(mux, pool, createGetenv, func() time.Time { return at },
		func(_ string, h http.HandlerFunc) http.Handler { return h }, nil)
	for _, c := range g.Cases {
		rec := editCSRFPost(t, mux, at, c.Path, "edit-golden", c.OwnerID, c.Fields, c.Headers)
		if rec.Code != c.Status {
			t.Fatalf("%s: status %d want %d", c.Name, rec.Code, c.Status)
		}
		if c.Body != "" && strings.TrimSpace(rec.Body.String()) != c.Body {
			t.Fatalf("%s: body %q", c.Name, rec.Body.String())
		}
		if c.Location != "" {
			loc := rec.Header().Get("Location")
			if !strings.HasPrefix(loc, c.Location) {
				t.Fatalf("%s: location %q want prefix %q", c.Name, loc, c.Location)
			}
		}
	}
}

func editSeedGolden(t *testing.T, pool *pgxpool.Pool, g editPostsGolden) {
	t.Helper()
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	ctx := t.Context()
	stamp := at.UTC().Format("2006-01-02T15:04:05") + "+00:00"
	ownerID := int64(9001)
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, role, active, session_version, created_at, email)
		VALUES ($1,'edit-posts-golden', 'x', 'host', 1, 1, $2, 'edit-posts@example.test')`, ownerID, stamp); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, at)
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at) VALUES ($1,'Entity',$2) RETURNING id`,
		ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Flat','tok-edit','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	for i, spec := range []struct {
		id     int64
		source string
	}{
		{801, "manual"},
		{802, "demo"},
	} {
		uid := fmt.Sprintf("uid-%d", i)
		if _, err := pool.Exec(ctx, `INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, declared_guests, created_at, updated_at)
			VALUES ($1,$2,$3,$4,'2026-07-01','2026-07-03','active',2,$5,$5)`,
			spec.id, aptID, spec.source, uid, stamp); err != nil {
			t.Fatal(err)
		}
	}
}
