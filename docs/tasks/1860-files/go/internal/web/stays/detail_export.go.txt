package stays

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// StayGuest is one live guest of a stay in reporting.reservation_progress order
// (lead first, then id), with the decrypted record the completeness checks read.
type StayGuest struct {
	ID            int64
	SubmitState   string
	ManualFiledAt string
	SubmittedAt   string
	IsLead        bool
	Row           validation.GuestRow
}

// StayDetail is reporting.reservation_progress and reporting.send_controls
// (send_enabled, send_hint_key, pending_count) for the stay page.
type StayDetail struct {
	Progress     Progress
	Controls     Controls
	SendHintKey  string
	PendingCount int
	Guests       []StayGuest
}

// StayProgress runs the stays-list progress code for one stay. A guest field
// that cannot be decrypted gives Progress{Unreadable: true}, as the list does.
func StayProgress(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, res Reservation, at time.Time) (StayDetail, error) {
	byStay, err := loadProgGuests(ctx, pool, []int64{res.ID}, getenv)
	if errors.Is(err, secure.ErrInvalidToken) {
		return StayDetail{Progress: Progress{Unreadable: true}}, nil
	}
	if err != nil {
		return StayDetail{}, err
	}
	return stayDetail(res, byStay[res.ID], at), nil
}

func stayDetail(res Reservation, guests []progGuest, at time.Time) StayDetail {
	st := listStay{
		id: res.ID, dateFrom: res.DateFrom, dateTo: res.DateTo,
		declared: res.Declared, override: res.Override, reduced: res.Reduced,
	}
	u := at.UTC()
	today := time.Date(u.Year(), u.Month(), u.Day(), 0, 0, 0, 0, time.UTC)
	lp := listProgress(st, guests, today)
	prog := buildProgress(st, guests, at)
	hint, pending := sendHint(res, lp, guests, prog.NotRegistered)
	out := StayDetail{
		Progress: prog, Controls: sendControls(res, res.AutomationMode, lp, guests),
		SendHintKey: hint, PendingCount: pending, Guests: make([]StayGuest, 0, len(guests)),
	}
	for _, g := range guests {
		out.Guests = append(out.Guests, StayGuest{
			ID: g.id, SubmitState: g.submitState, ManualFiledAt: g.manualFiledAt,
			SubmittedAt: g.submittedAt, IsLead: g.isLead, Row: g.row,
		})
	}
	return out
}

// sendHint is send_hint_key and pending_count of reporting.send_controls
// (reporting.py 768-845). pending is pending_reportable(progress["reportable"]).
// The demo test is the one sendControls uses.
func sendHint(res Reservation, p listProg, guests []progGuest, notRegistered *int) (string, int) {
	pending := len(pendingReportable(p.reportable, res.DateFrom))
	hasPending := pending > 0
	sendable := p.status == "ready" || p.status == "failed" || p.status == "awaiting_verification"
	canSend := sendable && hasPending
	if res.Source == "demo" {
		return "hint.demo_stay", pending
	}
	if strings.Contains(res.InternalName, "(demo)") {
		return "hint.demo_preview", pending
	}
	switch {
	case p.status == "failed":
		return "hint.failed", pending
	case res.AutomationMode == "immediate":
		return "hint.auto_immediate", pending
	case !hasPending && p.status == "reported":
		return "hint.all_reported", pending
	case !hasPending && p.status == "not_required":
		return "hint.nothing_duty", pending
	case len(guests) == 0:
		return "hint.awaiting_guest", pending
	case p.status == "incomplete" && notRegistered != nil:
		return "hint.missing_guests", pending
	case !hasPending:
		for _, g := range guests {
			if validation.GuestIsReportable(g.nationality) && !signatureSettled(g, res.DateFrom) {
				return "hint.need_signature", pending
			}
		}
		return "hint.nothing_left", pending
	case !canSend:
		return "hint.not_ready", pending
	case p.status == "awaiting_verification":
		return "hint.ready_id_optional", pending
	}
	return "hint.ready_to_send", pending
}
