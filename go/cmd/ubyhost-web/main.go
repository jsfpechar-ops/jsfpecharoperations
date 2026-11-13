// Command ubyhost-web is the Go service skeleton: /healthz, /metrics and a goose check at start.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

const version = "go-dev"

type key struct {
	route string
	code  int
}

// metrics counts requests per route pattern and status code.
type metrics struct {
	mu     sync.Mutex
	counts map[key]int64
}

type statusRecorder struct {
	http.ResponseWriter
	code int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.code = code
	r.ResponseWriter.WriteHeader(code)
}

// hardenHeaders are Python's _harden defaults plus the middleware's
// Cache-Control (App/app/main.py 181-218, 293-300). A route's own value wins.
var hardenHeaders = [][2]string{
	{"X-Content-Type-Options", "nosniff"},
	{"X-Frame-Options", "DENY"},
	{"Referrer-Policy", "strict-origin-when-cross-origin"},
	{"Permissions-Policy", "camera=(self), microphone=()"},
	{"Content-Security-Policy", "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://challenges.cloudflare.com"},
	{"Cache-Control", "no-store, private"},
}

func (m *metrics) wrap(route string, h http.HandlerFunc) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		for _, hv := range hardenHeaders {
			w.Header().Set(hv[0], hv[1])
		}
		rec := &statusRecorder{ResponseWriter: w, code: http.StatusOK}
		h(rec, r)
		m.mu.Lock()
		m.counts[key{route, rec.code}]++
		m.mu.Unlock()
	})
}

func (m *metrics) serve(w http.ResponseWriter, _ *http.Request) {
	m.mu.Lock()
	keys := make([]key, 0, len(m.counts))
	for k := range m.counts {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].route != keys[j].route {
			return keys[i].route < keys[j].route
		}
		return keys[i].code < keys[j].code
	})
	var b strings.Builder
	b.WriteString("# TYPE ubyhost_go_up gauge\nubyhost_go_up 1\n")
	b.WriteString("# TYPE ubyhost_go_http_requests_total counter\n")
	for _, k := range keys {
		fmt.Fprintf(&b, "ubyhost_go_http_requests_total{route=\"%s\",code=\"%d\"} %d\n", k.route, k.code, m.counts[k])
	}
	m.mu.Unlock()
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	_, _ = w.Write([]byte(b.String()))
}

type health struct {
	Status          string `json:"status"`
	Version         string `json:"version"`
	DataDirWritable bool   `json:"data_dir_writable"`
	DatabaseOK      bool   `json:"database_ok"`
}

func healthz(pool *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		var one int
		dbOK := pool.QueryRow(ctx, "SELECT 1").Scan(&one) == nil
		h := health{Status: "ok", Version: version, DataDirWritable: true, DatabaseOK: dbOK}
		code := http.StatusOK
		if !dbOK {
			h.Status = "degraded"
			code = http.StatusServiceUnavailable
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(code)
		_ = json.NewEncoder(w).Encode(h)
	}
}

func notFound(w http.ResponseWriter, _ *http.Request) {
	http.NotFound(w, nil)
}

func getenv(name, def string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return def
}

func main() {
	slog.SetDefault(slog.New(slog.NewTextHandler(os.Stdout, nil)))
	os.Exit(run())
}

// run returns the process exit code. The database URL is never logged.
func run() int {
	dbURL := os.Getenv("UBYHOST_DATABASE_URL")
	if dbURL == "" {
		slog.Error("UBYHOST_DATABASE_URL is required")
		return 1
	}
	redact := func(err error) string {
		return strings.ReplaceAll(err.Error(), dbURL, "<redacted>")
	}
	goKinds, err := parseGoKinds(os.Getenv("UBYHOST_GO_JOB_KINDS"))
	if err != nil {
		slog.Error(err.Error())
		return 1
	}
	addr := getenv("UBYHOST_GO_ADDR", "127.0.0.1:8081")
	migrations := getenv("UBYHOST_MIGRATIONS_DIR", "App/migrations_pg")

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := checkSchema(ctx, dbURL, migrations, redact); err != nil {
		return 1
	}

	pool, err := pgxpool.New(ctx, dbURL)
	if err != nil {
		slog.Error("database pool failed", "error", redact(err))
		return 1
	}
	defer pool.Close()
	jobCtx, cancelJobs := context.WithCancel(ctx)
	var jobsDone sync.WaitGroup
	defer func() { cancelJobs(); jobsDone.Wait() }()
	if len(goKinds) > 0 {
		jobsDone.Add(1)
		go func() {
			defer jobsDone.Done()
			jobs.Run(jobCtx, pool, goKinds, goHandlers(pool), goIntervals)
		}()
	}

	m := &metrics{counts: map[key]int64{}}
	mux := newMux(m, pool)

	srv := &http.Server{Addr: addr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	errCh := make(chan error, 1)
	go func() { errCh <- srv.ListenAndServe() }()
	slog.Info("listening", "addr", addr)

	select {
	case err := <-errCh:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("server failed", "error", err.Error())
			return 1
		}
		return 0
	case <-ctx.Done():
	}

	shutCtx, cancelShut := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancelShut()
	if err := srv.Shutdown(shutCtx); err != nil {
		slog.Error("shutdown failed", "error", err.Error())
		return 1
	}
	slog.Info("stopped")
	return 0
}

// newMux builds every route: health and metrics, the lane files, the
// per-thread files (registerRoutes), then the "/" catch-all.
func newMux(m *metrics, pool *pgxpool.Pool) *http.ServeMux {
	mux := http.NewServeMux()
	mux.Handle("GET /healthz", m.wrap("/healthz", healthz(pool)))
	mux.Handle("GET /metrics", m.wrap("/metrics", m.serve))
	registerWeb(mux, m, pool)
	registerFiling(mux, m, pool)
	for _, fn := range routeFuncs {
		fn(mux, m, pool)
	}
	mux.Handle("/", m.wrap("/", notFound))
	return mux
}

// goIntervals are the schedule intervals (minutes) that cap a retry backoff.
// Each lane owns its own map (register_jobs.go, register_filing.go); registerJob adds the rest.
var goIntervals = mergeIntervals(jobIntervals, filingIntervals)

// goHandlers maps each Go-owned job kind to its handler, merged from the
// lane files.
func goHandlers(pool *pgxpool.Pool) map[string]jobs.Handler {
	out := map[string]jobs.Handler{}
	for _, part := range []map[string]jobs.Handler{jobHandlers(pool), filingHandlers(pool)} {
		for k, h := range part {
			if _, dup := out[k]; dup {
				panic("duplicate job kind in lane files: " + k)
			}
			out[k] = h
		}
	}
	for k, f := range jobFactories {
		if _, dup := out[k]; dup {
			panic("duplicate job kind in lane files: " + k)
		}
		out[k] = f(pool)
	}
	return out
}

// mergeIntervals joins the lane interval maps; a duplicate kind is a
// programmer error.
func mergeIntervals(parts ...map[string]int) map[string]int {
	out := map[string]int{}
	for _, part := range parts {
		for k, v := range part {
			if _, dup := out[k]; dup {
				panic("duplicate job interval in lane files: " + k)
			}
			out[k] = v
		}
	}
	return out
}

// parseGoKinds reads UBYHOST_GO_JOB_KINDS. Only the kinds in goHandlers are supported.
func parseGoKinds(raw string) ([]string, error) {
	handlers := goHandlers(nil)
	var kinds []string
	for _, k := range strings.Split(raw, ",") {
		k = strings.TrimSpace(k)
		if k == "" {
			continue
		}
		if _, ok := handlers[k]; !ok {
			supported := make([]string, 0, len(handlers))
			for name := range handlers {
				supported = append(supported, name)
			}
			sort.Strings(supported)
			return nil, fmt.Errorf("UBYHOST_GO_JOB_KINDS has an unsupported kind: %s (supported: %s)", k, strings.Join(supported, ", "))
		}
		kinds = append(kinds, k)
	}
	return kinds, nil
}
