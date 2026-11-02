// Package webpush is the Go port of App/app/webpush.py: Web Push message
// encryption (RFC 8291, aes128gcm of RFC 8188) and VAPID (RFC 8292, ES256).
// Standard library only.
package webpush

import (
	"bytes"
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdh"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/hkdf"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	// RecordSize is the aes128gcm record size the browser must accept.
	RecordSize = 4096
	// MaxPayload is the largest plaintext: the header and tag use 103 bytes.
	MaxPayload = 3800
	// TokenHours is the VAPID token lifetime.
	TokenHours = 12
)

// ErrTransport means the push service could not be reached (Python TransportError).
var ErrTransport = errors.New("webpush: transport error")

// PushHosts are the push services browsers subscribe with (push.py PUSH_HOST_SUFFIXES).
var PushHosts = []string{
	"fcm.googleapis.com",
	"push.services.mozilla.com",
	"push.apple.com",
	"notify.windows.com",
}

// EndpointAllowed is the save-time and send-time endpoint rule (push.py
// clean_subscription): https, no userinfo, default port only, and a host that
// is one of PushHosts or a subdomain of one.
func EndpointAllowed(raw string) bool {
	u, err := url.Parse(raw)
	if err != nil || u.Scheme != "https" || u.User != nil {
		return false
	}
	if port := u.Port(); port != "" && port != "443" {
		return false
	}
	host := strings.ToLower(u.Hostname())
	for _, suffix := range PushHosts {
		if host == suffix || strings.HasSuffix(host, "."+suffix) {
			return true
		}
	}
	return false
}

// B64URL encodes without padding, as Python's b64url does.
func B64URL(data []byte) string {
	return base64.RawURLEncoding.EncodeToString(data)
}

// UnB64URL decodes text with or without padding and ignores whitespace.
func UnB64URL(text string) ([]byte, error) {
	clean := strings.Join(strings.Fields(text), "")
	clean = strings.TrimRight(clean, "=")
	return base64.RawURLEncoding.DecodeString(clean)
}

// NewPrivateKey makes a fresh P-256 VAPID or application-server key.
func NewPrivateKey() (*ecdsa.PrivateKey, error) {
	return ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
}

// PrivateFromRaw loads a 32-byte big-endian P-256 scalar.
func PrivateFromRaw(raw []byte) (*ecdsa.PrivateKey, error) {
	if len(raw) != 32 {
		return nil, errors.New("a P-256 private key is 32 bytes")
	}
	ecdhKey, err := ecdh.P256().NewPrivateKey(raw)
	if err != nil {
		return nil, err
	}
	return ecdsaFromECDH(ecdhKey)
}

func ecdsaFromECDH(key *ecdh.PrivateKey) (*ecdsa.PrivateKey, error) {
	pub := key.PublicKey().Bytes()
	x := new(big.Int).SetBytes(pub[1:33])
	y := new(big.Int).SetBytes(pub[33:65])
	return &ecdsa.PrivateKey{
		PublicKey: ecdsa.PublicKey{Curve: elliptic.P256(), X: x, Y: y},
		D:         new(big.Int).SetBytes(key.Bytes()),
	}, nil
}

// PrivateRaw returns the 32-byte scalar.
func PrivateRaw(key *ecdsa.PrivateKey) []byte {
	return key.D.FillBytes(make([]byte, 32))
}

// PublicRaw returns the uncompressed 65-byte public point.
func PublicRaw(key *ecdsa.PrivateKey) []byte {
	return elliptic.Marshal(elliptic.P256(), key.X, key.Y) //nolint:staticcheck // fixed-format point
}

// CheckPublicKey parses a browser's p256dh key, or errors when it is not a P-256 point.
func CheckPublicKey(raw []byte) (*ecdh.PublicKey, error) {
	if len(raw) != 65 || raw[0] != 4 {
		return nil, errors.New("not an uncompressed P-256 point")
	}
	return ecdh.P256().NewPublicKey(raw)
}

// Encrypt returns one aes128gcm record for one browser (RFC 8291 section 3.4).
// asPrivate and salt are nil for production (fresh values); tests pass fixed ones.
func Encrypt(plaintext, uaPublic, authSecret []byte, asPrivate *ecdh.PrivateKey, salt []byte) ([]byte, error) {
	if len(plaintext) > MaxPayload {
		return nil, errors.New("push payload too large")
	}
	if asPrivate == nil {
		k, err := ecdh.P256().GenerateKey(rand.Reader)
		if err != nil {
			return nil, err
		}
		asPrivate = k
	}
	if salt == nil {
		salt = make([]byte, 16)
		if _, err := rand.Read(salt); err != nil {
			return nil, err
		}
	}
	uaKey, err := CheckPublicKey(uaPublic)
	if err != nil {
		return nil, err
	}
	asPublic := asPrivate.PublicKey().Bytes()
	ecdhSecret, err := asPrivate.ECDH(uaKey)
	if err != nil {
		return nil, err
	}
	keyInfo := append(append([]byte("WebPush: info\x00"), uaPublic...), asPublic...)
	ikm, err := hkdf.Key(sha256.New, ecdhSecret, authSecret, string(keyInfo), 32)
	if err != nil {
		return nil, err
	}
	cek, err := hkdf.Key(sha256.New, ikm, salt, "Content-Encoding: aes128gcm\x00", 16)
	if err != nil {
		return nil, err
	}
	nonce, err := hkdf.Key(sha256.New, ikm, salt, "Content-Encoding: nonce\x00", 12)
	if err != nil {
		return nil, err
	}
	block, err := aes.NewCipher(cek)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	// 0x02 marks the last (here: the only) record; no further padding.
	msg := append(append([]byte{}, plaintext...), 0x02)
	ciphertext := gcm.Seal(nil, nonce, msg, nil)
	header := make([]byte, 0, 16+5+len(asPublic)+len(ciphertext))
	header = append(header, salt...)
	var rs [4]byte
	binary.BigEndian.PutUint32(rs[:], RecordSize)
	header = append(header, rs[:]...)
	header = append(header, byte(len(asPublic)))
	header = append(header, asPublic...)
	return append(header, ciphertext...), nil
}

// VapidHeader returns the Authorization value for one push service origin (RFC 8292).
func VapidHeader(key *ecdsa.PrivateKey, audience, subject string, now time.Time) (string, error) {
	head := B64URL([]byte(`{"typ":"JWT","alg":"ES256"}`))
	audJSON, err := marshalNoHTMLEscape(audience)
	if err != nil {
		return "", err
	}
	subJSON, err := marshalNoHTMLEscape(subject)
	if err != nil {
		return "", err
	}
	claimsJSON := fmt.Sprintf(`{"aud":%s,"exp":%d,"sub":%s}`, audJSON, now.Unix()+TokenHours*3600, subJSON)
	claims := B64URL([]byte(claimsJSON))
	signingInput := head + "." + claims
	digest := sha256.Sum256([]byte(signingInput))
	r, s, err := ecdsa.Sign(rand.Reader, key, digest[:])
	if err != nil {
		return "", err
	}
	sig := append(r.FillBytes(make([]byte, 32)), s.FillBytes(make([]byte, 32))...)
	return fmt.Sprintf("vapid t=%s.%s.%s, k=%s", head, claims, B64URL(sig), B64URL(PublicRaw(key))), nil
}

// marshalNoHTMLEscape matches Python's json.dumps for plain text: no <,>,& escaping.
func marshalNoHTMLEscape(s string) (string, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(s); err != nil {
		return "", err
	}
	return strings.TrimSuffix(buf.String(), "\n"), nil
}

// Send encrypts payload and POSTs it to the push service. It returns the HTTP
// status. A network failure is ErrTransport. Redirects are not followed.
func Send(ctx context.Context, client *http.Client, endpoint string, uaPublic, authSecret, payload []byte,
	key *ecdsa.PrivateKey, subject string, ttl int, urgency string, now time.Time) (int, error) {
	parts, err := url.Parse(endpoint)
	if err != nil {
		return 0, ErrTransport
	}
	auth, err := VapidHeader(key, parts.Scheme+"://"+parts.Host, subject, now)
	if err != nil {
		return 0, err
	}
	body, err := Encrypt(payload, uaPublic, authSecret, nil, nil)
	if err != nil {
		return 0, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return 0, ErrTransport
	}
	req.Header.Set("Authorization", auth)
	req.Header.Set("Content-Encoding", "aes128gcm")
	req.Header.Set("Content-Type", "application/octet-stream")
	req.Header.Set("TTL", fmt.Sprint(ttl))
	req.Header.Set("Urgency", urgency)
	resp, err := client.Do(req)
	if err != nil {
		return 0, ErrTransport
	}
	defer resp.Body.Close()
	return resp.StatusCode, nil
}
