package staydetail

import (
	"context"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/palette"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

const guestExtrasSQL = `SELECT id, COALESCE(doc_type,''), COALESCE(entered_by,''), COALESCE(last_errors,''),
       COALESCE(restricted_at,''), COALESCE(manual_marked_at,''), COALESCE(manual_reference,'')
  FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`

const submissionsSQL = `SELECT id, COALESCE(created_at,''), COALESCE(state,''), COALESCE(pseudo_stamp,''),
       (receipt_pdf IS NOT NULL AND TRIM(receipt_pdf) != '') AS has_receipt
  FROM submission WHERE id IN (
    SELECT DISTINCT submission_id FROM guest WHERE reservation_id = $1 AND submission_id IS NOT NULL
    UNION SELECT DISTINCT receipt_submission_id FROM guest
    WHERE reservation_id = $2 AND receipt_submission_id IS NOT NULL
  ) AND apartment_id = $3 ORDER BY created_at DESC`

type guestExtra struct {
	docType, enteredBy, lastErrors, restrictedAt, manualMarkedAt, manualReference string
}

func loadGuestExtras(ctx context.Context, pool *pgxpool.Pool, reservationID int64) (map[int64]guestExtra, error) {
	rows, err := pool.Query(ctx, guestExtrasSQL, reservationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[int64]guestExtra{}
	for rows.Next() {
		var id int64
		var e guestExtra
		if err := rows.Scan(&id, &e.docType, &e.enteredBy, &e.lastErrors, &e.restrictedAt, &e.manualMarkedAt, &e.manualReference); err != nil {
			return nil, err
		}
		out[id] = e
	}
	return out, rows.Err()
}

func loadSubmissions(ctx context.Context, pool *pgxpool.Pool, reservationID, apartmentID int64) ([]Submission, error) {
	rows, err := pool.Query(ctx, submissionsSQL, reservationID, reservationID, apartmentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Submission
	for rows.Next() {
		var s Submission
		if err := rows.Scan(&s.ID, &s.CreatedAt, &s.State, &s.PseudoStamp, &s.HasReceipt); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// Build is the read model for reservation_detail.html.
func Build(ctx context.Context, d Deps, ownerID, id int64, rawReturnTo string, at time.Time) (View, bool, error) {
	s, ok, err := LoadStay(ctx, d.Pool, ownerID, id)
	if err != nil || !ok {
		return View{}, ok, err
	}

	det, err := stays.StayProgress(ctx, d.Pool, d.Getenv, s.Reservation, at)
	if err != nil {
		return View{}, false, err
	}

	extras, err := loadGuestExtras(ctx, d.Pool, id)
	if err != nil {
		return View{}, false, err
	}

	u := at.UTC()
	today := time.Date(u.Year(), u.Month(), u.Day(), 0, 0, 0, 0, time.UTC)
	guestRows := make([]GuestRow, 0, len(det.Guests))
	for _, g := range det.Guests {
		ex := extras[g.ID]
		guestRows = append(guestRows, GuestRow{
			Guest: Guest{
				StayGuest:       g,
				DocType:         ex.docType,
				EnteredBy:       ex.enteredBy,
				LastErrors:      ex.lastErrors,
				RestrictedAt:    ex.restrictedAt,
				ManualMarkedAt:  ex.manualMarkedAt,
				ManualReference: ex.manualReference,
			},
			Issues:   validation.GuestIssues(g.Row, s.DateFrom, s.DateTo, today),
			Complete: validation.GuestIsComplete(g.Row, s.DateFrom, s.DateTo, today),
		})
	}

	var checkIn *time.Time
	var deadline *time.Time
	if det.Progress.HasAnchor {
		ci := det.Progress.Anchor
		checkIn = &ci
		dl := deadlines.ReportingDeadline(ci)
		deadline = &dl
	}

	subs, err := loadSubmissions(ctx, d.Pool, id, s.ApartmentID)
	if err != nil {
		return View{}, false, err
	}

	returnTo := ai.HavelSafeLocalPath(rawReturnTo, "/reservations")

	key, err := palette.LinkKey(ctx, d.Pool, s.ApartmentID, s.InternalName, s.PermalinkToken)
	if err != nil {
		return View{}, false, err
	}
	guestLink := billingjob.PublicBaseURL() + "/l/" + key + "/" + strconv.FormatInt(id, 10)

	stayClaim, err := ensureClaimRow(ctx, d.Pool, id)
	if err != nil {
		return View{}, false, err
	}

	isDemo := isDemoStay(s.Source)
	claimResend := billingjob.MailEnabled() && !isDemo && stayClaim.State == "claimed" && stayClaim.GuestAccessLockedAt == ""

	var handFiling HandFiling
	if isDemo {
		handFiling = HandFiling{}
	} else {
		handFiling = handFilingView(guestRows, at)
	}

	stayInvoice, err := invoices.ActiveInvoiceForStay(ctx, d.Pool, id)
	if err != nil {
		return View{}, false, err
	}

	v := View{
		Reservation: s,
		Progress:    det.Progress,
		SendControls: SendControls{
			SendEnabled:  det.Controls.SendEnabled,
			SendHintKey:  det.SendHintKey,
			PendingCount: det.PendingCount,
		},
		GuestRows:   guestRows,
		CheckIn:     checkIn,
		Deadline:    deadline,
		Submissions: subs,
		ReturnTo:    returnTo,
		GuestLink:   guestLink,
		StayClaim:   stayClaim,
		ClaimResend: claimResend,
		IsDemoStay:  isDemo,
		HandFiling:  handFiling,
		StayInvoice: stayInvoice,
	}
	if d.DoorCodes != nil {
		v.DoorCode, err = d.DoorCodes.ViewForStay(ctx, id, s.ApartmentID)
		if err != nil {
			return View{}, false, err
		}
	}
	return v, true, nil
}
