// Package properties ports the property settings POST actions of
// App/app/routes/admin.py: archive, unarchive and delete a legal entity,
// archive, unarchive and re-key a property, and remove a calendar feed. Each
// handler follows its Python route line by line; the route is named in the
// comment above it.
package properties

import (
	"context"
	_ "embed"
	"errors"
	"log"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var stringsJSON []byte

// catalog is the flash catalog generated from App/app/host_i18n.py by
// App/scripts/go_host_i18n.py.
var catalog = hostweb.Load(stringsJSON)

// Wrap is the metrics wrapper of cmd/ubyhost-web (metrics.wrap).
type Wrap func(route string, h http.HandlerFunc) http.Handler

// Register adds the property POST routes. It does not touch the pool.
func Register(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &server{pool: pool, getenv: getenv, now: now}
	for _, route := range []struct {
		path string
		h    http.HandlerFunc
	}{
		{"/entities/{id}/archive", s.archiveEntity},
		{"/entities/{id}/unarchive", s.unarchiveEntity},
		{"/entities/{id}/delete", s.deleteEntity},
		{"/apartments/{id}/archive", s.archiveApartment},
		{"/apartments/{id}/unarchive", s.unarchiveApartment},
		{"/apartments/{id}/regenerate-pin", s.regeneratePIN},
		{"/apartments/{id}/regenerate-link", s.regenerateLink},
		{"/feeds/{id}/delete", s.deleteFeed},
	} {
		mux.Handle("POST "+route.path, wrap(route.path, route.h))
	}
}

type server struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

// propertySummaries is admin.py _PROPERTY_SUMMARIES.
const propertySummaries = "/apartments#property-summaries"

const (
	entityOwnedSQL     = `SELECT name, COALESCE(archived_at, '') FROM legal_entity WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
	apartmentOwnedSQL  = `SELECT internal_name, COALESCE(archived_at, '') FROM apartment WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
	feedOwnedSQL       = `SELECT f.apartment_id FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id WHERE f.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`
	entityUsedSQL      = `SELECT COUNT(*) FROM apartment WHERE (legal_entity_id = $1 OR data_controller_entity_id = $1) AND owner_user_id IS NOT DISTINCT FROM $2`
	entityInvoicedSQL  = `SELECT COUNT(*) FROM invoice WHERE legal_entity_id = $1`
	entityArchiveSQL   = `UPDATE legal_entity SET archived_at = $1 WHERE id = $2`
	entityUnarchiveSQL = `UPDATE legal_entity SET archived_at = NULL WHERE id = $1`
	entityDeleteSQL    = `DELETE FROM legal_entity WHERE id = $1`
	aptArchiveSQL      = `UPDATE apartment SET archived_at = $1, active = 0 WHERE id = $2`
	aptUnarchiveSQL    = `UPDATE apartment SET archived_at = NULL, active = 1 WHERE id = $1`
	aptPINSQL          = `UPDATE apartment SET permalink_pin = $1 WHERE id = $2`
	aptLinkSQL         = `UPDATE apartment SET permalink_token = $1, permalink_pin = $2 WHERE id = $3`
	feedDeleteSQL      = `DELETE FROM ical_feed WHERE id = $1`
	auditSQL           = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`
)

// pathID is what pydantic's lax int accepts from a string, once ASCII
// whitespace is trimmed: a sign, digit groups joined by single underscores, and
// a fraction of zeros only ("130_201.00" is 130201).
var pathID = regexp.MustCompile(`^([+-]?[0-9]+(?:_[0-9]+)*)(?:\.0+)?$`)

// parseID is the FastAPI int path parameter. A number past int64 is a valid
// int to Python that matches no row (psycopg sends it as numeric), so it
// becomes 0, which matches no row either.
func parseID(raw string) (int64, bool) {
	m := pathID.FindStringSubmatch(strings.Trim(raw, " \t\n\r\v\f"))
	if m == nil {
		return 0, false
	}
	id, err := strconv.ParseInt(strings.ReplaceAll(m[1], "_", ""), 10, 64)
	if err != nil {
		return 0, true
	}
	return id, true
}

// stamp is db.utcnow(): UTC, whole seconds, "+00:00".
func stamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// request is what every handler starts with: the signed-in host, the id from
// the path, the request language and the clock reading.
type request struct {
	host *session.Host
	id   int64
	lang string
	at   time.Time
}

// enter runs the CSRF check, the path id check and the login gate in the order
// FastAPI does (dependencies, then the int path parameter, then
// auth.require_login). It returns false when it has written the response.
func (s *server) enter(w http.ResponseWriter, r *http.Request) (*request, bool) {
	at := s.now()
	if !hostweb.CSRF(w, r, s.getenv, at) {
		return nil, false
	}
	id, valid := parseID(r.PathValue("id"))
	if !valid {
		http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
		return nil, false
	}
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		fail(w, err)
		return nil, false
	}
	if h == nil {
		return nil, false
	}
	// The form is read here so return_to is available to every handler.
	_ = r.ParseMultipartForm(32 << 20) // an unreadable body is an empty form
	return &request{host: h, id: id, lang: hostweb.Lang(r), at: at}, true
}

func fail(w http.ResponseWriter, err error) {
	log.Printf("properties route failed: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// flash is a translated flash, with the key it was raised under.
func (q *request) flash(key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(q.lang, key, params), Key: key}
}

// back is admin_helpers.back with Starlette's Location quoting.
func (q *request) back(w http.ResponseWriter, r *http.Request, path string, msg, err hostweb.Flash) {
	hostweb.Back(w, r, locationQuote(path), msg, err)
}

// audit is db.audit for the signed-in account acting in its workspace.
func (s *server) audit(ctx context.Context, q *request, action, detail string) error {
	var impersonator *int64
	if q.host.Impersonating {
		id := q.host.Account.ID
		impersonator = &id
	}
	_, err := s.pool.Exec(ctx, auditSQL, stamp(q.at), q.host.Account.Username, action, detail,
		q.host.Workspace.ID, q.host.Account.ID, impersonator)
	return err
}

// named reads a row of an ownership query: its name and whether it is archived
// (archived_at is a non-empty string, as Python's truthiness has it).
func (s *server) named(ctx context.Context, sql string, id, owner int64) (name string, archived, found bool, err error) {
	var at string
	err = s.pool.QueryRow(ctx, sql, id, owner).Scan(&name, &at)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, false, nil
	}
	if err != nil {
		return "", false, false, err
	}
	return name, at != "", true, nil
}

func (s *server) count(ctx context.Context, sql string, args ...any) (int64, error) {
	var n int64
	err := s.pool.QueryRow(ctx, sql, args...).Scan(&n)
	return n, err
}

// archiveEntity is POST /entities/{id}/archive (admin.py archive_entity).
func (s *server) archiveEntity(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx, owner := r.Context(), q.host.Workspace.ID
	name, archived, found, err := s.named(ctx, entityOwnedSQL, q.id, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if !found {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.no_such_entity", nil))
		return
	}
	if archived {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.already_archived", nil))
		return
	}
	used, err := s.count(ctx, entityUsedSQL, q.id, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if used > 0 {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.entity_has_properties", nil))
		return
	}
	if _, err := s.pool.Exec(ctx, entityArchiveSQL, stamp(q.at), q.id); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "entity_archived", "id="+strconv.FormatInt(q.id, 10)); err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, "/entities", q.flash("flash.entities.archived", map[string]any{"name": name}), hostweb.Flash{})
}

// unarchiveEntity is POST /entities/{id}/unarchive (admin.py unarchive_entity).
func (s *server) unarchiveEntity(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx, owner := r.Context(), q.host.Workspace.ID
	idText := strconv.FormatInt(q.id, 10)
	returnTo := formReturnTo(r, "/entities?edit="+idText, false)
	name, archived, found, err := s.named(ctx, entityOwnedSQL, q.id, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if !found {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.no_such_entity", nil))
		return
	}
	if !archived {
		q.back(w, r, returnTo, hostweb.Flash{}, q.flash("flash.error.not_archived", nil))
		return
	}
	if _, err := s.pool.Exec(ctx, entityUnarchiveSQL, q.id); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "entity_unarchived", "id="+idText); err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, returnTo, q.flash("flash.entities.restored", map[string]any{"name": name}), hostweb.Flash{})
}

// deleteEntity is POST /entities/{id}/delete (admin.py delete_entity).
func (s *server) deleteEntity(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx, owner := r.Context(), q.host.Workspace.ID
	_, archived, found, err := s.named(ctx, entityOwnedSQL, q.id, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if !found {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.no_such_entity", nil))
		return
	}
	if !archived {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.archive_entity_first", nil))
		return
	}
	used, err := s.count(ctx, entityUsedSQL, q.id, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if used > 0 {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.detach_properties_first", nil))
		return
	}
	invoiced, err := s.count(ctx, entityInvoicedSQL, q.id)
	if err != nil {
		fail(w, err)
		return
	}
	if invoiced > 0 {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.entity_has_invoices", nil))
		return
	}
	if _, err := s.pool.Exec(ctx, entityDeleteSQL, q.id); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "entity_deleted", "id="+strconv.FormatInt(q.id, 10)); err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, "/entities", q.flash("flash.entities.deleted", nil), hostweb.Flash{})
}

// archiveApartment is POST /apartments/{id}/archive (admin.py archive_apartment).
func (s *server) archiveApartment(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	idText := strconv.FormatInt(q.id, 10)
	name, archived, found, err := s.named(ctx, apartmentOwnedSQL, q.id, q.host.Workspace.ID)
	if err != nil {
		fail(w, err)
		return
	}
	if !found {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	if archived {
		q.back(w, r, "/apartments/"+idText, hostweb.Flash{}, q.flash("flash.error.already_archived", nil))
		return
	}
	returnTo := formReturnTo(r, "/apartments", false)
	if _, err := s.pool.Exec(ctx, aptArchiveSQL, stamp(q.at), q.id); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "apartment_archived", "id="+idText); err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, returnTo, q.flash("flash.apartments.archived", map[string]any{"name": name}), hostweb.Flash{})
}

// unarchiveApartment is POST /apartments/{id}/unarchive (admin.py unarchive_apartment).
func (s *server) unarchiveApartment(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	idText := strconv.FormatInt(q.id, 10)
	returnTo := formReturnTo(r, "/apartments/"+idText, false)
	_, archived, found, err := s.named(ctx, apartmentOwnedSQL, q.id, q.host.Workspace.ID)
	if err != nil {
		fail(w, err)
		return
	}
	if !found {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	if !archived {
		q.back(w, r, returnTo, hostweb.Flash{}, q.flash("flash.error.not_archived", nil))
		return
	}
	if _, err := s.pool.Exec(ctx, aptUnarchiveSQL, q.id); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "apartment_unarchived", "id="+idText); err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, returnTo, q.flash("flash.apartments.restored", nil), hostweb.Flash{})
}

// regeneratePIN is POST /apartments/{id}/regenerate-pin (admin.py regenerate_pin).
// The PIN stays out of the flash, as in Python.
func (s *server) regeneratePIN(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	idText := strconv.FormatInt(q.id, 10)
	_, _, found, err := s.named(ctx, apartmentOwnedSQL, q.id, q.host.Workspace.ID)
	if err != nil {
		fail(w, err)
		return
	}
	if !found {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	pin, err := newPermalinkPIN()
	if err != nil {
		fail(w, err)
		return
	}
	if _, err := s.pool.Exec(ctx, aptPINSQL, pin, q.id); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "pin_rotated", "apartment="+idText); err != nil {
		fail(w, err)
		return
	}
	returnTo := formReturnTo(r, "/apartments/"+idText+"?view=settings&section=guests#communication", false)
	if returnTo == "/apartments" {
		// 0098: safe_local_path drops the fragment, so land on the summaries row.
		returnTo = propertySummaries
	}
	q.back(w, r, returnTo, q.flash("flash.apartments.pin_rotated", nil), hostweb.Flash{})
}

// regenerateLink is POST /apartments/{id}/regenerate-link (admin.py regenerate_link).
func (s *server) regenerateLink(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	idText := strconv.FormatInt(q.id, 10)
	_, _, found, err := s.named(ctx, apartmentOwnedSQL, q.id, q.host.Workspace.ID)
	if err != nil {
		fail(w, err)
		return
	}
	if !found {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	token, err := newPermalinkToken()
	if err != nil {
		fail(w, err)
		return
	}
	pin, err := newPermalinkPIN()
	if err != nil {
		fail(w, err)
		return
	}
	if _, err := s.pool.Exec(ctx, aptLinkSQL, token, pin, q.id); err != nil {
		fail(w, err)
		return
	}
	// The old slugs go with the old token (guest_slug.rotate).
	if err := rotateSlug(ctx, s.pool, q.id, q.at); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "permalink_rotated", "apartment="+idText); err != nil {
		fail(w, err)
		return
	}
	returnTo := formReturnTo(r, "/apartments/"+idText+"?view=settings&section=guests#communication", false)
	q.back(w, r, returnTo, q.flash("flash.apartments.guest_link", nil), hostweb.Flash{})
}

// deleteFeed is POST /feeds/{id}/delete (admin.py delete_feed).
func (s *server) deleteFeed(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	var apartmentID int64
	err := s.pool.QueryRow(ctx, feedOwnedSQL, q.id, q.host.Workspace.ID).Scan(&apartmentID)
	if errors.Is(err, pgx.ErrNoRows) {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_calendar", nil))
		return
	}
	if err != nil {
		fail(w, err)
		return
	}
	if _, err := s.pool.Exec(ctx, feedDeleteSQL, q.id); err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, "/apartments/"+strconv.FormatInt(apartmentID, 10)+"?view=bookings#calendars",
		q.flash("flash.feeds.removed", nil), hostweb.Flash{})
}
