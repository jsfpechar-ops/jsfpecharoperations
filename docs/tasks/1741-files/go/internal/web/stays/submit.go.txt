package stays

// Brief 1741: POST /reservations/submit-ready and POST /reservations/{id}/submit
// (admin.py reservations_submit_ready, reservation_submit).

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

const submitAuditSQL = editAuditSQL

var submitTransportKeys = map[string]string{
	"dial":     "flash.error.ubyport_unreachable",
	"auth":     "flash.error.ubyport_login_refused",
	"fault":    "flash.error.ubyport_fault",
	"http4xx":  "flash.error.ubyport_http_error",
	"redirect": "flash.error.ubyport_http_error",
}

// RegisterSubmit wires filing POST routes (dormant until UBYHOST_GO_PATHS).
func RegisterSubmit(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := postDeps{pool, getenv, now}
	mux.Handle("POST /reservations/submit-ready", wrap("/reservations/submit-ready", SubmitReadyHandler(d)))
	mux.Handle("POST /reservations/{reservation_id}/submit", wrap("/reservations/{reservation_id}/submit", ReservationSubmitHandler(d)))
}

func parseSubmitID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return 0, false
	}
	return id, true
}

func submitServerError(w http.ResponseWriter, err error) {
	log.Printf("stays submit: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

func (c *postCall) submitAudit(ctx context.Context, action, detail string) error {
	h, err := hostweb.Login(c.w, c.r, c.pool, c.getenv, c.at)
	if err != nil || h == nil {
		return err
	}
	var impersonator any
	if h.Impersonating {
		impersonator = h.Account.ID
	}
	_, err = c.pool.Exec(ctx, submitAuditSQL, isoStamp(c.at), h.Account.Username, action, detail,
		c.owner, h.Account.ID, impersonator)
	return err
}

func submitReturnTo(r *http.Request, def string) string {
	raw := formStr(r, "return_to")
	if p := ai.HavelSafeLocalPath(raw, ""); p != "" {
		return p
	}
	return def
}

func submitPluralFlash(r *http.Request, lang, base string, n int, params map[string]any) hostweb.Flash {
	p := map[string]any{"count": n, "n": n}
	for k, v := range params {
		p[k] = v
	}
	key := submitPluralKey(base, n, lang)
	return hostweb.Flash{Text: catalog.T(lang, key, p), Key: base, Count: n}
}

func submitPluralKey(base string, n int, lang string) string {
	if lang == "uk" {
		switch {
		case n%10 == 1 && n%100 != 11:
			return base + ".one"
		case n%10 >= 2 && n%10 <= 4 && (n%100 < 12 || n%100 > 14):
			return base + ".few"
		}
		return base
	}
	switch {
	case n == 1:
		return base + ".one"
	case n >= 2 && n <= 4:
		return base + ".few"
	}
	return base
}

func (c *postCall) submitTransportFlash(res ubyport.BatchResult) hostweb.Flash {
	key := submitTransportKeys[res.Cause]
	if key == "" {
		key = "flash.error.ubyport_send_failed"
	}
	if key == "flash.error.ubyport_fault" {
		if rowKey := ubyport.FaultHostKey(res.Cause, res.Detail); rowKey != "" && rowKey != ubyport.FaultUnknownKey {
			return c.flash(rowKey, map[string]any{"detail": ubyport.FaultHostDetail(res.Detail)})
		}
		return c.flash(key, map[string]any{"detail": ubyport.FaultHostDetail(res.Detail)})
	}
	if key == "flash.error.ubyport_http_error" {
		return c.flash(key, map[string]any{"detail": res.Detail})
	}
	return c.flash(key, nil)
}

func (c *postCall) newSweep(ctx context.Context) (ubyport.SweepDeps, error) {
	keys, err := secure.LoadDataKeys(c.getenv)
	if err != nil {
		return ubyport.SweepDeps{}, err
	}
	return ubyport.NewSweepDeps(ctx, c.pool, keys, c.getenv)
}

func submitCollectOpts(guestIDs []int64, allowResend bool, now func() time.Time, getenv func(string) string) ubyport.CollectOptions {
	return ubyport.CollectOptions{
		OnlyGuestIDs:     guestIDs,
		IgnoreAutomation: true,
		AllowResend:      allowResend,
		Now:              now,
		Decrypt:          guestSaveDecrypter(getenv),
	}
}

func submitSummarize(results []ubyport.BatchResult) (sent, failed int) {
	for _, r := range results {
		sent += r.Submitted
		failed += r.Failed + r.Blocked
	}
	return sent, failed
}

func submitFirstTransport(results []ubyport.BatchResult) *ubyport.BatchResult {
	for i := range results {
		if results[i].State == "transport_error" {
			return &results[i]
		}
	}
	return nil
}

func (c *postCall) submitOneStay(ctx context.Context, res Reservation, mode string, guestIDs []int64, allowResend bool) ([]ubyport.BatchResult, error) {
	if len(guestIDs) == 0 {
		return nil, nil
	}
	sweep, err := c.newSweep(ctx)
	if err != nil {
		return nil, err
	}
	return ubyport.SubmitForApartment(ctx, sweep, res.ApartmentID,
		submitCollectOpts(guestIDs, allowResend, c.now, c.getenv), mode)
}

func submitLoadReservation(ctx context.Context, pool *pgxpool.Pool, owner, id int64) (Reservation, bool, error) {
	var res Reservation
	err := pool.QueryRow(ctx, `SELECT r.id, r.apartment_id, r.date_from, r.date_to, COALESCE(r.status,''),
		COALESCE(r.source,''), COALESCE(r.summary,''), COALESCE(a.internal_name,''),
		COALESCE(a.permalink_token,''), COALESCE(a.automation_mode,''), a.submit_after_hours,
		r.declared_guests, r.expected_guests_override, r.lead_reduced_guests
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`,
		id, owner).Scan(&res.ID, &res.ApartmentID, &res.DateFrom, &res.DateTo, &res.Status, &res.Source,
		&res.Summary, &res.InternalName, &res.PermalinkToken, &res.AutomationMode, &res.SubmitAfterHours,
		&res.Declared, &res.Override, &res.Reduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return Reservation{}, false, nil
	}
	if err != nil {
		return Reservation{}, false, err
	}
	return res, true, nil
}

func submitGuestIDs(ctx context.Context, pool *pgxpool.Pool, resID int64) ([]int64, error) {
	rows, err := pool.Query(ctx, `SELECT id FROM guest WHERE reservation_id = $1 ORDER BY id`, resID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

func submitReadyGuestIDs(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, res Reservation, at time.Time) ([]int64, error) {
	det, err := StayProgress(ctx, pool, getenv, res, at)
	if err != nil {
		return nil, err
	}
	if det.Progress.Unreadable {
		return nil, nil
	}
	pending := pendingReportable(det.GuestsToProg(), res.DateFrom)
	ids := make([]int64, 0, len(pending))
	for _, g := range pending {
		ids = append(ids, g.id)
	}
	return ids, nil
}

// GuestsToProg adapts StayGuest rows for pendingReportable.
func (d StayDetail) GuestsToProg() []progGuest {
	out := make([]progGuest, 0, len(d.Guests))
	for _, g := range d.Guests {
		out = append(out, progGuest{
			id: g.ID, submitState: g.SubmitState, nationality: g.Row.Nationality, row: g.Row,
		})
	}
	return out
}

func submitActiveReservations(ctx context.Context, pool *pgxpool.Pool, owner int64) ([]Reservation, error) {
	rows, err := pool.Query(ctx, `SELECT r.id, r.apartment_id, r.date_from, r.date_to, COALESCE(r.status,''),
		COALESCE(r.source,''), COALESCE(r.summary,''), COALESCE(a.internal_name,''),
		COALESCE(a.permalink_token,''), COALESCE(a.automation_mode,''), a.submit_after_hours,
		r.declared_guests, r.expected_guests_override, r.lead_reduced_guests
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
		AND a.archived_at IS NULL AND a.owner_user_id IS NOT DISTINCT FROM $1`,
		owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var list []Reservation
	for rows.Next() {
		var res Reservation
		if err := rows.Scan(&res.ID, &res.ApartmentID, &res.DateFrom, &res.DateTo, &res.Status, &res.Source,
			&res.Summary, &res.InternalName, &res.PermalinkToken, &res.AutomationMode, &res.SubmitAfterHours,
			&res.Declared, &res.Override, &res.Reduced); err != nil {
			return nil, err
		}
		list = append(list, res)
	}
	return list, rows.Err()
}

func SubmitReadyHandler(d postDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		returnTo := submitReturnTo(r, "/reservations")
		ctx := r.Context()
		stays, err := submitActiveReservations(ctx, c.pool, c.owner)
		if err != nil {
			submitServerError(w, err)
			return
		}
		var sentStays, sentGuests int
		var failedTransport *ubyport.BatchResult
		for _, res := range stays {
			det, err := StayProgress(ctx, c.pool, c.getenv, res, c.at)
			if err != nil || det.Progress.Unreadable {
				continue
			}
			if !det.Controls.SendEnabled {
				continue
			}
			guestIDs, err := submitReadyGuestIDs(ctx, c.pool, c.getenv, res, c.at)
			if err != nil || len(guestIDs) == 0 {
				continue
			}
			results, err := c.submitOneStay(ctx, res, "manual_bulk", guestIDs, false)
			if err != nil {
				submitServerError(w, err)
				return
			}
			if len(results) == 0 {
				continue
			}
			batchSent, _ := submitSummarize(results)
			if failedTransport == nil {
				failedTransport = submitFirstTransport(results)
			}
			if batchSent > 0 {
				sentStays++
				sentGuests += batchSent
			}
		}
		if sentGuests == 0 {
			if failedTransport != nil {
				c.back(returnTo, hostweb.Flash{}, c.submitTransportFlash(*failedTransport))
				return
			}
			c.back(returnTo, hostweb.Flash{}, c.flash("flash.error.nothing_ready", nil))
			return
		}
		staysWord := submitPluralFlash(r, c.lang, "flash.reservations.sent.stays", sentStays, nil).Text
		msg := submitPluralFlash(r, c.lang, "flash.reservations.sent", sentGuests, map[string]any{
			"guests": sentGuests,
			"stays":  staysWord,
		})
		c.back(returnTo, msg, hostweb.Flash{})
	}
}

func ReservationSubmitHandler(d postDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		resID, ok := parseSubmitID(w, r)
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		ctx := r.Context()
		res, found, err := submitLoadReservation(ctx, c.pool, c.owner, resID)
		if err != nil {
			submitServerError(w, err)
			return
		}
		if !found {
			c.back("/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_stay", nil))
			return
		}
		det, err := StayProgress(ctx, c.pool, c.getenv, res, c.at)
		if err != nil {
			submitServerError(w, err)
			return
		}
		if !det.Controls.SendEnabled {
			key := det.SendHintKey
			if key == "" {
				key = "flash.error.not_sendable"
			}
			returnTo := fmt.Sprintf("/reservations/%d", resID)
			c.back(returnTo, hostweb.Flash{}, c.flash(key, nil))
			return
		}
		allowResend := formStr(r, "allow_resend") != ""
		if allowResend && formStr(r, "confirm_duplicate") == "" {
			c.back(fmt.Sprintf("/reservations/%d", resID), hostweb.Flash{},
				c.flash("flash.error.confirm_duplicate_resend", nil))
			return
		}
		returnTo := submitReturnTo(r, fmt.Sprintf("/reservations/%d", resID))
		guestIDs, err := submitGuestIDs(ctx, c.pool, resID)
		if err != nil {
			submitServerError(w, err)
			return
		}
		results, err := c.submitOneStay(ctx, res, "manual", guestIDs, allowResend)
		if err != nil {
			submitServerError(w, err)
			return
		}
		if len(results) == 0 {
			c.back(returnTo, hostweb.Flash{}, c.flash("flash.error.nothing_sendable", nil))
			return
		}
		first := results[0]
		switch first.State {
		case "noop":
			c.back(returnTo, hostweb.Flash{}, c.flash("flash.error.nothing_to_send", nil))
		case "not_configured":
			c.back(returnTo, hostweb.Flash{}, c.flash("flash.error.ubyport_not_configured", nil))
		case "outcome_unknown":
			_ = c.submitAudit(ctx, "ubyport_send_outcome_unknown",
				fmt.Sprintf("apartment=%d error=%s", res.ApartmentID, first.Error))
			c.back(returnTo, hostweb.Flash{}, c.flash("flash.error.ubyport_outcome_unknown", nil))
		case "transport_error":
			_ = c.submitAudit(ctx, "ubyport_send_failed",
				fmt.Sprintf("apartment=%d error=%s", res.ApartmentID, first.Error))
			c.back(returnTo, hostweb.Flash{}, c.submitTransportFlash(first))
		default:
			sent, failed := submitSummarize(results)
			if failed > 0 {
				c.back(returnTo,
					submitPluralFlash(r, c.lang, "flash.reservations.accepted", sent, nil),
					submitPluralFlash(r, c.lang, "flash.error.rejected", failed, nil))
				return
			}
			c.back(returnTo, submitPluralFlash(r, c.lang, "flash.reservations.reported", sent, nil), hostweb.Flash{})
		}
	}
}
