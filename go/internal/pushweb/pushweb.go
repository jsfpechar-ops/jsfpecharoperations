// Package pushweb serves four routes of the Web Push device API
// (App/app/routes/push.py): turn alerts on (subscribe), refresh a known device,
// turn alerts off (unsubscribe) and the Settings remove form. The test-alert
// route stays in Python until the push sender moves to Go.
//
// Every route runs the CSRF gate first, as the Python admin router does. The
// routes act on the signed-in account only: an admin previewing another
// workspace gets 401 (JSON) or the sign-in flash (the form), so alerts about
// someone else's stays never reach the admin's phone.
package pushweb

import (
	"context"
	"crypto/ecdh"
	"crypto/sha256"
	_ "embed"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the keys in i18n_keys.txt, generated from host_i18n.py by
// App/scripts/go_host_i18n.py.
var catalog = hostweb.Load(catalogJSON)

const (
	phonePath   = "/settings#settings-group-phone"
	maxBody     = 8 * 1024 // push.py _MAX_BODY
	maxDevices  = 10       // push.py MAX_DEVICES
	maxEndpoint = 1024
	maxDevice   = 40
	defaultLang = "en"
)

// pushHosts are the push services browsers use (push.py PUSH_HOST_SUFFIXES).
var pushHosts = []string{
	"fcm.googleapis.com",
	"push.services.mozilla.com",
	"push.apple.com",
	"notify.windows.com",
}

// deviceFamilies is passkeys._DEVICES in order; the first match names the device.
var deviceFamilies = []struct {
	re    *regexp.Regexp
	label string
}{
	{regexp.MustCompile(`iPhone`), "iPhone"},
	{regexp.MustCompile(`iPad`), "iPad"},
	{regexp.MustCompile(`Android`), "Android"},
	{regexp.MustCompile(`Macintosh|Mac OS X`), "Mac"},
	{regexp.MustCompile(`Windows`), "Windows"},
	{regexp.MustCompile(`CrOS`), "Chromebook"},
	{regexp.MustCompile(`Linux`), "Linux"},
}

var (
	errTooMany         = errors.New("pushweb: too many devices")
	errBadSubscription = errors.New("pushweb: bad subscription")
)

type okBody struct {
	OK bool `json:"ok"`
}

type knownBody struct {
	Known bool `json:"known"`
}

type errorBody struct {
	Error string `json:"error"`
}

// SubscribeHandler serves POST /account/push/subscribe (push.py save_subscription).
func SubscribeHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		h, ok := ownHost(w, r, pool, getenv, at)
		if !ok {
			return
		}
		if h == nil {
			answerError(w, r, "push.error.signed_out", http.StatusUnauthorized)
			return
		}
		if !pushEnabled(getenv) {
			answerError(w, r, "push.error.failed", http.StatusConflict)
			return
		}
		data := readBody(r)
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			serverError(w, err)
			return
		}
		ctx := r.Context()
		err = saveSubscription(ctx, pool, keys, h.Account.ID, data["subscription"], langOf(data, r), deviceFor(r))
		switch {
		case errors.Is(err, errTooMany):
			answerError(w, r, "push.error.too_many", http.StatusBadRequest)
			return
		case errors.Is(err, errBadSubscription):
			answerError(w, r, "push.error.failed", http.StatusBadRequest)
			return
		case err != nil:
			serverError(w, err)
			return
		}
		count, err := countFor(ctx, pool, h.Account.ID)
		if err != nil {
			serverError(w, err)
			return
		}
		if err := audit(ctx, pool, h, "push_device_added", fmt.Sprintf("devices=%d", count)); err != nil {
			serverError(w, err)
			return
		}
		answer(w, http.StatusOK, okBody{OK: true})
	}
}

// RefreshHandler serves POST /account/push/refresh (push.py refresh). It never
// creates a device: a removed one stays removed until alerts are turned on again.
func RefreshHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		h, ok := ownHost(w, r, pool, getenv, at)
		if !ok {
			return
		}
		if h == nil {
			answerError(w, r, "push.error.signed_out", http.StatusUnauthorized)
			return
		}
		data := readBody(r)
		known, err := refreshDevice(r.Context(), pool, h.Account.ID, pyStr(data["endpoint"]), langOf(data, r))
		if err != nil {
			serverError(w, err)
			return
		}
		answer(w, http.StatusOK, knownBody{Known: known})
	}
}

// UnsubscribeHandler serves POST /account/push/unsubscribe (push.py remove_endpoint).
func UnsubscribeHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		h, ok := ownHost(w, r, pool, getenv, at)
		if !ok {
			return
		}
		if h == nil {
			answerError(w, r, "push.error.signed_out", http.StatusUnauthorized)
			return
		}
		data := readBody(r)
		ctx := r.Context()
		id, found, err := findDevice(ctx, pool,
			`SELECT id FROM push_subscription WHERE endpoint_hash = $1 AND user_account_id = $2`,
			hashEndpoint(pyStr(data["endpoint"])), h.Account.ID)
		if err != nil {
			serverError(w, err)
			return
		}
		if found {
			if err := dropRow(ctx, pool, id); err != nil {
				serverError(w, err)
				return
			}
			if err := audit(ctx, pool, h, "push_device_removed", "source=device"); err != nil {
				serverError(w, err)
				return
			}
		}
		answer(w, http.StatusOK, okBody{OK: true})
	}
}

// DeviceDeleteHandler serves POST /account/push/devices/{id}/delete, the Settings
// remove form. It works without JavaScript: it answers with a redirect back to
// the phone section, carrying a flash.
func DeviceDeleteHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		h, ok := ownHost(w, r, pool, getenv, at)
		if !ok {
			return
		}
		if h == nil {
			hostweb.Back(w, r, phonePath, hostweb.Flash{}, flashFor(r, "flash.push.signed_out"))
			return
		}
		ctx := r.Context()
		found, err := ownDeviceExists(ctx, pool, h.Account.ID, id)
		if err != nil {
			serverError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, phonePath, hostweb.Flash{}, hostweb.Flash{})
			return
		}
		if err := dropRow(ctx, pool, id); err != nil {
			serverError(w, err)
			return
		}
		if err := audit(ctx, pool, h, "push_device_removed", "source=settings"); err != nil {
			serverError(w, err)
			return
		}
		hostweb.Back(w, r, phonePath, flashFor(r, "flash.push.device_removed"), hostweb.Flash{})
	}
}

// ownHost is own_account: the signed-in account when it is not previewing another
// workspace. It returns (nil, true) when nobody is signed in or an admin is
// previewing, and false after it has written a 500.
func ownHost(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, bool) {
	h, err := session.Load(r.Context(), pool, hostweb.Cookie(r, session.CookieName), at, getenv)
	if err != nil {
		serverError(w, err)
		return nil, false
	}
	if h == nil || h.Workspace.ID != h.Account.ID {
		return nil, true
	}
	return h, true
}

// pushEnabled is push.enabled(): on unless UBYHOST_WEB_PUSH is 0, false or no.
func pushEnabled(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_WEB_PUSH"))) {
	case "0", "false", "no":
		return false
	}
	return true
}

// readBody is push.py _body: over 8 KiB, bad JSON or a non-object gives an empty map.
func readBody(r *http.Request) map[string]any {
	raw, err := io.ReadAll(io.LimitReader(r.Body, maxBody+1))
	if err != nil || len(raw) > maxBody {
		return map[string]any{}
	}
	var data any
	if json.Unmarshal(raw, &data) != nil {
		return map[string]any{}
	}
	m, ok := data.(map[string]any)
	if !ok {
		return map[string]any{}
	}
	return m
}

// pyStr is Python's str(value or ""): falsy values give "", strings pass
// through, and other values get a non-empty text (their Python repr is never a
// valid endpoint, key or language, so the exact text does not matter).
func pyStr(v any) string {
	switch t := v.(type) {
	case nil:
		return ""
	case string:
		return t
	case bool:
		if t {
			return "True"
		}
		return ""
	case []any:
		if len(t) == 0 {
			return ""
		}
	case map[string]any:
		if len(t) == 0 {
			return ""
		}
	case float64:
		if t == 0 {
			return ""
		}
	}
	return fmt.Sprint(v)
}

// langOf is str(data.get("lang") or lang_from_request(request)).
func langOf(data map[string]any, r *http.Request) string {
	if v := pyStr(data["lang"]); v != "" {
		return v
	}
	return hostweb.Lang(r)
}

// normaliseLang is host_i18n.normalise_language: the first two letters when we
// speak them, else the default.
func normaliseLang(v string) string {
	code := firstTwo(strings.ToLower(v))
	switch code {
	case "en", "cs", "vi":
		return code
	}
	return defaultLang
}

// firstTwo is Python's [:2] on a string.
func firstTwo(s string) string {
	if r := []rune(s); len(r) > 2 {
		return string(r[:2])
	}
	return s
}

// truncate is Python's s[:n] on a string.
func truncate(s string, n int) string {
	if r := []rune(s); len(r) > n {
		return string(r[:n])
	}
	return s
}

// deviceFor is _device(request): a coarse family such as "iPhone", or "" when
// the browser does not say.
func deviceFor(r *http.Request) string {
	name := catalog.T("en", "passkeys.default_name", nil)
	label := name
	ua := r.Header.Get("User-Agent")
	for _, fam := range deviceFamilies {
		if fam.re.MatchString(ua) {
			label = fam.label
			break
		}
	}
	if label == name {
		return ""
	}
	return label
}

// unb64url is webpush.unb64url: whitespace dropped, padding added, URL alphabet.
func unb64url(text string) ([]byte, error) {
	text = strings.Join(strings.Fields(text), "")
	text += strings.Repeat("=", (4-len(text)%4)%4)
	return base64.URLEncoding.DecodeString(text)
}

func pushHost(host string) bool {
	for _, suffix := range pushHosts {
		if host == suffix || strings.HasSuffix(host, "."+suffix) {
			return true
		}
	}
	return false
}

// cleanSubscription is push.clean_subscription: the three parts of a browser's
// PushSubscription, checked. Every refusal is errBadSubscription.
func cleanSubscription(v any) (endpoint, p256dh, auth string, err error) {
	data, ok := v.(map[string]any)
	if !ok {
		return "", "", "", errBadSubscription
	}
	keys, _ := data["keys"].(map[string]any)
	endpoint = pyStr(data["endpoint"])
	p256dh = pyStr(keys["p256dh"])
	auth = pyStr(keys["auth"])
	if endpoint == "" || utf8.RuneCountInString(endpoint) > maxEndpoint {
		return "", "", "", errBadSubscription
	}
	u, perr := url.Parse(endpoint)
	if perr != nil || u.Scheme != "https" || u.User != nil {
		return "", "", "", errBadSubscription
	}
	if port := u.Port(); port != "" && port != "443" {
		return "", "", "", errBadSubscription
	}
	if !pushHost(strings.ToLower(u.Hostname())) {
		return "", "", "", errBadSubscription
	}
	point, perr := unb64url(p256dh)
	if perr != nil {
		return "", "", "", errBadSubscription
	}
	if _, perr := ecdh.P256().NewPublicKey(point); perr != nil {
		return "", "", "", errBadSubscription
	}
	secret, perr := unb64url(auth)
	if perr != nil || len(secret) != 16 {
		return "", "", "", errBadSubscription
	}
	return endpoint, p256dh, auth, nil
}

// hashEndpoint is push._hash: SHA-256 hex of the push address.
func hashEndpoint(endpoint string) string {
	sum := sha256.Sum256([]byte(endpoint))
	return hex.EncodeToString(sum[:])
}

// saveSubscription is push.save_subscription. An endpoint already stored moves to
// this account (its queued alerts for the previous account are dropped); a new
// one needs room under the device cap.
func saveSubscription(ctx context.Context, pool *pgxpool.Pool, keys *secure.MultiFernet, account int64, data any, lang, device string) error {
	endpoint, p256dh, auth, err := cleanSubscription(data)
	if err != nil {
		return err
	}
	digest := hashEndpoint(endpoint)
	lang = normaliseLang(lang)
	device = truncate(device, maxDevice)
	now := ubyport.UTCNow()
	var existingID, existingOwner int64
	found := true
	err = pool.QueryRow(ctx, `SELECT id, user_account_id FROM push_subscription WHERE endpoint_hash = $1`, digest).
		Scan(&existingID, &existingOwner)
	switch {
	case errors.Is(err, pgx.ErrNoRows):
		found = false
	case err != nil:
		return err
	}
	p256Enc, err := keys.EncryptString(p256dh)
	if err != nil {
		return err
	}
	authEnc, err := keys.EncryptString(auth)
	if err != nil {
		return err
	}
	if found {
		if existingOwner != account {
			if _, err := pool.Exec(ctx, `DELETE FROM push_outbox WHERE subscription_id = $1`, existingID); err != nil {
				return err
			}
		}
		_, err := pool.Exec(ctx,
			`UPDATE push_subscription SET user_account_id = $1, p256dh_enc = $2, auth_enc = $3, lang = $4, device = $5, failures = 0, last_seen_at = $6 WHERE id = $7`,
			account, p256Enc, authEnc, lang, device, now, existingID)
		return err
	}
	count, err := countFor(ctx, pool, account)
	if err != nil {
		return err
	}
	if count >= maxDevices {
		return errTooMany
	}
	endpointEnc, err := keys.EncryptString(endpoint)
	if err != nil {
		return err
	}
	_, err = pool.Exec(ctx,
		`INSERT INTO push_subscription (user_account_id, endpoint_hash, endpoint_enc, p256dh_enc, auth_enc, lang, device, failures, created_at, last_seen_at) VALUES ($1, $2, $3, $4, $5, $6, $7, 0, $8, $8)`,
		account, digest, endpointEnc, p256Enc, authEnc, lang, device, now)
	return err
}

func countFor(ctx context.Context, pool *pgxpool.Pool, account int64) (int64, error) {
	var n int64
	err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM push_subscription WHERE user_account_id = $1`, account).Scan(&n)
	return n, err
}

// refreshDevice is push.refresh: keeps the device's language and last visit.
func refreshDevice(ctx context.Context, pool *pgxpool.Pool, account int64, endpoint, lang string) (bool, error) {
	id, found, err := findDevice(ctx, pool,
		`SELECT id FROM push_subscription WHERE endpoint_hash = $1 AND user_account_id = $2`,
		hashEndpoint(endpoint), account)
	if err != nil || !found {
		return false, err
	}
	_, err = pool.Exec(ctx, `UPDATE push_subscription SET lang = $1, last_seen_at = $2 WHERE id = $3`,
		normaliseLang(lang), ubyport.UTCNow(), id)
	return err == nil, err
}

// ownDeviceExists reports whether the account has the device with this id.
func ownDeviceExists(ctx context.Context, pool *pgxpool.Pool, account, id int64) (bool, error) {
	_, found, err := findDevice(ctx, pool,
		`SELECT id FROM push_subscription WHERE id = $1 AND user_account_id = $2`, id, account)
	return found, err
}

// findDevice runs a one-row lookup for a device id; found is false for no row.
func findDevice(ctx context.Context, pool *pgxpool.Pool, query string, args ...any) (int64, bool, error) {
	var id int64
	err := pool.QueryRow(ctx, query, args...).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, false, nil
	}
	if err != nil {
		return 0, false, err
	}
	return id, true, nil
}

// dropRow is push._drop: the device's queued alerts, then the device.
func dropRow(ctx context.Context, pool *pgxpool.Pool, id int64) error {
	if _, err := pool.Exec(ctx, `DELETE FROM push_outbox WHERE subscription_id = $1`, id); err != nil {
		return err
	}
	_, err := pool.Exec(ctx, `DELETE FROM push_subscription WHERE id = $1`, id)
	return err
}

// audit is db.audit for a signed-in account acting on its own workspace: the
// actor is the username and both user ids are the account.
func audit(ctx context.Context, pool *pgxpool.Pool, h *session.Host, action, detail string) error {
	_, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id) VALUES ($1, $2, $3, $4, $5, $6, NULL)`,
		ubyport.UTCNow(), h.Account.Username, action, detail, h.Account.ID, h.Account.ID)
	return err
}

// answer is push.py _answer: JSON with Cache-Control no-store.
func answer(w http.ResponseWriter, status int, body any) {
	raw, _ := json.Marshal(body)
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_, _ = w.Write(raw)
}

// answerError is push.py _error: {"error": text} in the request's language.
func answerError(w http.ResponseWriter, r *http.Request, key string, status int) {
	answer(w, status, errorBody{Error: catalog.T(hostweb.Lang(r), key, nil)})
}

// flashFor is a translated flash for a redirect, in the request's language.
func flashFor(r *http.Request, key string) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(hostweb.Lang(r), key, nil), Key: key}
}

func serverError(w http.ResponseWriter, err error) {
	log.Printf("pushweb: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}
