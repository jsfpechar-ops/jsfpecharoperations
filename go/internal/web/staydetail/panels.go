package staydetail

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// StayClaim is the reservation_claim fields the stay page reads.
type StayClaim struct {
	State               string
	EmailMasked         string
	GuestAccessLockedAt string
}

const claimRowSQL = `SELECT COALESCE(state,''), COALESCE(email_masked,''), COALESCE(guest_access_locked_at,'')
  FROM reservation_claim WHERE reservation_id = $1`

// ensureClaimRow is claim.ensure_row: the stay's claim row, created unclaimed when missing.
func ensureClaimRow(ctx context.Context, pool *pgxpool.Pool, reservationID int64) (StayClaim, error) {
	var c StayClaim
	err := pool.QueryRow(ctx, claimRowSQL, reservationID).Scan(&c.State, &c.EmailMasked, &c.GuestAccessLockedAt)
	if err == nil {
		return c, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return c, err
	}
	now := ubyport.UTCNow()
	if _, err := pool.Exec(ctx,
		`INSERT INTO reservation_claim (reservation_id, state, token_version, created_at, updated_at)
		 VALUES ($1, 'unclaimed', 0, $2, $2)`, reservationID, now); err != nil {
		return c, err
	}
	err = pool.QueryRow(ctx, claimRowSQL, reservationID).Scan(&c.State, &c.EmailMasked, &c.GuestAccessLockedAt)
	return c, err
}

// HandFiling is reporting.hand_filing_view. FiledAt and UndoUntil are Prague time.
type HandFiling struct {
	Count, Candidates int
	FiledAt           *time.Time
	Reference         string
	CanUndo           bool
	UndoUntil         *time.Time
	DefaultFiledAt    string
}

const manualUndoWindow = 24 * time.Hour

// handFilingView is reporting.hand_filing_view(progress, now).
func handFilingView(rows []GuestRow, now time.Time) HandFiling {
	current := now.UTC()
	out := HandFiling{DefaultFiledAt: deadlines.LocalNow(current).Format("2006-01-02T15:04")}
	var latest *Guest
	var lastMark *time.Time
	for i := range rows {
		g := &rows[i].Guest
		switch g.SubmitState {
		case "pending", "error", "blocked":
			if validation.GuestIsReportable(g.Row.Nationality) {
				out.Candidates++
			}
		}
		if g.SubmitState != "sent" || g.ManualFiledAt == "" {
			continue
		}
		out.Count++
		if latest == nil || g.ManualFiledAt > latest.ManualFiledAt {
			latest = g
		}
		marked, ok := ubyport.ParseStoredUTC(g.ManualMarkedAt)
		if ok && current.Sub(marked) >= 0 && current.Sub(marked) <= manualUndoWindow {
			out.CanUndo = true
			if lastMark == nil || marked.After(*lastMark) {
				m := marked
				lastMark = &m
			}
		}
	}
	if latest != nil {
		if t, ok := ubyport.ParseStoredUTC(latest.ManualFiledAt); ok {
			l := deadlines.LocalNow(t)
			out.FiledAt = &l
		}
		out.Reference = latest.ManualReference
	}
	if lastMark != nil {
		u := deadlines.LocalNow(lastMark.Add(manualUndoWindow))
		out.UndoUntil = &u
	}
	return out
}
