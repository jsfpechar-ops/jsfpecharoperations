package session

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Login by e-mail link and its rate limits, ported from App/app/login_link.py
// and App/app/rate_limit.py (brief 1280).
const (
	PurposeLogin       = "login"
	PurposeInvite      = "invite"
	PurposeEmailChange = "email_change"

	linkWindow        = 15 * 60
	linkDay           = 24 * 60 * 60
	linkEmailMaxWin   = 3
	linkEmailMaxDay   = 10
	linkIPMaxWindow   = 10
	linkConsumeFail   = 20
	account2FAMaxFail = 10
	rateWindow        = 15 * 60
)

// LinkTTL is login_link.TTL_SECONDS.
var LinkTTL = map[string]int{PurposeLogin: 15 * 60, PurposeInvite: 72 * 60 * 60, PurposeEmailChange: 60 * 60}

// LoginToken is a login_token row.
type LoginToken struct {
	ID            int64
	TokenHash     string
	UserAccountID int64
	Purpose       string
	Email         string
	Remember      int64
	NextPath      *string
	CreatedAt     string
	ExpiresAt     string
	UsedAt        *string
}

func linkHash(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])
}

// IssueLoginLink is login_link.issue: retire this account's unused links for
// purpose, store the SHA-256 of a new token_urlsafe(32) secret, return it.
// email "" means the account's own address.
func IssueLoginLink(ctx context.Context, db *pgxpool.Pool, account *LoginAccount, purpose, email string, remember bool, nextPath string, now time.Time) (string, error) {
	return issueLink(ctx, db, account, purpose, email, remember, nextPath, now, tokenURLSafe(32))
}

func issueLink(ctx context.Context, db *pgxpool.Pool, account *LoginAccount, purpose, email string, remember bool, nextPath string, now time.Time, token string) (string, error) {
	ttl, ok := LinkTTL[purpose]
	if !ok {
		return "", fmt.Errorf("unknown purpose %s", purpose)
	}
	address := email
	if address == "" && account.Email != nil {
		address = *account.Email
	}
	address = NormaliseUsername(address) // (email or account["email"] or "").strip().lower()
	if address == "" {
		return "", errors.New("account has no login e-mail")
	}
	if nextPath == "" {
		nextPath = "/"
	}
	rem := int64(0)
	if remember {
		rem = 1
	}
	stamp := UTCNow(now)
	if _, err := db.Exec(ctx, `UPDATE login_token SET used_at = $1 WHERE user_account_id = $2 AND purpose = $3 `+
		`AND used_at IS NULL`, stamp, account.ID, purpose); err != nil {
		return "", err
	}
	_, err := db.Exec(ctx, `INSERT INTO login_token (token_hash, user_account_id, purpose, email, remember, `+
		`next_path, created_at, expires_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id`,
		linkHash(token), account.ID, purpose, address, rem, nextPath, stamp,
		UTCNow(now.Add(time.Duration(ttl)*time.Second)))
	if err != nil {
		return "", err
	}
	return token, nil
}

func hasPurpose(purposes []string, p string) bool {
	for _, x := range purposes {
		if x == p {
			return true
		}
	}
	return false
}

// PeekLoginLink is login_link.peek: the live row, or nil. nil purposes means
// (login, invite).
func PeekLoginLink(ctx context.Context, db *pgxpool.Pool, token string, purposes []string, now time.Time) (*LoginToken, error) {
	if token == "" || utf8.RuneCountInString(token) > 200 {
		return nil, nil
	}
	if purposes == nil {
		purposes = []string{PurposeLogin, PurposeInvite}
	}
	var t LoginToken
	err := db.QueryRow(ctx, `SELECT id, token_hash, user_account_id, purpose, email, remember, next_path, `+
		`created_at, expires_at, used_at FROM login_token WHERE token_hash = $1 AND used_at IS NULL AND expires_at > $2`,
		linkHash(token), UTCNow(now)).Scan(&t.ID, &t.TokenHash, &t.UserAccountID, &t.Purpose, &t.Email,
		&t.Remember, &t.NextPath, &t.CreatedAt, &t.ExpiresAt, &t.UsedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if !hasPurpose(purposes, t.Purpose) {
		return nil, nil
	}
	return &t, nil
}

// ConsumeLoginLink is login_link.consume: spend the token once (compare-and-set
// on used_at), return the row it was, or nil.
func ConsumeLoginLink(ctx context.Context, db *pgxpool.Pool, token string, purposes []string, now time.Time) (*LoginToken, error) {
	row, err := PeekLoginLink(ctx, db, token, purposes, now)
	if err != nil || row == nil {
		return nil, err
	}
	stamp := UTCNow(now)
	tag, err := db.Exec(ctx, `UPDATE login_token SET used_at = $1 WHERE id = $2 AND used_at IS NOT DISTINCT FROM $3 `+
		`AND expires_at > $4`, stamp, row.ID, nil, stamp)
	if err != nil {
		return nil, err
	}
	if tag.RowsAffected() != 1 {
		return nil, nil
	}
	return row, nil
}

// AccountForLink is login_link.account_for: the active account a spent row
// logs into while its address still matches (for email_change: differs).
func AccountForLink(ctx context.Context, db *pgxpool.Pool, row *LoginToken) (*LoginAccount, error) {
	if row == nil {
		return nil, nil
	}
	account, err := AccountByID(ctx, db, row.UserAccountID)
	if err != nil || account == nil {
		return nil, err
	}
	current := ""
	if account.Email != nil {
		current = NormaliseUsername(*account.Email)
	}
	if row.Purpose == PurposeEmailChange {
		if current == row.Email {
			return nil, nil
		}
	} else if current != row.Email {
		return nil, nil
	}
	return account, nil
}

// RateBlocked is rate_limit.blocked: prune, then count >= max (an empty key is blocked).
func RateBlocked(ctx context.Context, db *pgxpool.Pool, scope, key string, max, window int, now time.Time) (bool, error) {
	if key == "" {
		return true, nil
	}
	if _, err := db.Exec(ctx, `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`,
		scope, key, seconds(now)-float64(window)); err != nil {
		return false, err
	}
	var n int64
	if err := db.QueryRow(ctx, `SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = $1 AND key = $2`,
		scope, key).Scan(&n); err != nil {
		return false, err
	}
	return n >= int64(max), nil
}

// RateRecord is rate_limit.record.
func RateRecord(ctx context.Context, db *pgxpool.Pool, scope, key string, now time.Time) error {
	_, err := db.Exec(ctx, `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3) RETURNING id`,
		scope, key, seconds(now))
	return err
}

// LinkRequestBlocked is login_link.request_blocked.
func LinkRequestBlocked(ctx context.Context, db *pgxpool.Pool, ipKey, email string, now time.Time) (bool, error) {
	if b, err := RateBlocked(ctx, db, "login_link_ip", ipKey, linkIPMaxWindow, linkWindow, now); b || err != nil {
		return b, err
	}
	if email == "" {
		return false, nil
	}
	if b, err := RateBlocked(ctx, db, "login_link_email", email, linkEmailMaxWin, linkWindow, now); b || err != nil {
		return b, err
	}
	return RateBlocked(ctx, db, "login_link_email_day", email, linkEmailMaxDay, linkDay, now)
}

// LinkRecordRequest is login_link.record_request.
func LinkRecordRequest(ctx context.Context, db *pgxpool.Pool, ipKey, email string, now time.Time) error {
	if err := RateRecord(ctx, db, "login_link_ip", ipKey, now); err != nil {
		return err
	}
	if email == "" {
		return nil
	}
	if err := RateRecord(ctx, db, "login_link_email", email, now); err != nil {
		return err
	}
	return RateRecord(ctx, db, "login_link_email_day", email, now)
}

// LinkConsumeBlocked is login_link.consume_blocked.
func LinkConsumeBlocked(ctx context.Context, db *pgxpool.Pool, ipKey string, now time.Time) (bool, error) {
	return RateBlocked(ctx, db, "login_link_bad", ipKey, linkConsumeFail, linkWindow, now)
}

// LinkRecordConsumeFailure is login_link.record_consume_failure.
func LinkRecordConsumeFailure(ctx context.Context, db *pgxpool.Pool, ipKey string, now time.Time) error {
	return RateRecord(ctx, db, "login_link_bad", ipKey, now)
}

// Account2FABlocked is rate_limit.account_2fa_blocked.
func Account2FABlocked(ctx context.Context, db *pgxpool.Pool, userID int64, now time.Time) (bool, error) {
	return RateBlocked(ctx, db, "2fa_fail_account", fmt.Sprint(userID), account2FAMaxFail, rateWindow, now)
}

// RecordAccount2FAFailure is rate_limit.record_account_2fa_failure.
func RecordAccount2FAFailure(ctx context.Context, db *pgxpool.Pool, userID int64, now time.Time) error {
	return RateRecord(ctx, db, "2fa_fail_account", fmt.Sprint(userID), now)
}
