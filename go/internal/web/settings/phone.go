package settings

// The phone group of /settings (brief 1704c), the Go twin of the
// `group == 'phone'` block of templates/settings.html: the PWA install row
// (the buttons are driven by static JS) and the push row with the account's
// devices. Read only: the device remove form posts to the 1760 push route.

import (
	"context"
	"net/http"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pushsend"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth/authpage"
)

// PushDevice is one row of push.devices_for: the id, the coarse device name
// ("" shows push.device_unknown) and the stored UTC creation stamp.
type PushDevice struct {
	ID        int64
	Device    string
	CreatedAt string
}

// PhoneData is the context of the phone group.
type PhoneData struct {
	PasskeysAvailable bool   // passkeys.available(): the iOS passkey hint
	PushAvailable     bool   // _push_available: web push on and no admin preview
	PushKey           string // push.public_key(), only when PushAvailable
	Devices           []PushDevice
}

// pushDevicesSQL is push.devices_for. The rows are the signed-in account's
// own (user_account_id = h.Account.ID); they are read only while the account
// looks at its own workspace.
const pushDevicesSQL = `SELECT id, device, created_at FROM push_subscription WHERE user_account_id = $1 ORDER BY created_at, id`

// webPushOn is push.enabled(): UBYHOST_WEB_PUSH is on unless 0, false or no.
func webPushOn(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_WEB_PUSH"))) {
	case "0", "false", "no":
		return false
	}
	return true
}

// loadPhone builds PhoneData: _push_available (alerts are per person, off
// while an admin previews another workspace), push.public_key() and
// _own_push_devices.
func loadPhone(ctx context.Context, d deps, h *session.Host, _ *http.Request, _ time.Time, p *pageData) error {
	v := &PhoneData{PasskeysAvailable: authpage.PasskeysAvailable(d.getenv)}
	v.PushAvailable = webPushOn(d.getenv) && h.Workspace.ID == h.Account.ID
	if v.PushAvailable {
		key, err := (&pushsend.Sender{Pool: d.pool, Getenv: d.getenv}).PublicKey(ctx)
		if err != nil {
			return err
		}
		v.PushKey = key
		rows, err := d.pool.Query(ctx, pushDevicesSQL, h.Account.ID)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var dev PushDevice
			if err := rows.Scan(&dev.ID, &dev.Device, &dev.CreatedAt); err != nil {
				return err
			}
			v.Devices = append(v.Devices, dev)
		}
		if err := rows.Err(); err != nil {
			return err
		}
	}
	p.Phone = v
	return nil
}
