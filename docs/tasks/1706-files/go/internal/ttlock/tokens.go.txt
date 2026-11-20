package ttlock

import (
	"context"
	"errors"
	"time"
)

// Account statuses, as the lock_account.status column holds them.
const (
	AccountStatusOK           = "ok"
	AccountStatusReauthNeeded = "reauth_needed"
)

// refreshWindow is how close to expiry a token is renewed before use (_access_token).
const refreshWindow = 7 * 24 * time.Hour

// Account is one TTLock user of a host, as the AccountStore returns it. Password
// and the tokens are plain text here: the store decrypts on read and encrypts on
// write (the Python lock_account columns are *_enc). Nothing in this package logs them.
type Account struct {
	ID           int64
	OwnerUserID  int64
	Username     string // the prefixed username TTLock returned at registration
	Password     string
	Status       string
	AccessToken  string
	RefreshToken string
	// ExpiresAt is the zero time when no expiry is stored (Python: token_expires_at NULL).
	ExpiresAt    time.Time
	TokenVersion int64
	LocksJSON    []byte
}

// TokenRecord is one token answer from TTLock, with its expiry worked out from expires_in.
type TokenRecord struct {
	AccessToken  string
	RefreshToken string
	ExpiresAt    time.Time
}

// AccountStore is the lock_account table as the client uses it. The door-codes port
// implements it on pgxpool, through the secure package for the *_enc columns.
//
// SaveRefresh is the compare-and-set the Python _refresh does with
// "WHERE token_version = ?": it returns false, and writes nothing, when the version has moved on.
type AccountStore interface {
	// Load returns the row with this id, or nil when there is none.
	Load(ctx context.Context, id int64) (*Account, error)
	// ForOwner returns the host's TTLock account, or nil.
	ForOwner(ctx context.Context, ownerUserID int64) (*Account, error)
	// Insert stores a new row with status ok and token_version 0, and returns its id.
	Insert(ctx context.Context, ownerUserID int64, username, password string, now time.Time) (int64, error)
	// SaveLogin stores a token pair from the password login and bumps token_version by one.
	SaveLogin(ctx context.Context, id int64, rec TokenRecord, now time.Time) error
	// SaveRefresh stores a token pair only if token_version is still expectVersion.
	SaveRefresh(ctx context.Context, id int64, expectVersion int64, rec TokenRecord, now time.Time) (bool, error)
	SetStatus(ctx context.Context, id int64, status string, now time.Time) error
	SaveLocks(ctx context.Context, id int64, locksJSON []byte, now time.Time) error
	Delete(ctx context.Context, id int64) error
}

// tokenRecord reads access_token, refresh_token and expires_in (default 0) from a token answer.
// Missing access_token or refresh_token is an error (Python raises KeyError).
func tokenRecord(data map[string]any, now time.Time) (TokenRecord, error) {
	access, okAccess := data["access_token"]
	refresh, okRefresh := data["refresh_token"]
	if !okAccess || !okRefresh {
		return TokenRecord{}, errors.New("ttlock: token answer has no access_token or refresh_token")
	}
	var secs int64
	if v, ok := data["expires_in"]; ok && v != nil {
		n, err := asInt(v)
		if err != nil {
			return TokenRecord{}, err
		}
		secs = n
	}
	return TokenRecord{
		AccessToken:  pyStr(access),
		RefreshToken: pyStr(refresh),
		ExpiresAt:    now.Add(time.Duration(secs) * time.Second).Truncate(time.Second),
	}, nil
}

// account loads the row or fails with "missing account" (Python TTLockError kind config).
func (c *Client) account(ctx context.Context, accountID int64) (*Account, error) {
	acc, err := c.accounts.Load(ctx, accountID)
	if err != nil {
		return nil, err
	}
	if acc == nil {
		return nil, newErr(KindConfig, "missing account")
	}
	return acc, nil
}

// login ports _login: the password exchange (md5 of the password) for a new token pair.
func (c *Client) login(ctx context.Context, accountID int64) (string, error) {
	acc, err := c.account(ctx, accountID)
	if err != nil {
		return "", err
	}
	if acc.Password == "" {
		return "", newErr(KindConfig, "missing password")
	}
	data, err := c.post(ctx, "/oauth2/token", map[string]any{
		"username": acc.Username,
		"password": md5Password(acc.Password),
	}, PriorityNormal)
	if err != nil {
		return "", err
	}
	now := c.now()
	rec, err := tokenRecord(data, now)
	if err != nil {
		return "", err
	}
	if err := c.accounts.SaveLogin(ctx, accountID, rec, now); err != nil {
		return "", err
	}
	return rec.AccessToken, nil
}

// refresh ports _refresh: exchanges the refresh token. A "reauth" answer falls back to
// the password login; if that fails too, the row is marked reauth_needed. When another
// request refreshed first (version moved on), the stored token is used instead.
func (c *Client) refresh(ctx context.Context, acc *Account) (string, error) {
	if acc.RefreshToken == "" {
		return "", newErr(KindReauth, "missing refresh token")
	}
	version := acc.TokenVersion
	data, err := c.post(ctx, "/oauth2/token", map[string]any{
		"grant_type":    "refresh_token",
		"refresh_token": acc.RefreshToken,
	}, PriorityNormal)
	if err != nil {
		if !IsKind(err, KindReauth) {
			return "", err
		}
		token, loginErr := c.login(ctx, acc.ID)
		if loginErr != nil {
			var te *TTLockError
			if errors.As(loginErr, &te) {
				if statusErr := c.accounts.SetStatus(ctx, acc.ID, AccountStatusReauthNeeded, c.now()); statusErr != nil {
					return "", statusErr
				}
			}
			return "", loginErr
		}
		return token, nil
	}

	now := c.now()
	rec, err := tokenRecord(data, now)
	if err != nil {
		return "", err
	}
	saved, err := c.accounts.SaveRefresh(ctx, acc.ID, version, rec, now)
	if err != nil {
		return "", err
	}
	if saved {
		return rec.AccessToken, nil
	}
	fresh, err := c.account(ctx, acc.ID)
	if err != nil {
		return "", err
	}
	if fresh.AccessToken == "" {
		return "", newErr(KindReauth, "missing access token")
	}
	return fresh.AccessToken, nil
}

// accessToken ports _access_token: the stored token, refreshed when it expires within 7 days,
// when none is stored, or never if the status is not ok (then "reauth needed").
func (c *Client) accessToken(ctx context.Context, accountID int64) (string, error) {
	acc, err := c.account(ctx, accountID)
	if err != nil {
		return "", err
	}
	if acc.Status != AccountStatusOK {
		return "", newErr(KindReauth, "reauth needed")
	}
	if !acc.ExpiresAt.IsZero() && acc.ExpiresAt.Before(c.now().Add(refreshWindow)) {
		return c.refresh(ctx, acc)
	}
	if acc.AccessToken == "" {
		return c.refresh(ctx, acc)
	}
	return acc.AccessToken, nil
}

// call ports _call: one signed request with a valid access token. If TTLock answers with
// an auth error, the token is refreshed and the request is sent once more.
func (c *Client) call(ctx context.Context, accountID int64, path string, data map[string]any, priority string) (map[string]any, error) {
	token, err := c.accessToken(ctx, accountID)
	if err != nil {
		return nil, err
	}
	out, err := c.post(ctx, path, withToken(data, token), priority)
	if err == nil {
		return out, nil
	}
	if !IsKind(err, KindAuth) {
		return nil, err
	}
	first := err
	acc, err := c.accounts.Load(ctx, accountID)
	if err != nil {
		return nil, err
	}
	if acc == nil {
		return nil, first
	}
	if _, err := c.refresh(ctx, acc); err != nil {
		return nil, err
	}
	token, err = c.accessToken(ctx, accountID)
	if err != nil {
		return nil, err
	}
	return c.post(ctx, path, withToken(data, token), priority)
}
