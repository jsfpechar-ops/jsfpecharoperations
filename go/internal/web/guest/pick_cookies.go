package guest

import (
	"bytes"
	"compress/zlib"
	"crypto/hmac"
	"crypto/sha1"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"sort"
	"strconv"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const (
	ownedCookieName = "ubyhost_owned"
	ownedCookieSalt = "ubyhost-guest-owned"
	claimCookieName = "ubyhost_claim"
	claimCookieSalt = "ubyhost-guest-claim"
)

// ownedGuestIDs is guest.py _owned_ids.
func ownedGuestIDs(r *http.Request, getenv func(string) string) []int64 {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return nil
	}
	raw := hostweb.Cookie(r, ownedCookieName)
	if raw == "" {
		return nil
	}
	arr, ok := urlSafeJSON(secret, ownedCookieSalt, raw)
	if !ok {
		return nil
	}
	list, ok := arr.([]any)
	if !ok {
		return nil
	}
	out := make([]int64, 0, len(list))
	for _, v := range list {
		switch n := v.(type) {
		case float64:
			out = append(out, int64(n))
		case int64:
			out = append(out, n)
		case json.Number:
			i, _ := n.Int64()
			out = append(out, i)
		}
	}
	return out
}

// claimedReservationIDs is guest.py _claimed_reservation_ids (ids only).
func claimedReservationIDs(r *http.Request, getenv func(string) string) []int64 {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return nil
	}
	raw := hostweb.Cookie(r, claimCookieName)
	if raw == "" {
		return nil
	}
	doc, ok := urlSafeJSON(secret, claimCookieSalt, raw)
	if !ok {
		return nil
	}
	m, ok := doc.(map[string]any)
	if !ok {
		return nil
	}
	out := make([]int64, 0, len(m))
	for k := range m {
		if id, err := strconv.ParseInt(k, 10, 64); err == nil {
			out = append(out, id)
		}
	}
	return out
}

func urlSafeJSON(secret, salt, token string) (any, bool) {
	cut := strings.LastIndex(token, ".")
	if cut < 0 {
		return nil, false
	}
	value, sig := token[:cut], token[cut+1:]
	if !hmac.Equal([]byte(urlSafeSign(secret, salt, value)), []byte(sig)) {
		return nil, false
	}
	compressed := strings.HasPrefix(value, ".")
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(value, "."))
	if err != nil {
		return nil, false
	}
	if compressed {
		r, err := zlib.NewReader(bytes.NewReader(raw))
		if err != nil {
			return nil, false
		}
		raw, err = io.ReadAll(r)
		_ = r.Close()
		if err != nil {
			return nil, false
		}
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, false
	}
	if m, ok := v.(map[string]any); ok {
		for k, e := range m {
			m[k] = jsonNumber(e)
		}
		return m, true
	}
	if a, ok := v.([]any); ok {
		for i, e := range a {
			a[i] = jsonNumber(e)
		}
		return a, true
	}
	return v, true
}

func jsonNumber(v any) any {
	switch x := v.(type) {
	case json.Number:
		if i, err := x.Int64(); err == nil {
			return i
		}
	}
	return v
}

func urlSafeSign(secret, salt, message string) string {
	derived := sha1.Sum([]byte(salt + "signer" + secret))
	mac := hmac.New(sha1.New, derived[:])
	mac.Write([]byte(message))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func urlSafeDumps(secret, salt string, v any) (string, error) {
	raw, err := json.Marshal(v)
	if err != nil {
		return "", err
	}
	value := base64.RawURLEncoding.EncodeToString(raw)
	return value + "." + urlSafeSign(secret, salt, value), nil
}

// rememberOwnedGuestIDs is guest.py _remember_owned.
func rememberOwnedGuestIDs(w http.ResponseWriter, getenv func(string) string, ids []int64) {
	if w == nil || getenv == nil {
		return
	}
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return
	}
	seen := map[int64]bool{}
	uniq := make([]int64, 0, len(ids))
	for _, id := range ids {
		if id <= 0 || seen[id] {
			continue
		}
		seen[id] = true
		uniq = append(uniq, id)
	}
	sort.Slice(uniq, func(i, j int) bool { return uniq[i] < uniq[j] })
	if len(uniq) > 40 {
		uniq = uniq[len(uniq)-40:]
	}
	tok, err := urlSafeDumps(secret, ownedCookieSalt, uniq)
	if err != nil {
		return
	}
	http.SetCookie(w, &http.Cookie{
		Name:     ownedCookieName,
		Value:    tok,
		Path:     "/",
		MaxAge:   60 * 60 * 24 * 60,
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   hostweb.SecureCookies(getenv),
	})
}
