package doorcodes

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"
	_ "time/tzdata" // Europe/Prague without a system zoneinfo

	"github.com/jackc/pgx/v5"
)

// pragueLoc is config.TIMEZONE.
var pragueLoc, _ = time.LoadLocation("Europe/Prague")

// iso is db.utcnow() for an instant: whole seconds with "+00:00".
func iso(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// msToISO is _ms_to_iso.
func msToISO(ms int64) string {
	return iso(time.UnixMilli(ms))
}

// isoToMS is _iso_to_ms.
func isoToMS(v string) (int64, error) {
	t, err := parseISO(v)
	if err != nil {
		return 0, err
	}
	return t.UnixMilli(), nil
}

// parseISO reads the forms Python fromisoformat accepts for stored values. A value with no
// zone is UTC, as _waited_minutes and _iso_to_ms assume.
func parseISO(v string) (time.Time, error) {
	if t, err := time.Parse(time.RFC3339Nano, v); err == nil {
		return t, nil
	}
	for _, layout := range []string{"2006-01-02T15:04:05", "2006-01-02"} {
		if t, err := time.Parse(layout, v); err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("doorcodes: bad timestamp %q", v)
}

// fmtLocal is _fmt_local: a stored instant shown as Prague civil time.
func fmtLocal(v string) (string, error) {
	t, err := parseISO(v)
	if err != nil {
		return "", err
	}
	return t.In(pragueLoc).Format("02.01.2006 15:04"), nil
}

// stayCheckinLabel is _stay_checkin_label: a stay date at an hour in Prague.
func stayCheckinLabel(dateValue string, hour int64) (string, error) {
	t, err := parseISO(dateValue)
	if err != nil {
		return "", err
	}
	local := time.Date(t.Year(), t.Month(), t.Day(), int(hour), 0, 0, 0, pragueLoc)
	return local.Format("02.01.2006 15:04"), nil
}

// eligibleSQL is _eligible_sql: the WHERE clause for a stay that may hold a code. dateArg is
// the placeholder for today's Czech date (for example "$2").
func eligibleSQL(live bool, dateArg string) string {
	sql := "r.status = 'active' AND r.archived_at IS NULL " +
		"AND r.registration_completed_at IS NOT NULL AND r.date_to >= " + dateArg + " " +
		"AND a.lock_provider = 'ttlock' AND a.lock_id IS NOT NULL " +
		"AND a.checkin_hour IS NOT NULL AND a.checkout_hour IS NOT NULL " +
		// 0100: the setup guide's demo stay never opens a real door.
		"AND COALESCE(r.source, '') != 'demo'"
	if !live {
		sql += " AND r.source = 'manual'"
	}
	return sql
}

// today is the Czech civil date used by eligibleSQL.
func (s *Service) today() string {
	return s.Clock.Now().In(pragueLoc).Format("2006-01-02")
}

// guestPinDisplay is guest_pin_display: the digits a guest types, with the final # confirm.
func guestPinDisplay(pin string) string {
	pin = strings.TrimSpace(pin)
	if pin == "" || strings.HasSuffix(pin, KeypadConfirmSuffix) {
		return pin
	}
	return pin + KeypadConfirmSuffix
}

// mailIdempotencyKey is _mail_idempotency_key.
func mailIdempotencyKey(reservationID int64, row *doorCode) string {
	codeID := derefOr(row.ProviderCodeID, "")
	if codeID == "" {
		codeID = "none"
	}
	return fmt.Sprintf("door_code:%d:%s:%s:%s", reservationID, derefNone(row.ValidFrom), derefNone(row.ValidTo), codeID)
}

// truncateRunes cuts v to n characters (Python str[:n]).
func truncateRunes(v string, n int) string {
	r := []rune(v)
	if len(r) > n {
		return string(r[:n])
	}
	return v
}

func derefOr(v *string, fallback string) string {
	if v == nil {
		return fallback
	}
	return *v
}

// derefNone is str(value) for a nullable column: Python prints None for NULL.
func derefNone(v *string) string {
	if v == nil {
		return "None"
	}
	return *v
}

// hourOf is the hour as an int, or -1 when unset (StayWindow then rejects it, as ValueError).
func hourOf(h *int64) int {
	if h == nil {
		return -1
	}
	return int(*h)
}

func isNoRows(err error) bool {
	return errors.Is(err, pgx.ErrNoRows)
}

// exec runs a statement and returns the number of rows it touched.
func (s *Service) exec(ctx context.Context, sql string, args ...any) (int64, error) {
	tag, err := s.Pool.Exec(ctx, sql, args...)
	if err != nil {
		return 0, err
	}
	return tag.RowsAffected(), nil
}

// exists runs "SELECT EXISTS (<inner>)".
func (s *Service) exists(ctx context.Context, inner string, args ...any) (bool, error) {
	var ok bool
	err := s.Pool.QueryRow(ctx, "SELECT EXISTS ("+inner+")", args...).Scan(&ok)
	return ok, err
}

func (s *Service) log() *slog.Logger {
	if s.Log != nil {
		return s.Log
	}
	return slog.Default()
}

// waited is _waited_minutes against the clock.
func (s *Service) waited(since *string) float64 {
	if since == nil || *since == "" {
		return 0
	}
	t, err := parseISO(*since)
	if err != nil {
		return 0
	}
	return s.Clock.Now().Sub(t).Minutes()
}

// encryptField is db.encrypt_field: "" and NULL stay NULL.
func (s *Service) encryptField(plain string) (any, error) {
	if plain == "" {
		return nil, nil
	}
	token, err := s.Keys.EncryptString(plain)
	if err != nil {
		return nil, err
	}
	return token, nil
}

// decryptField is db.decrypt_field: strict, an undecryptable value is an error.
func (s *Service) decryptField(token *string) (string, error) {
	if token == nil || *token == "" {
		return "", nil
	}
	plain, err := s.Keys.Decrypt(*token, 0, s.Clock.Now())
	if err != nil {
		return "", err
	}
	return string(plain), nil
}

// releaseIssueClaim is _release_issue_claim: the row goes back to pending. reason "" means none.
func (s *Service) releaseIssueClaim(ctx context.Context, id int64, decrement bool, reason string) error {
	now := s.Clock.Now()
	var reasonArg, nextArg any
	if reason != "" {
		reasonArg = reason
	}
	if minutes := releaseRetryMinutes[reason]; minutes > 0 {
		nextArg = iso(now.Add(time.Duration(minutes) * time.Minute))
	}
	if decrement {
		_, err := s.exec(ctx,
			"UPDATE door_code SET state = $1, claimed_at = NULL, attempts = attempts - 1, "+
				"last_error = COALESCE($2::text, last_error), next_attempt_at = COALESCE($3::text, next_attempt_at), "+
				"updated_at = $4 WHERE id = $5 AND attempts > 0",
			StatePending, reasonArg, nextArg, iso(now), id)
		return err
	}
	_, err := s.exec(ctx,
		"UPDATE door_code SET state = $1, claimed_at = NULL, "+
			"last_error = COALESCE($2::text, last_error), next_attempt_at = COALESCE($3::text, next_attempt_at), "+
			"updated_at = $4 WHERE id = $5",
		StatePending, reasonArg, nextArg, iso(now), id)
	return err
}
