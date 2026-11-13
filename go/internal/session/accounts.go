package session

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Account helpers used by login, ported from App/app/auth.py (brief 1280).

// Errors of create_account; the text is the Python ValueError message.
var (
	ErrEmailInvalid = errors.New("users.email.error.invalid")
	ErrUnknownRole  = errors.New("Unknown account role.")
	ErrUsername     = errors.New("auth.error.username")
)

var usernameRE = regexp.MustCompile(`^[a-z0-9][a-z0-9._-]{2,31}$`)

// usernameEq is db.username_eq() on Postgres: ASCII-only case folding.
const usernameEq = `translate(username, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz') ` +
	`= translate($1, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')`

// LoginAccount is the user_account columns login reads (SELECT * in Python).
// Nullable columns are pointers so NULL and "" stay apart.
type LoginAccount struct {
	ID                int64
	Username          string
	DisplayName       *string
	Email             *string
	Role              string
	Active            int64
	SessionVersion    int64
	TOTPEnabled       int64
	TOTPSecretEnc     *string
	RecoveryCodesHash *string
	TOTPLastStep      *int64
	EmailVerifiedAt   *string
	LastLoginAt       *string
	CreatedAt         string
}

const accountColumns = `id, username, display_name, email, role, active, session_version, totp_enabled, ` +
	`totp_secret_enc, recovery_codes_hash, totp_last_step, email_verified_at, last_login_at, created_at`

// accountWhere loads the first user_account row matching where (trusted SQL).
func accountWhere(ctx context.Context, db *pgxpool.Pool, where string, args ...any) (*LoginAccount, error) {
	var a LoginAccount
	err := db.QueryRow(ctx, `SELECT `+accountColumns+` FROM user_account WHERE `+where, args...).Scan(
		&a.ID, &a.Username, &a.DisplayName, &a.Email, &a.Role, &a.Active, &a.SessionVersion, &a.TOTPEnabled,
		&a.TOTPSecretEnc, &a.RecoveryCodesHash, &a.TOTPLastStep, &a.EmailVerifiedAt, &a.LastLoginAt, &a.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// AccountByID is SELECT * FROM user_account WHERE id = ? AND active = 1.
func AccountByID(ctx context.Context, db *pgxpool.Pool, id int64) (*LoginAccount, error) {
	return accountWhere(ctx, db, `id = $1 AND active = 1`, id)
}

// NormaliseUsername is normalise_username: strip, lower-case.
func NormaliseUsername(value string) string {
	return strings.ToLower(pyStrip(value))
}

// UsernameIsValid is username_is_valid.
func UsernameIsValid(value string) bool {
	return usernameRE.MatchString(NormaliseUsername(value))
}

// AccountByEmail is account_by_email: the active account with this exact
// login e-mail, or nil.
func AccountByEmail(ctx context.Context, db *pgxpool.Pool, email string) (*LoginAccount, error) {
	if email == "" {
		return nil, nil
	}
	return accountWhere(ctx, db, `email = $1 AND active = 1`, email)
}

// AccountByUsername is account_by_username (ASCII case-insensitive).
func AccountByUsername(ctx context.Context, db *pgxpool.Pool, username string) (*LoginAccount, error) {
	name := NormaliseUsername(username)
	if name == "" {
		return nil, nil
	}
	return accountWhere(ctx, db, usernameEq+` AND active = 1`, name)
}

var (
	usernameStrip   = regexp.MustCompile(`[^a-z0-9._-]`)
	usernameLeading = regexp.MustCompile(`^[^a-z0-9]+`)
)

func tokenHex(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}

// usernameBase is the handle stem new_username derives from the e-mail.
func usernameBase(email string) string {
	local := strings.ToLower(strings.SplitN(email, "@", 2)[0])
	local = usernameStrip.ReplaceAllString(local, "")
	base := usernameLeading.ReplaceAllString(local, "")
	if len(base) > 20 {
		base = base[:20]
	}
	if base == "" {
		base = "host"
	}
	return base
}

// NewUsername is new_username: "<stem>-<4 hex>", unused, else "host-<12 hex>".
func NewUsername(ctx context.Context, db *pgxpool.Pool, email string) (string, error) {
	base := usernameBase(email)
	for range 20 {
		candidate := base + "-" + tokenHex(2)
		if !UsernameIsValid(candidate) {
			continue
		}
		var id int64
		err := db.QueryRow(ctx, `SELECT id FROM user_account WHERE `+usernameEq, candidate).Scan(&id)
		if errors.Is(err, pgx.ErrNoRows) {
			return candidate, nil
		}
		if err != nil {
			return "", err
		}
	}
	return "host-" + tokenHex(6), nil
}

// UTCNow is db.utcnow(): ISO seconds with "+00:00".
func UTCNow(now time.Time) string {
	return now.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// CreateAccount is create_account; email must already be normalised.
func CreateAccount(ctx context.Context, db *pgxpool.Pool, email, displayName, role, username string, now time.Time) (int64, error) {
	email = strings.ToLower(pyStrip(email))
	if email == "" || !strings.Contains(email, "@") {
		return 0, ErrEmailInvalid
	}
	if role != "admin" && role != "host" {
		return 0, ErrUnknownRole
	}
	username = NormaliseUsername(username)
	if username == "" {
		var err error
		if username, err = NewUsername(ctx, db, email); err != nil {
			return 0, err
		}
	}
	if !UsernameIsValid(username) {
		return 0, ErrUsername
	}
	var id int64
	err := db.QueryRow(ctx, `INSERT INTO user_account (username, display_name, email, password_hash, role, `+
		`active, must_change_password, session_version, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) `+
		`RETURNING id`, username, pyStrip(displayName), email, "", role, 1, 0, 1, UTCNow(now)).Scan(&id)
	return id, err
}

// EmailTaken is email_taken: another account (id != exceptUserID) has it.
func EmailTaken(ctx context.Context, db *pgxpool.Pool, email string, exceptUserID int64) (bool, error) {
	var id int64
	err := db.QueryRow(ctx, `SELECT id FROM user_account WHERE email = $1 AND id != $2`, email, exceptUserID).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return err == nil, err
}

// SetAccountEmail is set_account_email: new unverified address, a
// session_version bump when an address is replaced, and every unused
// login_token of the account spent.
func SetAccountEmail(ctx context.Context, db *pgxpool.Pool, userID int64, email string, now time.Time) error {
	var current *string
	err := db.QueryRow(ctx, `SELECT email FROM user_account WHERE id = $1`, userID).Scan(&current)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	sql := `UPDATE user_account SET email = $1, email_verified_at = NULL`
	if current != nil && pyStrip(*current) != "" {
		sql += `, session_version = session_version + 1`
	}
	if _, err := db.Exec(ctx, sql+` WHERE id = $2`, email, userID); err != nil {
		return err
	}
	_, err = db.Exec(ctx, `UPDATE login_token SET used_at = $1 WHERE user_account_id = $2 AND used_at IS NULL`,
		UTCNow(now), userID)
	return err
}
