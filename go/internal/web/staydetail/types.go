package staydetail

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

// DoorCodeViewer is door_codes.view for one stay (*doorcodes.Service).
type DoorCodeViewer interface {
	ViewForStay(ctx context.Context, reservationID, apartmentID int64) (*doorcodes.Shown, error)
}

// Deps are what Build reads besides the request. DoorCodes nil hides the panel.
type Deps struct {
	Pool      *pgxpool.Pool
	Getenv    func(string) string
	DoorCodes DoorCodeViewer
}

// GuestRow is one guest_rows item: the guest, guest_issues and guest_is_complete.
type GuestRow struct {
	Guest    Guest
	Issues   []validation.Issue
	Complete bool
}

// Guest is a guest row as the stay template reads it.
type Guest struct {
	stays.StayGuest
	DocType, EnteredBy, LastErrors, RestrictedAt, ManualMarkedAt, ManualReference string
}

// Submission is one row of the stay's report list.
type Submission struct {
	ID          int64
	CreatedAt   string
	State       string
	PseudoStamp string
	HasReceipt  bool
}

// View is the context of reservation_detail.html.
type View struct {
	Reservation  Stay
	Progress     stays.Progress
	SendControls SendControls
	GuestRows    []GuestRow
	CheckIn      *time.Time
	Deadline     *time.Time
	Submissions  []Submission
	ReturnTo     string
	GuestLink    string
	StayClaim    StayClaim
	ClaimResend  bool
	IsDemoStay   bool
	HandFiling   HandFiling
	StayInvoice  *invoices.StayInvoice
	DoorCode     *doorcodes.Shown
}

// SendControls is the part of reporting.send_controls the stay page reads.
type SendControls struct {
	SendEnabled  bool
	SendHintKey  string
	PendingCount int
}

// isDemoStay is demo.is_demo_stay (demo.py 81): the stay's source is "demo".
func isDemoStay(source string) bool { return source == "demo" }
