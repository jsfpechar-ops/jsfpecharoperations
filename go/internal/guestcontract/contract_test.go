package guestcontract

import (
	"bytes"
	"compress/gzip"
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

func TestSupported(t *testing.T) {
	cases := []struct {
		v    int
		want bool
	}{{-1, false}, {0, false}, {1, true}, {2, false}}
	for _, c := range cases {
		if got := Supported(c.v); got != c.want {
			t.Errorf("Supported(%d) = %v, want %v", c.v, got, c.want)
		}
	}
}

func TestTokenHash(t *testing.T) {
	// SHA-256("abc"), the same as hashlib.sha256(b"abc").hexdigest().
	want := "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
	if got := TokenHash("abc"); got != want {
		t.Errorf("TokenHash = %s, want %s", got, want)
	}
}

func TestIdempotencyKey(t *testing.T) {
	k, err := NewIdempotencyKey()
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		key  string
		want bool
	}{
		{k, true},
		{"0123456789abcdef0123456789abcdef", true},
		{"0123456789ABCDEF0123456789ABCDEF", false},
		{"0123456789abcdef", false},
		{"0123456789abcdef0123456789abcdeg", false},
		{"", false},
	}
	for _, c := range cases {
		if got := ValidIdempotencyKey(c.key); got != c.want {
			t.Errorf("ValidIdempotencyKey(%q) = %v, want %v", c.key, got, c.want)
		}
	}
}

func testKeys(t *testing.T, fill byte) *secure.MultiFernet {
	t.Helper()
	key := []byte(base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{fill}, 32)))
	m, err := secure.NewMultiFernet(key)
	if err != nil {
		t.Fatal(err)
	}
	return m
}

func sample() Submission {
	return Submission{
		ContractVersion: V1,
		IdempotencyKey:  "0123456789abcdef0123456789abcdef",
		ReservationID:   42,
		Lang:            "de",
		Guest:           GuestForm{Surname: "Novák", FirstName: "Jan", LegalAck: true, Signature: "data:image/png;base64,AAAA"},
	}
}

func TestPayloadRoundTrip(t *testing.T) {
	keys := testKeys(t, 1)
	enc, err := EncodePayload(keys, sample())
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(enc, []byte("Nov")) {
		t.Fatal("payload is not encrypted")
	}
	compressed, err := keys.Decrypt(string(enc), 0, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if len(compressed) < 2 || compressed[0] != 0x1f || compressed[1] != 0x8b {
		t.Fatal("plaintext is not gzip")
	}
	got, err := DecodePayload(keys, enc)
	if err != nil {
		t.Fatal(err)
	}
	if got != sample() {
		t.Errorf("round trip\nwant %+v\ngot  %+v", sample(), got)
	}
}

func TestPayloadRefusals(t *testing.T) {
	keys := testKeys(t, 1)
	bad := sample()
	bad.ContractVersion = 2
	if _, err := EncodePayload(keys, bad); !errors.Is(err, ErrUnsupportedVersion) {
		t.Errorf("version 2: err = %v, want ErrUnsupportedVersion", err)
	}
	bad = sample()
	bad.IdempotencyKey = "short"
	if _, err := EncodePayload(keys, bad); !errors.Is(err, ErrBadIdempotencyKey) {
		t.Errorf("bad key: err = %v, want ErrBadIdempotencyKey", err)
	}
	enc, err := EncodePayload(keys, sample())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := DecodePayload(testKeys(t, 2), enc); err == nil {
		t.Error("decoded with the wrong key")
	}
	tampered := append([]byte(nil), enc...)
	tampered[len(tampered)/2] ^= 1
	if _, err := DecodePayload(keys, tampered); err == nil {
		t.Error("decoded a tampered payload")
	}
	decodedUnsupported := sample()
	decodedUnsupported.ContractVersion = 2
	plain, err := json.Marshal(decodedUnsupported)
	if err != nil {
		t.Fatal(err)
	}
	reenc, err := keys.Encrypt(gzipPlain(plain))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := DecodePayload(keys, []byte(reenc)); !errors.Is(err, ErrUnsupportedVersion) {
		t.Errorf("decode version 2: err = %v, want ErrUnsupportedVersion", err)
	}
}

func TestPayloadRejectsOversizedPlainJSON(t *testing.T) {
	keys := testKeys(t, 1)
	huge := sample()
	huge.Guest.Signature = strings.Repeat("x", MaxPayloadBytes+1)
	if _, err := EncodePayload(keys, huge); !errors.Is(err, ErrPayloadTooLarge) {
		t.Fatalf("encode: err = %v, want ErrPayloadTooLarge", err)
	}
}

func gzipPlain(plain []byte) []byte {
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	_, _ = zw.Write(plain)
	_ = zw.Close()
	return buf.Bytes()
}
