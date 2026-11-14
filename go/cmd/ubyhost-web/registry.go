package main

// Per-thread registration. A thread that ports one job or one web area adds
// its own file, register_job_<kind>.go or register_web_<area>.go, whose
// init() calls registerJob or registerRoutes. No thread edits main.go, this
// file or another thread's file. The handler factory and the route function
// must not use the pool while they build: parseGoKinds and the tests call
// them with a nil pool.

import (
	"context"
	"log/slog"
	"net/http"
	"sync"

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

// backgroundTask is one task added with registerBackground.
type backgroundTask struct {
	name  string
	setup func(*pgxpool.Pool) (func(context.Context), error)
}

// backgroundTasks holds the tasks added with registerBackground, in init order.
var backgroundTasks []backgroundTask

// registerBackground adds a long-running background task (brief 1452). Call
// it from init(). run() calls setup once per process, after the schema check
// and after the pool exists; newMux never does, so tests that build the mux
// start nothing. setup must not block. It returns the function to run, nil
// when the task is switched off, or an error: the error is logged and the
// service keeps serving without the task (it serves live pages). The run
// function gets a context that is cancelled on SIGINT or SIGTERM, and run()
// waits for it to return before it closes the pool. A name registered twice
// panics at start.
func registerBackground(name string, setup func(pool *pgxpool.Pool) (func(ctx context.Context), error)) {
	if name == "" || setup == nil {
		panic("registerBackground needs a name and a setup function: " + name)
	}
	for _, t := range backgroundTasks {
		if t.name == name {
			panic("background task registered twice: " + name)
		}
	}
	backgroundTasks = append(backgroundTasks, backgroundTask{name: name, setup: setup})
}

// startBackground runs every setup in order and starts each returned
// function in its own goroutine, counted on wg.
func startBackground(ctx context.Context, pool *pgxpool.Pool, wg *sync.WaitGroup) {
	for _, t := range backgroundTasks {
		run, err := t.setup(pool)
		if err != nil {
			slog.Error("background task not started", "task", t.name, "error", err.Error())
			continue
		}
		if run == nil {
			continue
		}
		wg.Add(1)
		go func() {
			defer wg.Done()
			run(ctx)
		}()
		slog.Info("background task started", "task", t.name)
	}
}
