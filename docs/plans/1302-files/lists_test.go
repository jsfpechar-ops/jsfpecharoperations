package properties

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// listCase is a pageCase of lists_cases.json; Go 501 marks a branch this
// package does not serve yet (Python's page is still in the golden).
type listCase struct {
	pageCase
	Go int `json:"go"`
}

// seedExtra adds the tables seedWorld does not know: settings and alert.
func seedExtra(t *testing.T, pool *pgxpool.Pool, seed map[string][]map[string]any) {
	t.Helper()
	for _, table := range []string{"settings", "alert"} {
		for _, row := range seed[table] {
			var cols, marks []string
			var args []any
			for col, v := range row {
				cols = append(cols, col)
				args = append(args, sqlValue(v))
				marks = append(marks, fmt.Sprintf("$%d", len(args)))
			}
			q := "INSERT INTO " + table + " (" + strings.Join(cols, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
			if _, err := pool.Exec(context.Background(), q, args...); err != nil {
				t.Fatalf("seed %s: %v", table, err)
			}
		}
	}
}

func TestListsMatchPython(t *testing.T) {
	pool := testPool(t)
	var c casesFile
	readJSON(t, "lists_cases.json", &c)
	var raw struct {
		Cases []listCase `json:"cases"`
	}
	readJSON(t, "lists_cases.json", &raw)
	var golden []pageGolden
	readJSON(t, "lists_golden.json", &golden)
	if len(golden) != len(raw.Cases) || len(golden) < 15 {
		t.Fatalf("golden has %d cases, cases file %d", len(golden), len(raw.Cases))
	}
	seedWorld(t, pool, &c)
	seedExtra(t, pool, c.Seed)
	mux := http.NewServeMux()
	RegisterLists(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, testEnv, testClock)
	notPortedSeen := 0
	for i, tc := range raw.Cases {
		req := httptest.NewRequest(http.MethodGet, tc.Path, nil)
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: tc.Lang})
		if tc.User != 0 {
			payload := map[string]any{"uid": tc.User, "sv": int64(1), "iat": testNow.Unix()}
			if tc.As != 0 {
				payload["as"] = tc.As
				payload["ast"] = testNow.Unix()
			}
			req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		want := golden[i]
		if tc.Go != 0 {
			notPortedSeen++
			if rec.Code != tc.Go || want.Status != http.StatusOK || want.Name != tc.Name {
				t.Errorf("case %s: Go code %d (want %d), Python status %d", tc.Name, rec.Code, tc.Go, want.Status)
			}
			continue
		}
		body := ""
		if rec.Code == http.StatusOK {
			body = rec.Body.String()
		}
		got := pageGolden{Name: tc.Name, Status: rec.Code, Location: rec.Header().Get("Location"), Items: extractItems(body)}
		if m := titleRE.FindStringSubmatch(body); m != nil {
			got.Title = squash(m[1])
		}
		if want.Items == nil {
			want.Items = []string{}
		}
		if got.Name != want.Name || got.Status != want.Status || got.Location != want.Location || got.Title != want.Title {
			g, _ := json.Marshal(pageGolden{got.Name, got.Status, got.Location, got.Title, nil})
			w, _ := json.Marshal(pageGolden{want.Name, want.Status, want.Location, want.Title, nil})
			t.Errorf("case %d differs\n got: %s\nwant: %s", i, g, w)
			continue
		}
		if !reflect.DeepEqual(got.Items, want.Items) {
			n := 0
			for n < len(got.Items) && n < len(want.Items) && got.Items[n] == want.Items[n] {
				n++
			}
			lo := max(0, n-3)
			t.Errorf("case %s: items differ at %d (go %d, py %d)\n go: %q\n py: %q", tc.Name, n, len(got.Items), len(want.Items),
				got.Items[lo:min(len(got.Items), n+4)], want.Items[lo:min(len(want.Items), n+4)])
		}
	}
	if notPortedSeen != 3 {
		t.Errorf("%d not-ported cases, want 3", notPortedSeen)
	}
}

func TestListsRegisterDoesNotTouchThePool(t *testing.T) {
	mux := http.NewServeMux()
	RegisterLists(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, nil, testEnv, testClock)
	for _, path := range []string{"/entities", "/apartments"} {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, path, nil))
		if rec.Code != http.StatusMethodNotAllowed {
			t.Errorf("POST %s: code %d, want 405", path, rec.Code)
		}
	}
}

func TestListHelpers(t *testing.T) {
	for v, want := range map[string]bool{"": false, "12": true, "abc": false, "1a": false, "١": true, "²": true} {
		if editAsked(v) != want {
			t.Errorf("editAsked(%q) = %v", v, !want)
		}
	}
	for v, want := range map[string]string{"2026-03-05T10:00:00+00:00": "05.03.2026", "2026-03-05": "05.03.2026", "soon": "soon", "": ""} {
		if got := dateCZ(v); got != want {
			t.Errorf("dateCZ(%q) = %q", v, got)
		}
	}
	for _, tc := range []struct {
		house, zip, obec string
		want             bool
	}{{"5", "110 00", "Praha", true}, {"5", "1100", "Praha", false}, {" ", "11000", "Praha", false}, {"5", "11000", "", false}} {
		if got := addressComplete(tc.house, tc.zip, tc.obec); got != tc.want {
			t.Errorf("addressComplete(%q, %q, %q) = %v", tc.house, tc.zip, tc.obec, got)
		}
	}
}
