package main

// Thread 1240 (stay-fee mail) owns this file. The stay_fee_mail job seals the
// due stay-fee periods and queues the host reports (stayfeemail.Handler).
// stayFeeRenderer is nil until brief 1243 plugs in the PDF renderer; until
// then the handler returns stayfeemail.ErrNoRenderer before it reads or
// writes anything, so the kind in UBYHOST_GO_JOB_KINDS only fails the job.

import (
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeemail"
)

// stayFeeRenderer draws the hlášení PDF. Brief 1243 sets it.
var stayFeeRenderer stayfee.PDFRenderer

func init() {
	registerJob("stay_fee_mail", 24*60, stayFeeMailJob)
}

// stayFeeMailJob builds the handler without touching the pool.
func stayFeeMailJob(pool *pgxpool.Pool) jobs.Handler {
	return stayfeemail.Handler(pool, stayfeemail.Deps{Getenv: os.Getenv, Now: time.Now, Renderer: stayFeeRenderer})
}
