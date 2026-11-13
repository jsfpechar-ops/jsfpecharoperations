package main

// Per-thread registration. A thread that ports one job or one web area adds
// its own file, register_job_<kind>.go or register_web_<area>.go, whose
// init() calls registerJob or registerRoutes. No thread edits main.go, this
// file or another thread's file. The handler factory and the route function
// must not use the pool while they build: parseGoKinds and the tests call
// them with a nil pool.

import (
	"net/http"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

// jobFactories holds the job kinds added with registerJob.
var jobFactories = map[string]func(*pgxpool.Pool) jobs.Handler{}

// routeFuncs holds the route groups added with registerRoutes, in init order.
var routeFuncs []func(*http.ServeMux, *metrics, *pgxpool.Pool)

// registerJob adds a Go job kind and its schedule interval in minutes. Call
// it from init(). A kind registered twice, here or in the lane files,
// panics at start.
func registerJob(kind string, minutes int, h func(*pgxpool.Pool) jobs.Handler) {
	if kind == "" || minutes <= 0 || h == nil {
		panic("registerJob needs a kind, minutes > 0 and a handler: " + kind)
	}
	if _, dup := goIntervals[kind]; dup {
		panic("job kind registered twice: " + kind)
	}
	goIntervals[kind] = minutes
	jobFactories[kind] = h
}

// registerRoutes adds a group of web routes. Call it from init(). A route
// pattern registered twice panics in http.ServeMux when newMux runs.
func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {
	if fn == nil {
		panic("registerRoutes needs a function")
	}
	routeFuncs = append(routeFuncs, fn)
}
