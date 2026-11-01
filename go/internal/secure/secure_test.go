package secure

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"reflect"
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
		if c.Name == "long" && len(c.Token) > 0 && c.Token[0] == '.' {
			compressedSeen = true
		}
		enc, err := s.Dumps(valueFor(c.Name), now)
		if err != nil {
			t.Fatal(err)
		}
		if enc != c.Token {
			t.Fatalf("%s/%s: first differing byte %d\n got  %s\n want %s", c.Salt, c.Name, firstDiff(enc, c.Token), enc, c.Token)
		}
	}
	if !compressedSeen {
		t.Fatal("the long payload was not compressed in the fixtures")
	}
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
