package guest

import (
	"context"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
)

// StayGate is guest_guide_view._stay_gate: same door as the stay page before the guide renders.
func StayGate(r *http.Request, w http.ResponseWriter, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, token string, resID int64) (lang string, apt *GuideApartment, res *GuideReservation, done bool) {
	lang = Language(r)
	aptRow, link, early := OpenLink(r, pool, token, lang)
	if early != nil {
		early.ServeHTTP(w, r)
		return lang, nil, nil, true
	}
	sh := shellDeps{pool: pool, getenv: getenv, now: now}
	if requirePin(w, r, sh, link, lang, aptRow) {
		return lang, nil, nil, true
	}
	stay, code := stayReservationForGuest(r, pool, aptRow, link, resID, true)
	if code != 0 {
		WriteUnavailable(w, r, lang, "stay_gone", code, link, hardenedHeaders)
		return lang, nil, nil, true
	}
	row, err := EnsureClaimRow(r.Context(), pool, resID, isoNow(now()))
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return lang, nil, nil, true
	}
	if !GuestAccessOpen(stay.status, row.guestAccessLock) {
		WriteUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, link, hardenedHeaders)
		return lang, nil, nil, true
	}
	if billingjob.MailEnabled() && !HostOwnsStay(r, aptRow.OwnerUserID) {
		if row.state != claimStateClaimed || !DeviceHoldsClaim(r, resID, row.tokenVersion) {
			http.Redirect(w, r, stayHubURL(link, resID, lang), http.StatusSeeOther)
			return lang, nil, nil, true
		}
	}
	gApt := &GuideApartment{ID: aptRow.ID, OwnerUserID: aptRow.OwnerUserID, Name: aptRow.InternalName}
	gRes, err := guideReservationDates(r.Context(), pool, resID, aptRow.ID)
	if err != nil || gRes == nil {
		WriteUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, link, hardenedHeaders)
		return lang, nil, nil, true
	}
	return lang, gApt, gRes, false
}

// stayReservationForGuest is guest.py _reservation_for_guest (permalink stay paths).
func stayReservationForGuest(r *http.Request, pool *pgxpool.Pool, apt *Apartment, link string, resID int64, pinOk bool) (*scStay, int) {
	_, stay, code := LoadGuestStay(r.Context(), pool, link, resID, pinOk, false)
	if code != 0 {
		return nil, code
	}
	if stay.source == "demo" && !HostOwnsStay(r, apt.OwnerUserID) {
		return nil, http.StatusNotFound
	}
	return stay, 0
}

func stayHubURL(token string, resID int64, lang string) string {
	return GuestLink(token, resID, LangQuery(lang, ""))
}

func guideReservationDates(ctx context.Context, pool *pgxpool.Pool, resID, aptID int64) (*GuideReservation, error) {
	var res GuideReservation
	err := pool.QueryRow(ctx, `SELECT id, COALESCE(date_from::text,''), COALESCE(date_to::text,'')
		FROM reservation WHERE id = $1 AND apartment_id = $2 AND archived_at IS NULL`,
		resID, aptID).Scan(&res.ID, &res.DateFrom, &res.DateTo)
	if err != nil {
		return nil, err
	}
	return &res, nil
}