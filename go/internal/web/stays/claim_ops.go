package stays

// Brief 1732: POST claim and manual-filing routes from App/app/routes/admin.py
// (reopen-guest, resend-claim, release-claim, filed-by-hand, undo). Python:
// claim.reopen_guest_access, claim.resend_to_verified_email, claim.release,
// reporting.mark_filed_by_hand, reporting.undo_filed_by_hand.

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	_ "time/tzdata"
)

const (
	claimStateUnclaimed   = "unclaimed"
	claimStateProvisional = "provisional"
	claimStateClaimed     = "claimed"

	claimResendCooldown   = 60 * time.Second
	claimHoldMinutes      = 30
	claimTokenBytes       = 24
	claimMailRecipientMax = 5
	claimMailRecipientWin = 3600
	claimMailStayMax      = 8
	claimMailStayWin      = 3600
	claimSecretMarker     = "{{claim_secret}}"
	manualRefMax          = 200
	manualUndoWindow      = 24 * time.Hour
	manualFiledMaxAge     = 60 * 24 * time.Hour
	manualFiledMaxAhead   = 5 * time.Minute
	pragueTZ              = "Europe/Prague"
)

var handFilableStates = map[string]bool{"pending": true, "error": true, "blocked": true}

var claimResendErrors = map[string]string{
	"not_claimed":    "flash.error.claim_resend_not_claimed",
	"locked":         "flash.error.claim_resend_locked",
	"cooldown":       "flash.error.claim_resend_cooldown",
	"recipient_rate": "flash.error.claim_resend_recipient_rate",
}

const claimResendFailed = "flash.error.claim_resend_failed"

const auditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
	VALUES ($1, $2, $3, $4, $5, $6, $7)`

type claimOpsDeps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

type claimStay struct {
	id                              int64
	apartmentID                     int64
	status, source                  string
	declared, override, leadReduced *int64
}

type claimApt struct {
	id, ownerID     int64
	permalink, name string
	legalEntityID   *int64
}

type claimCall struct {
	claimOpsDeps
	w     http.ResponseWriter
	r     *http.Request
	at    time.Time
	lang  string
	host  *session.Host
	resID int64
}

func (d claimOpsDeps) enter(w http.ResponseWriter, r *http.Request, resID int64) *claimCall {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return nil
	}
	_ = r.ParseForm()
	h, err := hostweb.Login(w, r, d.pool, d.getenv, at)
	if err != nil {
		claimServerError(w, err)
		return nil
	}
	if h == nil {
		return nil
	}
	return &claimCall{claimOpsDeps: d, w: w, r: r, at: at, lang: hostweb.Lang(r), host: h, resID: resID}
}

func (c *claimCall) flashes(key string, params map[string]any) hostweb.Flash {
	text := hostweb.HostStrings.T(c.lang, key, params)
	if text == key {
		text = catalog.T(c.lang, key, params)
	}
	return hostweb.Flash{Text: text, Key: key}
}

func (c *claimCall) audit(ctx context.Context, action, detail string) error {
	var impersonator any
	if c.host.Impersonating {
		impersonator = c.host.Account.ID
	}
	owner := c.host.Workspace.ID
	_, err := c.pool.Exec(ctx, auditSQL, isoStamp(c.at), c.host.Account.Username, action, detail,
		owner, c.host.Account.ID, impersonator)
	return err
}

func claimServerError(w http.ResponseWriter, err error) {
	log.Printf("stays claim_ops: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

func (c *claimCall) loadStay(ctx context.Context) (*claimStay, bool, error) {
	var s claimStay
	err := c.pool.QueryRow(ctx, `SELECT r.id, r.apartment_id, r.status, COALESCE(r.source,''),
		r.declared_guests, r.expected_guests_override, r.lead_reduced_guests
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`,
		c.resID, c.host.Workspace.ID).Scan(&s.id, &s.apartmentID, &s.status, &s.source,
		&s.declared, &s.override, &s.leadReduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return &s, true, nil
}

func (c *claimCall) loadApartment(ctx context.Context, id int64) (*claimApt, error) {
	var a claimApt
	err := c.pool.QueryRow(ctx, `SELECT id, owner_user_id, COALESCE(permalink_token,''),
		COALESCE(internal_name,''), legal_entity_id FROM apartment WHERE id = $1`, id).
		Scan(&a.id, &a.ownerID, &a.permalink, &a.name, &a.legalEntityID)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return &a, err
}

func isDemoStaySource(source string) bool { return source == "demo" }

// RegisterClaimOps wires the five POST routes (dormant until UBYHOST_GO_PATHS).
func RegisterClaimOps(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := claimOpsDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /reservations/{reservation_id}/reopen-guest", wrap("/reservations/{reservation_id}/reopen-guest", reopenGuestHandler(d)))
	mux.Handle("POST /reservations/{reservation_id}/resend-claim", wrap("/reservations/{reservation_id}/resend-claim", resendClaimHandler(d)))
	mux.Handle("POST /reservations/{reservation_id}/release-claim", wrap("/reservations/{reservation_id}/release-claim", releaseClaimHandler(d)))
	mux.Handle("POST /reservations/{reservation_id}/filed-by-hand", wrap("/reservations/{reservation_id}/filed-by-hand", filedByHandHandler(d)))
	mux.Handle("POST /reservations/{reservation_id}/filed-by-hand/undo", wrap("/reservations/{reservation_id}/filed-by-hand/undo", filedByHandUndoHandler(d)))
}

func parseClaimID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return 0, false
	}
	return id, true
}

func reopenGuestHandler(d claimOpsDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseClaimID(w, r)
		if !ok {
			return
		}
		c := d.enter(w, r, id)
		if c == nil {
			return
		}
		ctx := r.Context()
		st, found, err := c.loadStay(ctx)
		if err != nil {
			claimServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flashes("flash.error.no_such_stay", nil))
			return
		}
		_ = st
		stamp := isoStamp(c.at)
		if _, err := c.pool.Exec(ctx, `UPDATE reservation_claim SET guest_access_locked_at = NULL,
			guest_access_reopened_at = $1, updated_at = $1 WHERE reservation_id = $2`, stamp, id); err != nil {
			claimServerError(w, err)
			return
		}
		if err := c.audit(ctx, "guest_access_reopened", fmt.Sprintf("reservation=%d", id)); err != nil {
			claimServerError(w, err)
			return
		}
		hostweb.Back(w, r, fmt.Sprintf("/reservations/%d", id), c.flashes("flash.reservations.access_reopened", nil), hostweb.Flash{})
	}
}

func releaseClaimHandler(d claimOpsDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseClaimID(w, r)
		if !ok {
			return
		}
		c := d.enter(w, r, id)
		if c == nil {
			return
		}
		ctx := r.Context()
		st, found, err := c.loadStay(ctx)
		if err != nil {
			claimServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flashes("flash.error.no_such_stay", nil))
			return
		}
		_ = st
		stamp := isoStamp(c.at)
		if _, err := c.pool.Exec(ctx, `UPDATE reservation_claim SET state = $1, email = NULL, email_masked = NULL,
			token_hash = NULL, token_version = token_version + 1, provisional_until = NULL, claimed_at = NULL,
			guest_access_locked_at = NULL, guest_access_reopened_at = $2, updated_at = $2 WHERE reservation_id = $3`,
			claimStateUnclaimed, stamp, id); err != nil {
			claimServerError(w, err)
			return
		}
		if err := c.audit(ctx, "guest_claim_released", fmt.Sprintf("reservation=%d", id)); err != nil {
			claimServerError(w, err)
			return
		}
		hostweb.Back(w, r, fmt.Sprintf("/reservations/%d", id), c.flashes("flash.reservations.claim_released", nil), hostweb.Flash{})
	}
}

func resendClaimHandler(d claimOpsDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseClaimID(w, r)
		if !ok {
			return
		}
		c := d.enter(w, r, id)
		if c == nil {
			return
		}
		ctx := r.Context()
		st, found, err := c.loadStay(ctx)
		if err != nil {
			claimServerError(w, err)
			return
		}
		back := fmt.Sprintf("/reservations/%d", id)
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flashes("flash.error.no_such_stay", nil))
			return
		}
		if !billingjob.MailEnabled() {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flashes("flash.error.claim_resend_mail_off", nil))
			return
		}
		if isDemoStaySource(st.source) {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flashes(claimResendFailed, nil))
			return
		}
		apt, err := c.loadApartment(ctx, st.apartmentID)
		if err != nil {
			claimServerError(w, err)
			return
		}
		if apt == nil {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flashes("flash.error.no_such_stay", nil))
			return
		}
		okSend, code, err := resendToVerifiedEmail(ctx, c.claimOpsDeps, st, apt, c.at)
		if err != nil {
			claimServerError(w, err)
			return
		}
		if !okSend {
			key := claimResendErrors[code]
			if key == "" {
				key = claimResendFailed
			}
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flashes(key, nil))
			return
		}
		if err := c.audit(ctx, "guest_claim_resent", fmt.Sprintf("reservation=%d", id)); err != nil {
			claimServerError(w, err)
			return
		}
		hostweb.Back(w, r, back, c.flashes("flash.reservations.claim_resent", nil), hostweb.Flash{})
	}
}

func filedByHandHandler(d claimOpsDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseClaimID(w, r)
		if !ok {
			return
		}
		c := d.enter(w, r, id)
		if c == nil {
			return
		}
		ctx := r.Context()
		st, found, err := c.loadStay(ctx)
		if err != nil {
			claimServerError(w, err)
			return
		}
		back := fmt.Sprintf("/reservations/%d#reports", id)
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flashes("flash.error.no_such_stay", nil))
			return
		}
		if isDemoStaySource(st.source) {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flashes("hint.demo_stay", nil))
			return
		}
		filedAt := parseManualFiledAt(formStr(r, "filed_at"), c.at)
		if filedAt == "" {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flashes("flash.error.hand_filing_time", nil))
			return
		}
		ref := cleanManualReference(formStr(r, "reference"))
		res, err := markFiledByHand(ctx, c.pool, id, filedAt, ref, c.at)
		if err != nil {
			claimServerError(w, err)
			return
		}
		if res.Marked == 0 {
			key := "flash.error.hand_filing_nothing"
			if res.Busy > 0 {
				key = "flash.error.hand_filing_busy"
			}
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flashes(key, nil))
			return
		}
		detail := fmt.Sprintf("reservation=%d guests=%d filed_at=%s", id, res.Marked, filedAt)
		if res.Busy > 0 {
			detail += fmt.Sprintf(" busy=%d", res.Busy)
			if ref != "" {
				detail += " reference=" + ref
			}
		} else if ref != "" {
			detail += " reference=" + ref
		}
		if err := c.audit(ctx, "stay_filed_manually", detail); err != nil {
			claimServerError(w, err)
			return
		}
		hostweb.Back(w, r, back, c.flashes("flash.hand_filing.marked", nil), hostweb.Flash{})
	}
}

func filedByHandUndoHandler(d claimOpsDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseClaimID(w, r)
		if !ok {
			return
		}
		c := d.enter(w, r, id)
		if c == nil {
			return
		}
		ctx := r.Context()
		_, found, err := c.loadStay(ctx)
		if err != nil {
			claimServerError(w, err)
			return
		}
		back := fmt.Sprintf("/reservations/%d#reports", id)
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flashes("flash.error.no_such_stay", nil))
			return
		}
		undone, err := undoFiledByHand(ctx, c.pool, id, c.at)
		if err != nil {
			claimServerError(w, err)
			return
		}
		if len(undone) == 0 {
			hostweb.Back(w, r, back, hostweb.Flash{}, c.flashes("flash.error.hand_filing_undo_closed", nil))
			return
		}
		if err := c.audit(ctx, "stay_filed_manually_undone", fmt.Sprintf("reservation=%d guests=%d", id, len(undone))); err != nil {
			claimServerError(w, err)
			return
		}
		hostweb.Back(w, r, back, c.flashes("flash.hand_filing.undone", nil), hostweb.Flash{})
	}
}

type markResult struct {
	Marked int
	Busy   int
}

func parseManualFiledAt(raw string, now time.Time) string {
	loc, err := time.LoadLocation(pragueTZ)
	if err != nil {
		return ""
	}
	current := now.UTC()
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return current.Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
	}
	var local time.Time
	if strings.Contains(raw, "T") {
		local, err = time.ParseInLocation("2006-01-02T15:04", raw, loc)
	} else {
		local, err = time.ParseInLocation("2006-01-02 15:04", raw, loc)
	}
	if err != nil {
		return ""
	}
	when := local.UTC().Truncate(time.Second)
	if when.Sub(current) > manualFiledMaxAhead || current.Sub(when) > manualFiledMaxAge {
		return ""
	}
	return when.Format("2006-01-02T15:04:05") + "+00:00"
}

func cleanManualReference(raw string) string {
	text := strings.Join(strings.Fields(raw), " ")
	if text == "" {
		return ""
	}
	r := []rune(text)
	if len(r) > manualRefMax {
		text = string(r[:manualRefMax])
	}
	return text
}

func markFiledByHand(ctx context.Context, pool *pgxpool.Pool, reservationID int64, filedAt, reference string, now time.Time) (markResult, error) {
	var out markResult
	markedAt := isoStamp(now)
	liveAfter := now.UTC().Unix() - int64(ubyport.SubmissionClaimTTL.Seconds())
	tx, err := pool.Begin(ctx)
	if err != nil {
		return out, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	rows, err := tx.Query(ctx, `SELECT id FROM guest WHERE reservation_id = $1 ORDER BY id`, reservationID)
	if err != nil {
		return out, err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return out, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	for _, id := range ids {
		if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "guest", int32(id)); err != nil {
			return out, err
		}
	}
	grows, err := tx.Query(ctx, `SELECT id, submit_state, nationality FROM guest
		WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id`, reservationID)
	if err != nil {
		return out, err
	}
	type guestHandRow struct {
		id          int64
		state       string
		nationality string
	}
	var handGuests []guestHandRow
	for grows.Next() {
		var row guestHandRow
		if err := grows.Scan(&row.id, &row.state, &row.nationality); err != nil {
			grows.Close()
			return out, err
		}
		if !handFilableStates[row.state] || !validation.GuestIsReportable(row.nationality) {
			continue
		}
		handGuests = append(handGuests, row)
	}
	if err := grows.Err(); err != nil {
		grows.Close()
		return out, err
	}
	grows.Close()
	for _, row := range handGuests {
		var busy int
		if err := tx.QueryRow(ctx, `SELECT 1 FROM submission_claim WHERE guest_id = $1 AND claimed_at >= $2`,
			row.id, float64(liveAfter)).Scan(&busy); err == nil {
			out.Busy++
			continue
		} else if !errors.Is(err, pgx.ErrNoRows) {
			return out, err
		}
		var ref any
		if reference != "" {
			ref = reference
		}
		tag, err := tx.Exec(ctx, `UPDATE guest SET submit_state = 'sent', manual_filed_at = $1, manual_reference = $2,
			manual_marked_at = $3, manual_prev_state = $4
			WHERE id = $5 AND submit_state = $6`, filedAt, ref, markedAt, row.state, row.id, row.state)
		if err != nil {
			return out, err
		}
		if tag.RowsAffected() == 1 {
			out.Marked++
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return out, err
	}
	return out, nil
}

func undoFiledByHand(ctx context.Context, pool *pgxpool.Pool, reservationID int64, now time.Time) ([]int64, error) {
	current := now.UTC()
	var undone []int64
	tx, err := pool.Begin(ctx)
	if err != nil {
		return nil, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	rows, err := tx.Query(ctx, `SELECT id FROM guest WHERE reservation_id = $1 ORDER BY id`, reservationID)
	if err != nil {
		return nil, err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return nil, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	for _, id := range ids {
		if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "guest", int32(id)); err != nil {
			return nil, err
		}
	}
	grows, err := tx.Query(ctx, `SELECT id, manual_marked_at, manual_prev_state FROM guest
		WHERE reservation_id = $1 AND submit_state = 'sent' AND manual_filed_at IS NOT NULL ORDER BY id`, reservationID)
	if err != nil {
		return nil, err
	}
	defer grows.Close()
	for grows.Next() {
		var gid int64
		var markedAt string
		var prev *string
		if err := grows.Scan(&gid, &markedAt, &prev); err != nil {
			return nil, err
		}
		marked, err := time.Parse(time.RFC3339, strings.ReplaceAll(markedAt, "Z", "+00:00"))
		if err != nil {
			continue
		}
		if current.Sub(marked.UTC()) < 0 || current.Sub(marked.UTC()) > manualUndoWindow {
			continue
		}
		previous := "pending"
		if prev != nil && handFilableStates[*prev] {
			previous = *prev
		}
		tag, err := tx.Exec(ctx, `UPDATE guest SET submit_state = $1, manual_filed_at = NULL, manual_reference = NULL,
			manual_marked_at = NULL, manual_prev_state = NULL
			WHERE id = $2 AND submit_state = 'sent' AND manual_marked_at = $3`, previous, gid, markedAt)
		if err != nil {
			return nil, err
		}
		if tag.RowsAffected() == 1 {
			undone = append(undone, gid)
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, err
	}
	return undone, nil
}

func resendToVerifiedEmail(ctx context.Context, d claimOpsDeps, st *claimStay, apt *claimApt, at time.Time) (bool, string, error) {
	_, _ = mailjob.ExpireHolds(ctx, d.pool, at)
	row, err := ensureClaimRow(ctx, d.pool, st.id, isoStamp(at))
	if err != nil {
		return false, "", err
	}
	if row.State != claimStateClaimed {
		return false, "not_claimed", nil
	}
	if !guestAccessOpen(st.status, row.GuestAccessLocked) {
		return false, "locked", nil
	}
	addr := ubyport.NormaliseEmail(row.Email)
	if addr == "" {
		return false, "not_claimed", nil
	}
	party := declaredCount(st, row.DeclaredGuests)
	lang := row.Lang
	if lang == "" {
		lang = "cs"
	}
	ok, code, _, err := startClaimResend(ctx, d, st, apt, row, addr, party, lang, at)
	return ok, code, err
}

type claimRow struct {
	State, Email, Lang string
	TokenVersion       int64
	ProvisionalUntil   *string
	GuestAccessLocked  bool
	DeclaredGuests     *int64
	UpdatedAt          string
}

func ensureClaimRow(ctx context.Context, pool *pgxpool.Pool, resID int64, stamp string) (*claimRow, error) {
	var r claimRow
	var locked *string
	err := pool.QueryRow(ctx, `SELECT state, COALESCE(email,''), COALESCE(lang,''), COALESCE(token_version,0),
		provisional_until, guest_access_locked_at, declared_guests, updated_at
		FROM reservation_claim WHERE reservation_id = $1`, resID).Scan(
		&r.State, &r.Email, &r.Lang, &r.TokenVersion, &r.ProvisionalUntil, &locked, &r.DeclaredGuests, &r.UpdatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		if _, err := pool.Exec(ctx, `INSERT INTO reservation_claim (reservation_id, state, token_version, created_at, updated_at)
			VALUES ($1, $2, 0, $3, $3)`, resID, claimStateUnclaimed, stamp); err != nil {
			return nil, err
		}
		return ensureClaimRow(ctx, pool, resID, stamp)
	}
	if err != nil {
		return nil, err
	}
	r.GuestAccessLocked = locked != nil && *locked != ""
	return &r, nil
}

func guestAccessOpen(status string, locked bool) bool {
	return status == "active" && !locked
}

func declaredCount(st *claimStay, declared *int64) int {
	exp := headcount.Expected(st.override, st.declared, st.leadReduced)
	if exp != nil && *exp > 0 {
		return int(*exp)
	}
	if declared != nil && *declared > 0 {
		return int(*declared)
	}
	return 1
}

func claimTokenHash(secret string) string {
	h := sha256.Sum256([]byte(secret))
	return hex.EncodeToString(h[:])
}

func newClaimSecret() (string, error) {
	b := make([]byte, claimTokenBytes)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

func resendTooSoon(updatedAt string, now time.Time) bool {
	t, err := time.Parse(time.RFC3339, strings.ReplaceAll(updatedAt, "Z", "+00:00"))
	if err != nil {
		return false
	}
	return now.UTC().Sub(t.UTC()) < claimResendCooldown
}

func claimMailBlocked(ctx context.Context, pool *pgxpool.Pool, resID int64, addr string, now time.Time) (string, error) {
	recKey := "claim_to:" + hex.EncodeToString(sha256Sum([]byte(addr)))
	if blocked, err := rateBlocked(ctx, pool, "claim_mail_recipient", recKey, claimMailRecipientMax, claimMailRecipientWin, now); err != nil {
		return "", err
	} else if blocked {
		return "recipient_rate", nil
	}
	stKey := fmt.Sprintf("claim_res:%d", resID)
	if blocked, err := rateBlocked(ctx, pool, "claim_mail_reservation", stKey, claimMailStayMax, claimMailStayWin, now); err != nil {
		return "", err
	} else if blocked {
		return "rate", nil
	}
	return "", nil
}

func sha256Sum(b []byte) []byte {
	h := sha256.Sum256(b)
	return h[:]
}

func rateBlocked(ctx context.Context, pool *pgxpool.Pool, scope, key string, max int, window time.Duration, now time.Time) (bool, error) {
	cutoff := float64(now.UTC().Unix()) - window.Seconds()
	if _, err := pool.Exec(ctx, `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`, scope, key, cutoff); err != nil {
		return false, err
	}
	var n int64
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`, scope, key).Scan(&n); err != nil {
		return false, err
	}
	return n >= int64(max), nil
}

func rateRecord(ctx context.Context, pool *pgxpool.Pool, scope, key string, now time.Time) error {
	_, err := pool.Exec(ctx, `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`, scope, key, float64(now.UTC().Unix()))
	return err
}

func startClaimResend(ctx context.Context, d claimOpsDeps, st *claimStay, apt *claimApt, row *claimRow, addr string, party int, lang string, at time.Time) (bool, string, string, error) {
	if resendTooSoon(row.UpdatedAt, at) {
		return false, "cooldown", "", nil
	}
	if code, err := claimMailBlocked(ctx, d.pool, st.id, addr, at); err != nil {
		return false, "", "", err
	} else if code != "" {
		return false, code, "", nil
	}
	secret, err := newClaimSecret()
	if err != nil {
		return false, "", "", err
	}
	stamp := isoStamp(at)
	version := row.TokenVersion + 1
	tag, err := d.pool.Exec(ctx, `UPDATE reservation_claim SET state = $1, email = $2, email_masked = $3, lang = $4,
		token_hash = $5, token_version = $6, updated_at = $7
		WHERE reservation_id = $8 AND state = $9 AND token_version = $10`,
		claimStateClaimed, addr, mail.MaskEmail(addr), lang, claimTokenHash(secret), version, stamp,
		st.id, row.State, row.TokenVersion)
	if err != nil {
		return false, "", "", err
	}
	if tag.RowsAffected() != 1 {
		return false, "held", "", nil
	}
	if err := enqueueClaimResend(ctx, d, st, apt, addr, lang, secret, version, party, stamp); err != nil {
		return false, "", "", err
	}
	recKey := "claim_to:" + hex.EncodeToString(sha256Sum([]byte(addr)))
	_ = rateRecord(ctx, d.pool, "claim_mail_recipient", recKey, at)
	_ = rateRecord(ctx, d.pool, "claim_mail_reservation", fmt.Sprintf("claim_res:%d", st.id), at)
	cfg, drainErr := mail.ConfigFromEnv(d.getenv)
	if drainErr == nil {
		_, _ = mail.Drain(ctx, d.pool, cfg, 4)
	}
	return true, "", secret, nil
}

func enqueueClaimResend(ctx context.Context, d claimOpsDeps, st *claimStay, apt *claimApt, addr, lang, secret string, version int64, party int, stamp string) error {
	base := strings.TrimRight(hostweb.PublicBase(d.getenv), "/")
	link := fmt.Sprintf("%s/l/%s/%d/claim#c=%s", base, apt.permalink, st.id, claimSecretMarker)
	return enqueueClaimMail(ctx, d, st, apt, addr, lang, secret, version, true, link, stamp)
}
