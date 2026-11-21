package secure

import (
	"encoding/base64"
	"testing"
	"time"
)

func TestRotateTokenRoundTrip(t *testing.T) {
	raw := make([]byte, 32)
	for i := range raw {
		raw[i] = byte(i)
	}
	key := []byte(base64.URLEncoding.EncodeToString(raw))
	old, err := NewMultiFernet(key)
	if err != nil {
		t.Fatal(err)
	}
	newKey := make([]byte, 32)
	for i := range newKey {
		newKey[i] = byte(31 - i)
	}
	key2 := []byte(base64.URLEncoding.EncodeToString(newKey))
	both, err := NewMultiFernet(key2, key)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Unix(1_700_000_000, 0)
	tok, err := old.EncryptString("hello")
	if err != nil {
		t.Fatal(err)
	}
	if both.TokenIsCurrent(tok, now) {
		t.Fatal("old key token should not be current under new primary")
	}
	rot, err := both.RotateToken(tok, now)
	if err != nil {
		t.Fatal(err)
	}
	if !both.TokenIsCurrent(rot, now) {
		t.Fatal("rotated token should be current")
	}
	got, err := both.DecryptField(rot, now)
	if err != nil || got != "hello" {
		t.Fatalf("decrypt: %q err=%v", got, err)
	}
}
