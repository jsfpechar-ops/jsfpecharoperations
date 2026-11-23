package retention

import (
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

func TestWorkspaceDeletionReminderStage(t *testing.T) {
	t.Parallel()
	if mail.DeletionWeekBefore != "week_before" {
		t.Fatalf("stage = %q, want week_before", mail.DeletionWeekBefore)
	}
}
