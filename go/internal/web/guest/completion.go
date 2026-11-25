package guest

import (
	"context"
	"log/slog"
)

// CompletionHooks is door_codes.on_registration_complete then claim.maybe_notify_completion (force=false).
// Nil means off (tests). Errors are logged by the adapter, never raised: the save must not fail.
type CompletionHooks interface {
	OnRegistrationComplete(ctx context.Context, reservationID int64)
	MaybeNotifyCompletion(ctx context.Context, reservationID, apartmentID int64, force bool) error
}

// runCompletion runs the completion pair in Python's order. It never returns an error.
func runCompletion(ctx context.Context, h CompletionHooks, apartmentID, reservationID int64) {
	if h == nil {
		return
	}
	h.OnRegistrationComplete(ctx, reservationID)
	if err := h.MaybeNotifyCompletion(ctx, reservationID, apartmentID, false); err != nil {
		slog.Error("completion notify failed", "reservation", reservationID, "error", err)
	}
}
