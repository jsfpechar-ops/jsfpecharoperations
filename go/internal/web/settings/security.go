package settings

// The security group of /settings (brief 1704c), the Go twin of the
// `group == 'security'` block of templates/settings.html: the logout-all row,
// the passkeys list (read only: add, rename and remove post to the 1760
// routes) and the 2FA state (the forms post to the Python routes).
//
// SecurityData is the one page-data struct of this page and loadSecurity the
// one function that builds it, so brief 1764 adds `DeviceKind string` to the
// struct and sets it in loadSecurity; it edits the template "settings.passkeys"
// in group_security.tmpl, never the routes.

import (
	"context"
	"net/http"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth/authpage"
)

// Passkey is one row of "passkeys.for_account": the name and the two stamps.
type Passkey struct {
	ID                    int64
	Name                  string
	CreatedAt, LastUsedAt string // stored UTC stamps; LastUsedAt is "" for never
}

// SecurityData is the context of the security group. Brief 1764 adds
// `DeviceKind string` here (and nothing else in this file).
type SecurityData struct {
	TOTPEnabled       bool // current_user.totp_enabled
	PasskeysAvailable bool // passkeys.available()
	Passkeys          []Passkey
}

// The signed-in account's own rows: both are keyed by h.Account.ID (Python
// reads auth.current_user, not the workspace), as 1704b's accountSQL is.
const (
	totpSQL     = `SELECT COALESCE(totp_enabled, 0) <> 0 FROM user_account WHERE id = $1`
	passkeysSQL = `SELECT id, name, created_at, COALESCE(last_used_at, '') FROM passkey WHERE user_account_id = $1 ORDER BY id`
)

// loadSecurity builds SecurityData: routes/admin.py _settings_page keys
// "passkeys" (_own_passkeys) and "passkeys_available", and the template's
// current_user.totp_enabled.
func loadSecurity(ctx context.Context, d deps, h *session.Host, _ *http.Request, _ time.Time, p *pageData) error {
	v := &SecurityData{PasskeysAvailable: authpage.PasskeysAvailable(d.getenv)}
	if err := d.pool.QueryRow(ctx, totpSQL, h.Account.ID).Scan(&v.TOTPEnabled); err != nil {
		return err
	}
	rows, err := d.pool.Query(ctx, passkeysSQL, h.Account.ID)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var k Passkey
		if err := rows.Scan(&k.ID, &k.Name, &k.CreatedAt, &k.LastUsedAt); err != nil {
			return err
		}
		v.Passkeys = append(v.Passkeys, k)
	}
	if err := rows.Err(); err != nil {
		return err
	}
	p.Security = v
	return nil
}
