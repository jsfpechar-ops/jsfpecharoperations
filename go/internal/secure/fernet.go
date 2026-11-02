// Package secure reproduces the Python app's secrets byte for byte: Fernet and
// MultiFernet (data at rest), itsdangerous URLSafeTimedSerializer (cookies) and
// the HMAC-SHA256 digests. Standard library only.
package secure

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"io"
	"time"
)

const (
	fernetVersion   = 0x80
	fernetClockSkew = 60
)

// ErrInvalidToken is returned for any token that does not decrypt or verify.
var ErrInvalidToken = errors.New("secure: invalid token")

// ErrTokenExpired is returned when a Fernet token is older than its ttl.
var ErrTokenExpired = errors.New("secure: token expired")

// LegacyKey returns the Fernet key the app derived from its session secret:
// urlsafe-base64(SHA-256(secret)), as text.
func LegacyKey(secret string) []byte {
	sum := sha256.Sum256([]byte(secret))
	out := make([]byte, base64.URLEncoding.EncodedLen(len(sum)))
	base64.URLEncoding.Encode(out, sum[:])
	return out
}

// Fernet is one key: bytes 0-15 sign, bytes 16-31 encrypt.
type Fernet struct {
	sign []byte
	enc  []byte
}

// NewFernet parses a urlsafe-base64 Fernet key (32 bytes once decoded).
func NewFernet(key []byte) (*Fernet, error) {
	raw, err := base64.URLEncoding.DecodeString(string(key))
	if err != nil || len(raw) != 32 {
		return nil, ErrInvalidToken
	}
	return &Fernet{sign: raw[:16], enc: raw[16:]}, nil
}

// Encrypt encrypts with the current time and a random IV.
func (f *Fernet) Encrypt(data []byte) (string, error) {
	iv := make([]byte, aes.BlockSize)
	if _, err := io.ReadFull(rand.Reader, iv); err != nil {
		return "", err
	}
	return f.EncryptAt(data, time.Now(), iv)
}

// EncryptAt encrypts with an injected time and IV (tests and fixtures only).
func (f *Fernet) EncryptAt(data []byte, now time.Time, iv []byte) (string, error) {
	if len(iv) != aes.BlockSize {
		return "", ErrInvalidToken
	}
	block, err := aes.NewCipher(f.enc)
	if err != nil {
		return "", err
	}
	pad := aes.BlockSize - len(data)%aes.BlockSize
	padded := append(append([]byte{}, data...), bytes.Repeat([]byte{byte(pad)}, pad)...)
	ct := make([]byte, len(padded))
	cipher.NewCBCEncrypter(block, iv).CryptBlocks(ct, padded)

	msg := make([]byte, 0, 1+8+aes.BlockSize+len(ct)+sha256.Size)
	msg = append(msg, fernetVersion)
	msg = binary.BigEndian.AppendUint64(msg, uint64(now.Unix()))
	msg = append(msg, iv...)
	msg = append(msg, ct...)
	mac := hmac.New(sha256.New, f.sign)
	mac.Write(msg)
	msg = mac.Sum(msg)
	return base64.URLEncoding.EncodeToString(msg), nil
}

// Decrypt verifies and decrypts a token. A ttl of 0 means no age limit.
func (f *Fernet) Decrypt(token string, ttl time.Duration, now time.Time) ([]byte, error) {
	raw, err := base64.URLEncoding.DecodeString(token)
	const minLen = 1 + 8 + aes.BlockSize + aes.BlockSize + sha256.Size
	if err != nil || len(raw) < minLen || raw[0] != fernetVersion {
		return nil, ErrInvalidToken
	}
	body, mac := raw[:len(raw)-sha256.Size], raw[len(raw)-sha256.Size:]
	check := hmac.New(sha256.New, f.sign)
	check.Write(body)
	if !hmac.Equal(check.Sum(nil), mac) {
		return nil, ErrInvalidToken
	}
	ts := int64(binary.BigEndian.Uint64(raw[1:9]))
	if ttl > 0 {
		if ts+int64(ttl/time.Second) < now.Unix() {
			return nil, ErrTokenExpired
		}
		if ts > now.Unix()+fernetClockSkew {
			return nil, ErrInvalidToken
		}
	}
	iv := raw[9 : 9+aes.BlockSize]
	ct := raw[9+aes.BlockSize : len(raw)-sha256.Size]
	if len(ct) == 0 || len(ct)%aes.BlockSize != 0 {
		return nil, ErrInvalidToken
	}
	block, err := aes.NewCipher(f.enc)
	if err != nil {
		return nil, err
	}
	pt := make([]byte, len(ct))
	cipher.NewCBCDecrypter(block, iv).CryptBlocks(pt, ct)
	n := int(pt[len(pt)-1])
	if n < 1 || n > aes.BlockSize {
		return nil, ErrInvalidToken
	}
	for _, b := range pt[len(pt)-n:] {
		if int(b) != n {
			return nil, ErrInvalidToken
		}
	}
	return pt[:len(pt)-n], nil
}

// MultiFernet tries keys in order on decrypt and encrypts with the first.
type MultiFernet struct {
	fernets []*Fernet
}

// NewMultiFernet builds a MultiFernet from keys in the order the app uses.
func NewMultiFernet(keys ...[]byte) (*MultiFernet, error) {
	if len(keys) == 0 {
		return nil, ErrInvalidToken
	}
	m := &MultiFernet{}
	for _, k := range keys {
		f, err := NewFernet(k)
		if err != nil {
			return nil, err
		}
		m.fernets = append(m.fernets, f)
	}
	return m, nil
}

// Encrypt encrypts with the first key, at the current time.
func (m *MultiFernet) Encrypt(data []byte) (string, error) {
	return m.fernets[0].Encrypt(data)
}

// EncryptAt encrypts with the first key, at an injected time and IV.
func (m *MultiFernet) EncryptAt(data []byte, now time.Time, iv []byte) (string, error) {
	return m.fernets[0].EncryptAt(data, now, iv)
}

// Decrypt returns the plaintext from the first key that verifies the token.
func (m *MultiFernet) Decrypt(token string, ttl time.Duration, now time.Time) ([]byte, error) {
	for _, f := range m.fernets {
		if pt, err := f.Decrypt(token, ttl, now); err == nil {
			return pt, nil
		}
	}
	return nil, ErrInvalidToken
}
