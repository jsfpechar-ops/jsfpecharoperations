package secure

import (
	"bytes"
	"compress/zlib"
	"crypto/hmac"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"strings"
	"time"
)

// NoMaxAge passed as maxAge to Loads accepts a token of any age.
const NoMaxAge time.Duration = -1

// ErrBadSignature is returned when a token fails verification.
var ErrBadSignature = errors.New("secure: bad signature")

// ErrSignatureExpired is returned when a token is older than maxAge or dated in the future.
var ErrSignatureExpired = errors.New("secure: signature expired")

// TimedSerializer reproduces itsdangerous URLSafeTimedSerializer(secret, salt=salt)
// with the django-concat key derivation and HMAC-SHA1.
type TimedSerializer struct {
	Secret string
	Salt   string
}

// NewTimedSerializer returns a serializer for one salt.
func NewTimedSerializer(secret string, salt string) *TimedSerializer {
	return &TimedSerializer{Secret: secret, Salt: salt}
}

func (s *TimedSerializer) sign(message string) string {
	derived := sha1.Sum([]byte(s.Salt + "signer" + s.Secret))
	mac := hmac.New(sha1.New, derived[:])
	mac.Write([]byte(message))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func encodeTimestamp(ts int64) string {
	var full [8]byte
	binary.BigEndian.PutUint64(full[:], uint64(ts))
	return base64.RawURLEncoding.EncodeToString(bytes.TrimLeft(full[:], "\x00"))
}

func decodeTimestamp(s string) (int64, error) {
	raw, err := base64.RawURLEncoding.DecodeString(s)
	if err != nil || len(raw) > 8 {
		return 0, ErrBadSignature
	}
	var full [8]byte
	copy(full[8-len(raw):], raw)
	return int64(binary.BigEndian.Uint64(full[:])), nil
}

// Dumps serializes v as compact JSON (keys in struct field order), compresses
// it like itsdangerous when that is shorter, and signs it at time now.
func (s *TimedSerializer) Dumps(v any, now time.Time) (string, error) {
	var jb bytes.Buffer
	enc := json.NewEncoder(&jb)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
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
	signed := value + "." + encodeTimestamp(now.Unix())
	return signed + "." + s.sign(signed), nil
}

// Loads verifies token at time now, refuses tokens older than maxAge (NoMaxAge
// disables the check) and decodes the payload into out.
func (s *TimedSerializer) Loads(token string, maxAge time.Duration, now time.Time, out any) error {
	cut := strings.LastIndex(token, ".")
	if cut < 0 {
		return ErrBadSignature
	}
	signed, sig := token[:cut], token[cut+1:]
	if !hmac.Equal([]byte(s.sign(signed)), []byte(sig)) {
		return ErrBadSignature
	}
	cut = strings.LastIndex(signed, ".")
	if cut < 0 {
		return ErrBadSignature
	}
	value, tsPart := signed[:cut], signed[cut+1:]
	ts, err := decodeTimestamp(tsPart)
	if err != nil {
		return err
	}
	age := now.Unix() - ts
	if age < 0 {
		return ErrSignatureExpired
	}
	if maxAge != NoMaxAge && age > int64(maxAge/time.Second) {
		return ErrSignatureExpired
	}
	compressed := strings.HasPrefix(value, ".")
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(value, "."))
	if err != nil {
		return ErrBadSignature
	}
	if compressed {
		r, err := zlib.NewReader(bytes.NewReader(raw))
		if err != nil {
			return ErrBadSignature
		}
		raw, err = io.ReadAll(r)
		if err != nil {
			return ErrBadSignature
		}
	}
	return json.Unmarshal(raw, out)
}
