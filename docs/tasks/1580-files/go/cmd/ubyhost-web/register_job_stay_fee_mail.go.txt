package main

// Thread 1240 (stay-fee mail) owns this file. The stay_fee_mail job seals the
// due stay-fee periods and queues the host reports (stayfeemail.Handler).
// stayFeeRenderer is the hlášení PDF renderer (brief 1580, which replaces the
// never-written brief 1243). Registering the handler does not switch the job
// on: which process runs the kind is decided by UBYHOST_GO_JOB_KINDS and the
// queue kinds, and the owner steps for that belong to brief 1589. Briefs 1585
// and 1586 (finalize, confirm-ready) read this same variable.

import (
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeemail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeepdf"
)

// stayFeeRenderer draws the hlášení PDF (go/internal/stayfeepdf, brief 1580).
var stayFeeRenderer stayfee.PDFRenderer = stayfeepdf.Renderer{}

func init() {
	registerJob("stay_fee_mail", 24*60, stayFeeMailJob)
}

// stayFeeMailJob builds the handler without touching the pool.
func stayFeeMailJob(pool *pgxpool.Pool) jobs.Handler {
	return stayfeemail.Handler(pool, stayfeemail.Deps{Getenv: os.Getenv, Now: time.Now, Renderer: stayFeeRenderer})
}
