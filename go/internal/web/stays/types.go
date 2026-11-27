package stays

import (
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

// Guest is one live guest row for the stays list (first_name/surname/is_lead).
type Guest struct {
	FirstName, Surname string
	IsLead             bool
}

// Progress is reporting.reservation_progress for one stay row.
type Progress struct {
	Filled             int
	Expected           *int
	Incomplete         int
	ReportedCount      int
	ReportableCount    int
	ScheduledSendLabel string
	Status             string
	Guests             []Guest
	NotRegistered      *int
	HasCell            bool
	Cell               layout.DeadlineCell
	Anchor             time.Time
	HasAnchor          bool
	Unreadable         bool
}

// Controls is reporting.send_controls (subset used on the list page).
type Controls struct {
	SendEnabled bool
}
