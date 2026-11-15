package auth

// The WebAuthn ceremonies behind the passkey routes, ported from
// App/app/passkeys.py with github.com/go-webauthn/webauthn (brief 1760).
//
// What stays the same as Python, on purpose:
//   - the relying party is the host of UBYHOST_PUBLIC_BASE_URL; the public and
//     the app origin are the only origins accepted;
//   - a challenge is stored as its SHA-256 for five minutes in
//     webauthn_challenge and is spent once (one UPDATE, so two replays cannot
//     both win); the browser's answer carries the challenge back in
//     clientDataJSON;
//   - registration needs the signed-in account's own challenge, login none;
//   - passkeys are discoverable and need user verification;
//   - a counter that does not go up (when either side is not 0) refuses the
//     login and is audited as a suspected clone; the row is not touched.
//
// Differences (listed in docs/tasks/1760-report.md): the library also checks
// that the backup-eligible flag does not change between registration and
// login. The table stores only "backed up", so for a row stored as not backed
// up the flag is taken from the answer itself (a row stored as backed up must
// still present the flag).

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"net/url"
	"strings"
	"time"

	"github.com/go-webauthn/webauthn/protocol"
	"github.com/go-webauthn/webauthn/webauthn"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

const (
	passkeyRegister = "register"
	passkeyLogin    = "login"

	passkeyRPName       = "UbyHost"
	passkeyChallengeTTL = 5 * time.Minute
	passkeyTimeout      = 4 * time.Minute
	passkeyMax          = 10
	passkeyNameMax      = 60

	passkeyWindow          = 15 * 60
	passkeyOptionsMax      = 30
	passkeyFailMax         = 20
	passkeyOptionsScope    = "passkey_options"
	passkeyFailScope       = "passkey_fail"
	passkeyBodyMax         = 64 * 1024
	passkeyTimeLayout      = "2006-01-02T15:04:05.000000+00:00"
	passkeyHandleBytes     = 64
	passkeyTransportsLimit = 200
)

// passkeyError is Python's PasskeyError: the browser's answer proved nothing.
// reason goes to the audit log.
type passkeyError struct{ reason string }

func (e *passkeyError) Error() string { return e.reason }

func failed(reason string) error { return &passkeyError{reason: reason} }

// passkeyAccount is the part of user_account a ceremony needs.
type passkeyAccount struct {
	ID          int64
	Username    string
	Email       string
	DisplayName string
	Handle      []byte // decoded webauthn_user_handle, nil when none yet
}

// rpUser adapts an account to the library's User.
type rpUser struct {
	acct passkeyAccount
	cred []webauthn.Credential
}

func (u rpUser) WebAuthnID() []byte   { return u.acct.Handle }
func (u rpUser) WebAuthnName() string { return firstNonEmpty(u.acct.Email, u.acct.Username) }
func (u rpUser) WebAuthnDisplayName() string {
	return firstNonEmpty(u.acct.DisplayName, u.acct.Email, u.acct.Username)
}
func (u rpUser) WebAuthnCredentials() []webauthn.Credential { return u.cred }

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

// origin is the scheme://host[:port] of a base URL, default ports dropped
// (passkeys._base and expected_origin).
func passkeyOrigin(base string) (scheme, host, origin string) {
	u, err := url.Parse(base)
	if err != nil {
		return "", "", ""
	}
	scheme = strings.ToLower(u.Scheme)
	host = strings.ToLower(u.Hostname())
	origin = scheme + "://" + host
	if port := u.Port(); port != "" && !(scheme == "https" && port == "443") && !(scheme == "http" && port == "80") {
		origin += ":" + port
	}
	return scheme, host, origin
}

// passkeyConfig is passkeys.available plus the library setup: nil when this
// deployment cannot offer passkeys (no host name, an IP address, or plain
// http outside localhost).
func passkeyConfig(getenv func(string) string) *webauthn.WebAuthn {
	scheme, host, origin := passkeyOrigin(hostweb.PublicBase(getenv))
	if host == "" || strings.Contains(host, ":") || isDigitsAndDots(host) {
		return nil
	}
	if scheme != "https" && host != "localhost" {
		return nil
	}
	origins := []string{origin}
	if _, _, app := passkeyOrigin(hostweb.AppBase(getenv)); app != "" && app != origin {
		origins = append(origins, app)
	}
	wa, err := webauthn.New(&webauthn.Config{
		RPID:                  host,
		RPDisplayName:         passkeyRPName,
		RPOrigins:             origins,
		AttestationPreference: protocol.PreferNoAttestation,
		AuthenticatorSelection: protocol.AuthenticatorSelection{
			ResidentKey:        protocol.ResidentKeyRequirementRequired,
			RequireResidentKey: protocol.ResidentKeyRequired(),
			UserVerification:   protocol.VerificationRequired,
		},
		Timeouts: webauthn.TimeoutsConfig{
			Login:        webauthn.TimeoutConfig{Timeout: passkeyTimeout, TimeoutUVD: passkeyTimeout},
			Registration: webauthn.TimeoutConfig{Timeout: passkeyTimeout, TimeoutUVD: passkeyTimeout},
		},
	})
	if err != nil {
		return nil
	}
	return wa
}

func isDigitsAndDots(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c != '.' && (c < '0' || c > '9') {
			return false
		}
	}
	return true
}

func passkeyTime(t time.Time) string { return t.UTC().Format(passkeyTimeLayout) }

func challengeHash(challenge []byte) string {
	sum := sha256.Sum256(challenge)
	return hex.EncodeToString(sum[:])
}

// b64 is the stored form of every id and key: base64url without padding.
func b64(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

// unb64 reads base64url with or without padding, as Python's helper does.
func unb64(s string) ([]byte, error) {
	return base64.RawURLEncoding.DecodeString(strings.TrimRight(s, "="))
}

// storeChallenge keeps only the SHA-256 of the challenge (passkeys._store_challenge).
func storeChallenge(ctx context.Context, pool *pgxpool.Pool, challenge []byte, purpose string, userID *int64, at time.Time) error {
	_, err := pool.Exec(ctx, `INSERT INTO webauthn_challenge (challenge_hash, purpose, user_account_id, created_at, expires_at)
		VALUES ($1, $2, $3, $4, $5)`, challengeHash(challenge), purpose, userID, passkeyTime(at), passkeyTime(at.Add(passkeyChallengeTTL)))
	return err
}

// spendChallenge finds and spends the challenge the browser signed in one
// statement: a replay, an expired, a foreign-purpose or (for registration) a
// foreign-account challenge matches no row.
func spendChallenge(ctx context.Context, pool *pgxpool.Pool, challenge []byte, purpose string, userID int64, at time.Time) error {
	now := passkeyTime(at)
	var id int64
	var err error
	if purpose == passkeyRegister {
		err = pool.QueryRow(ctx, `UPDATE webauthn_challenge SET used_at = $1
			WHERE challenge_hash = $2 AND purpose = $3 AND user_account_id = $4 AND used_at IS NULL AND expires_at > $1
			RETURNING id`, now, challengeHash(challenge), purpose, userID).Scan(&id)
	} else {
		err = pool.QueryRow(ctx, `UPDATE webauthn_challenge SET used_at = $1
			WHERE challenge_hash = $2 AND purpose = $3 AND used_at IS NULL AND expires_at > $1
			RETURNING id`, now, challengeHash(challenge), purpose).Scan(&id)
	}
	if errors.Is(err, pgx.ErrNoRows) {
		return failed("challenge")
	}
	return err
}

// loadPasskeyAccount is the active account with its WebAuthn fields.
func loadPasskeyAccount(ctx context.Context, pool *pgxpool.Pool, id int64) (*passkeyAccount, error) {
	var (
		a                      passkeyAccount
		email, display, handle *string
	)
	err := pool.QueryRow(ctx, `SELECT id, username, email, display_name, webauthn_user_handle
		FROM user_account WHERE id = $1 AND active = 1`, id).Scan(&a.ID, &a.Username, &email, &display, &handle)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if email != nil {
		a.Email = *email
	}
	if display != nil {
		a.DisplayName = *display
	}
	if handle != nil && *handle != "" {
		if a.Handle, err = unb64(*handle); err != nil {
			return nil, failed("handle")
		}
	}
	return &a, nil
}

// ensureHandle is passkeys._user_handle: the account's opaque handle, made on
// first use; a lost race uses what the winner stored.
func ensureHandle(ctx context.Context, pool *pgxpool.Pool, a *passkeyAccount) error {
	if len(a.Handle) > 0 {
		return nil
	}
	fresh := make([]byte, passkeyHandleBytes)
	if _, err := rand.Read(fresh); err != nil {
		return err
	}
	tag, err := pool.Exec(ctx, `UPDATE user_account SET webauthn_user_handle = $1 WHERE id = $2 AND webauthn_user_handle IS NULL`, b64(fresh), a.ID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 1 {
		a.Handle = fresh
		return nil
	}
	var stored string
	if err := pool.QueryRow(ctx, `SELECT webauthn_user_handle FROM user_account WHERE id = $1`, a.ID).Scan(&stored); err != nil {
		return err
	}
	a.Handle, err = unb64(stored)
	return err
}

func passkeyCount(ctx context.Context, pool *pgxpool.Pool, userID int64) (int, error) {
	var n int
	err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM passkey WHERE user_account_id = $1`, userID).Scan(&n)
	return n, err
}

// registrationOptions is passkeys.registration_options: the options object the
// browser's navigator.credentials.create() takes (not wrapped in "publicKey").
func registrationOptions(ctx context.Context, pool *pgxpool.Pool, wa *webauthn.WebAuthn, a *passkeyAccount, at time.Time) (any, error) {
	if err := ensureHandle(ctx, pool, a); err != nil {
		return nil, err
	}
	rows, err := pool.Query(ctx, `SELECT credential_id, transports FROM passkey WHERE user_account_id = $1`, a.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var exclude []protocol.CredentialDescriptor
	for rows.Next() {
		var id string
		var transports *string
		if err := rows.Scan(&id, &transports); err != nil {
			return nil, err
		}
		raw, err := unb64(id)
		if err != nil {
			continue
		}
		d := protocol.CredentialDescriptor{Type: protocol.PublicKeyCredentialType, CredentialID: raw}
		if transports != nil {
			for _, t := range strings.Split(*transports, ",") {
				if t = strings.TrimSpace(t); t != "" {
					d.Transport = append(d.Transport, protocol.AuthenticatorTransport(t))
				}
			}
		}
		exclude = append(exclude, d)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	creation, _, err := wa.BeginRegistration(rpUser{acct: *a}, webauthn.WithExclusions(exclude))
	if err != nil {
		return nil, err
	}
	if err := storeChallenge(ctx, pool, creation.Response.Challenge, passkeyRegister, &a.ID, at); err != nil {
		return nil, err
	}
	return creation.Response, nil
}

// authenticationOptions is passkeys.authentication_options: any passkey this
// site knows (empty allow list), user verification required.
func authenticationOptions(ctx context.Context, pool *pgxpool.Pool, wa *webauthn.WebAuthn, at time.Time) (any, error) {
	assertion, _, err := wa.BeginDiscoverableLogin(webauthn.WithUserVerification(protocol.VerificationRequired))
	if err != nil {
		return nil, err
	}
	if err := storeChallenge(ctx, pool, assertion.Response.Challenge, passkeyLogin, nil, at); err != nil {
		return nil, err
	}
	return assertion.Response, nil
}

// registerPasskey is passkeys.register: verify the browser's answer, spend the
// challenge and store the new passkey. The count limit is part of the INSERT.
func registerPasskey(ctx context.Context, pool *pgxpool.Pool, wa *webauthn.WebAuthn, a *passkeyAccount,
	credential []byte, name string, at time.Time) (int64, error) {
	if n, err := passkeyCount(ctx, pool, a.ID); err != nil {
		return 0, err
	} else if n >= passkeyMax {
		return 0, failed("too_many")
	}
	parsed, err := protocol.ParseCredentialCreationResponseBytes(credential)
	if err != nil {
		return 0, failed("malformed")
	}
	challenge, err := unb64(parsed.Response.CollectedClientData.Challenge)
	if err != nil || len(challenge) == 0 {
		return 0, failed("malformed")
	}
	if err := spendChallenge(ctx, pool, challenge, passkeyRegister, a.ID, at); err != nil {
		return 0, err
	}
	if err := ensureHandle(ctx, pool, a); err != nil {
		return 0, err
	}
	session := webauthn.SessionData{
		Challenge:        b64(challenge),
		RelyingPartyID:   wa.Config.RPID,
		UserID:           a.Handle,
		UserVerification: protocol.VerificationRequired,
		CredParams:       webauthn.CredentialParametersDefault(),
	}
	cred, err := wa.CreateCredential(rpUser{acct: *a}, session, parsed)
	if err != nil {
		return 0, failed("invalid")
	}
	transports := make([]string, 0, len(parsed.Response.Transports))
	for _, t := range parsed.Response.Transports {
		transports = append(transports, string(t))
	}
	joined := strings.Join(transports, ",")
	if len(joined) > passkeyTransportsLimit {
		joined = joined[:passkeyTransportsLimit]
	}
	backedUp := 0
	if cred.Flags.BackupState {
		backedUp = 1
	}
	var id int64
	err = pool.QueryRow(ctx, `INSERT INTO passkey (user_account_id, credential_id, public_key, sign_count, transports, name, backed_up, created_at)
		SELECT $1, $2, $3, $4, $5, $6, $7, $8 WHERE (SELECT COUNT(*) FROM passkey WHERE user_account_id = $1) < $9
		RETURNING id`, a.ID, b64(cred.ID), b64(cred.PublicKey), int64(cred.Authenticator.SignCount), joined, name, backedUp,
		passkeyTime(at), passkeyMax).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, failed("too_many")
	}
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		return 0, failed("duplicate")
	}
	return id, err
}

// passkeyRow is one stored credential.
type passkeyRow struct {
	ID        int64
	UserID    int64
	PublicKey []byte
	SignCount int64
	BackedUp  bool
	ID64      string
}

// authenticatePasskey is passkeys.authenticate: verify a login answer and
// return the active account and the passkey row, or a passkeyError. A refused
// counter reports "sign_count" together with the row (so the caller can audit
// the clone); no row is changed then.
func authenticatePasskey(ctx context.Context, pool *pgxpool.Pool, wa *webauthn.WebAuthn, credential []byte, at time.Time) (*passkeyAccount, *passkeyRow, error) {
	parsed, err := protocol.ParseCredentialRequestResponseBytes(credential)
	if err != nil {
		return nil, nil, failed("malformed")
	}
	challenge, err := unb64(parsed.Response.CollectedClientData.Challenge)
	if err != nil || len(challenge) == 0 {
		return nil, nil, failed("malformed")
	}
	if err := spendChallenge(ctx, pool, challenge, passkeyLogin, 0, at); err != nil {
		return nil, nil, err
	}
	row := &passkeyRow{ID64: b64(parsed.RawID)}
	var publicKey string
	var backed int64
	err = pool.QueryRow(ctx, `SELECT id, user_account_id, public_key, sign_count, backed_up FROM passkey WHERE credential_id = $1`, row.ID64).
		Scan(&row.ID, &row.UserID, &publicKey, &row.SignCount, &backed)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil, failed("unknown")
	}
	if err != nil {
		return nil, nil, err
	}
	row.BackedUp = backed != 0
	if row.PublicKey, err = unb64(publicKey); err != nil {
		return nil, nil, failed("invalid")
	}
	account, err := loadPasskeyAccount(ctx, pool, row.UserID)
	if err != nil {
		return nil, nil, err
	}
	if account == nil {
		return nil, nil, failed("inactive")
	}
	// The passkey belongs to this account only if the handle it presents is
	// the account's. An account without a handle cannot own a passkey.
	if len(account.Handle) == 0 {
		return nil, nil, failed("handle")
	}
	if len(parsed.Response.UserHandle) > 0 && string(parsed.Response.UserHandle) != string(account.Handle) {
		return nil, nil, failed("handle")
	}
	stored := webauthn.Credential{
		ID:        parsed.RawID,
		PublicKey: row.PublicKey,
		Flags: webauthn.CredentialFlags{
			UserPresent:    true,
			UserVerified:   true,
			BackupEligible: row.BackedUp || parsed.Response.AuthenticatorData.Flags.HasBackupEligible(),
			BackupState:    row.BackedUp,
		},
		Authenticator: webauthn.Authenticator{SignCount: uint32(row.SignCount)},
	}
	session := webauthn.SessionData{
		Challenge:        b64(challenge),
		RelyingPartyID:   wa.Config.RPID,
		UserID:           account.Handle,
		UserVerification: protocol.VerificationRequired,
	}
	verified, err := wa.ValidateLogin(rpUser{acct: *account, cred: []webauthn.Credential{stored}}, session, parsed)
	if err != nil {
		return nil, nil, failed("invalid")
	}
	if verified.Authenticator.CloneWarning {
		return account, row, failed("sign_count")
	}
	backedUp := 0
	if verified.Flags.BackupState {
		backedUp = 1
	}
	// The old counter is part of the WHERE: of two logins that raced on the
	// same row only one can move it.
	tag, err := pool.Exec(ctx, `UPDATE passkey SET sign_count = $1, last_used_at = $2, backed_up = $3 WHERE id = $4 AND sign_count = $5`,
		int64(verified.Authenticator.SignCount), passkeyTime(at), backedUp, row.ID, row.SignCount)
	if err != nil {
		return nil, nil, err
	}
	if tag.RowsAffected() != 1 {
		return nil, nil, failed("invalid")
	}
	return account, row, nil
}
