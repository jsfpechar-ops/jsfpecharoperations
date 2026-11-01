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

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/schema"
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

func (m *metrics) wrap(route string, h http.HandlerFunc) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
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

	startCtx, cancelStart := context.WithTimeout(ctx, 10*time.Second)
	conn, err := pgx.Connect(startCtx, dbURL)
	if err != nil {
		cancelStart()
		slog.Error("database connect failed", "error", redact(err))
		return 1
	}
	pending, err := schema.Pending(startCtx, conn, migrations)
	_ = conn.Close(startCtx)
	cancelStart()
	if err != nil {
		slog.Error("goose check failed", "error", redact(err))
		return 1
	}
	if len(pending) > 0 {
		slog.Error(fmt.Sprintf("goose files pending: %v", pending))
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
	mux := http.NewServeMux()
	mux.Handle("GET /healthz", m.wrap("/healthz", healthz(pool)))
	mux.Handle("GET /metrics", m.wrap("/metrics", m.serve))
	mux.Handle("/", m.wrap("/", notFound))

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

// goIntervals are the schedule intervals (minutes) that cap a retry backoff.
var goIntervals = map[string]int{"billing_snapshot": 24 * 60}

// goHandlers maps each Go-owned job kind to its handler.
func goHandlers(pool *pgxpool.Pool) map[string]jobs.Handler {
	return map[string]jobs.Handler{
		"billing_snapshot": func(ctx context.Context) (int, error) {
			return billing.WriteMonthSnapshot(ctx, pool, time.Now().UTC().Format("2006-01"), jobs.Now(0))
		},
	}
}

// parseGoKinds reads UBYHOST_GO_JOB_KINDS. Only billing_snapshot is supported.
func parseGoKinds(raw string) ([]string, error) {
	var kinds []string
	for _, k := range strings.Split(raw, ",") {
		k = strings.TrimSpace(k)
		if k == "" {
			continue
		}
		if k != "billing_snapshot" {
			return nil, fmt.Errorf("UBYHOST_GO_JOB_KINDS has an unsupported kind: %s", k)
		}
		kinds = append(kinds, k)
	}
	return kinds, nil
}
