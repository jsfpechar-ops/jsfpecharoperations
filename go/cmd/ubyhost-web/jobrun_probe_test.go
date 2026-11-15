package main

// Runs the Go stay_fee_mail handler once against the database in GO_JOBRUN_DB
// with a fixed clock (GO_JOBRUN_NOW, RFC 3339) and writes the count to
// GO_JOBRUN_OUT. Used by scripts/e2e/diff_harness.py to compare the job with
// Python's on the same data. Skips when GO_JOBRUN_DB is unset.

import (
	"context"
	"os"
	"strconv"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeemail"
)

func TestJobRunProbe(t *testing.T) {
	dsn := os.Getenv("GO_JOBRUN_DB")
	if dsn == "" {
		t.Skip("GO_JOBRUN_DB not set")
	}
	now, err := time.Parse(time.RFC3339, os.Getenv("GO_JOBRUN_NOW"))
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	h := stayfeemail.Handler(pool, stayfeemail.Deps{Getenv: os.Getenv, Now: func() time.Time { return now }, Renderer: stayFeeRenderer})
	n, err := h(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(os.Getenv("GO_JOBRUN_OUT"), []byte(strconv.Itoa(n)), 0o644); err != nil {
		t.Fatal(err)
	}
}
