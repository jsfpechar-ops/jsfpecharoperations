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

// The fallback viewer holds the receipt for a ttlock apartment (door codes in use), so the
// later release path sends it with the code instead of without one.
func TestNoDoorCodesViewerHoldsTTLockApartment(t *testing.T) {
	apt := doorcodes.Apartment{LockProvider: "ttlock"}
	got, err := noDoorCodes{}.CompletionDoorCode(context.Background(), doorcodes.Reservation{}, apt)
	if err != nil {
		t.Fatal(err)
	}
	if got.Action != doorcodes.CompletionHold {
		t.Fatalf("action %q, want %q", got.Action, doorcodes.CompletionHold)
	}
}

// The fallback viewer sends "without" only for an apartment that does not use door codes.
func TestNoDoorCodesViewerReportsWithoutForNonTTLock(t *testing.T) {
	for _, provider := range []string{"", "none", "manual"} {
		apt := doorcodes.Apartment{LockProvider: provider}
		got, err := noDoorCodes{}.CompletionDoorCode(context.Background(), doorcodes.Reservation{}, apt)
		if err != nil {
			t.Fatal(err)
		}
		if got.Action != doorcodes.CompletionWithout {
			t.Fatalf("provider %q: action %q, want %q", provider, got.Action, doorcodes.CompletionWithout)
		}
	}
}
