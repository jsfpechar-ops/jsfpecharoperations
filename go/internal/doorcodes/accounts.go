package doorcodes

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// pgAccounts is the lock_account table as ttlock.AccountStore. The *_enc columns are
// read and written through the secure package; plain values never reach SQL.
type pgAccounts struct {
	pool *pgxpool.Pool
	keys *secure.MultiFernet
}

// NewAccountStore returns the lock_account store for the TTLock client.
func NewAccountStore(pool *pgxpool.Pool, keys *secure.MultiFernet) ttlock.AccountStore {
	return &pgAccounts{pool: pool, keys: keys}
}

const accountColumns = "id, owner_user_id, username, password_enc, access_token_enc, refresh_token_enc, " +
	"token_expires_at, token_version, status, locks_json"

func (p *pgAccounts) decrypt(token *string) (string, error) {
	if token == nil || *token == "" {
		return "", nil
	}
	plain, err := p.keys.Decrypt(*token, 0, time.Now())
	if err != nil {
		return "", err
	}
	return string(plain), nil
}

func (p *pgAccounts) encrypt(plain string) (any, error) {
	if plain == "" {
		return nil, nil
	}
	return p.keys.EncryptString(plain)
}

// tokenExpiry stores a zero time as NULL (Python token_expires_at NULL).
func tokenExpiry(t time.Time) any {
	if t.IsZero() {
		return nil
	}
	return iso(t)
}

func (p *pgAccounts) scan(row pgx.Row) (*ttlock.Account, error) {
	var (
		a                                   ttlock.Account
		pwEnc, accEnc, refEnc, expires, loc *string
	)
	err := row.Scan(&a.ID, &a.OwnerUserID, &a.Username, &pwEnc, &accEnc, &refEnc, &expires,
		&a.TokenVersion, &a.Status, &loc)
	if isNoRows(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if a.Password, err = p.decrypt(pwEnc); err != nil {
		return nil, err
	}
	if a.AccessToken, err = p.decrypt(accEnc); err != nil {
		return nil, err
	}
	if a.RefreshToken, err = p.decrypt(refEnc); err != nil {
		return nil, err
	}
	if expires != nil && *expires != "" {
		if a.ExpiresAt, err = parseISO(*expires); err != nil {
			return nil, err
		}
	}
	if loc != nil {
		a.LocksJSON = []byte(*loc)
	}
	return &a, nil
}

// Load returns the row with this id, or nil.
func (p *pgAccounts) Load(ctx context.Context, id int64) (*ttlock.Account, error) {
	return p.scan(p.pool.QueryRow(ctx, "SELECT "+accountColumns+" FROM lock_account WHERE id = $1", id))
}

// ForOwner returns the host's TTLock account (provider ttlock), or nil.
func (p *pgAccounts) ForOwner(ctx context.Context, ownerUserID int64) (*ttlock.Account, error) {
	return p.scan(p.pool.QueryRow(ctx,
		"SELECT "+accountColumns+" FROM lock_account WHERE owner_user_id = $1 AND provider = 'ttlock' ORDER BY id LIMIT 1",
		ownerUserID))
}

// Insert stores a new row with status ok and token_version 0.
func (p *pgAccounts) Insert(ctx context.Context, ownerUserID int64, username, password string, now time.Time) (int64, error) {
	enc, err := p.encrypt(password)
	if err != nil {
		return 0, err
	}
	stamp := iso(now)
	var id int64
	err = p.pool.QueryRow(ctx,
		"INSERT INTO lock_account (owner_user_id, provider, username, password_enc, status, token_version, created_at, updated_at) "+
			"VALUES ($1, 'ttlock', $2, $3, 'ok', 0, $4, $4) RETURNING id",
		ownerUserID, username, enc, stamp).Scan(&id)
	return id, err
}

// SaveLogin stores a token pair from the password login and bumps token_version.
func (p *pgAccounts) SaveLogin(ctx context.Context, id int64, rec ttlock.TokenRecord, now time.Time) error {
	access, err := p.encrypt(rec.AccessToken)
	if err != nil {
		return err
	}
	refresh, err := p.encrypt(rec.RefreshToken)
	if err != nil {
		return err
	}
	_, err = p.pool.Exec(ctx,
		"UPDATE lock_account SET access_token_enc = $1, refresh_token_enc = $2, token_expires_at = $3, "+
			"token_version = token_version + 1, updated_at = $4 WHERE id = $5",
		access, refresh, tokenExpiry(rec.ExpiresAt), iso(now), id)
	return err
}

// SaveRefresh stores a token pair only while token_version is still expectVersion
// (Python _refresh: WHERE token_version = ?). It reports whether the row was written.
func (p *pgAccounts) SaveRefresh(ctx context.Context, id int64, expectVersion int64, rec ttlock.TokenRecord, now time.Time) (bool, error) {
	access, err := p.encrypt(rec.AccessToken)
	if err != nil {
		return false, err
	}
	refresh, err := p.encrypt(rec.RefreshToken)
	if err != nil {
		return false, err
	}
	tag, err := p.pool.Exec(ctx,
		"UPDATE lock_account SET access_token_enc = $1, refresh_token_enc = $2, token_expires_at = $3, "+
			"token_version = $4, updated_at = $5 WHERE id = $6 AND token_version = $7",
		access, refresh, tokenExpiry(rec.ExpiresAt), expectVersion+1, iso(now), id, expectVersion)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// SetStatus stores the row status (ok or reauth_needed).
func (p *pgAccounts) SetStatus(ctx context.Context, id int64, status string, now time.Time) error {
	_, err := p.pool.Exec(ctx, "UPDATE lock_account SET status = $1, updated_at = $2 WHERE id = $3",
		status, iso(now), id)
	return err
}

// SaveLocks stores the lock list and when it was fetched.
func (p *pgAccounts) SaveLocks(ctx context.Context, id int64, locksJSON []byte, now time.Time) error {
	stamp := iso(now)
	_, err := p.pool.Exec(ctx,
		"UPDATE lock_account SET locks_json = $1, locks_fetched_at = $2, updated_at = $2 WHERE id = $3",
		string(locksJSON), stamp, id)
	return err
}

// Delete removes the row.
func (p *pgAccounts) Delete(ctx context.Context, id int64) error {
	_, err := p.pool.Exec(ctx, "DELETE FROM lock_account WHERE id = $1", id)
	return err
}
