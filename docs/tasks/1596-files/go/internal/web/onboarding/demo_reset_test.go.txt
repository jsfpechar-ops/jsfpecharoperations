package onboarding

// Tests of POST /demo/reset (brief 1596). The golden cases are what
// App/scripts/go_demo_reset_golden.py recorded from the real Python route.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

type demoResetGolden struct {
	CSRFNonce string                    `json:"csrf_nonce"`
	Seed      []onboardingPageSeedTable `json:"seed"`
	Photos    []string                  `json:"photos"`
	Cases     []struct {
		Name      string `json:"name"`
		User      int64  `json:"user"`
		Workspace int64  `json:"workspace"`
		Lang      string `json:"lang"`
		CSRF      bool   `json:"csrf"`
		Status    int    `json:"status"`
		Location  string `json:"location"`
	} `json:"cases"`
	Final      map[string][]any `json:"final"`
	PhotosLeft []string         `json:"photos_left"`
	Audit      []struct {
		Action       string `json:"action"`
		Detail       string `json:"detail"`
		Actor        string `json:"actor"`
		Owner        int64  `json:"owner_user_id"`
		ActorID      int64  `json:"actor_user_id"`
		Impersonator *int64 `json:"impersonator_user_id"`
	} `json:"audit"`
}

func loadDemoResetGolden(t *testing.T) demoResetGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/demo_reset_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	var g demoResetGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 7 || len(g.Final) < 10 {
		t.Fatal("demo reset golden file is too small")
	}
	return g
}

// demoResetSetup seeds PostgreSQL and a data directory with the golden photos.
func demoResetSetup(t *testing.T, g demoResetGolden) (*pgxpool.Pool, func(string) string, string) {
	t.Helper()
	pool := testPool(t)
	dataDir := t.TempDir()
	env := map[string]string{"UBYHOST_SECRET_KEY": onboardingPageSecret, "UBYHOST_DATA_DIR": dataDir}
	getenv := func(k string) string { return env[k] }
	onboardingPageSeed(t, pool, onboardingPageGolden{Seed: g.Seed}, getenv)
	photos := filepath.Join(dataDir, "passport_photos")
	if err := os.MkdirAll(photos, 0o700); err != nil {
		t.Fatal(err)
	}
	for _, name := range g.Photos {
		if err := os.WriteFile(filepath.Join(photos, name), []byte("golden"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	return pool, getenv, dataDir
}

// demoResetPost sends POST /demo/reset as user (0: signed out), previewing
// workspace when it is not 0, with a valid CSRF token when csrf is true.
func demoResetPost(t *testing.T, h http.Handler, nonce string, user, workspace int64, lang string, csrf bool) *httptest.ResponseRecorder {
	t.Helper()
	form := url.Values{}
	if csrf {
		sum := sha256.Sum256([]byte(nonce))
		token, err := secure.NewTimedSerializer(onboardingPageSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
		if err != nil {
			t.Fatal(err)
		}
		form.Set("_csrf", token)
	}
	req := httptest.NewRequest(http.MethodPost, "/demo/reset", strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: nonce})
	if user != 0 {
		payload := map[string]any{"uid": user, "sv": 1}
		if workspace != 0 {
			payload["as"] = workspace
			payload["ast"] = testNow.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(onboardingPageSecret, payload, testNow)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// demoResetState is the ids left in the golden tables, as JSON values.
func demoResetState(t *testing.T, pool *pgxpool.Pool, tables map[string][]any) map[string][]any {
	t.Helper()
	cols := map[string]string{"apartment_slug": "slug", "cleaning_property": "apartment_id"}
	out := map[string][]any{}
	for table := range tables {
		col := cols[table]
		if col == "" {
			col = "id"
		}
		rows, err := pool.Query(context.Background(), fmt.Sprintf("SELECT %s::text FROM %s ORDER BY %s", col, table, col))
		if err != nil {
			t.Fatal(err)
		}
		var vals []any
		for rows.Next() {
			var v string
			if err := rows.Scan(&v); err != nil {
				t.Fatal(err)
			}
			vals = append(vals, v)
		}
		rows.Close()
		out[table] = vals
	}
	return out
}

// demoResetText turns golden values (json.Number or string) into text.
func demoResetText(in map[string][]any) map[string][]any {
	out := map[string][]any{}
	for k, vs := range in {
		var vals []any
		for _, v := range vs {
			vals = append(vals, fmt.Sprint(v))
		}
		out[k] = vals
	}
	return out
}

func demoResetPhotos(t *testing.T, dataDir string) []string {
	t.Helper()
	entries, err := os.ReadDir(filepath.Join(dataDir, "passport_photos"))
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	for _, e := range entries {
		names = append(names, e.Name())
	}
	sort.Strings(names)
	return names
}

// TestDemoResetMatchesPython sends the golden requests in order and compares
// each answer, then the rows, photo files and audit rows left.
func TestDemoResetMatchesPython(t *testing.T) {
	g := loadDemoResetGolden(t)
	pool, getenv, dataDir := demoResetSetup(t, g)
	h := DemoResetHandler(pool, getenv, func() time.Time { return testNow })
	for _, c := range g.Cases {
		rec := demoResetPost(t, h, g.CSRFNonce, c.User, c.Workspace, c.Lang, c.CSRF)
		if rec.Code != c.Status || rec.Header().Get("Location") != c.Location {
			t.Errorf("%s: %d %q, Python %d %q", c.Name, rec.Code, rec.Header().Get("Location"), c.Status, c.Location)
		}
	}
	if got, want := demoResetState(t, pool, g.Final), demoResetText(g.Final); !reflect.DeepEqual(got, want) {
		t.Errorf("rows left:\n go %v\n py %v", got, want)
	}
	if got := demoResetPhotos(t, dataDir); !reflect.DeepEqual(got, g.PhotosLeft) {
		t.Errorf("photos left %v, Python %v", got, g.PhotosLeft)
	}
	rows, err := pool.Query(context.Background(), `SELECT action, detail, actor, owner_user_id, actor_user_id, impersonator_user_id, at
FROM audit WHERE action LIKE 'demo%' ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	i := 0
	for rows.Next() {
		var action, detail, actor, at string
		var owner, actorID int64
		var impersonator *int64
		if err := rows.Scan(&action, &detail, &actor, &owner, &actorID, &impersonator, &at); err != nil {
			t.Fatal(err)
		}
		if i >= len(g.Audit) {
			t.Fatalf("extra audit row %s", action)
		}
		w := g.Audit[i]
		if action != w.Action || detail != w.Detail || actor != w.Actor || owner != w.Owner || actorID != w.ActorID ||
			(impersonator == nil) != (w.Impersonator == nil) || (impersonator != nil && *impersonator != *w.Impersonator) {
			t.Errorf("audit %d: %s %q %s %d %d %v, Python %+v", i, action, detail, actor, owner, actorID, impersonator, w)
		}
		if at != stamp(testNow) {
			t.Errorf("audit %d at %q, want %q", i, at, stamp(testNow))
		}
		i++
	}
	if i != len(g.Audit) {
		t.Errorf("%d audit rows, Python %d", i, len(g.Audit))
	}
}

// TestDemoResetStopsBeforeDeleting: when the photo files cannot be checked
// (no data directory, or passport_photos is not a directory) the answer is a
// 500 and no row and no file is deleted.
func TestDemoResetStopsBeforeDeleting(t *testing.T) {
	g := loadDemoResetGolden(t)
	for _, mode := range []string{"no data dir", "photos not a directory"} {
		t.Run(mode, func(t *testing.T) {
			pool, getenv, dataDir := demoResetSetup(t, g)
			before := demoResetState(t, pool, g.Final)
			env := getenv
			if mode == "no data dir" {
				env = func(k string) string {
					if k == "UBYHOST_DATA_DIR" {
						return ""
					}
					return getenv(k)
				}
			} else {
				photos := filepath.Join(dataDir, "passport_photos")
				if err := os.RemoveAll(photos); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(photos, []byte("not a directory"), 0o600); err != nil {
					t.Fatal(err)
				}
			}
			rec := demoResetPost(t, DemoResetHandler(pool, env, func() time.Time { return testNow }), g.CSRFNonce, 2, 0, "en", true)
			if rec.Code != http.StatusInternalServerError {
				t.Fatalf("status %d, want 500", rec.Code)
			}
			if after := demoResetState(t, pool, g.Final); !reflect.DeepEqual(after, before) {
				t.Fatalf("rows changed:\n before %v\n after %v", before, after)
			}
			if mode == "no data dir" && len(demoResetPhotos(t, dataDir)) != len(g.Photos) {
				t.Fatal("a photo was deleted")
			}
		})
	}
}

// TestDemoResetRollsBack: a delete that the database refuses (another
// owner's property still points at the demo entity) is a 500 and leaves
// every row, as one transaction.
func TestDemoResetRollsBack(t *testing.T) {
	g := loadDemoResetGolden(t)
	pool, getenv, _ := demoResetSetup(t, g)
	if _, err := pool.Exec(context.Background(), `UPDATE apartment SET legal_entity_id = 21 WHERE id = 302`); err != nil {
		t.Fatal(err)
	}
	before := demoResetState(t, pool, g.Final)
	rec := demoResetPost(t, DemoResetHandler(pool, getenv, func() time.Time { return testNow }), g.CSRFNonce, 2, 0, "en", true)
	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("status %d, want 500", rec.Code)
	}
	if after := demoResetState(t, pool, g.Final); !reflect.DeepEqual(after, before) {
		t.Fatalf("rows changed:\n before %v\n after %v", before, after)
	}
	var n int
	if err := pool.QueryRow(context.Background(), `SELECT COUNT(*) FROM audit WHERE action = 'demo_cleared'`).Scan(&n); err != nil || n != 0 {
		t.Fatalf("%d audit rows (%v), want 0", n, err)
	}
}
