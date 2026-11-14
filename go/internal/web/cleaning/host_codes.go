package cleaning

// Door-code actions of one property (brief 1573): POST /cleaning/properties/
// {id}/code/{action}, routes/cleaning.code_action (297-315) with
// cleaning_codes.save_manual (119-147), queue_permanent (150-183), remove
// (323-343) and _activate (67-116) in App/app/cleaning_codes.py.
//
// Nothing here calls the lock provider: queue_permanent only writes a pending
// cleaning_code row, which the Python worker (process_queue) hands to TTLock.
// The writers share Python's advisory lock key (hashtext('cleaning_property'),
// apartment id), so a Go request and the Python worker never write one
// property's code rows at the same time.

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

var pinRE = regexp.MustCompile(`^[A-Za-z0-9*#-]{1,32}$`)

// ValueError texts of cleaning_codes; the page shows ct(text) for them.
const (
	keyLoginRequired = "login_required"
	keyCode          = "code"
	keyPending       = "pending"
	keyLockSetup     = "lock_setup"
)

func init() { hostAdd("POST /cleaning/properties/{id}/code/{action}", (*hostServer).codeAction) }

// codeAction is routes/cleaning.code_action.
func (s *hostServer) codeAction() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		if !s.csrf(w, r, at) {
			return
		}
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		owner := ownerID(h)
		home, err := homeFor(r.Context(), s.pool, owner, id)
		if err != nil {
			serverError(w)
			return
		}
		if home == nil {
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		}
		if !parseHostForm(w, r) {
			return
		}
		var key string
		switch r.PathValue("action") {
		case "manual":
			key, err = s.saveManual(r.Context(), id, r.PostForm.Get("code"), at)
		case "ttlock":
			key, err = s.queuePermanent(r.Context(), *home, owner, at)
		case "remove":
			key, err = s.removeCode(r.Context(), id, at)
		default:
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		}
		if err != nil {
			serverError(w)
			return
		}
		if key != "" {
			s.renderSettings(w, r, h, at, id, key, http.StatusUnprocessableEntity, nil)
			return
		}
		redirect(w, "/cleaning/properties/"+strconv.FormatInt(id, 10)+"?notice=saved")
	}
}

// lockProperty is db.lock_key(cur, "cleaning_property", apartment).
func lockProperty(ctx context.Context, tx pgx.Tx, apartment int64) error {
	_, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1::text), $2::int4)`, "cleaning_property", apartment)
	return err
}

// encrypt is db.encrypt_field: the first data key.
func (s *hostServer) encrypt(plain string) (string, error) {
	keys, err := secure.LoadDataKeys(s.getenv)
	if err != nil {
		return "", err
	}
	return keys.Encrypt([]byte(plain))
}

func randHex(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

// saveManual is cleaning_codes.save_manual. The key is the ValueError text.
func (s *hostServer) saveManual(ctx context.Context, apartment int64, value string, at time.Time) (string, error) {
	if stagingNoLogin(s.getenv) {
		return keyLoginRequired, nil
	}
	pin := pyStrip(value)
	if !pinRE.MatchString(pin) {
		return keyCode, nil
	}
	if err := ensureProperty(ctx, s.pool, apartment, at); err != nil {
		return "", err
	}
	enc, err := s.encrypt(pin)
	if err != nil {
		return "", err
	}
	ref, err := randHex(16)
	if err != nil {
		return "", err
	}
	now := stamp(at)
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return "", err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if err := lockProperty(ctx, tx, apartment); err != nil {
		return "", err
	}
	var pendingID int64
	var pendingState string
	err = tx.QueryRow(ctx,
		`SELECT c.id, c.state FROM cleaning_property p JOIN cleaning_code c ON c.id = p.pending_code_id WHERE p.apartment_id = $1`,
		apartment).Scan(&pendingID, &pendingState)
	if err != nil && err != pgx.ErrNoRows {
		return "", err
	}
	if err == nil {
		if pendingState == "issuing" || pendingState == "revoking" {
			return keyPending, nil
		}
		// A timed-out creation may have succeeded: keep it and let the worker reconcile and revoke it.
		if _, err := tx.Exec(ctx, `UPDATE cleaning_code SET state = 'revoke_pending', attempts = 0, next_attempt_at = $1 WHERE id = $2`, now, pendingID); err != nil {
			return "", err
		}
	}
	var rowID int64
	if err := tx.QueryRow(ctx,
		`INSERT INTO cleaning_code (apartment_id, source, pin_enc, operation_ref, state, created_at, updated_at)
		 VALUES ($1, 'manual', $2, $3, 'active', $4, $4) RETURNING id`, apartment, enc, ref, now).Scan(&rowID); err != nil {
		return "", err
	}
	if err := s.activate(ctx, tx, rowID, apartment, at); err != nil {
		return "", err
	}
	return "", tx.Commit(ctx)
}

// activate is cleaning_codes._activate for a manual code (the lock-provider
// branch only runs in the worker, which stays in Python).
func (s *hostServer) activate(ctx context.Context, tx pgx.Tx, id, apartment int64, at time.Time) error {
	now := stamp(at)
	var current *int64
	err := tx.QueryRow(ctx, `SELECT p.code_id FROM cleaning_property p JOIN apartment a ON a.id = p.apartment_id WHERE p.apartment_id = $1`, apartment).Scan(&current)
	if err != nil && err != pgx.ErrNoRows {
		return err
	}
	var managedPin *string
	if err := tx.QueryRow(ctx, `SELECT pin_enc FROM cleaning_code WHERE id = $1`, id).Scan(&managedPin); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `UPDATE cleaning_property SET code_id = $1, pending_code_id = NULL, updated_at = $2 WHERE apartment_id = $3`, id, now, apartment); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `UPDATE cleaning_code SET state = 'active', claimed_at = NULL, updated_at = $1 WHERE id = $2`, now, id); err != nil {
		return err
	}
	if current == nil || *current == id {
		return nil
	}
	var state, source string
	var previousPin *string
	if err := tx.QueryRow(ctx, `SELECT state, source, pin_enc FROM cleaning_code WHERE id = $1`, *current).Scan(&state, &source, &previousPin); err != nil {
		return err
	}
	if state != "active" {
		return nil
	}
	// A manual takeover of the same physical TTLock PIN must not delete it. The
	// page shows the keypad's final # for a TTLock code; it is not part of the API PIN.
	same := false
	if source == "ttlock" && previousPin != nil && managedPin != nil && *previousPin != "" && *managedPin != "" {
		f := &fieldReader{getenv: s.getenv, at: at}
		prev, err := f.decrypt(*previousPin)
		if err != nil {
			return err
		}
		mine, err := f.decrypt(*managedPin)
		if err != nil {
			return err
		}
		same = subtle.ConstantTimeCompare([]byte(prev), []byte(strings.TrimSuffix(mine, "#"))) == 1
	}
	if same {
		_, err = tx.Exec(ctx, `UPDATE cleaning_code SET state = 'detached', pin_enc = NULL, updated_at = $1 WHERE id = $2`, now, *current)
		return err
	}
	_, err = tx.Exec(ctx,
		`UPDATE cleaning_code SET state = CASE WHEN source = 'ttlock' THEN 'revoke_pending' ELSE 'revoked' END,
		        pin_enc = CASE WHEN source = 'manual' THEN NULL ELSE pin_enc END, attempts = 0,
		        next_attempt_at = $1, updated_at = $1 WHERE id = $2`, now, *current)
	return err
}

// removeCode is cleaning_codes.remove.
func (s *hostServer) removeCode(ctx context.Context, apartment int64, at time.Time) (string, error) {
	if err := ensureProperty(ctx, s.pool, apartment, at); err != nil {
		return "", err
	}
	now := stamp(at)
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return "", err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if err := lockProperty(ctx, tx, apartment); err != nil {
		return "", err
	}
	var codeID, pendingID *int64
	if err := tx.QueryRow(ctx, `SELECT code_id, pending_code_id FROM cleaning_property WHERE apartment_id = $1`, apartment).Scan(&codeID, &pendingID); err != nil {
		return "", err
	}
	for _, id := range []*int64{codeID, pendingID} {
		if id == nil {
			continue
		}
		var state, source string
		var pin *string
		if err := tx.QueryRow(ctx, `SELECT state, source, pin_enc FROM cleaning_code WHERE id = $1`, *id).Scan(&state, &source, &pin); err != nil {
			return "", err
		}
		if state == "issuing" || state == "revoking" {
			return keyPending, nil
		}
		next, keep := "revoked", (*string)(nil)
		if source == "ttlock" {
			next, keep = "revoke_pending", pin
		}
		if _, err := tx.Exec(ctx,
			`UPDATE cleaning_code SET state = $1, pin_enc = $2, attempts = 0, next_attempt_at = $3, updated_at = $3 WHERE id = $4`,
			next, keep, now, *id); err != nil {
			return "", err
		}
	}
	if _, err := tx.Exec(ctx, `UPDATE cleaning_property SET code_id = NULL, pending_code_id = NULL, updated_at = $1 WHERE apartment_id = $2`, now, apartment); err != nil {
		return "", err
	}
	return "", tx.Commit(ctx)
}

// lockProviderAllowed is ttlock.allowed_for(owner): door codes are switched on
// (UBYHOST_DOOR_CODES and the app's TTLock credentials) and the plan allows them.
func (s *hostServer) lockProviderAllowed(ctx context.Context, owner *int64) (bool, error) {
	on := s.getenv("UBYHOST_DOOR_CODES")
	if (on != "1" && on != "true" && on != "yes") ||
		strings.TrimSpace(s.getenv("UBYHOST_TTLOCK_CLIENT_ID")) == "" || strings.TrimSpace(s.getenv("UBYHOST_TTLOCK_CLIENT_SECRET")) == "" {
		return false, nil
	}
	if owner == nil {
		return false, nil
	}
	switch strings.ToLower(s.getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
	default:
		return true, nil // billing.UNBILLED
	}
	var status string
	var plan *string
	var addon int64
	err := s.pool.QueryRow(ctx, `SELECT status, plan, addon_ttlock FROM billing_account WHERE owner_user_id = $1`, *owner).Scan(&status, &plan, &addon)
	if err == pgx.ErrNoRows {
		return true, nil
	}
	if err != nil {
		return false, err
	}
	switch status {
	case "paused":
		return false, nil
	case "trial_pending", "trialing":
		return true, nil
	}
	return str(plan) == "max" || addon != 0, nil
}

// queuePermanent is cleaning_codes.queue_permanent: it queues a TTLock code
// for the worker; it does not call the provider.
func (s *hostServer) queuePermanent(ctx context.Context, h home, owner *int64, at time.Time) (string, error) {
	if stagingNoLogin(s.getenv) {
		return keyLoginRequired, nil
	}
	allowed, err := s.lockProviderAllowed(ctx, owner)
	if err != nil {
		return "", err
	}
	var accountID int64
	var accountStatus string
	var locksJSON *string
	found := false
	if owner != nil {
		err := s.pool.QueryRow(ctx,
			`SELECT id, status, locks_json FROM lock_account WHERE owner_user_id = $1 AND provider = 'ttlock' ORDER BY id LIMIT 1`, *owner).
			Scan(&accountID, &accountStatus, &locksJSON)
		if err != nil && err != pgx.ErrNoRows {
			return "", err
		}
		found = err == nil
	}
	if !allowed || !found || accountStatus != "ok" || str(h.LockProvider) != "ttlock" || str(h.LockID) == "" ||
		!lockListed(str(locksJSON), str(h.LockID)) {
		return keyLockSetup, nil
	}
	if err := ensureProperty(ctx, s.pool, h.ID, at); err != nil {
		return "", err
	}
	now := stamp(at)
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return "", err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if err := lockProperty(ctx, tx, h.ID); err != nil {
		return "", err
	}
	var pending *int64
	if err := tx.QueryRow(ctx, `SELECT pending_code_id FROM cleaning_property WHERE apartment_id = $1`, h.ID).Scan(&pending); err != nil {
		return "", err
	}
	if pending != nil {
		if _, err := tx.Exec(ctx,
			`UPDATE cleaning_code SET state = 'retrying', attempts = 1, next_attempt_at = $1, updated_at = $1 WHERE id = $2 AND state = 'failed'`,
			now, *pending); err != nil {
			return "", err
		}
		return "", tx.Commit(ctx)
	}
	n, err := rand.Int(rand.Reader, big.NewInt(9_000_000))
	if err != nil {
		return "", err
	}
	enc, err := s.encrypt(strconv.FormatInt(n.Int64()+1_000_000, 10))
	if err != nil {
		return "", err
	}
	suffix, err := randHex(8)
	if err != nil {
		return "", err
	}
	var rowID int64
	if err := tx.QueryRow(ctx,
		`INSERT INTO cleaning_code (apartment_id, source, pin_enc, lock_account_id, lock_id, operation_ref, state, next_attempt_at, created_at, updated_at)
		 VALUES ($1, 'ttlock', $2, $3, $4, $5, 'pending', $6, $6, $6) RETURNING id`,
		h.ID, enc, accountID, str(h.LockID), "UH Cleaning "+suffix, now).Scan(&rowID); err != nil {
		return "", err
	}
	if _, err := tx.Exec(ctx, `UPDATE cleaning_property SET pending_code_id = $1, updated_at = $2 WHERE apartment_id = $3`, rowID, now, h.ID); err != nil {
		return "", err
	}
	return "", tx.Commit(ctx)
}

// lockListed is `str(lock_id) in {str(x["lock_id"]) for x in locks_of(account)}`.
func lockListed(locksJSON, lockID string) bool {
	if strings.TrimSpace(locksJSON) == "" {
		return false
	}
	dec := json.NewDecoder(strings.NewReader(locksJSON))
	dec.UseNumber()
	var list []map[string]any
	if err := dec.Decode(&list); err != nil {
		return false
	}
	for _, entry := range list {
		if v, ok := entry["lock_id"]; ok && fmt.Sprint(v) == lockID {
			return true
		}
	}
	return false
}
