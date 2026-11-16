package main

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// fakeCleaningPass replaces cleaningQueuePass and reports each call on the returned channel.
func fakeCleaningPass(t *testing.T, err error) chan struct{} {
	t.Helper()
	called := make(chan struct{}, 4)
	prev := cleaningQueuePass
	cleaningQueuePass = func(ctx context.Context, pool *pgxpool.Pool) error {
		called <- struct{}{}
		return err
	}
	t.Cleanup(func() { cleaningQueuePass = prev })
	return called
}

func passRan(called chan struct{}, d time.Duration) bool {
	select {
	case <-called:
		return true
	case <-time.After(d):
		return false
	}
}

func TestCleaningKickGates(t *testing.T) {
	cases := []struct {
		name, on, kinds string
		want            bool
	}{
		{"door codes off", "", "door_codes", false},
		{"door_codes not a Go job", "1", "mail", false},
		{"owned by Go", "1", "door_codes", true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			called := fakeCleaningPass(t, nil)
			t.Setenv("UBYHOST_DOOR_CODES", c.on)
			t.Setenv("UBYHOST_GO_JOB_KINDS", c.kinds)
			cleaningKick(nil)
			if got := passRan(called, 500*time.Millisecond); got != c.want {
				t.Fatalf("pass ran = %v, want %v", got, c.want)
			}
		})
	}
}

func TestCleaningKickWhileRunning(t *testing.T) {
	t.Setenv("UBYHOST_DOOR_CODES", "1")
	t.Setenv("UBYHOST_GO_JOB_KINDS", "door_codes")
	called := fakeCleaningPass(t, nil)
	cleaningKickMu.Lock()
	defer cleaningKickMu.Unlock()
	cleaningKick(nil)
	if passRan(called, 500*time.Millisecond) {
		t.Fatal("kick ran a pass while another pass held the lock")
	}
}

func TestCleaningKickFailingPass(t *testing.T) {
	t.Setenv("UBYHOST_DOOR_CODES", "1")
	t.Setenv("UBYHOST_GO_JOB_KINDS", "door_codes")
	called := fakeCleaningPass(t, errors.New("lock offline"))
	cleaningKick(nil)
	if !passRan(called, 2*time.Second) {
		t.Fatal("pass did not run")
	}
}
