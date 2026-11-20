package secure

import (
	"errors"
	"time"
)

// ErrDecrypt is returned when no configured key can read a stored token.
var ErrDecrypt = errors.New("stored value could not be decrypted with any key")

// EncryptField is db.encrypt_field: absent plaintext stays absent.
func (m *MultiFernet) EncryptField(plain string) (string, error) {
	if plain == "" {
		return "", nil
	}
	return m.EncryptString(plain)
}

// DecryptField is db.decrypt_field with no plaintext fallback: failure is an error.
func (m *MultiFernet) DecryptField(token string, now time.Time) (string, error) {
	if token == "" {
		return "", nil
	}
	pt, err := m.Decrypt(token, 0, now)
	if err != nil {
		return "", ErrDecrypt
	}
	return string(pt), nil
}

// TokenIsCurrent is db.token_is_current: the primary key alone can decrypt.
func (m *MultiFernet) TokenIsCurrent(token string, now time.Time) bool {
	if token == "" {
		return false
	}
	_, err := m.fernets[0].Decrypt(token, 0, now)
	return err == nil
}

// RotateToken re-encrypts under the primary key (db.rotate_token).
func (m *MultiFernet) RotateToken(token string, now time.Time) (string, error) {
	pt, err := m.Decrypt(token, 0, now)
	if err != nil {
		return "", ErrDecrypt
	}
	return m.Encrypt(pt)
}

// EncryptBlob is db.encrypt_blob for file bodies.
func (m *MultiFernet) EncryptBlob(data []byte) ([]byte, error) {
	s, err := m.Encrypt(data)
	if err != nil {
		return nil, err
	}
	return []byte(s), nil
}

// RotateBlob re-encrypts bytes (photos on disk).
func (m *MultiFernet) RotateBlob(token []byte, now time.Time) ([]byte, error) {
	pt, err := m.Decrypt(string(token), 0, now)
	if err != nil {
		return nil, ErrDecrypt
	}
	return m.EncryptBlob(pt)
}
