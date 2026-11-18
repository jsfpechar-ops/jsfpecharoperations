package settings

// Tests of GET /settings/security and GET /settings/phone (brief 1704c). The
// expected strings are written by hand from the seed below, the Python
// template (templates/settings.html) and the host catalog; there is no Python
// golden file. The helpers (testPool, seed, req, page, mustContain, ...) are
// the ones of settings_test.go.

import (
	"context"
	"net/http"
	"regexp"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

func init() {
	groupOf["/settings/security"] = "security"
	groupOf["/settings/phone"] = "phone"
}

// seedDevices adds, on top of seed(): host 3 has two-factor sign-in on;
// passkeys 1 and 2 of host 2 (the second has no last use and a name with
// markup) and 3 of host 3; push devices 1 and 2 of host 2 (2 is older and has
// no device name) and 3 of host 3. Admin 1 owns none.
func seedDevices(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	exec := func(sql string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, sql, args...); err != nil {
			t.Fatalf("%s: %v", sql, err)
		}
	}
	exec(`UPDATE user_account SET totp_enabled = 1 WHERE id = 3`)
	exec(`INSERT INTO passkey (id, user_account_id, credential_id, public_key, name, created_at, last_used_at) VALUES
		(1, 2, 'cred-1', 'pk', 'iPhone of Hana', '2026-03-01T09:00:00+00:00', '2026-07-05T08:30:00+00:00'),
		(2, 2, 'cred-2', 'pk', 'Work "Key" <b>', '2026-06-01T10:00:00+00:00', NULL),
		(3, 3, 'cred-3', 'pk', 'Foreign Passkey', '2026-04-01T10:00:00+00:00', NULL)`)
	exec(`INSERT INTO push_subscription (id, user_account_id, endpoint_hash, endpoint_enc, p256dh_enc, auth_enc, device, created_at, last_seen_at) VALUES
		(1, 2, 'h1', 'e', 'p', 'a', 'iPhone', '2026-02-01T11:00:00+00:00', '2026-02-01T11:00:00+00:00'),
		(2, 2, 'h2', 'e', 'p', 'a', '', '2026-01-15T07:00:00+00:00', '2026-01-15T07:00:00+00:00'),
		(3, 3, 'h3', 'e', 'p', 'a', 'Foreign Phone', '2026-02-02T11:00:00+00:00', '2026-02-02T11:00:00+00:00')`)
}

// httpsEnv is the environment of an installation that offers passkeys.
func httpsEnv() map[string]string {
	env := baseEnv()
	env["UBYHOST_PUBLIC_BASE_URL"] = "https://host.example.test"
	return env
}

func body(t *testing.T, pool *pgxpool.Pool, env map[string]string, target string, user, as int64, lang string) string {
	t.Helper()
	rec := req(t, pool, env, target, user, as, lang)
	if rec.Code != http.StatusOK {
		t.Fatalf("%s as %d: status %d, body %.200s", target, user, rec.Code, rec.Body.String())
	}
	if got := rec.Header().Get("Cache-Control"); got != "no-store, private" {
		t.Errorf("%s: Cache-Control %q", target, got)
	}
	return rec.Body.String()
}

// everyPostFormHasCSRF fails unless each post form of the group carries the
// hidden _csrf input (the pages work without JavaScript).
func everyPostFormHasCSRF(t *testing.T, name, section string, wantForms int) {
	t.Helper()
	forms := strings.Count(section, `<form method="post"`)
	if forms != wantForms {
		t.Errorf("%s: %d post forms, want %d", name, forms, wantForms)
	}
	if n := strings.Count(section, `<input type="hidden" name="_csrf" value="`); n != forms {
		t.Errorf("%s: %d _csrf inputs for %d forms", name, n, forms)
	}
}

func TestSettingsSecuritySignedOut(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	for _, target := range []string{"/settings/security", "/settings/phone"} {
		rec := req(t, pool, baseEnv(), target, 0, 0, "en")
		if rec.Code != http.StatusSeeOther && rec.Code != http.StatusFound {
			t.Fatalf("%s: status %d, want a redirect", target, rec.Code)
		}
		if loc := rec.Header().Get("Location"); loc != "/login?next="+target {
			t.Errorf("%s: Location %q", target, loc)
		}
	}
}

// TestSettingsSecurity is host 2 on an https installation: the logout-all row,
// two passkeys in id order, and two-factor sign-in off.
func TestSettingsSecurity(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	page := body(t, pool, httpsEnv(), "/settings/security", 2, 0, "en")
	mustContain(t, "security", page,
		`<title>Settings`,
		`<a class="airbnb-back" href="/settings" aria-label="Back">`,
		`<h1 class="airbnb-title">Security</h1>`,
		`<section class="settings-group" id="settings-group-security" aria-labelledby="settings-group-security-title"><h2 class="settings-group-title sec" id="settings-group-security-title">Security</h2>`,
		`<div class="ui-section" id="settings-security">`,
		`<div class="settings-action-list" id="settings-logout-all">`,
		`<form method="post" action="/account/logout-all">`,
		`Log out of all devices</button>`,
		`<div class="settings-action-list" id="settings-passkeys">`,
		// The add button and the unsupported note exist because passkeys are available.
		`<button class="ui-btn ui-btn-primary ui-btn-compact" type="button" data-passkey-add data-passkey-supported hidden>Add a passkey</button>`,
		`<p class="ui-sub" data-passkey-unsupported>This browser cannot create passkeys.`,
		`<p class="ui-sub err-text" data-passkey-error data-generic="`,
		// The count card.
		`<span class="settings-value-label">Registered</span>
  <strong class="settings-value">2</strong>`,
		// Passkey 1: created 09:00 UTC is 10:00 in Prague in March; last used 08:30 UTC is 10:30 in July.
		`<strong>iPhone of Hana</strong>`,
		`<small>Added 2026-03-01 10:00 ·`,
		`last used 2026-07-05 10:30</small>`,
		`<form method="post" action="/account/passkeys/1/delete"`,
		`<form method="post" action="/account/passkeys/1/rename" class="settings-move-form">`,
		`<label for="passkey-name-1">Name</label>`,
		`<input id="passkey-name-1" name="name" type="text" maxlength="60"
                       value="iPhone of Hana" required>`,
		// Passkey 2: never used, the name is escaped everywhere it is printed.
		`<small>Added 2026-06-01 12:00 ·`,
		`not used yet</small>`,
		`<form method="post" action="/account/passkeys/2/delete"`,
		`<strong>Work &#34;Key&#34; &lt;b&gt;</strong>`,
		`value="Work &#34;Key&#34; &lt;b&gt;" required>`,
		`data-confirm-message="Remove the passkey “Work &#34;Key&#34; &lt;b&gt;”? That device then logs in with the e-mail link."`,
		// Two-factor sign-in is off: the setup row, no move or disable forms.
		`<strong class="tip-label">Two-factor <span class="tip-nowrap">authentication`,
		`<a class="ui-btn ui-btn-secondary ui-btn-compact" href="/account/2fa/setup">Set up</a>`,
	)
	inOrder(t, "security order", page,
		`id="settings-logout-all"`, `id="settings-passkeys"`, `/account/passkeys/1/delete`, `/account/passkeys/1/rename`,
		`/account/passkeys/2/delete`, `/account/passkeys/2/rename`, `href="/account/2fa/setup"`)
	mustNotContain(t, "security", page,
		`Foreign Passkey`, `<b>`, `/account/passkeys/3/`, `/account/2fa/move`, `/account/2fa/disable`, `id="move-code"`,
		`id="settings-group-phone"`, `id="settings-group-account"`, `id="settings-install"`,
		`Passkeys need the site&#39;s own https address`)
	// 5 post forms: logout-all, and delete and rename for each of the two passkeys.
	everyPostFormHasCSRF(t, "security", from(t, page, `id="settings-group-security"`), 5)
}

// TestSettingsSecurityNoHTTPS is the default installation (an http address):
// no add button and no unsupported note, the help says passkeys are unavailable.
func TestSettingsSecurityNoHTTPS(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	page := body(t, pool, baseEnv(), "/settings/security", 2, 0, "en")
	mustContain(t, "no https", page,
		`<div class="settings-action-list" id="settings-passkeys">`,
		`Passkeys need the site&#39;s own https address. They are not available on this installation.`,
		`<strong>iPhone of Hana</strong>`,
	)
	mustNotContain(t, "no https", page, `data-passkey-add`, `data-passkey-unsupported`, `data-passkey-error`)
}

// TestSettingsSecurityTwoFactorOn is host 3: the state card and the two forms
// replace the setup row; its passkey shows, host 2's do not.
func TestSettingsSecurityTwoFactorOn(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	page := body(t, pool, httpsEnv(), "/settings/security", 3, 0, "en")
	mustContain(t, "2fa on", page,
		`<span class="settings-value-label">Two-factor authentication</span>
  <strong class="settings-value">Enabled</strong>`,
		`<summary>
              <strong>Move to a new phone</strong>`,
		`<form method="post" action="/account/2fa/move" class="settings-move-form">`,
		`<input id="move-code" name="code" type="text" inputmode="numeric"
                       autocomplete="one-time-code" aria-describedby="move-code-hint" required>`,
		`<p class="hint" id="move-code-hint">`,
		`<strong>Switch off the authenticator app</strong>`,
		`<form method="post" action="/account/2fa/disable" class="settings-move-form">`,
		`<input id="disable-code" name="code" type="text" inputmode="numeric"
                       autocomplete="one-time-code" required>`,
		`<strong>Foreign Passkey</strong>`,
		`<strong class="settings-value">1</strong>`,
	)
	mustNotContain(t, "2fa on", page, `/account/2fa/setup`, `iPhone of Hana`, `Work &#34;Key&#34;`)
	// logout-all, delete and rename of the one passkey, move and disable.
	everyPostFormHasCSRF(t, "2fa on", from(t, page, `id="settings-group-security"`), 5)
}

// TestSettingsSecurityNoPasskeys is the admin, who owns no passkey: an
// empty list shows only the count card with 0.
func TestSettingsSecurityNoPasskeys(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	page := body(t, pool, httpsEnv(), "/settings/security", 1, 0, "en")
	mustContain(t, "admin", page, `<strong class="settings-value">0</strong>`, `href="/account/2fa/setup"`)
	mustNotContain(t, "admin", page, `passkey-row`, `iPhone of Hana`, `Foreign Passkey`)
	everyPostFormHasCSRF(t, "admin", from(t, page, `id="settings-group-security"`), 1)
}

// TestSettingsSecurityAdminPreview: an admin looking at host 2's workspace
// still sees the admin's own passkeys and two-factor state (current_user), not
// host 2's.
func TestSettingsSecurityAdminPreview(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	page := body(t, pool, httpsEnv(), "/settings/security", 1, 2, "en")
	mustContain(t, "preview", page, `<strong class="settings-value">0</strong>`, `href="/account/2fa/setup"`)
	mustNotContain(t, "preview", page, `iPhone of Hana`, `Foreign Passkey`, `passkey-row`)
}

// TestSettingsSecurityLanguages checks the group title, a passkey line and the
// two-factor row in cs and vi.
func TestSettingsSecurityLanguages(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	cs := body(t, pool, httpsEnv(), "/settings/security", 2, 0, "cs")
	mustContain(t, "cs", cs, `<title>Nastavení`, `<h1 class="airbnb-title">Zabezpečení</h1>`,
		`Odhlásit ze všech zařízení</button>`, `Přidán 2026-03-01 10:00 ·`, `naposledy použit 2026-07-05 10:30`,
		`zatím nepoužit`, `Zaregistrováno`, `>Nastavit</a>`)
	vi := body(t, pool, httpsEnv(), "/settings/security", 3, 0, "vi")
	mustContain(t, "vi", vi, `<title>Cài đặt`, `<h1 class="airbnb-title">Bảo mật</h1>`,
		`Đăng xuất khỏi mọi thiết bị</button>`, `<strong class="settings-value">Đã bật</strong>`, `Tắt ứng dụng xác thực`)
}

// TestSettingsPhone is host 2 with web push on: the install row, the push row
// with the public key, and the two devices of host 2 in created order.
func TestSettingsPhone(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	page := body(t, pool, httpsEnv(), "/settings/phone", 2, 0, "en")
	mustContain(t, "phone", page,
		`<title>Settings`,
		`<h1 class="airbnb-title">Phone app</h1>`,
		`<section class="settings-group" id="settings-group-phone" aria-labelledby="settings-group-phone-title"><h2 class="settings-group-title sec" id="settings-group-phone-title">Phone app</h2>`,
		`<div class="ui-section" id="settings-phone">`,
		`<div class="settings-action-list" id="settings-install" data-pwa-install-row>`,
		// The install help is the text escaped, then the markup of the second paragraph.
		`It opens full screen, like any other app, and can show urgent alerts.<p class="ui-sub" data-pwa-other>Open this page on your phone, in Safari on iPhone or Chrome on Android, to add UbyHost to the home screen.</p>`,
		`data-pwa-install hidden>`, `data-pwa-installed hidden>`,
		`<p class="ui-sub" data-pwa-ios hidden>`,
		// Passkeys are available, so the second iOS hint exists.
		`<p class="ui-sub" data-pwa-ios hidden>Add a passkey first (under Security).`,
		`id="settings-alerts" data-push-row data-push-key="`,
		`data-push-on hidden>`, `data-push-state-on hidden>`, `data-push-controls hidden>`, `data-push-test>`, `data-push-off>`,
		`<p class="ui-sub" data-push-unsupported>`, `data-push-ios-first hidden>`, `data-push-denied role="status" hidden>`,
		`data-push-status role="status" hidden></p>`, `data-push-error data-generic="`,
		`<p class="ui-sub"><strong>Devices with alerts on</strong></p>`,
		`<strong>Device</strong>
                <small>Added 2026-01-15 08:00</small>`,
		`<form method="post" action="/account/push/devices/2/delete"
                    data-confirm data-confirm-message="Stop alerts on Device?">`,
		`<strong>iPhone</strong>
                <small>Added 2026-02-01 12:00</small>`,
		`<form method="post" action="/account/push/devices/1/delete"
                    data-confirm data-confirm-message="Stop alerts on iPhone?">`,
	)
	inOrder(t, "phone order", page, `id="settings-install"`, `id="settings-alerts"`, `/account/push/devices/2/delete`, `/account/push/devices/1/delete`)
	mustNotContain(t, "phone", page, `Foreign Phone`, `/account/push/devices/3/`, `id="settings-group-security"`, `id="settings-passkeys"`)
	everyPostFormHasCSRF(t, "phone", from(t, page, `id="settings-group-phone"`), 2)
	// The key is the VAPID public key: 65 raw bytes, base64url without padding (87 characters),
	// and it is the same on the next request (made once, kept in settings).
	re := regexp.MustCompile(`data-push-key="([A-Za-z0-9_-]{87})"`)
	m := re.FindStringSubmatch(page)
	if m == nil {
		t.Fatalf("no 87 character push key in %.300s", page)
	}
	again := body(t, pool, httpsEnv(), "/settings/phone", 3, 0, "en")
	if m2 := re.FindStringSubmatch(again); m2 == nil || m2[1] != m[1] {
		t.Errorf("the push key changed between requests")
	}
}

// TestSettingsPhoneNoPasskeys is the default http installation: no passkey hint
// in the install row.
func TestSettingsPhoneNoPasskeys(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	page := body(t, pool, baseEnv(), "/settings/phone", 2, 0, "en")
	mustContain(t, "phone http", page, `id="settings-install"`, `id="settings-alerts"`)
	if n := strings.Count(page, `data-pwa-ios hidden`); n != 1 {
		t.Errorf("data-pwa-ios paragraphs = %d, want 1", n)
	}
	mustNotContain(t, "phone http", page, `Add a passkey first`)
}

// TestSettingsPhonePushOff: UBYHOST_WEB_PUSH=0 removes the push row and its devices.
func TestSettingsPhonePushOff(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	for _, off := range []string{"0", "false", "no"} {
		env := httpsEnv()
		env["UBYHOST_WEB_PUSH"] = off
		page := body(t, pool, env, "/settings/phone", 2, 0, "en")
		mustContain(t, "push off "+off, page, `id="settings-install"`)
		mustNotContain(t, "push off "+off, page, `settings-alerts`, `data-push-key`, `<strong>iPhone</strong>`, `/account/push/devices/`)
		everyPostFormHasCSRF(t, "push off "+off, from(t, page, `id="settings-group-phone"`), 0)
	}
}

// TestSettingsPhoneOwnerScope: host 3 sees only its device; an admin previewing
// host 2 gets no push row at all (alerts are per person).
func TestSettingsPhoneOwnerScope(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	own := body(t, pool, httpsEnv(), "/settings/phone", 3, 0, "en")
	mustContain(t, "host 3", own, `<strong>Foreign Phone</strong>`, `/account/push/devices/3/delete`)
	mustNotContain(t, "host 3", own, `<strong>iPhone</strong>`, `/account/push/devices/1/`, `/account/push/devices/2/`)
	preview := body(t, pool, httpsEnv(), "/settings/phone", 1, 2, "en")
	mustContain(t, "preview", preview, `id="settings-install"`)
	mustNotContain(t, "preview", preview, `settings-alerts`, `data-push-key`, `<strong>iPhone</strong>`, `Foreign Phone`, `/account/push/devices/`)
	// A host without devices has the push row and no device list.
	none := body(t, pool, httpsEnv(), "/settings/phone", 1, 0, "en")
	mustContain(t, "no devices", none, `id="settings-alerts"`)
	mustNotContain(t, "no devices", none, `Devices with alerts on`, `/account/push/devices/`)
}

func TestSettingsPhoneLanguages(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	cs := body(t, pool, httpsEnv(), "/settings/phone", 2, 0, "cs")
	mustContain(t, "cs", cs, `<title>Nastavení`, `<h1 class="airbnb-title">Aplikace v telefonu</h1>`,
		`Zařízení se zapnutými upozorněními`, `Přidáno 2026-01-15 08:00`, `Zastavit upozornění na zařízení iPhone?`, `>Odebrat</button>`)
	vi := body(t, pool, httpsEnv(), "/settings/phone", 2, 0, "vi")
	mustContain(t, "vi", vi, `<title>Cài đặt`, `Thiết bị đang bật cảnh báo`, `Đã thêm 2026-02-01 12:00`, `Dừng cảnh báo trên iPhone?`)
}

// TestSettingsIndexHasNoSecurityBody: the index still draws no group body now that
// security and phone are templates too.
func TestSettingsIndexHasNoSecurityBody(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedDevices(t, pool)
	page := body(t, pool, httpsEnv(), "/settings", 2, 0, "en")
	mustNotContain(t, "index", page, `id="settings-group-security"`, `id="settings-group-phone"`, `id="settings-passkeys"`, `id="settings-install"`)
}

func TestWebPushOn(t *testing.T) {
	for v, want := range map[string]bool{"": true, "1": true, "yes": true, "0": false, "false": false, "No": false, " FALSE ": false, "off": true} {
		got := webPushOn(func(string) string { return v })
		if got != want {
			t.Errorf("UBYHOST_WEB_PUSH=%q: %v, want %v", v, got, want)
		}
	}
}
