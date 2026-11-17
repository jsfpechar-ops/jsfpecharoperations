package properties

// Brief 1702: POST /apartments/{id}/door-codes (routes/admin.py
// apartment_door_codes, 0954): the Turn on / Turn off buttons of the Door lock
// section. No JavaScript. The lock list, the owner's plan and the other
// properties on a lock are read through the 1701 helpers (detailLoad,
// detailDoorContext, detailLockUsers), so the page and this switch agree.

import (
	_ "embed"
	"fmt"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

//go:embed apartmentdoorcodes/i18n.json
var apartmentDoorCodesJSON []byte

// apartmentDoorCodesStrings is the catalog of this route (apartmentdoorcodes/i18n_keys.txt,
// written by App/scripts/go_host_i18n.py).
var apartmentDoorCodesStrings = hostweb.Load(apartmentDoorCodesJSON)

const (
	doorCodesOffSQL = `UPDATE apartment SET lock_provider = NULL WHERE id = $1`
	doorCodesOnSQL  = `UPDATE apartment SET lock_provider = 'ttlock', lock_id = $1 WHERE id = $2`
)

// RegisterApartmentDoorCodes adds POST /apartments/{id}/door-codes. It only
// builds the handler; the pool is first used inside a request.
func RegisterApartmentDoorCodes(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &server{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /apartments/{id}/door-codes", wrap("/apartments/{id}/door-codes", s.apartmentDoorCodes))
}

// doorCodesFlash is _flash(request, key) from this route's catalog.
func doorCodesFlash(q *request, key string) hostweb.Flash {
	return hostweb.Flash{Text: apartmentDoorCodesStrings.T(q.lang, key, nil), Key: key}
}

func (s *server) apartmentDoorCodes(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	// access.apartment: only a property of the signed-in workspace.
	a, err := p.detailLoad(ctx, q.host.Workspace.ID, q.id)
	if err != nil {
		fail(w, err)
		return
	}
	allowed := false
	if a != nil {
		if allowed, err = p.detailLockAllowed(ctx, a.OwnerUserID); err != nil {
			fail(w, err)
			return
		}
	}
	if !allowed {
		q.back(w, r, "/apartments", hostweb.Flash{}, doorCodesFlash(q, "flash.error.smart_locks_unavailable"))
		return
	}
	here := fmt.Sprintf("/apartments/%d?view=settings&section=lock#sec-lock", a.ID)
	switch formStr(r, "mode") {
	case "off":
		// Keeps lock_id and every issued code; only new codes stop.
		if _, err := s.pool.Exec(ctx, doorCodesOffSQL, a.ID); err != nil {
			fail(w, err)
			return
		}
		if err := s.audit(ctx, q, "door_codes_off", fmt.Sprintf("apartment=%d", a.ID)); err != nil {
			fail(w, err)
			return
		}
		q.back(w, r, here, hostweb.Flash{}, hostweb.Flash{})
		return
	case "on":
	default:
		q.back(w, r, here, hostweb.Flash{}, hostweb.Flash{})
		return
	}
	door, err := p.detailDoorContext(ctx, a)
	if err != nil {
		fail(w, err)
		return
	}
	if door == nil {
		q.back(w, r, here, hostweb.Flash{}, doorCodesFlash(q, "flash.error.smart_locks_unavailable"))
		return
	}
	lockID := a.LockID
	if lockID == "" {
		lockID = door.DefaultLockID
	}
	listed := false
	for _, l := range door.Locks {
		listed = listed || (lockID != "" && l.LockID == lockID)
	}
	if !listed {
		q.back(w, r, here, hostweb.Flash{}, doorCodesFlash(q, "flash.error.door_code_lock"))
		return
	}
	users, err := p.detailLockUsers(ctx, *a.OwnerUserID, lockID, a.ID)
	if err != nil {
		fail(w, err)
		return
	}
	if users != "" {
		q.back(w, r, here, hostweb.Flash{}, doorCodesFlash(q, "flash.error.door_code_lock_taken"))
		return
	}
	if a.CheckinHour == nil || a.CheckoutHour == nil {
		q.back(w, r, here, hostweb.Flash{}, doorCodesFlash(q, "why.times_missing"))
		return
	}
	if _, err := s.pool.Exec(ctx, doorCodesOnSQL, lockID, a.ID); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "door_codes_on", fmt.Sprintf("apartment=%d", a.ID)); err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, here, hostweb.Flash{}, hostweb.Flash{})
}
