package stays

// Brief 1735: guest_archive/unarchive, guest_delete, guest_resend (admin.py 4999-5132).

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

type lifecycleGuest struct {
	id, reservationID, apartmentID int64
	submitState                    string
	archivedAt                     string
	lastErrors                     string
}

func (d guestEditDeps) loadLifecycleGuest(ctx context.Context, owner, guestID int64) (*lifecycleGuest, bool, error) {
	var g lifecycleGuest
	err := d.pool.QueryRow(ctx, `SELECT g.id, g.reservation_id, r.apartment_id,
		COALESCE(g.submit_state,''), COALESCE(g.archived_at,''), COALESCE(g.last_errors,'')
		FROM guest g JOIN reservation r ON r.id = g.reservation_id
		JOIN apartment a ON a.id = r.apartment_id
		WHERE g.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`, guestID, owner).
		Scan(&g.id, &g.reservationID, &g.apartmentID, &g.submitState, &g.archivedAt, &g.lastErrors)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	return &g, err == nil, err
}

// RegisterGuestLifecycle wires archive/delete/resend (dormant until UBYHOST_GO_PATHS).
func RegisterGuestLifecycle(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := guestEditDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /guests/{guest_id}/archive", wrap("/guests/{guest_id}/archive", guestArchiveHandler(d)))
	mux.Handle("POST /guests/{guest_id}/unarchive", wrap("/guests/{guest_id}/unarchive", guestUnarchiveHandler(d)))
	mux.Handle("POST /guests/{guest_id}/delete", wrap("/guests/{guest_id}/delete", guestDeleteHandler(d)))
	mux.Handle("POST /guests/{guest_id}/resend", wrap("/guests/{guest_id}/resend", guestResendHandler(d)))
}

func guestArchiveHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		g, found, err := d.loadLifecycleGuest(r.Context(), c.owner, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/housebook", hostweb.Flash{}, c.flash("flash.error.no_such_housebook_guest", nil))
			return
		}
		if g.submitState == submitStateSent {
			hostweb.Back(w, r, fmt.Sprintf("/guests/%d", id), hostweb.Flash{}, c.flash("flash.error.reported_kept", nil))
			return
		}
		if g.archivedAt != "" {
			hostweb.Back(w, r, fmt.Sprintf("/guests/%d", id), hostweb.Flash{}, c.flash("flash.error.already_archived", nil))
			return
		}
		returnTo := editFormReturnTo(r, "/housebook")
		_ = deleteGuestPhoto(c.getenv, id)
		now := isoStamp(c.at)
		if _, err = c.pool.Exec(r.Context(), `UPDATE guest SET archived_at = $1, updated_at = $1 WHERE id = $2`, now, id); err != nil {
			guestEditServerError(w, err)
			return
		}
		_ = c.audit(r.Context(), "guest_archived", fmt.Sprintf("id=%d", id))
		_ = guestSubmitStayIfComplete(r.Context(), d, g.apartmentID, g.reservationID)
		hostweb.Back(w, r, returnTo, c.flash("flash.housebook.archived", nil), hostweb.Flash{})
	}
}

func guestUnarchiveHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		g, found, err := d.loadLifecycleGuest(r.Context(), c.owner, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/housebook", hostweb.Flash{}, c.flash("flash.error.no_such_housebook_guest", nil))
			return
		}
		returnTo := editFormReturnTo(r, "/housebook")
		if g.archivedAt == "" {
			hostweb.Back(w, r, returnTo, hostweb.Flash{}, c.flash("flash.error.not_archived", nil))
			return
		}
		now := isoStamp(c.at)
		if _, err = c.pool.Exec(r.Context(), `UPDATE guest SET archived_at = NULL, updated_at = $1 WHERE id = $2`, now, id); err != nil {
			guestEditServerError(w, err)
			return
		}
		_ = c.audit(r.Context(), "guest_unarchived", fmt.Sprintf("id=%d", id))
		_ = guestSubmitStayIfComplete(r.Context(), d, g.apartmentID, g.reservationID)
		hostweb.Back(w, r, returnTo, c.flash("flash.housebook.restored", nil), hostweb.Flash{})
	}
}

func guestDeleteHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		g, found, err := d.loadLifecycleGuest(r.Context(), c.owner, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_guest", nil))
			return
		}
		if g.submitState == submitStateSent {
			hostweb.Back(w, r, fmt.Sprintf("/guests/%d", id), hostweb.Flash{}, c.flash("flash.error.reported_kept", nil))
			return
		}
		resID := g.reservationID
		aptID := g.apartmentID
		_ = deleteGuestPhoto(c.getenv, id)
		if _, err = c.pool.Exec(r.Context(), `DELETE FROM guest WHERE id = $1`, id); err != nil {
			guestEditServerError(w, err)
			return
		}
		_ = c.audit(r.Context(), "guest_deleted", fmt.Sprintf("id=%d", id))
		_ = guestSubmitStayIfComplete(r.Context(), d, aptID, resID)
		hostweb.Back(w, r, fmt.Sprintf("/reservations/%d", resID), c.flash("flash.guests.removed", nil), hostweb.Flash{})
	}
}

func guestResendHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		g, found, err := d.loadLifecycleGuest(r.Context(), c.owner, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_guest", nil))
			return
		}
		back := fmt.Sprintf("/guests/%d", id)
		if formStr(r, "confirm_duplicate") == "" {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flash("flash.error.confirm_duplicate", nil))
			return
		}
		if blockedAsDuplicateGuest(g.lastErrors) {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flash("flash.error.already_reported_duplicate", nil))
			return
		}
		keys, err := secure.LoadDataKeys(c.getenv)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		sweep, err := ubyport.NewSweepDeps(r.Context(), c.pool, keys, c.getenv)
		if err != nil {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flash("flash.error.record_not_sendable", nil))
			return
		}
		results, err := ubyport.SubmitForApartment(r.Context(), sweep, g.apartmentID, ubyport.CollectOptions{
			OnlyGuestIDs:     []int64{id},
			IgnoreAutomation: true,
			AllowResend:      true,
			Now:              d.now,
			Decrypt:          guestSaveDecrypter(c.getenv),
		}, "manual_resend")
		if err != nil || len(results) == 0 {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flash("flash.error.record_not_sendable", nil))
			return
		}
		_ = c.audit(r.Context(), "guest_resent", fmt.Sprintf("id=%d", id))
		res := results[0]
		switch res.State {
		case "outcome_unknown":
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flash("flash.error.ubyport_outcome_unknown", nil))
		case "transport_error":
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flash("flash.error.record_not_sendable", nil))
		default:
			if res.Submitted > 0 {
				hostweb.Back(w, r, back, c.flash("flash.guests.resent", nil), hostweb.Flash{})
			} else {
				hostweb.Back(w, r, back, hostweb.Flash{}, c.flash("flash.error.resent_rejected", nil))
			}
		}
	}
}
