package guest

// Brief 1721: guest stay overview, claim landing/confirm, demo PIN preview.
// Python: App/app/routes/guest.py (demo_pin_preview, stay_overview, claim_landing, claim_confirm).
// Shell helpers (_open_link, _require_pin, PIN page) move to shell.go in brief 1720;
// minimal copies live here until 1720 lands so this package builds on its own.

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	claimStateUnclaimed   = "unclaimed"
	claimStateProvisional = "provisional"
	claimStateClaimed     = "claimed"

	claimConfirmRateMax = 20
	claimTokenBytes     = 24
)

// DoorCodeViewer is door_codes.view for one stay (*doorcodes.Service).
type DoorCodeViewer interface {
	ViewForStay(ctx context.Context, reservationID, apartmentID int64) (*doorcodes.Shown, error)
}

type stayClaimDeps struct {
	pool      *pgxpool.Pool
	getenv    func(string) string
	now       func() time.Time
	doorCodes DoorCodeViewer
}

type scApt struct {
	id, ownerID int64
	token, pin  string
	reachback   int
}

type scStay struct {
	id          int64
	apartmentID int64
	status      string
	source      string
	dateFrom    string
	dateTo      string
	override    *int64
	declared    *int64
	leadReduced *int64
}

type scClaim struct {
	state           string
	emailMasked     string
	tokenHash       string
	tokenVersion    int64
	guestAccessLock bool
	declaredGuests  *int64
}

// RegisterStayClaim wires brief 1721 routes (dormant until UBYHOST_GO_PATHS).
func RegisterStayClaim(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler, doorCodes DoorCodeViewer) {
	d := stayClaimDeps{pool: pool, getenv: getenv, now: now, doorCodes: doorCodes}
	mux.Handle("POST /l/{token}/{reservation_id}/claim/confirm", wrap("POST /l/{token}/{reservation_id}/claim/confirm", WithPOSTCSRF(getenv, now, d.claimConfirm)))
	mux.Handle("GET /l/{token}/{rest...}", wrap("GET /l/{token}/{rest...}", d.dispatchGET))
}

func (d stayClaimDeps) dispatchGET(w http.ResponseWriter, r *http.Request) {
	// guest.py error_page runs before any resolver: a shape Python has no route
	// for is bad_link carrying the key from the path, even for an unknown key.
	// Recognised shapes resolve through _open_link inside their own handler.
	lang := langFromRequest(r)
	token := strings.TrimSpace(r.PathValue("token"))
	rest := strings.Trim(strings.TrimSpace(r.PathValue("rest")), "/")
	switch {
	case strings.HasPrefix(rest, "demo/"):
		parts := strings.SplitN(strings.TrimPrefix(rest, "demo/"), "/", 2)
		if len(parts) != 1 || parts[0] == "" {
			d.badLink(w, r, lang, token)
			return
		}
		r.SetPathValue("reservation_id", parts[0])
		d.demoPreview(w, r)
	case strings.HasSuffix(rest, "/claim"):
		base := strings.TrimSuffix(rest, "/claim")
		if base == "" || strings.Contains(base, "/") {
			d.badLink(w, r, lang, token)
			return
		}
		r.SetPathValue("reservation_id", base)
		d.claimLanding(w, r)
	default:
		if rest == "" || strings.Contains(rest, "/") {
			d.badLink(w, r, lang, token)
			return
		}
		r.SetPathValue("reservation_id", rest)
		d.stayOverview(w, r)
	}
}

func (d stayClaimDeps) demoPreview(w http.ResponseWriter, r *http.Request) {
	lang := langFromRequest(r)
	token := strings.TrimSpace(r.PathValue("token"))
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		d.badLink(w, r, lang, token)
		return
	}
	if _, link, early := OpenLink(r, d.pool, token, lang); early != nil {
		early.ServeHTTP(w, r)
		return
	} else if link != "" {
		token = link
	}
	apt, stay, code := d.loadGuestStay(r.Context(), token, resID, false, true)
	if code != 0 {
		d.scWriteUnavailable(w, r, lang, token, code)
		return
	}
	if !d.access().hostOwns(r.Context(), r, apt.ownerID) {
		d.scWriteUnavailable(w, r, lang, token, http.StatusNotFound)
		return
	}
	if stay.source != "demo" {
		d.scWriteUnavailable(w, r, lang, token, http.StatusNotFound)
		return
	}
	// Brief 1720 owns the full PIN page; until then redirect through the hub path the tests expect.
	target := guestPath(token, resID) + langQuery(lang)
	d.redirectLang(w, r, target, lang)
}

func (d stayClaimDeps) stayOverview(w http.ResponseWriter, r *http.Request) {
	lang := langFromRequest(r)
	token := strings.TrimSpace(r.PathValue("token"))
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		d.badLink(w, r, lang, token)
		return
	}
	if _, link, early := OpenLink(r, d.pool, token, lang); early != nil {
		early.ServeHTTP(w, r)
		return
	} else if link != "" {
		token = link
	}
	if redir := d.pinRedirect(w, r, token, lang, resID); redir {
		return
	}
	apt, stay, code := d.loadGuestStay(r.Context(), token, resID, true, false)
	if code != 0 {
		d.scWriteUnavailable(w, r, lang, token, code)
		return
	}
	row, err := EnsureClaimRow(r.Context(), d.pool, resID, isoNow(d.now()))
	if err != nil {
		scError(w, err)
		return
	}
	if !GuestAccessOpen(stay.status, row.guestAccessLock) {
		d.scWriteUnavailable(w, r, lang, token, http.StatusNotFound)
		return
	}
	access := d.access()
	aptRow, _, _, found := ResolveKey(r.Context(), d.pool, token)
	if !found {
		aptRow = nil
	}
	if billingjob.MailEnabled() && !access.hostOwns(r.Context(), r, apt.ownerID) {
		if row.state != claimStateClaimed {
			d.renderClaimPage(w, r, token, lang, aptRow, stay, row)
			return
		}
		if !DeviceHoldsClaim(r, d.getenv, resID, row.tokenVersion) {
			d.renderAssignedPage(w, r, token, lang, aptRow, stay, row)
			return
		}
	}
	var guestCount int
	if err := d.pool.QueryRow(r.Context(), `SELECT COUNT(*) FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, resID).Scan(&guestCount); err != nil {
		scError(w, err)
		return
	}
	if guestCount == 0 {
		target := guestPath(token, resID) + "/new" + langQuery(lang)
		d.redirectLang(w, r, target, lang)
		return
	}
	d.renderStayPage(w, r, token, lang, aptRow, stay, row, billingjob.MailEnabled())
}

func (d stayClaimDeps) claimLanding(w http.ResponseWriter, r *http.Request) {
	lang := langFromRequest(r)
	token := strings.TrimSpace(r.PathValue("token"))
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		d.badLink(w, r, lang, token)
		return
	}
	// guest.py claim_landing: the PIN comes before the claim, so a link handed
	// to the wrong person cannot be claimed without it.
	if _, link, early := OpenLink(r, d.pool, token, lang); early != nil {
		early.ServeHTTP(w, r)
		return
	} else if link != "" {
		token = link
	}
	if redir := d.pinRedirect(w, r, token, lang, resID); redir {
		return
	}
	apt, stay, code := d.loadClaimable(r.Context(), token, resID)
	if code != 0 {
		d.scWriteUnavailable(w, r, lang, token, code)
		return
	}
	row, err := EnsureClaimRow(r.Context(), d.pool, resID, isoNow(d.now()))
	if err != nil {
		scError(w, err)
		return
	}
	if DeviceHoldsClaim(r, d.getenv, resID, row.tokenVersion) {
		d.redirectLang(w, r, guestPath(token, resID)+langQuery(lang), lang)
		return
	}
	_ = apt
	aptRow, _, _, _ := ResolveKey(r.Context(), d.pool, token)
	page := d.access().page(r.Context(), r, token, lang, aptRow)
	csrf, err := mintGuestPageCSRF(w, r, d.getenv, d.now())
	if err != nil {
		scError(w, err)
		return
	}
	view := confirmView{
		Page:       page,
		StayFrom:   stay.dateFrom,
		StayTo:     stay.dateTo,
		ClaimError: r.URL.Query().Get("claim_error") == "1",
		CSRFToken:  csrf,
		ActionURL:  guestPath(token, resID) + "/claim/confirm" + langQuery(lang),
	}
	d.access().renderPage(w, r, confirmSet, view, nil)
}

func (d stayClaimDeps) claimConfirm(w http.ResponseWriter, r *http.Request) {
	lang := langFromRequest(r)
	token := strings.TrimSpace(r.PathValue("token"))
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		d.badLink(w, r, lang, token)
		return
	}
	// guest.py _open_link: a POST on an earlier slug is served in place, and an
	// unknown key is the bad_link page, both before the form is read.
	if _, _, early := OpenLink(r, d.pool, token, lang); early != nil {
		early.ServeHTTP(w, r)
		return
	}
	if err := r.ParseForm(); err != nil {
		scError(w, err)
		return
	}
	secret := strings.TrimSpace(r.FormValue("secret"))
	apt, stay, code := d.loadClaimable(r.Context(), token, resID)
	if code != 0 || stay == nil || apt == nil {
		d.scWriteUnavailable(w, r, lang, token, code)
		return
	}
	key := clientip.Key(r, d.getenv, "claim:"+apt.token)
	at := d.now()
	if blocked, err := rateBlocked(r.Context(), d.pool, "claim_confirm", key, claimConfirmRateMax, int(time.Hour/time.Second), at); err != nil {
		scError(w, err)
		return
	} else if blocked {
		d.scWriteUnavailable(w, r, lang, token, http.StatusTooManyRequests)
		return
	}
	_ = rateRecord(r.Context(), d.pool, "claim_confirm", key, at)
	ok, err := confirmClaim(r.Context(), d.pool, resID, secret, apt, stay, at)
	if err != nil {
		scError(w, err)
		return
	}
	if !ok {
		target := guestPath(token, resID) + "/claim" + langQueryAmp(lang, "claim_error=1")
		d.redirectLang(w, r, target, lang)
		return
	}
	dec := guestSaveDecrypter(d.getenv)
	if _, err := ubyport.RefreshRegistrationCompletedAt(r.Context(), d.pool, resID, dec, d.now); err != nil {
		log.Printf("stay_claim: refresh registration: %v", err)
	}
	row, err := EnsureClaimRow(r.Context(), d.pool, resID, isoNow(at))
	if err != nil {
		scError(w, err)
		return
	}
	rememberClaim(w, r, d.getenv, resID, row.tokenVersion)
	d.redirectLang(w, r, guestPath(token, resID)+langQuery(lang), lang)
}

type claimPage struct {
	Token      string
	ResID      int64
	Stay       *scStay
	Claim      scClaim
	ClaimError bool
}

var guestTemplates = template.Must(template.New("guest").Parse(
	`{{define "claim"}}<!doctype html><html lang="{{.Lang}}"><head><title>claim</title></head><body class="guest-claim"></body></html>{{end}}` +
		`{{define "confirm"}}<!doctype html><html lang="{{.Lang}}"><head><title>confirm</title></head><body class="guest-confirm"></body></html>{{end}}` +
		`{{define "unavailable"}}<!doctype html><html lang="{{.Lang}}"><head><title>unavailable</title></head><body class="guest-unavailable"></body></html>{{end}}`,
))

func renderGuestPage(w http.ResponseWriter, name, lang string, data claimPage) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_ = guestTemplates.ExecuteTemplate(w, name, struct {
		Lang string
		Data claimPage
	}{Lang: lang, Data: data})
}

func (d stayClaimDeps) access() guestAccess {
	return guestAccess{pool: d.pool, getenv: d.getenv, now: d.now}
}

// renderClaimPage is guest/claim.html with stay_overview's context: the guest
// count ask and the e-mail the stay's link goes to.
func (d stayClaimDeps) renderClaimPage(w http.ResponseWriter, r *http.Request, token, lang string, apt *Apartment, stay *scStay, row scClaim) {
	page := d.access().page(r.Context(), r, token, lang, apt)
	declared := int64(1)
	if row.declaredGuests != nil && *row.declaredGuests > 0 {
		declared = *row.declaredGuests
	}
	csrf, err := mintGuestPageCSRF(w, r, d.getenv, d.now())
	if err != nil {
		scError(w, err)
		return
	}
	view := claimView{
		Page:             page,
		StayFrom:         stay.dateFrom,
		StayTo:           stay.dateTo,
		CanPickOther:     canPickOtherStays(r.Context(), d.pool, apt, d.now),
		BackURL:          GuestLink(token, 0, "") + LangQuery(page.Lang, ""),
		ClaimSent:        r.URL.Query().Get("claim_sent") == "1",
		ClaimErrorText:   claimErrorText(page.Lang, r.URL.Query().Get("claim_error")),
		ClaimEmailMasked: row.emailMasked,
		DeclaredGuests:   declared,
		CSRFToken:        csrf,
		ActionURL:        guestPath(token, stay.id) + "/party" + langQuery(page.Lang),
	}
	d.access().renderPage(w, r, claimSet, view, map[string]string{"Cache-Control": "no-store"})
}

// badLink is guest.py error_page: a path under /l/ no route matches gets the
// bad_link page with the key from the path, so it still offers "start again".
func (d stayClaimDeps) badLink(w http.ResponseWriter, r *http.Request, lang, token string) {
	d.access().unavailable(w, r, lang, "bad_link", http.StatusNotFound, token, 0, nil)
}

// scWriteUnavailable is guest.py _unavailable, chosen by the status the guard returned.
func (d stayClaimDeps) scWriteUnavailable(w http.ResponseWriter, r *http.Request, lang, token string, status int) {
	d.access().unavailable(w, r, lang, reasonForStatus(status), status, token, 0, nil)
}

// reasonForStatus maps a guard's status onto the reason whose words it shows.
func reasonForStatus(status int) string {
	switch status {
	case http.StatusTooManyRequests:
		return "rate_limited"
	case http.StatusInternalServerError:
		return "server_error"
	default:
		return "stay_gone"
	}
}

func scError(w http.ResponseWriter, err error) {
	log.Printf("guest stay_claim: %v", err)
	http.Error(w, "error", http.StatusInternalServerError)
}

func (d stayClaimDeps) loadGuestStay(ctx context.Context, token string, resID int64, pinOk, demoOnly bool) (*scApt, *scStay, int) {
	return LoadGuestStay(ctx, d.pool, token, resID, pinOk, demoOnly)
}

// LoadGuestStay is guest.py stay resolution for permalink routes (demo/pin gates).
func LoadGuestStay(ctx context.Context, pool *pgxpool.Pool, token string, resID int64, pinOk, demoOnly bool) (*scApt, *scStay, int) {
	apt, err := scLoadApartment(ctx, pool, token)
	if err != nil || apt == nil {
		return nil, nil, http.StatusNotFound
	}
	stay, err := loadReservation(ctx, pool, resID, apt.id)
	if err != nil || stay == nil || stay.status != "active" {
		return nil, nil, http.StatusNotFound
	}
	if demoOnly && stay.source != "demo" {
		return nil, nil, http.StatusNotFound
	}
	if !demoOnly && stay.source == "demo" && !pinOk {
		return nil, nil, http.StatusNotFound
	}
	return apt, stay, 0
}

func (d stayClaimDeps) loadClaimable(ctx context.Context, token string, resID int64) (*scApt, *scStay, int) {
	apt, stay, code := d.loadGuestStay(ctx, token, resID, false, false)
	if code != 0 {
		return nil, nil, code
	}
	if stay.source == "demo" {
		return nil, nil, http.StatusNotFound
	}
	if !GuestAccessOpen(stay.status, false) {
		return nil, nil, http.StatusNotFound
	}
	return apt, stay, 0
}

func (d stayClaimDeps) pinRedirect(w http.ResponseWriter, r *http.Request, token, lang string, resID int64) bool {
	if !guestPinRequired(d.getenv) {
		return false
	}
	apt, err := scLoadApartment(r.Context(), d.pool, token)
	if err != nil || apt == nil {
		return false
	}
	if d.access().hostOwns(r.Context(), r, apt.ownerID) {
		return false
	}
	expected := strings.TrimSpace(apt.pin)
	lockToken := apt.token
	if lockToken == "" {
		lockToken = token
	}
	if PinSessionValid(r, d.getenv, lockToken, expected, d.now()) {
		return false
	}
	returnTo := r.URL.Path
	if r.URL.RawQuery != "" {
		returnTo += "?" + r.URL.RawQuery
	}
	if safe := safeReturnTo(returnTo, token, lang); safe != "" {
		returnTo = safe
	}
	// Hub PIN page honours return_to after verifyPin.
	target := "/l/" + url.PathEscape(token) +
		langQueryAmp(lang, "return_to="+url.QueryEscape(returnTo))
	d.redirectLang(w, r, target, lang)
	return true
}

func scLoadApartment(ctx context.Context, pool *pgxpool.Pool, key string) (*scApt, error) {
	if pool == nil {
		return nil, nil
	}
	apt, _, _, ok := ResolveKey(ctx, pool, key)
	if !ok || apt == nil {
		return nil, nil
	}
	var a scApt
	err := pool.QueryRow(ctx, `SELECT id, owner_user_id, COALESCE(permalink_token,''), COALESCE(permalink_pin,''),
		COALESCE(permalink_reachback_days,0) FROM apartment WHERE id = $1 AND active = 1 AND archived_at IS NULL`,
		apt.ID).Scan(&a.id, &a.ownerID, &a.token, &a.pin, &a.reachback)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

func loadReservation(ctx context.Context, pool *pgxpool.Pool, resID, aptID int64) (*scStay, error) {
	var s scStay
	err := pool.QueryRow(ctx, `SELECT id, apartment_id, status, COALESCE(source,''), COALESCE(date_from::text,''), COALESCE(date_to::text,''),
		expected_guests_override, declared_guests, lead_reduced_guests
		FROM reservation WHERE id = $1 AND apartment_id = $2 AND archived_at IS NULL`,
		resID, aptID).Scan(&s.id, &s.apartmentID, &s.status, &s.source, &s.dateFrom, &s.dateTo, &s.override, &s.declared, &s.leadReduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &s, nil
}

// EnsureClaimRow is claim.ensure_row.
func EnsureClaimRow(ctx context.Context, pool *pgxpool.Pool, resID int64, stamp string) (scClaim, error) {
	var c scClaim
	var locked *string
	var hash *string
	err := pool.QueryRow(ctx, `SELECT state, COALESCE(email_masked,''), token_hash, COALESCE(token_version,0),
		guest_access_locked_at, declared_guests FROM reservation_claim WHERE reservation_id = $1`, resID).
		Scan(&c.state, &c.emailMasked, &hash, &c.tokenVersion, &locked, &c.declaredGuests)
	if errors.Is(err, pgx.ErrNoRows) {
		if _, err := pool.Exec(ctx, `INSERT INTO reservation_claim (reservation_id, state, token_version, created_at, updated_at)
			VALUES ($1, $2, 0, $3, $3)`, resID, claimStateUnclaimed, stamp); err != nil {
			return c, err
		}
		return EnsureClaimRow(ctx, pool, resID, stamp)
	}
	if err != nil {
		return c, err
	}
	if hash != nil {
		c.tokenHash = *hash
	}
	c.guestAccessLock = locked != nil && *locked != ""
	return c, nil
}

// GuestAccessOpen is claim.guest_access_open.
func GuestAccessOpen(status string, locked bool) bool {
	return status == "active" && !locked
}

// DeviceHoldsClaim is guest.py _device_holds_claim.
func DeviceHoldsClaim(r *http.Request, getenv func(string) string, resID, version int64) bool {
	if r == nil || getenv == nil || resID <= 0 {
		return false
	}
	gen, ok := claimedClaims(r, getenv)[resID]
	return ok && gen == version
}

func rememberClaim(w http.ResponseWriter, r *http.Request, getenv func(string) string, resID, version int64) {
	if w == nil || getenv == nil || resID <= 0 {
		return
	}
	held := claimedClaims(r, getenv)
	held[resID] = version
	keys := make([]int64, 0, len(held))
	for id := range held {
		keys = append(keys, id)
	}
	sort.Slice(keys, func(i, j int) bool { return keys[i] < keys[j] })
	if len(keys) > 40 {
		keys = keys[len(keys)-40:]
	}
	kept := make(map[string]int64, len(keys))
	for _, id := range keys {
		kept[strconv.FormatInt(id, 10)] = held[id]
	}
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return
	}
	tok, err := urlSafeDumps(secret, claimCookieSalt, kept)
	if err != nil {
		return
	}
	http.SetCookie(w, &http.Cookie{
		Name:     claimCookieName,
		Value:    tok,
		Path:     "/",
		MaxAge:   60 * 60 * 24 * 60,
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   hostweb.SecureCookies(getenv),
	})
}

func confirmClaim(ctx context.Context, pool *pgxpool.Pool, resID int64, secret string, apt *scApt, stay *scStay, at time.Time) (bool, error) {
	if secret == "" || apt == nil {
		return false, nil
	}
	stamp := isoNow(at)
	hash := claimTokenHash(secret)
	tx, err := pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "reservation", int32(resID)); err != nil {
		return false, err
	}
	var state string
	var declared *int64
	var version int64
	var curHash *string
	if err := tx.QueryRow(ctx, `SELECT state, declared_guests, token_version, token_hash FROM reservation_claim WHERE reservation_id = $1 FOR UPDATE`,
		resID).Scan(&state, &declared, &version, &curHash); err != nil {
		return false, err
	}
	tag, err := tx.Exec(ctx, `UPDATE reservation_claim SET state = $1, claimed_at = $2, token_hash = NULL,
		provisional_until = NULL, updated_at = $2
		WHERE reservation_id = $3 AND token_hash = $4 AND token_version = $5 AND state IN ($6, $7)`,
		claimStateClaimed, stamp, resID, hash, version, claimStateProvisional, claimStateClaimed)
	if err != nil {
		return false, err
	}
	if tag.RowsAffected() != 1 {
		return false, nil
	}
	if state == claimStateProvisional && declared != nil && *declared > 0 {
		exp := headcount.Expected(stay.override, stay.declared, stay.leadReduced)
		target := int(*declared)
		if exp != nil && int(*exp) > target {
			target = int(*exp)
		}
		if _, err := tx.Exec(ctx, `UPDATE reservation SET declared_guests = $1 WHERE id = $2`, target, resID); err != nil {
			return false, err
		}
	}
	if _, err := tx.Exec(ctx, `UPDATE reservation_claim SET declared_guests = NULL WHERE reservation_id = $1`, resID); err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, tx.Commit(ctx)
}

func claimTokenHash(secret string) string {
	h := sha256.Sum256([]byte(secret))
	return hex.EncodeToString(h[:])
}

func guestSaveDecrypter(getenv func(string) string) ubyport.FieldDecrypter {
	var keys *secure.MultiFernet
	return func(token string) (string, error) {
		if token == "" {
			return "", nil
		}
		if keys == nil {
			k, err := secure.LoadDataKeys(getenv)
			if err != nil {
				return "", err
			}
			keys = k
		}
		b, err := keys.Decrypt(token, 0, time.Now())
		return string(b), err
	}
}

// langFromRequest is guest.py _language: ?lang=, the guest cookie, then
// Accept-Language, always a code the guest catalog speaks.
func langFromRequest(r *http.Request) string {
	return Language(r)
}

func guestPath(token string, resID int64) string {
	return fmt.Sprintf("/l/%s/%d", token, resID)
}

// langQuery is guest.py _lang_q: the language always rides along, Czech too.
// Dropping it for "cs" lost the guest's choice on every redirect and link,
// because a bare URL falls back to the cookie and then Accept-Language.
// redirectLang is guest.py _with_lang(RedirectResponse(...)): the choice is
// remembered on the response and carried in the URL, so neither the cookie nor
// a later bare link can drop the guest back into English.
func (d stayClaimDeps) redirectLang(w http.ResponseWriter, r *http.Request, loc, lang string) {
	if lang != "" {
		WithLang(w, getenvOr(d.getenv), lang)
	}
	http.Redirect(w, r, loc, http.StatusSeeOther)
}

func getenvOr(getenv func(string) string) func(string) string {
	if getenv != nil {
		return getenv
	}
	return func(string) string { return "" }
}

func langQuery(lang string) string {
	if lang == "" {
		return ""
	}
	return LangQuery(lang, "")
}

func langQueryAmp(lang, extra string) string {
	if lang == "" {
		return "?" + extra
	}
	return LangQuery(lang, "&"+extra)
}

func isoNow(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05+00:00")
}

func newClaimSecret() (string, error) {
	b := make([]byte, claimTokenBytes)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

// CookieHeld decodes the ubyhost_claim map for tests (brief 1720 owns production cookie).
func CookieHeld(raw string) map[int64]int64 {
	out := map[int64]int64{}
	if raw == "" {
		return out
	}
	_ = json.Unmarshal([]byte(raw), &out)
	return out
}
