// Package ttlock ports App/app/ttlock.py, the TTLock Open Platform client, to Go.
// Request shapes, md5 password signing, token refresh, error kinds and the
// monthly call budget follow the Python module. Each exported method's doc names
// the Python function it ports. Nothing here logs a token or a password, and
// nothing reads the environment except ConfigFromEnv, which takes the lookup
// function as an argument.
package ttlock

import (
	"bytes"
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const (
	defaultAPIBase      = "https://euapi.ttlock.com"
	defaultMonthlyCalls = 30000
	maxResponseBytes    = 1 << 20
	errMessageLimit     = 200
	gatewayTimeout      = 35 * time.Second
	plainTimeout        = 5 * time.Second
)

// Priorities, as in ttlock.py. The budget guard reads them.
const (
	PriorityLow      = "low"
	PriorityNormal   = "normal"
	PriorityCritical = "critical"
)

// Error kinds: the ttlock.py ERROR_KINDS values plus the kinds the client raises itself.
const (
	KindAuth        = "auth"
	KindReauth      = "reauth"
	KindLogin       = "login"
	KindConfig      = "config"
	KindPermission  = "permission"
	KindRate        = "rate"
	KindBudget      = "budget"
	KindClock       = "clock"
	KindOffline     = "offline"
	KindStorage     = "storage"
	KindTransient   = "transient"
	KindBug         = "bug"
	KindUnusedCode  = "unused_code"
	KindPeriodTaken = "period_taken"
	KindDuplicate   = "duplicate"
	KindCodeMissing = "code_missing"
	KindLockSetup   = "lock_setup"
	KindNetwork     = "network"
	KindDisabled    = "disabled"
)

// NoPasscodeDataCode is TTLock's -1007, "No password data of this lock".
const NoPasscodeDataCode = -1007

// newPINErrcodes are the refusals after which add_custom_code draws one new PIN.
var newPINErrcodes = []int{-3007, -2032}

// errorKinds mirrors ttlock.py ERROR_KINDS. An errcode missing here is "transient".
var errorKinds = map[int]string{
	10003: KindAuth,
	10004: KindAuth,
	10011: KindReauth,
	10007: KindLogin,
	10000: KindConfig,
	10001: KindConfig,
	10005: KindPermission,
	30001: KindPermission,
	-2018: KindPermission,
	20002: KindPermission,
	30006: KindRate,
	30007: KindBudget,
	80000: KindClock,
	-2012: KindOffline,
	-4056: KindStorage,
	-3009: KindStorage,
	90000: KindTransient,
	1:     KindTransient,
	-3:    KindBug,
	-3008: KindUnusedCode,
	-1026: KindPeriodTaken,
	-3007: KindDuplicate,
	-1007: KindCodeMissing,
	-3002: KindOffline,
	-3003: KindOffline,
	-3035: KindOffline,
	-3036: KindOffline,
	-3037: KindOffline,
	-2025: KindOffline,
	-1003: KindLockSetup,
	-4037: KindLockSetup,
	-4043: KindLockSetup,
	-3034: KindLockSetup,
	-4067: KindLockSetup,
	-4063: KindConfig,
	30008: KindConfig,
	80002: KindBug,
	-2009: KindBug,
	-2032: KindBug,
	-3006: KindBug,
	-3045: KindBug,
}

// retryableKinds are the kinds the door-codes plan retries on its own schedule
// (docs/plans/ttlock-door-codes.md section 3). Bug, clock, config, permission,
// reauth and disabled stop at once and are handed to the host or the operator.
var retryableKinds = map[string]bool{
	KindOffline:     true,
	KindTransient:   true,
	KindNetwork:     true,
	KindRate:        true,
	KindBudget:      true,
	KindCodeMissing: true,
	KindLockSetup:   true,
}

// allowedPaths is the ttlock.py ALLOWED_PATHS set: any other path is refused before a request.
var allowedPaths = map[string]bool{
	"/oauth2/token":            true,
	"/v3/user/register":        true,
	"/v3/user/delete":          true,
	"/v3/key/list":             true,
	"/v3/lock/listKeyboardPwd": true,
	"/v3/lock/queryDate":       true,
	"/v3/lock/updateDate":      true,
	"/v3/keyboardPwd/get":      true,
	"/v3/keyboardPwd/add":      true,
	"/v3/keyboardPwd/change":   true,
	"/v3/keyboardPwd/delete":   true,
}

// gatewayPaths are the calls that reach the lock through its gateway; they get the longer timeout.
var gatewayPaths = map[string]bool{
	"/v3/keyboardPwd/add":    true,
	"/v3/keyboardPwd/change": true,
	"/v3/keyboardPwd/delete": true,
	"/v3/lock/queryDate":     true,
	"/v3/lock/updateDate":    true,
}

// Sentinel errors for caller mistakes that ttlock.py raises as ValueError.
var (
	ErrPathNotAllowed      = errors.New("ttlock: path not allowed")
	ErrWholeHour           = errors.New("ttlock: time must be a whole hour")
	ErrBufferHours         = errors.New("ttlock: buffer_hours must not be negative")
	ErrHour                = errors.New("ttlock: hour must be 0 to 23")
	ErrWindow              = errors.New("ttlock: window ends before it starts")
	ErrInvalidPermanentPIN = errors.New("ttlock: invalid permanent PIN")
)

// TTLockError is every failure the client reports on purpose, as ttlock.py TTLockError.
type TTLockError struct {
	// Code is the TTLock errcode, or 0 when TTLock sent none (network, budget, disabled, reauth).
	Code int
	// Kind is one of the Kind constants: ERROR_KINDS for errcodes, the client's own kinds otherwise.
	Kind string
	// Message is TTLock's errmsg or the client's reason, cut to 200 characters.
	Message string
	// Unknown is true when the request may have reached TTLock but its answer is
	// missing or unreadable (a transport error or a non-JSON body), so the change
	// may or may not have happened. ttlock.py has no such field; the door-codes
	// port needs it to tell "failed" from "not known yet".
	Unknown bool
}

func (e *TTLockError) Error() string {
	return fmt.Sprintf("ttlock: %s (errcode %d): %s", e.Kind, e.Code, e.Message)
}

// Retryable reports whether the door-codes flow may repeat this call later
// (see retryableKinds). It says nothing about whether the change happened: check Unknown.
func (e *TTLockError) Retryable() bool { return retryableKinds[e.Kind] }

// AsError returns the TTLockError inside err, if there is one.
func AsError(err error) (*TTLockError, bool) {
	var te *TTLockError
	ok := errors.As(err, &te)
	return te, ok
}

// IsKind reports whether err is a TTLockError of this kind.
func IsKind(err error, kind string) bool {
	te, ok := AsError(err)
	return ok && te.Kind == kind
}

func newErr(kind, message string) *TTLockError {
	return &TTLockError{Kind: kind, Message: truncate(message, errMessageLimit)}
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

// Config holds the settings ttlock.py reads from config.py.
type Config struct {
	// DoorCodesEnabled is UBYHOST_DOOR_CODES. When false every call is refused as "disabled".
	DoorCodesEnabled bool
	// APIBase is UBYHOST_TTLOCK_API_BASE without a trailing slash.
	APIBase      string
	ClientID     string // UBYHOST_TTLOCK_CLIENT_ID
	ClientSecret string // UBYHOST_TTLOCK_CLIENT_SECRET, env only
	// MonthlyCalls is UBYHOST_TTLOCK_MONTHLY_CALLS (default 30000). Zero or less turns the guard off.
	MonthlyCalls int64
}

// ConfigFromEnv reads the same environment names as config.py. Pass os.Getenv in production.
// Differences from config.py: an empty API base or call limit takes the default
// (Python would use the empty string or fail to parse it).
func ConfigFromEnv(getenv func(string) string) (Config, error) {
	cfg := Config{
		DoorCodesEnabled: isOn(getenv("UBYHOST_DOOR_CODES")),
		APIBase:          strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_TTLOCK_API_BASE")), "/"),
		ClientID:         strings.TrimSpace(getenv("UBYHOST_TTLOCK_CLIENT_ID")),
		ClientSecret:     strings.TrimSpace(getenv("UBYHOST_TTLOCK_CLIENT_SECRET")),
		MonthlyCalls:     defaultMonthlyCalls,
	}
	if cfg.APIBase == "" {
		cfg.APIBase = defaultAPIBase
	}
	if raw := strings.TrimSpace(getenv("UBYHOST_TTLOCK_MONTHLY_CALLS")); raw != "" {
		n, err := strconv.ParseInt(raw, 10, 64)
		if err != nil {
			return Config{}, fmt.Errorf("UBYHOST_TTLOCK_MONTHLY_CALLS: %w", err)
		}
		cfg.MonthlyCalls = n
	}
	return cfg, nil
}

// isOn matches config.py: exactly "1", "true" or "yes", no lowercasing.
func isOn(v string) bool {
	switch v {
	case "1", "true", "yes":
		return true
	}
	return false
}

// Options are the injected collaborators. Tests pass an httptest client, a fixed clock and a fake store.
type Options struct {
	// HTTP performs the requests. Nil uses a plain http.Client; per-request timeouts are set on the context.
	HTTP *http.Client
	// Accounts is the lock_account table (see AccountStore). Required by every account call.
	Accounts AccountStore
	// Budget is the monthly call guard. Required; use NewPGBudget in production.
	Budget Budget
	// Now is the clock. Nil uses time.Now.
	Now func() time.Time
	// Log receives the same lines as the Python logger, without secrets. Nil discards them.
	Log *slog.Logger
}

// Client is the TTLock client. It is safe for concurrent use if its collaborators are.
type Client struct {
	cfg      Config
	http     *http.Client
	accounts AccountStore
	budget   Budget
	now      func() time.Time
	log      *slog.Logger
}

// New builds a client. ttlock.py used module globals; here the config, store, budget and clock are passed in.
func New(cfg Config, opt Options) *Client {
	c := &Client{cfg: cfg, http: opt.HTTP, accounts: opt.Accounts, budget: opt.Budget, now: opt.Now, log: opt.Log}
	if c.cfg.APIBase == "" {
		c.cfg.APIBase = defaultAPIBase
	}
	c.cfg.APIBase = strings.TrimRight(c.cfg.APIBase, "/")
	if c.http == nil {
		c.http = &http.Client{}
	}
	if c.now == nil {
		c.now = time.Now
	}
	if c.log == nil {
		c.log = slog.New(slog.DiscardHandler)
	}
	return c
}

// Enabled ports enabled(): door codes are switched on and both TTLock credentials are set.
// The Python allowed_for check (billing entitlement) is not ported here; it belongs to the caller.
func (c *Client) Enabled() bool {
	return c.cfg.DoorCodesEnabled && c.cfg.ClientID != "" && c.cfg.ClientSecret != ""
}

// timeoutFor returns the per-request timeout ttlock.py uses: 35 s for gateway calls, 5 s otherwise.
func timeoutFor(path string) time.Duration {
	if gatewayPaths[path] {
		return gatewayTimeout
	}
	return plainTimeout
}

// post ports _post: one signed form POST to a whitelisted path, with the enabled and budget checks.
// The budget is counted before the request is sent, as in Python, so a network failure still counts.
func (c *Client) post(ctx context.Context, path string, data map[string]any, priority string) (map[string]any, error) {
	if !allowedPaths[path] {
		return nil, fmt.Errorf("%w: %s", ErrPathNotAllowed, path)
	}
	if !c.cfg.DoorCodesEnabled {
		return nil, newErr(KindDisabled, "door codes disabled")
	}
	allowed, err := c.budget.Allows(ctx, priority)
	if err != nil {
		return nil, fmt.Errorf("ttlock: budget check: %w", err)
	}
	if !allowed {
		return nil, newErr(KindBudget, "monthly call budget")
	}

	nowMS := c.now().UnixMilli()
	body := map[string]any{"clientId": c.cfg.ClientID}
	switch path {
	case "/oauth2/token":
		body["clientSecret"] = c.cfg.ClientSecret
	case "/v3/user/register", "/v3/user/delete":
		body["clientSecret"] = c.cfg.ClientSecret
		body["date"] = nowMS
	default:
		body["date"] = nowMS
	}
	for k, v := range data {
		body[k] = v
	}
	form := url.Values{}
	for k, v := range body {
		if v == nil {
			continue // requests drops None-valued fields; so do we
		}
		form.Set(k, formValue(v))
	}

	if err := c.budget.Count(ctx); err != nil {
		return nil, fmt.Errorf("ttlock: budget count: %w", err)
	}

	reqCtx, cancel := context.WithTimeout(ctx, timeoutFor(path))
	defer cancel()
	req, err := http.NewRequestWithContext(reqCtx, http.MethodPost, c.cfg.APIBase+path, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, fmt.Errorf("ttlock: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := c.http.Do(req)
	if err != nil {
		c.log.Warn("ttlock network", "path", path, "priority", priority)
		return nil, &TTLockError{Kind: KindNetwork, Message: truncate(err.Error(), errMessageLimit), Unknown: true}
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		c.log.Warn("ttlock network", "path", path, "priority", priority)
		return nil, &TTLockError{Kind: KindNetwork, Message: truncate(err.Error(), errMessageLimit), Unknown: true}
	}

	out, err := parseResponse(raw)
	if err != nil {
		if te, ok := AsError(err); ok {
			c.log.Warn("ttlock", "path", path, "priority", priority, "errcode", te.Code, "kind", te.Kind)
		}
		return nil, err
	}
	c.log.Info("ttlock", "path", path, "priority", priority, "errcode", 0)
	return out, nil
}

// parseResponse ports _parse_response: the body must be one JSON object; a non-zero errcode is an error.
func parseResponse(raw []byte) (map[string]any, error) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, &TTLockError{Kind: KindNetwork, Message: "non-json response", Unknown: true}
	}
	if _, err := dec.Token(); err != io.EOF {
		return nil, &TTLockError{Kind: KindNetwork, Message: "non-json response", Unknown: true}
	}
	data, ok := v.(map[string]any)
	if !ok {
		return nil, &TTLockError{Kind: KindNetwork, Message: "bad json shape", Unknown: true}
	}
	if ec, has := data["errcode"]; has && ec != nil {
		code, err := asInt(ec)
		if err != nil {
			return nil, &TTLockError{Kind: KindNetwork, Message: "bad errcode", Unknown: true}
		}
		if code != 0 {
			msg := ""
			if m, ok := data["errmsg"]; ok {
				msg = pyStr(m)
			}
			return nil, &TTLockError{Code: int(code), Kind: kindFor(int(code)), Message: truncate(msg, errMessageLimit)}
		}
	}
	return data, nil
}

func kindFor(code int) string {
	if k, ok := errorKinds[code]; ok {
		return k
	}
	return KindTransient
}

// md5Password ports _md5_password: TTLock takes the password as a lowercase md5 hex digest.
func md5Password(password string) string {
	sum := md5.Sum([]byte(password))
	return hex.EncodeToString(sum[:])
}

// formValue renders a value the way requests renders it in a form body.
func formValue(v any) string {
	switch x := v.(type) {
	case string:
		return x
	case int:
		return strconv.Itoa(x)
	case int64:
		return strconv.FormatInt(x, 10)
	case bool:
		if x {
			return "True"
		}
		return "False"
	case json.Number:
		return x.String()
	default:
		return fmt.Sprint(x)
	}
}

// withToken returns a copy of data with accessToken set, as _call does; data itself is not changed.
func withToken(data map[string]any, token string) map[string]any {
	out := make(map[string]any, len(data)+1)
	for k, v := range data {
		out[k] = v
	}
	out["accessToken"] = token
	return out
}

// pyStr renders a decoded JSON value the way Python's str() does for the values TTLock sends.
func pyStr(v any) string {
	switch x := v.(type) {
	case nil:
		return "None"
	case string:
		return x
	case json.Number:
		return x.String()
	case bool:
		if x {
			return "True"
		}
		return "False"
	case int:
		return strconv.Itoa(x)
	case int64:
		return strconv.FormatInt(x, 10)
	}
	b, _ := json.Marshal(v)
	return string(b)
}

// asInt ports Python int() for the values TTLock sends.
func asInt(v any) (int64, error) {
	switch x := v.(type) {
	case json.Number:
		if n, err := x.Int64(); err == nil {
			return n, nil
		}
		f, err := x.Float64()
		if err != nil {
			return 0, err
		}
		return int64(f), nil
	case string:
		return strconv.ParseInt(strings.TrimSpace(x), 10, 64)
	case bool:
		if x {
			return 1, nil
		}
		return 0, nil
	case int:
		return int64(x), nil
	case int64:
		return x, nil
	}
	return 0, fmt.Errorf("ttlock: not an integer: %T", v)
}

// intOr0 ports int(x or 0): a falsy value is 0, anything else goes through asInt.
func intOr0(v any) (int64, error) {
	if !truthy(v) {
		return 0, nil
	}
	return asInt(v)
}

// truthy ports Python truthiness for decoded JSON values.
func truthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case string:
		return x != ""
	case bool:
		return x
	case json.Number:
		f, err := x.Float64()
		return err != nil || f != 0
	case []any:
		return len(x) > 0
	case map[string]any:
		return len(x) > 0
	}
	return true
}

// field returns str(m[key]) and fails when the key is absent (Python would raise KeyError).
func field(m map[string]any, key string) (string, error) {
	v, ok := m[key]
	if !ok {
		return "", fmt.Errorf("ttlock: answer has no %s", key)
	}
	return pyStr(v), nil
}

// listOf returns the dict entries of answer["list"], or nil when the list is absent or not a list.
func listOf(answer map[string]any) []map[string]any {
	items, ok := answer["list"].([]any)
	if !ok {
		return nil
	}
	out := make([]map[string]any, 0, len(items))
	for _, it := range items {
		if m, ok := it.(map[string]any); ok {
			out = append(out, m)
		}
	}
	return out
}
