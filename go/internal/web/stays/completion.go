package stays

import "context"

// CompletionHooks is door_codes.on_registration_complete then claim.maybe_notify_completion (force=false).
// Nil means off (tests). The adapter logs its errors; the save must not fail.
type CompletionHooks interface {
	OnRegistrationComplete(ctx context.Context, reservationID int64)
	MaybeNotifyCompletion(ctx context.Context, reservationID, apartmentID int64, force bool) error
}
