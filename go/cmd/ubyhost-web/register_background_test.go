package main

import (
	"context"
	"errors"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// withTasks swaps the registered background tasks for the test.
func withTasks(t *testing.T, tasks []backgroundTask) {
	t.Helper()
	saved := backgroundTasks
	backgroundTasks = tasks
	t.Cleanup(func() { backgroundTasks = saved })
}

// newMux builds the routes only: no background setup runs.
func TestNewMuxStartsNoBackgroundTask(t *testing.T) {
	var setups atomic.Int32
	withTasks(t, nil)
	registerBackground("probe", func(*pgxpool.Pool) (func(context.Context), error) {
		setups.Add(1)
		return nil, nil
	})
	newMux(&metrics{counts: map[key]int64{}}, nil)
	if n := setups.Load(); n != 0 {
		t.Fatalf("newMux ran %d setups", n)
	}
}

// A setup error skips that task only; a nil function means switched off;
// a started task runs until the context ends and the wait group waits for it.
func TestStartBackgroundRunsJoinsAndSkips(t *testing.T) {
	withTasks(t, nil)
	var ran, stopped atomic.Bool
	registerBackground("broken", func(*pgxpool.Pool) (func(context.Context), error) {
		return nil, errors.New("bad configuration")
	})
	registerBackground("off", func(*pgxpool.Pool) (func(context.Context), error) { return nil, nil })
	registerBackground("worker", func(*pgxpool.Pool) (func(context.Context), error) {
		return func(ctx context.Context) {
			ran.Store(true)
			<-ctx.Done()
			time.Sleep(20 * time.Millisecond) // a task finishing its last step
			stopped.Store(true)
		}, nil
	})
	ctx, cancel := context.WithCancel(context.Background())
	var wg sync.WaitGroup
	startBackground(ctx, nil, &wg)
	deadline := time.Now().Add(2 * time.Second)
	for !ran.Load() && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	if !ran.Load() {
		t.Fatal("task did not start")
	}
	cancel()
	wg.Wait()
	if !stopped.Load() {
		t.Fatal("Wait returned before the task stopped")
	}
}

func TestDuplicateBackgroundTaskFails(t *testing.T) {
	withTasks(t, nil)
	setup := func(*pgxpool.Pool) (func(context.Context), error) { return nil, nil }
	registerBackground("twice", setup)
	defer func() {
		r := recover()
		if r == nil || !strings.Contains(r.(string), "registered twice") {
			t.Fatalf("got %v", r)
		}
	}()
	registerBackground("twice", setup)
}
