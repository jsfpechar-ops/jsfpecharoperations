package guest

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// confirmRegistrationHandler handles POST /l/{token}/{reservation_id}/confirm-registration
// (Task 2096): verifies live guest progress is complete, atomically stamps
// reservation.registration_completed_at, writes a zero-PII audit row, runs the
// stay submission and completion hooks, and redirects to the confirmed stay view.
func confirmRegistrationHandler(d partyDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, resID, ok := parsePartyPath(w, r)
		if !ok {
			return
		}
		lang := r.URL.Query().Get("lang")
		ctx := r.Context()
		stay, found, err := d.loadPartyStay(ctx, token, resID)
		if err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
			return
		}
		if !found || stay.gone() {
			http.NotFound(w, r)
			return
		}
		ready, err := d.stayReadyForConfirm(ctx, resID, stay.dateFrom, stay.dateTo, stay.override, stay.declared, stay.reduced)
		if err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
			return
		}
		if !ready {
			redirectGuest(w, r, guestLink(token, resID, lang)+langQuery(lang), lang)
			return
		}
		nowS := d.now().UTC().Format(time.RFC3339)
		tag, err := d.pool.Exec(ctx,
			`UPDATE reservation SET registration_completed_at = $1, updated_at = $2
			 WHERE id = $3 AND registration_completed_at IS NULL`,
			nowS, nowS, resID)
		if err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
			return
		}
		if tag.RowsAffected() == 1 {
			if err := d.auditRegistrationConfirmed(ctx, resID, stay.apartmentID); err != nil {
				log.Printf("confirm registration audit %d: %v", resID, err)
			}
		}
		if err := guestFormSubmitStayIfComplete(ctx, d.pool, d.getenv, d.now, stay.apartmentID, resID); err != nil {
			log.Printf("confirm registration submit %d: %v", resID, err)
		}
		runCompletion(ctx, d.hooks, stay.apartmentID, resID)

		frag := ""
		fee := stayClaimDeps{pool: d.pool, getenv: d.getenv, now: d.now}.loadFeePanel(ctx, resID, stay.apartmentID, "")
		if fee != nil && len(fee.Rails) > 0 {
			frag = "#fee-pay"
		}
		loc := GuestLink(token, resID, LangQuery(lang, "&confirmed=1")+frag)
		WithLang(w, d.getenv, lang)
		http.Redirect(w, r, loc, http.StatusSeeOther)
	}
}

func (d partyDeps) stayReadyForConfirm(ctx context.Context, resID int64, dateFrom, dateTo string, override, declared, reduced *int64) (bool, error) {
	exp := headcount.Expected(override, declared, reduced)
	if exp == nil || *exp <= 0 {
		return false, nil
	}
	rows, err := d.pool.Query(ctx, "SELECT "+stayGuestSelect+" FROM guest WHERE reservation_id = $1 AND archived_at IS NULL", resID)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	today := legalToday(d.now)
	filled := 0
	for rows.Next() {
		var c stayGuestCols
		if err := rows.Scan(c.scanArgs()...); err != nil {
			return false, err
		}
		gr, err := c.validationRow(d.getenv, d.now)
		if err != nil {
			return false, err
		}
		if c.Submit == formSubmitSent || validation.GuestIsComplete(gr, dateFrom, dateTo, today) {
			filled++
		} else {
			return false, nil
		}
	}
	if err := rows.Err(); err != nil {
		return false, err
	}
	return int64(filled) >= *exp, nil
}

func (d partyDeps) auditRegistrationConfirmed(ctx context.Context, resID, aptID int64) error {
	var ownerID *int64
	_ = d.pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, aptID).Scan(&ownerID)
	_, err := d.pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, $2, $3, $4, $5)`,
		d.now().UTC(), "guest", "guest_registration_confirmed", fmt.Sprintf("reservation_id=%d", resID), ownerID)
	return err
}

// loadOwnedGuestNames returns display names only for live guests owned by the
// caller's device cookie (2096 privacy boundary: never leaks another device's PII).
func loadOwnedGuestNames(ctx context.Context, pool *pgxpool.Pool, resID int64, owned []int64) []string {
	if pool == nil || len(owned) == 0 {
		return nil
	}
	rows, err := pool.Query(ctx, `
		SELECT COALESCE(first_name, ''), COALESCE(surname, '')
		FROM guest
		WHERE reservation_id = $1 AND archived_at IS NULL AND id = ANY($2)
		ORDER BY is_lead DESC, id`, resID, owned)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var names []string
	for rows.Next() {
		var first, surname string
		if err := rows.Scan(&first, &surname); err != nil {
			continue
		}
		if name := strings.TrimSpace(first + " " + surname); name != "" {
			names = append(names, name)
		}
	}
	return names
}
