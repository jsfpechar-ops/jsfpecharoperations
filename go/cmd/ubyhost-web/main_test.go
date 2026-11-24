package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

type healthTestPool struct{ err error }

func (p healthTestPool) QueryRow(context.Context, string, ...any) pgx.Row {
	return healthTestRow{err: p.err}
}

type healthTestRow struct{ err error }

func (r healthTestRow) Scan(dest ...any) error {
	if r.err != nil {
		return r.err
	}
	if len(dest) != 1 {
		return errors.New("unexpected health query result")
	}
	value, ok := dest[0].(*int)
	if !ok {
		return errors.New("unexpected health query destination")
	}
	*value = 1
	return nil
}

func TestHealthzDataDirectory(t *testing.T) {
	cases := []struct {
		name       string
		dirOK      bool
		dbOK       bool
		wantStatus int
	}{
		{name: "directory and database healthy", dirOK: true, dbOK: true, wantStatus: http.StatusOK},
		{name: "directory invalid", dirOK: false, dbOK: true, wantStatus: http.StatusServiceUnavailable},
		{name: "database unavailable", dirOK: true, dbOK: false, wantStatus: http.StatusServiceUnavailable},
		{name: "both unavailable", dirOK: false, dbOK: false, wantStatus: http.StatusServiceUnavailable},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			root := t.TempDir()
			dataDir := filepath.Join(root, "volume")
			if tc.dirOK {
				if err := os.Mkdir(dataDir, 0o700); err != nil {
					t.Fatal(err)
				}
			} else if err := os.WriteFile(dataDir, []byte("fixture"), 0o600); err != nil {
				t.Fatal(err)
			}

			var queryErr error
			if !tc.dbOK {
				queryErr = errors.New("database unavailable")
			}
			recorder := httptest.NewRecorder()
			request := httptest.NewRequest(http.MethodGet, "/healthz", nil)
			healthzAt(healthTestPool{err: queryErr}, dataDir).ServeHTTP(recorder, request)
			if recorder.Code != tc.wantStatus {
				t.Fatalf("status = %d, want %d", recorder.Code, tc.wantStatus)
			}
			var got health
			if err := json.NewDecoder(recorder.Body).Decode(&got); err != nil {
				t.Fatal(err)
			}
			if got.DataDirWritable != tc.dirOK || got.DatabaseOK != tc.dbOK {
				t.Fatalf("health flags = directory:%t database:%t, want directory:%t database:%t", got.DataDirWritable, got.DatabaseOK, tc.dirOK, tc.dbOK)
			}
			wantStatus := "ok"
			if !tc.dirOK || !tc.dbOK {
				wantStatus = "degraded"
			}
			if got.Status != wantStatus {
				t.Fatalf("health status = %q, want %q", got.Status, wantStatus)
			}
			if strings.Contains(recorder.Body.String(), dataDir) {
				t.Fatal("health response exposed the local data directory")
			}
			if tc.dirOK {
				entries, err := os.ReadDir(dataDir)
				if err != nil {
					t.Fatal(err)
				}
				if len(entries) != 0 {
					t.Fatalf("health probe left %d files in the data directory", len(entries))
				}
			}
		})
	}
}

func TestParseGoKindsPush(t *testing.T) {
	kinds, err := parseGoKinds("push")
	if err != nil || len(kinds) != 1 || kinds[0] != "push" {
		t.Fatalf("parseGoKinds(push) = %v, %v", kinds, err)
	}
	if goIntervals["push"] != 1 {
		t.Fatalf("push interval %d, want 1 minute", goIntervals["push"])
	}
}

func TestParseGoKindsDeadlines(t *testing.T) {
	kinds, err := parseGoKinds("submit, deadlines")
	if err != nil || len(kinds) != 2 || kinds[1] != "deadlines" {
		t.Fatalf("parseGoKinds(submit, deadlines) = %v, %v", kinds, err)
	}
	if goIntervals["deadlines"] != 30 {
		t.Fatalf("deadlines interval %d, want 30 minutes", goIntervals["deadlines"])
	}
}

func TestWrapSetsHardenHeaders(t *testing.T) {
	m := &metrics{counts: map[key]int64{}}
	h := m.wrap("/test", func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte("ok"))
	})
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/test", nil))
	for _, hv := range hardenHeaders {
		if got := rec.Header().Get(hv[0]); got != hv[1] {
			t.Errorf("%s = %q, want %q", hv[0], got, hv[1])
		}
	}
}

func TestWrapRouteHeaderWins(t *testing.T) {
	m := &metrics{counts: map[key]int64{}}
	h := m.wrap("/test", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Write([]byte("ok"))
	})
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/test", nil))
	if got := rec.Header().Get("Cache-Control"); got != "no-store" {
		t.Errorf("Cache-Control = %q, want no-store", got)
	}
	if got := rec.Header().Get("X-Content-Type-Options"); got != "nosniff" {
		t.Errorf("X-Content-Type-Options = %q, want nosniff", got)
	}
}

func TestCSPMatchesPython(t *testing.T) {
	src, err := os.ReadFile("../../../App/app/main.py")
	if err != nil {
		t.Fatalf("read main.py: %v", err)
	}
	const want = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
	if !strings.Contains(string(src), want) {
		t.Fatalf("App/app/main.py no longer contains the CSP prefix %q; update hardenHeaders too", want)
	}
}

func TestLaneKindsDisjoint(t *testing.T) {
	filing := filingHandlers(nil)
	for k := range jobHandlers(nil) {
		if _, ok := filing[k]; ok {
			t.Errorf("kind %q is in both register_jobs.go and register_filing.go", k)
		}
	}
}

func TestEveryHandlerHasInterval(t *testing.T) {
	handlers := goHandlers(nil)
	for k := range handlers {
		if goIntervals[k] <= 0 {
			t.Errorf("handler %q has no interval > 0", k)
		}
	}
	for k := range goIntervals {
		if _, ok := handlers[k]; !ok {
			t.Errorf("interval %q has no handler", k)
		}
	}
}

func TestRoutesRegisterOnce(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("a route pattern is registered twice: %v", r)
		}
	}()
	newMux(&metrics{counts: map[key]int64{}}, nil)
}

func TestDuplicateRouteFails(t *testing.T) {
	defer func() {
		if recover() == nil {
			t.Fatal("registering a pattern twice must panic")
		}
	}()
	mux := http.NewServeMux()
	mux.Handle("GET /twice", http.NotFoundHandler())
	mux.Handle("GET /twice", http.NotFoundHandler())
}

func TestDuplicateJobKindFails(t *testing.T) {
	defer func() {
		if recover() == nil {
			t.Fatal("registerJob with an existing kind must panic")
		}
	}()
	registerJob("push", 1, func(*pgxpool.Pool) jobs.Handler { return nil })
}
