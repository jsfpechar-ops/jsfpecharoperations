package secure

import (
	"bytes"
	"compress/zlib"
	"crypto/hmac"
	"crypto/sha1"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"
)

type fixtures struct {
	Secret string            `json:"secret"`
	Now    int64             `json:"now"`
	IVHex  string            `json:"iv_hex"`
	Keys   map[string]string `json:"keys"`
	Fernet []struct {
		Name         string            `json:"name"`
		PlaintextHex string            `json:"plaintext_hex"`
		Tokens       map[string]string `json:"tokens"`
	} `json:"fernet"`
	Multifernet struct {
		PlaintextHex string            `json:"plaintext_hex"`
		Keys         []string          `json:"keys"`
		Tokens       map[string]string `json:"tokens"`
	} `json:"multifernet"`
	Signer []struct {
		Salt  string          `json:"salt"`
		Name  string          `json:"name"`
		Value json.RawMessage `json:"value"`
		Token string          `json:"token"`
	} `json:"signer"`
	Digest struct {
		RecoveryCodeHash struct {
			Input string `json:"input"`
			Hex   string `json:"hex"`
		} `json:"recovery_code_hash"`
		PinFingerprint struct {
			Token string `json:"token"`
			Pin   string `json:"pin"`
			Hex   string `json:"hex"`
		} `json:"pin_fingerprint"`
	} `json:"digest"`
}

type uidRM struct {
	UID int `json:"uid"`
	RM  int `json:"rm"`
}

type nameOnly struct {
	Name string `json:"name"`
}

func loadFixtures(t *testing.T) fixtures {
	t.Helper()
	raw, err := os.ReadFile("testdata/fixtures.json")
	if err != nil {
		t.Fatal(err)
	}
	var f fixtures
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatal(err)
	}
	return f
}

func valueFor(name string) any {
	switch name {
	case "small":
		return uidRM{UID: 7, RM: 1}
	case "unicode":
		return nameOnly{Name: "Jana Nováková"}
	case "long":
		list := make([]int, 200)
		for i := range list {
			list[i] = i % 7
		}
		return list
	}
	return nil
}

func iv(t *testing.T, f fixtures) []byte {
	t.Helper()
	b, err := hex.DecodeString(f.IVHex)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestFernetFixtures(t *testing.T) {
	f := loadFixtures(t)
	now := time.Unix(f.Now, 0)
	ivBytes := iv(t, f)
	for _, c := range f.Fernet {
		want, _ := hex.DecodeString(c.PlaintextHex)
		for label, token := range c.Tokens {
			fer, err := NewFernet([]byte(f.Keys[label]))
			if err != nil {
				t.Fatal(err)
			}
			got, err := fer.Decrypt(token, 0, now)
			if err != nil || string(got) != string(want) {
				t.Fatalf("%s/%s: decrypt failed: %v", c.Name, label, err)
			}
			enc, err := fer.EncryptAt(want, now, ivBytes)
			if err != nil || enc != token {
				t.Fatalf("%s/%s: token differs from Python", c.Name, label)
			}
		}
	}
}

func TestMultiFernetFixtures(t *testing.T) {
	f := loadFixtures(t)
	now := time.Unix(f.Now, 0)
	keys := make([][]byte, 0, len(f.Multifernet.Keys))
	for _, k := range f.Multifernet.Keys {
		keys = append(keys, []byte(k))
	}
	m, err := NewMultiFernet(keys...)
	if err != nil {
		t.Fatal(err)
	}
	want, _ := hex.DecodeString(f.Multifernet.PlaintextHex)
	for label, token := range f.Multifernet.Tokens {
		got, err := m.Decrypt(token, 0, now)
		if err != nil || string(got) != string(want) {
			t.Fatalf("multifernet %s: decrypt failed: %v", label, err)
		}
	}
	enc, err := m.EncryptAt(want, now, iv(t, f))
	if err != nil || enc != f.Multifernet.Tokens["key1"] {
		t.Fatalf("multifernet encrypt must use the first key")
	}
}

func TestSignerFixtures(t *testing.T) {
	f := loadFixtures(t)
	now := time.Unix(f.Now, 0)
	compressedSeen := false
	for _, c := range f.Signer {
		s := NewTimedSerializer(f.Secret, c.Salt)
		var want any
		if err := json.Unmarshal(c.Value, &want); err != nil {
			t.Fatal(err)
		}
		var got any
		if err := s.Loads(c.Token, NoMaxAge, now, &got); err != nil || !reflect.DeepEqual(got, want) {
			t.Fatalf("%s/%s: loads failed: %v", c.Salt, c.Name, err)
		}
		enc, err := s.Dumps(valueFor(c.Name), now)
		if err != nil {
			t.Fatal(err)
		}
		if strings.HasPrefix(c.Token, ".") {
			compressedSeen = true
			checkCompressedDumps(t, s, c.Salt, f.Secret, enc, c.Token, now, want)
			continue
		}
		if enc != c.Token {
			t.Fatalf("%s/%s: first differing byte %d\n got  %s\n want %s", c.Salt, c.Name, firstDiff(enc, c.Token), enc, c.Token)
		}
	}
	if !compressedSeen {
		t.Fatal("the long payload was not compressed in the fixtures")
	}
}

// checkCompressedDumps: zlib output differs from Go's deflate, so for a
// compressed Python token Go's Dumps must round-trip through Go Loads, carry
// the same timestamp as Python, carry a signature that HMAC-SHA1 over Go's
// signed string produces with the django-concat key, and decompress to the
// same JSON bytes as the Python payload.
func checkCompressedDumps(t *testing.T, s *TimedSerializer, salt, secret, enc, pyToken string, now time.Time, want any) {
	t.Helper()
	var got any
	if err := s.Loads(enc, NoMaxAge, now, &got); err != nil || !reflect.DeepEqual(got, want) {
		t.Fatalf("%s: Go Dumps token does not load back: %v", salt, err)
	}
	cut := strings.LastIndex(enc, ".")
	signed, sig := enc[:cut], enc[cut+1:]
	pySigned := pyToken[:strings.LastIndex(pyToken, ".")]
	if signed[strings.LastIndex(signed, ".")+1:] != pySigned[strings.LastIndex(pySigned, ".")+1:] {
		t.Fatalf("%s: timestamp differs from Python", salt)
	}
	key := sha1.Sum([]byte(salt + "signer" + secret))
	mac := hmac.New(sha1.New, key[:])
	mac.Write([]byte(signed))
	if base64.RawURLEncoding.EncodeToString(mac.Sum(nil)) != sig {
		t.Fatalf("%s: signature is not the itsdangerous signature over the Go payload", salt)
	}
	goRaw := decompressPayload(t, signed)
	pyRaw := decompressPayload(t, pySigned)
	if !bytes.Equal(goRaw, pyRaw) {
		t.Fatalf("%s: decompressed Go JSON %s differs from Python JSON %s", salt, goRaw, pyRaw)
	}
}

// decompressPayload returns the JSON inside a signed string whose payload is zlib-compressed.
func decompressPayload(t *testing.T, signed string) []byte {
	t.Helper()
	value := strings.TrimPrefix(signed[:strings.LastIndex(signed, ".")], ".")
	raw, err := base64.RawURLEncoding.DecodeString(value)
	if err != nil {
		t.Fatal(err)
	}
	r, err := zlib.NewReader(bytes.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}
	out, err := io.ReadAll(r)
	if err != nil {
		t.Fatal(err)
	}
	return out
}

func firstDiff(a, b string) int {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			return i
		}
	}
	return min(len(a), len(b))
}

func TestDigestFixtures(t *testing.T) {
	f := loadFixtures(t)
	if got := RecoveryCodeHash(f.Secret, f.Digest.RecoveryCodeHash.Input); got != f.Digest.RecoveryCodeHash.Hex {
		t.Fatalf("recovery_code_hash differs")
	}
	if got := PinFingerprint(f.Secret, f.Digest.PinFingerprint.Token, f.Digest.PinFingerprint.Pin); got != f.Digest.PinFingerprint.Hex {
		t.Fatalf("pin_fingerprint differs")
	}
}

func TestLegacyKeyMatchesFixture(t *testing.T) {
	f := loadFixtures(t)
	if string(LegacyKey(f.Secret)) != f.Keys["legacy"] {
		t.Fatal("legacy key differs")
	}
}

func flipAt(token string, i int) string {
	b := []byte(token)
	if b[i] == 'A' {
		b[i] = 'B'
	} else {
		b[i] = 'A'
	}
	return string(b)
}

func TestNegativeCases(t *testing.T) {
	f := loadFixtures(t)
	now := time.Unix(f.Now, 0)
	fer, _ := NewFernet([]byte(f.Keys["key1"]))
	token := f.Fernet[1].Tokens["key1"]
	if _, err := fer.Decrypt(flipAt(token, 40), 0, now); err == nil {
		t.Fatal("flipped fernet byte accepted")
	}
	if _, err := fer.Decrypt(token, time.Hour, now.Add(2*time.Hour)); err == nil {
		t.Fatal("expired fernet token accepted")
	}

	c := f.Signer[0]
	s := NewTimedSerializer(f.Secret, c.Salt)
	var out any
	if err := s.Loads(flipAt(c.Token, 2), NoMaxAge, now, &out); err == nil {
		t.Fatal("flipped signer byte accepted")
	}
	wrong := NewTimedSerializer(f.Secret, "ubyhost-not-a-salt")
	if err := wrong.Loads(c.Token, NoMaxAge, now, &out); err == nil {
		t.Fatal("wrong salt accepted")
	}
	if err := s.Loads(c.Token, time.Hour, now.Add(2*time.Hour), &out); err != ErrSignatureExpired {
		t.Fatalf("expired max_age not refused: %v", err)
	}
}
