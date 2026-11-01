// Package session reads the Python host session cookie ("ubyhost_session") so
// Go routes know who is signed in, exactly as App/app/auth.py does (brief 0672).
// It is a library only: no route is registered here.
package session

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const (
	// CookieName is SESSION_COOKIE (auth.py line 29).
	CookieName = "ubyhost_session"
	// salt is the itsdangerous salt of _serializer (auth.py lines 55-56).
	salt = "ubyhost-session"
	// rememberMaxAge is SESSION_REMEMBER_MAX_AGE (auth.py line 33).
	rememberMaxAge = 400 * 24 * time.Hour
	// shortMaxAge is SESSION_MAX_AGE (auth.py line 32), enforced unless "rm" is set.
	shortMaxAge = 12 * time.Hour
	// defaultVersion is the default of UBYHOST_*_VERSION (brief 0672, section 2).
	defaultVersion = "1.7"
)

// pythonKeyOrder is the insertion order of issue_session (auth.py lines 225-260).
// Python keeps dict order in its JSON, so Sign writes these keys first.
var pythonKeyOrder = []string{"uid", "sv", "iat", "rm", "as", "ast", "rv"}

// Account is the user_account row a host session needs.
type Account struct {
	ID             int64
	Username       string
	Role           string
	SessionVersion int64
}

// Host is the signed-in account and the workspace it acts in (current_user and
// workspace_user, auth.py lines 311-339).
type Host struct {
	Account              Account
	Workspace            Account
	Impersonating        bool
	ImpersonationExpired bool
	Payload              map[string]any
}

// orderedPayload marshals a payload with the Python key order, then the rest sorted.
type orderedPayload map[string]any

// MarshalJSON writes compact JSON, as itsdangerous's _CompactJSON does.
func (p orderedPayload) MarshalJSON() ([]byte, error) {
	seen := map[string]bool{}
	var keys []string
	for _, k := range pythonKeyOrder {
		if _, ok := p[k]; ok {
			keys = append(keys, k)
			seen[k] = true
		}
	}
	var rest []string
	for k := range p {
		if !seen[k] {
			rest = append(rest, k)
		}
	}
	sort.Strings(rest)
	keys = append(keys, rest...)
	var b bytes.Buffer
	b.WriteByte('{')
	for i, k := range keys {
		if i > 0 {
			b.WriteByte(',')
		}
		kb, err := json.Marshal(k)
		if err != nil {
			return nil, err
		}
		vb, err := json.Marshal(p[k])
		if err != nil {
			return nil, err
		}
		b.Write(kb)
		b.WriteByte(':')
		b.Write(vb)
	}
	b.WriteByte('}')
	return b.Bytes(), nil
}

// Sign issues the token that itsdangerous URLSafeTimedSerializer(secret,
// salt="ubyhost-session").dumps(payload) gives at now (auth.issue_session).
// It returns "" only if the payload cannot be encoded, which session payloads
// never are.
func Sign(secret string, payload map[string]any, now time.Time) string {
	token, err := secure.NewTimedSerializer(secret, salt).Dumps(orderedPayload(payload), now)
	if err != nil {
		return ""
	}
	return token
}

// Verify checks token at now as auth._session_payload does (auth.py lines 335-354):
// 400 days at most, and 12 hours unless the payload has a truthy "rm".
func Verify(secret, token string, now time.Time) (map[string]any, bool) {
	s := secure.NewTimedSerializer(secret, salt)
	var raw json.RawMessage
	if err := s.Loads(token, rememberMaxAge, now, &raw); err != nil {
		return nil, false
	}
	payload, ok := decodePayload(raw)
	if !ok {
		return nil, false
	}
	if !truthy(payload["rm"]) {
		if err := s.Loads(token, shortMaxAge, now, &raw); err != nil {
			return nil, false
		}
	}
	return payload, true
}

// decodePayload decodes a JSON object, with whole numbers as int64 (Python int).
func decodePayload(raw []byte) (map[string]any, bool) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, false
	}
	m, ok := convert(v).(map[string]any)
	return m, ok && m != nil
}

func convert(v any) any {
	switch x := v.(type) {
	case json.Number:
		if i, err := x.Int64(); err == nil {
			return i
		}
		return x
	case map[string]any:
		for k, e := range x {
			x[k] = convert(e)
		}
		return x
	case []any:
		for i, e := range x {
			x[i] = convert(e)
		}
		return x
	}
	return v
}

// truthy is Python truthiness for the JSON values a payload can hold.
func truthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case bool:
		return x
	case int64:
		return x != 0
	case json.Number:
		f, _ := x.Float64()
		return f != 0
	case string:
		return x != ""
	case []any:
		return len(x) > 0
	case map[string]any:
		return len(x) > 0
	}
	return true
}

// intOf returns a payload value that is a JSON integer (Python int, not bool).
func intOf(v any) (int64, bool) {
	i, ok := v.(int64)
	return i, ok
}

// Load resolves token to the signed-in host, as current_user and workspace_user
// do (auth.py lines 311-339). It returns nil, nil when there is no valid token,
// no active account, or a session_version mismatch. The no-login staging and
// bootstrap shortcuts and the expiry audit belong to the route (brief 0673).
func Load(ctx context.Context, db *pgxpool.Pool, token string, now time.Time, getenv func(string) string) (*Host, error) {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return nil, err
	}
	payload, ok := Verify(secret, token, now)
	if !ok {
		return nil, nil
	}
	uid, ok := intOf(payload["uid"])
	if !ok || uid == 0 {
		return nil, nil
	}
	account, found, err := queryAccount(ctx, db,
		`SELECT id, username, role, session_version FROM user_account WHERE id = $1 AND active = 1`, uid)
	if err != nil || !found {
		return nil, err
	}
	// Missing "sv" counts as 0, as payload.get("sv", 0) does (auth.py line 326).
	var sv int64
	if raw, present := payload["sv"]; present {
		v, ok := intOf(raw)
		if !ok {
			return nil, nil
		}
		sv = v
	}
	if account.SessionVersion != sv {
		return nil, nil
	}
	h := &Host{Account: account, Workspace: account, Payload: payload}
	// "as" is honoured only for an admin (auth.py line 330).
	target, _ := intOf(payload["as"])
	if account.Role != "admin" || target == 0 {
		return h, nil
	}
	if impersonationExpired(payload, now, getenv) {
		// The admin is back in their own view (auth.py lines 331-334).
		h.ImpersonationExpired = true
		return h, nil
	}
	workspace, found, err := queryAccount(ctx, db,
		`SELECT id, username, role, session_version FROM user_account WHERE id = $1 AND active = 1`, target)
	if err != nil {
		return nil, err
	}
	if found {
		h.Workspace = workspace
		h.Impersonating = workspace.ID != account.ID
	}
	return h, nil
}

// impersonationExpired is auth.impersonation_expired (auth.py lines 367-381).
func impersonationExpired(payload map[string]any, now time.Time, getenv func(string) string) bool {
	limit := impersonationMaxAge(getenv)
	if limit <= 0 {
		return false
	}
	started, ok := intOf(payload["ast"])
	if !ok {
		return true
	}
	return now.Unix()-started >= limit
}

// impersonationMaxAge is _impersonation_max_age (auth.py lines 35-46), in seconds.
// An unset or empty UBYHOST_IMPERSONATION_MAX_HOURS reads as 24. Python reads an
// empty value as 0 (no limit); getenv cannot tell the two apart, so the limit stays.
func impersonationMaxAge(getenv func(string) string) int64 {
	raw := strings.TrimSpace(getenv("UBYHOST_IMPERSONATION_MAX_HOURS"))
	if raw == "" {
		raw = "24"
	}
	hours, err := strconv.Atoi(raw)
	if err != nil {
		hours = 24
	}
	if hours < 0 {
		hours = 0
	}
	return int64(hours) * 3600
}

// AcceptancePending reports whether any of terms, privacy and dpa has no
// legal_acceptance row at its current version for userID (acceptance.pending,
// App/app/acceptance.py lines 46-56).
func AcceptancePending(ctx context.Context, db *pgxpool.Pool, userID int64, getenv func(string) string) (bool, error) {
	versions := map[string]string{
		"terms":   versionOr(getenv, "UBYHOST_TERMS_VERSION"),
		"privacy": versionOr(getenv, "UBYHOST_PRIVACY_VERSION"),
		"dpa":     versionOr(getenv, "UBYHOST_DPA_VERSION"),
	}
	rows, err := db.Query(ctx,
		`SELECT document, version FROM legal_acceptance WHERE user_account_id = $1`, userID)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	accepted := map[[2]string]bool{}
	for rows.Next() {
		var doc, version string
		if err := rows.Scan(&doc, &version); err != nil {
			return false, err
		}
		accepted[[2]string{doc, version}] = true
	}
	if err := rows.Err(); err != nil {
		return false, err
	}
	for _, doc := range []string{"terms", "privacy", "dpa"} {
		if !accepted[[2]string{doc, versions[doc]}] {
			return true, nil
		}
	}
	return false, nil
}

func versionOr(getenv func(string) string, key string) string {
	if v := strings.TrimSpace(getenv(key)); v != "" {
		return v
	}
	return defaultVersion
}

// queryAccount loads one user_account row; found is false when there is none.
func queryAccount(ctx context.Context, db *pgxpool.Pool, query string, id int64) (Account, bool, error) {
	var a Account
	err := db.QueryRow(ctx, query, id).Scan(&a.ID, &a.Username, &a.Role, &a.SessionVersion)
	if errors.Is(err, pgx.ErrNoRows) {
		return Account{}, false, nil
	}
	if err != nil {
		return Account{}, false, err
	}
	return a, true, nil
}
