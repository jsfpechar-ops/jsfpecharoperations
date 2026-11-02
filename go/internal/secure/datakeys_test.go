package secure

import (
	"bytes"
	"encoding/base64"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const dkSecret = "0123456789abcdef0123456789abcdef-test"

// dkKey returns a valid urlsafe Fernet key made from one repeated byte.
func dkKey(b byte) string {
	return base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{b}, 32))
}

// dkEnv returns a getenv that reads only from m.
func dkEnv(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

// dkToken encrypts plain under a single-key MultiFernet built from key.
func dkToken(t *testing.T, key []byte, plain string) string {
	t.Helper()
	mf, err := NewMultiFernet(key)
	if err != nil {
		t.Fatal(err)
	}
	tok, err := mf.EncryptString(plain)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func dkDecrypt(t *testing.T, mf *MultiFernet, tok string) string {
	t.Helper()
	raw, err := mf.Decrypt(tok, 0, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	return string(raw)
}

func TestDataKeysOnlyLegacyOff(t *testing.T) {
	key := dkKey(1)
	mf, err := LoadDataKeys(dkEnv(map[string]string{
		"UBYHOST_DATA_KEYS":       key,
		"UBYHOST_DATA_KEY_LEGACY": "0",
	}))
	if err != nil {
		t.Fatal(err)
	}
	tok := dkToken(t, []byte(key), "hello")
	if got := dkDecrypt(t, mf, tok); got != "hello" {
		t.Fatalf("got %q", got)
	}
}

func TestDataKeysWithLegacySecret(t *testing.T) {
	key := dkKey(2)
	mf, err := LoadDataKeys(dkEnv(map[string]string{
		"UBYHOST_DATA_KEYS":  key,
		"UBYHOST_SECRET_KEY": dkSecret,
	}))
	if err != nil {
		t.Fatal(err)
	}
	legacyTok := dkToken(t, LegacyKey(dkSecret), "old value")
	if got := dkDecrypt(t, mf, legacyTok); got != "old value" {
		t.Fatalf("legacy token: got %q", got)
	}
	newTok := dkToken(t, []byte(key), "new value")
	if got := dkDecrypt(t, mf, newTok); got != "new value" {
		t.Fatalf("new token: got %q", got)
	}
}

func TestDataKeysSecretFromFileTrimmed(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "secret_key"), []byte("  "+dkSecret+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	mf, err := LoadDataKeys(dkEnv(map[string]string{"UBYHOST_DATA_DIR": dir}))
	if err != nil {
		t.Fatal(err)
	}
	tok := dkToken(t, LegacyKey(dkSecret), "from file")
	if got := dkDecrypt(t, mf, tok); got != "from file" {
		t.Fatalf("got %q", got)
	}
}

func TestDataKeysNoKeysLegacyOffIsError(t *testing.T) {
	_, err := LoadDataKeys(dkEnv(map[string]string{
		"UBYHOST_SECRET_KEY":      dkSecret,
		"UBYHOST_DATA_KEY_LEGACY": "off",
	}))
	if err == nil {
		t.Fatal("want error")
	}
}

func TestDataKeysShortSecretIsError(t *testing.T) {
	_, err := LoadDataKeys(dkEnv(map[string]string{"UBYHOST_SECRET_KEY": "too-short"}))
	if err == nil {
		t.Fatal("want error")
	}
}

func TestDataKeysMissingFileIsErrorAndNotCreated(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "secret_key")
	_, err := LoadDataKeys(dkEnv(map[string]string{"UBYHOST_DATA_DIR": dir}))
	if err == nil {
		t.Fatal("want error")
	}
	if _, statErr := os.Stat(path); !os.IsNotExist(statErr) {
		t.Fatalf("secret file was created or stat failed: %v", statErr)
	}
}

func TestDataKeysMalformedSecondKey(t *testing.T) {
	bad := "not-a-valid-key-SECRETVALUE"
	_, err := LoadDataKeys(dkEnv(map[string]string{
		"UBYHOST_DATA_KEYS":       dkKey(3) + "," + bad,
		"UBYHOST_DATA_KEY_LEGACY": "0",
	}))
	if err == nil {
		t.Fatal("want error")
	}
	if err.Error() != "UBYHOST_DATA_KEYS entry 2 is not a valid Fernet key" {
		t.Fatalf("got %q", err.Error())
	}
	if strings.Contains(err.Error(), "SECRETVALUE") {
		t.Fatal("error leaks the key value")
	}
}

func TestDataKeysOffWithSpacesCountsAsOff(t *testing.T) {
	// No secret and no data dir: the secret must not be read when legacy is off.
	mf, err := LoadDataKeys(dkEnv(map[string]string{
		"UBYHOST_DATA_KEYS":       dkKey(4),
		"UBYHOST_DATA_KEY_LEGACY": "OFF ",
		"UBYHOST_DATA_DIR":        filepath.Join(t.TempDir(), "absent"),
	}))
	if err != nil {
		t.Fatal(err)
	}
	if got := len(mf.fernets); got != 1 {
		t.Fatalf("want 1 key, got %d", got)
	}
}
