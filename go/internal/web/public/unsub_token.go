package public

// The unsubscribe link of a lifecycle tip (brief 1624): reading the signed
// token of lifecycle_mail.read_unsubscribe_token. The token is an
// itsdangerous URLSafeSerializer (no timestamp) over {"u": account id,
// "h": address hash}; go/internal/lifecyclemail writes it, this file reads it.

import (
	"bytes"
	"compress/zlib"
	"crypto/hmac"
	"crypto/sha1"
	"encoding/base64"
	"encoding/json"
	"io"
	"strings"
)

// unsubscribeSalt is the salt lifecycle_mail._serializer passes to itsdangerous.
const unsubscribeSalt = "ubyhost-lifecycle-unsubscribe"

// readUnsubscribeToken is lifecycle_mail.read_unsubscribe_token: the account
// id and the address hash ("" when the token carries none), or ok false for a
// token that is forged, malformed or not shaped {"u": int, "h": str}.
func readUnsubscribeToken(secret, token string) (userID int64, digest string, ok bool) {
	cut := strings.LastIndexByte(token, '.')
	if cut < 0 {
		return 0, "", false
	}
	value, sig := token[:cut], token[cut+1:]
	given, err := base64.RawURLEncoding.DecodeString(sig)
	if err != nil {
		return 0, "", false
	}
	derived := sha1.Sum([]byte(unsubscribeSalt + "signer" + secret))
	mac := hmac.New(sha1.New, derived[:])
	mac.Write([]byte(value))
	if !hmac.Equal(given, mac.Sum(nil)) {
		return 0, "", false
	}
	compressed := strings.HasPrefix(value, ".")
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(value, "."))
	if err != nil {
		return 0, "", false
	}
	if compressed {
		zr, err := zlib.NewReader(bytes.NewReader(raw))
		if err != nil {
			return 0, "", false
		}
		if raw, err = io.ReadAll(io.LimitReader(zr, 4096)); err != nil {
			return 0, "", false
		}
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var data map[string]any
	if err := dec.Decode(&data); err != nil {
		return 0, "", false
	}
	num, isNum := data["u"].(json.Number)
	if !isNum {
		return 0, "", false
	}
	id, err := num.Int64()
	if err != nil {
		return 0, "", false
	}
	switch h := data["h"].(type) {
	case nil:
	case string:
		digest = h
	default:
		return 0, "", false
	}
	return id, digest, true
}
