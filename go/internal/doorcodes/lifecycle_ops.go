package doorcodes

import "context"

// HandleCancellations is the _handle_cancellations step, exported for the Reconciler's phase list.
func (l *Lifecycle) HandleCancellations(ctx context.Context, nowISO string) error {
	return l.handleCancellations(ctx, nowISO)
}

// HandleMoves is the _handle_moves step, exported for the Reconciler's phase list.
func (l *Lifecycle) HandleMoves(ctx context.Context, nowISO string) error {
	return l.handleMoves(ctx, nowISO)
}
