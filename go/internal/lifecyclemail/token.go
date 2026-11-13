package lifecyclemail

import (
	"bytes"
	"compress/zlib"
	"crypto/hmac"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// unsubscribeSalt is the salt lifecycle_mail._serializer passes to itsdangerous.
const unsubscribeSalt = "ubyhost-lifecycle-unsubscribe"

// EmailHash is lifecycle_mail.email_hash: HMAC-SHA256, keyed with the app
// secret, over "mail-suppression\0" and the normalised address, as lower-case
// hex. "" for a non-address.
func EmailHash(secret, address string) string {
	normalised := ubyport.NormaliseEmail(address)
	if normalised == "" {
		return ""
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte("mail-suppression\x00" + normalised))
	return hex.EncodeToString(mac.Sum(nil))
}

// tokenPayload is {"u": account id, "h": address hash}; field order is the
// key order of the Python dict.
type tokenPayload struct {
	U int64  `json:"u"`
	H string `json:"h"`
}

// UnsubscribeToken is lifecycle_mail.unsubscribe_token: an itsdangerous
// URLSafeSerializer (no timestamp, django-concat key, HMAC-SHA1) over
// {"u": user_id, "h": email_hash(address)}.
//
// Python compresses the JSON with zlib when that is shorter, and a hex hash
// always is. Go's deflate may pick different bytes than zlib for the same
// input, so a token can differ from Python's while still verifying there:
// the signature covers whatever bytes are written and zlib reads both.
func UnsubscribeToken(secret string, userID int64, address string) (string, error) {
	var jb bytes.Buffer
	enc := json.NewEncoder(&jb)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(tokenPayload{U: userID, H: EmailHash(secret, address)}); err != nil {
		return "", err
	}
	payload := bytes.TrimSuffix(jb.Bytes(), []byte("\n"))
	prefix := ""
	var zb bytes.Buffer
	w, err := zlib.NewWriterLevel(&zb, zlib.DefaultCompression)
	if err != nil {
		return "", err
	}
	if _, err := w.Write(payload); err != nil {
		return "", err
	}
	if err := w.Close(); err != nil {
		return "", err
	}
	if zb.Len() < len(payload)-1 {
		payload = zb.Bytes()
		prefix = "."
	}
	value := prefix + base64.RawURLEncoding.EncodeToString(payload)
	sig, err := signValue(secret, value)
	if err != nil {
		return "", err
	}
	return value + "." + sig, nil
}

// UnsubscribeURL is lifecycle_mail.unsubscribe_url. It uses the public base
// URL, not the app one.
func (c Config) UnsubscribeURL(userID int64, address, lang string) (string, error) {
	token, err := UnsubscribeToken(c.SecretKey, userID, address)
	if err != nil {
		return "", err
	}
	return c.PublicBaseURL + "/mail/unsubscribe/" + token + "?lang=" + lang, nil
}

// signValue is itsdangerous Signer.get_signature with the django-concat key.
func signValue(secret, value string) (string, error) {
	derived := sha1.Sum([]byte(unsubscribeSalt + "signer" + secret))
	mac := hmac.New(sha1.New, derived[:])
	mac.Write([]byte(value))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil)), nil
}
