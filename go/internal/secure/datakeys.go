package secure

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"
)

// LoadDataKeys reproduces db._fernet and config.data_keys / legacy_data_key_enabled
// / _load_secret in App/app/config.py (lines 210-300) and App/app/db.py (2216-2260).
// It never creates a file: a missing secret is an error, where Python would mint one.
// Error messages never contain a key or the secret.
func LoadDataKeys(getenv func(string) string) (*MultiFernet, error) {
	var keys [][]byte
	for _, part := range strings.Split(getenv("UBYHOST_DATA_KEYS"), ",") {
		if p := strings.TrimSpace(part); p != "" {
			keys = append(keys, []byte(p))
		}
	}
	legacy := legacyDataKeyEnabled(getenv("UBYHOST_DATA_KEY_LEGACY"))
	if len(keys) == 0 && !legacy {
		return nil, errors.New("UBYHOST_DATA_KEY_LEGACY=0 needs at least one key in UBYHOST_DATA_KEYS")
	}
	// Read the secret only when the legacy key is in use, as Python does.
	var secret string
	if legacy || len(keys) == 0 {
		s, err := loadSecret(getenv)
		if err != nil {
			return nil, err
		}
		secret = s
	}
	for i, k := range keys {
		if _, err := NewFernet(k); err != nil {
			return nil, fmt.Errorf("UBYHOST_DATA_KEYS entry %d is not a valid Fernet key", i+1)
		}
	}
	if secret != "" {
		keys = append(keys, LegacyKey(secret))
	}
	return NewMultiFernet(keys...)
}

// EncryptString encrypts text with the first key, so a MultiFernet fits
// ubyport.FieldEncrypter.
func (m *MultiFernet) EncryptString(plain string) (string, error) {
	return m.Encrypt([]byte(plain))
}

// legacyDataKeyEnabled is config.legacy_data_key_enabled: on unless the trimmed,
// lower-cased value is one of 0, false, no, off.
func legacyDataKeyEnabled(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "0", "false", "no", "off":
		return false
	}
	return true
}

// loadSecret is config._load_secret without the minting: env UBYHOST_SECRET_KEY
// (at least 32 characters), else the first line of $UBYHOST_DATA_DIR/secret_key
// (default dir "data"), stripped, at least 32 characters.
func loadSecret(getenv func(string) string) (string, error) {
	if env := getenv("UBYHOST_SECRET_KEY"); env != "" {
		if utf8.RuneCountInString(env) < 32 {
			return "", errors.New("UBYHOST_SECRET_KEY must contain at least 32 characters.")
		}
		return env, nil
	}
	dir := getenv("UBYHOST_DATA_DIR")
	if dir == "" {
		dir = "data"
	}
	path := filepath.Join(dir, "secret_key")
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("no UBYHOST_SECRET_KEY is set and there is no key file at %s", path)
	}
	stored := strings.TrimSpace(string(raw))
	if utf8.RuneCountInString(stored) < 32 {
		return "", fmt.Errorf("%s is empty or too short", path)
	}
	return stored, nil
}

// LoadSecret exposes loadSecret to the host session reader (go/internal/session).
func LoadSecret(getenv func(string) string) (string, error) {
	return loadSecret(getenv)
}
