// effects.go is the database side of the submit_batch side effects besides mail
// and push. It mirrors App/app/alerts.py raise_alert (439-500) and resolve (534),
// db.audit (App/app/db.py 2138), and App/app/reporting.py apartment_in_doubt
// (1522) and clear_stuck_alert_if_recovered (1195). Times are UTCNow, as db.utcnow.
package ubyport

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

// AlertParams are the values a host card is rendered from. Only string and int
// values are supported; anything else is an error and nothing is written.
type AlertParams map[string]any

// pyJSONParams is json.dumps(params, ensure_ascii=False, sort_keys=True) for
// string and int values. An empty map is NULL, as Python's falsy check is.
func pyJSONParams(params AlertParams) (*string, error) {
	if len(params) == 0 {
		return nil, nil
	}
	keys := make([]string, 0, len(params))
	for k := range params {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var b strings.Builder
	b.WriteByte('{')
	for i, k := range keys {
		if i > 0 {
			b.WriteString(", ")
		}
		writeJSONStringRaw(&b, k)
		b.WriteString(": ")
		switch v := params[k].(type) {
		case string:
			writeJSONStringRaw(&b, v)
		case int:
			b.WriteString(strconv.Itoa(v))
		case int64:
			b.WriteString(strconv.FormatInt(v, 10))
		default:
			return nil, fmt.Errorf("ubyport: alert param %q has unsupported type %T", k, v)
		}
	}
	b.WriteByte('}')
	s := b.String()
	return &s, nil
}

// writeJSONStringRaw writes s as json.dumps(ensure_ascii=False) does: non-ASCII
// is kept as it is, only the short escapes and other control characters change.
func writeJSONStringRaw(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		if esc, ok := pyShortEscapes[r]; ok {
			b.WriteString(esc)
		} else if r < 0x20 {
			fmt.Fprintf(b, `\u%04x`, r)
		} else {
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
}

// idOrNone prints an id as Python's f-string does: None for a missing one.
func idOrNone(id *int64) string {
	if id == nil {
		return "None"
	}
	return strconv.FormatInt(*id, 10)
}

// RaiseAlert records an alert, refreshing the open one with the same dedupe key.
// An empty dedupeKey means the key is built as raise_alert builds it.
func RaiseAlert(ctx context.Context, pool *pgxpool.Pool, level, kind, message, detail, dedupeKey string,
	apartmentID, reservationID, ownerUserID *int64, params AlertParams) error {
	stored, err := pyJSONParams(params)
	if err != nil {
		return err
	}
	if ownerUserID == nil && apartmentID != nil && *apartmentID != 0 {
		var owner *int64
		err := pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, *apartmentID).Scan(&owner)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
		ownerUserID = owner
	}
	if ownerUserID == nil && reservationID != nil && *reservationID != 0 {
		var owner *int64
		err := pool.QueryRow(ctx,
			`SELECT a.owner_user_id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = $1`,
			*reservationID).Scan(&owner)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
		ownerUserID = owner
	}
	key := dedupeKey
	if key == "" {
		key = fmt.Sprintf("%s:%s:%s:%s", kind, idOrNone(apartmentID), idOrNone(reservationID), message)
	}
	now := UTCNow()
	var openID int64
	err = pool.QueryRow(ctx,
		`SELECT id FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key).Scan(&openID)
	if err == nil {
		return updateOpenAlert(ctx, pool, key, level, message, detail, stored, now)
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	_, err = pool.Exec(ctx,
		`INSERT INTO alert (level, kind, apartment_id, reservation_id, owner_user_id, dedupe_key, message, detail, params, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		level, kind, apartmentID, reservationID, ownerUserID, key, message, detail, stored, now)
	if err == nil {
		return nil
	}
	// idx_alert_dedupe: another writer opened the same key first. Refresh that one.
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		return updateOpenAlert(ctx, pool, key, level, message, detail, stored, now)
	}
	return err
}

func updateOpenAlert(ctx context.Context, pool *pgxpool.Pool, key, level, message, detail string,
	stored *string, now string) error {
	_, err := pool.Exec(ctx,
		`UPDATE alert SET level = $1, message = $2, detail = $3, params = $4, created_at = $5
		 WHERE dedupe_key = $6 AND resolved_at IS NULL`,
		level, message, detail, stored, now, key)
	return err
}

// ResolveAlert closes the open alert with this dedupe key, if there is one.
func ResolveAlert(ctx context.Context, pool *pgxpool.Pool, dedupeKey string) error {
	_, err := pool.Exec(ctx,
		`UPDATE alert SET resolved_at = $1 WHERE dedupe_key = $2 AND resolved_at IS NULL`,
		UTCNow(), dedupeKey)
	return err
}

// Audit writes an audit row for a background action: no signed-in actor, so the
// actor is "host" and both user ids are NULL.
func Audit(ctx context.Context, pool *pgxpool.Pool, action, detail string, ownerUserID *int64) error {
	_, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		 VALUES ($1, $2, $3, $4, $5, NULL, NULL)`,
		UTCNow(), "host", action, detail, ownerUserID)
	return err
}

// ApartmentInDoubt reports whether any live guest still points at a batch whose
// outcome is unknown.
func ApartmentInDoubt(ctx context.Context, pool *pgxpool.Pool, apartmentID int64) (bool, error) {
	var one int
	err := pool.QueryRow(ctx,
		`SELECT 1 FROM guest g JOIN reservation r ON r.id = g.reservation_id
		 WHERE r.apartment_id = $1 AND r.status = 'active' AND r.archived_at IS NULL
		 AND g.archived_at IS NULL AND g.submission_id IN
		 (SELECT id FROM submission WHERE apartment_id = $2 AND state = 'outcome_unknown')
		 LIMIT 1`,
		apartmentID, apartmentID).Scan(&one)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, nil
}

// ClearStuckIfRecovered closes the stranded-records alert for a stay once no
// live guest on it is still in state error at the auto-attempt cap.
func ClearStuckIfRecovered(ctx context.Context, pool *pgxpool.Pool, reservationID int64) error {
	var n int64
	err := pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM guest WHERE reservation_id = $1
		 AND archived_at IS NULL AND submit_state = $2 AND submit_attempts >= $3`,
		reservationID, "error", SubmissionMaxAutoAttempts).Scan(&n)
	if err != nil {
		return err
	}
	if n == 0 {
		return ResolveAlert(ctx, pool, fmt.Sprintf("submission_stuck:%d", reservationID))
	}
	return nil
}
