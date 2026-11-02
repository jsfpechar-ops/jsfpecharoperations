package secure

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"strings"
)

func hmacSHA256Hex(secret string, message string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(message))
	return hex.EncodeToString(mac.Sum(nil))
}

// RecoveryCodeHash matches Python recovery_code_hash: drop "-" and spaces,
// upper-case, then HMAC-SHA256 keyed by the session secret.
func RecoveryCodeHash(secret string, code string) string {
	normalized := strings.ToUpper(strings.NewReplacer("-", "", " ", "").Replace(code))
	return hmacSHA256Hex(secret, normalized)
}

// PinFingerprint matches Python pin_fingerprint: HMAC-SHA256 over
// "token\0pin", keyed by the session secret.
func PinFingerprint(secret string, token string, pin string) string {
	return hmacSHA256Hex(secret, token+"\x00"+pin)
}
