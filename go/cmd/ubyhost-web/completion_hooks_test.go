package main

import (
	"context"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
)

// The adapter must never panic and never fail a save when there is no database pool
// (the route is registered with a nil pool in tests and while the pool is down).
func TestCompletionHooksNilPoolNeverPanics(t *testing.T) {
	ctx := context.Background()
	h := completionHooks(nil)
	h.OnRegistrationComplete(ctx, 5)
	if err := h.MaybeNotifyCompletion(ctx, 5, 7, false); err != nil {
		t.Fatalf("nil pool: MaybeNotifyCompletion returned %v, want nil", err)
	}
}

// The door-code viewer used when the wiring cannot be built reports "no code".
func TestNoDoorCodesViewerReportsWithout(t *testing.T) {
	got, err := noDoorCodes{}.CompletionDoorCode(context.Background(), doorcodes.Reservation{}, doorcodes.Apartment{})
	if err != nil {
		t.Fatal(err)
	}
	if got.Action != doorcodes.CompletionWithout {
		t.Fatalf("action %q, want %q", got.Action, doorcodes.CompletionWithout)
	}
}
