package webpush

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdh"
	"crypto/ecdsa"
	"crypto/hkdf"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"io"
	"math/big"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

type golden struct {
	UAPrivate    string `json:"ua_private"`
	UAPublic     string `json:"ua_public"`
	AuthSecret   string `json:"auth_secret"`
	ASPrivate    string `json:"as_private"`
	Salt         string `json:"salt"`
	VapidPrivate string `json:"vapid_private"`
	Payload      string `json:"payload"`
	Endpoint     string `json:"endpoint"`
	Subject      string `json:"subject"`
	Now          int64  `json:"now"`
	Body         string `json:"body"`
	VapidAuthz   string `json:"vapid_authorization"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func mustHex(t *testing.T, s string) []byte {
	t.Helper()
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// TestGoldenBodyMatchesPython checks the aes128gcm body byte for byte.
func TestGoldenBodyMatchesPython(t *testing.T) {
	g := loadGolden(t)
	asKey, err := ecdh.P256().NewPrivateKey(mustHex(t, g.ASPrivate))
	if err != nil {
		t.Fatal(err)
	}
	body, err := Encrypt([]byte(g.Payload), mustHex(t, g.UAPublic), mustHex(t, g.AuthSecret), asKey, mustHex(t, g.Salt))
	if err != nil {
		t.Fatal(err)
	}
	if hex.EncodeToString(body) != g.Body {
		t.Fatalf("body differs from Python golden")
	}
}

// TestGoldenVapidClaims checks the JWT header and claims equal Python's. The
// signature is random (ECDSA), so it is verified instead of compared.
func TestGoldenVapidClaims(t *testing.T) {
	g := loadGolden(t)
	key, err := PrivateFromRaw(mustHex(t, g.VapidPrivate))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Unix(g.Now, 0)
	header, err := VapidHeader(key, "https://push.example.net", g.Subject, now)
	if err != nil {
		t.Fatal(err)
	}
	if header != "" && !strings.HasPrefix(g.VapidAuthz, "vapid t=") {
		t.Fatal("golden header malformed")
	}
	pythonParts := strings.Split(strings.TrimPrefix(strings.Split(g.VapidAuthz, ",")[0], "vapid t="), ".")
	goParts := strings.Split(strings.TrimPrefix(strings.Split(header, ",")[0], "vapid t="), ".")
	if pythonParts[0] != goParts[0] || pythonParts[1] != goParts[1] {
		t.Fatalf("JWT header or claims differ from Python: %v vs %v", pythonParts, goParts)
	}
	if !strings.Contains(header, ", k="+B64URL(PublicRaw(key))) {
		t.Fatal("k= public key missing")
	}
	verifyJWT(t, header, key, "https://push.example.net", g.Subject, g.Now)
}

func verifyJWT(t *testing.T, header string, key *ecdsa.PrivateKey, aud, sub string, now int64) {
	t.Helper()
	token := strings.TrimPrefix(strings.Split(header, ",")[0], "vapid t=")
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		t.Fatalf("token has %d parts", len(parts))
	}
	claimsRaw, err := UnB64URL(parts[1])
	if err != nil {
		t.Fatal(err)
	}
	var claims struct {
		Aud string `json:"aud"`
		Exp int64  `json:"exp"`
		Sub string `json:"sub"`
	}
	if err := json.Unmarshal(claimsRaw, &claims); err != nil {
		t.Fatal(err)
	}
	if claims.Aud != aud || claims.Sub != sub || claims.Exp != now+TokenHours*3600 {
		t.Fatalf("claims %+v", claims)
	}
	sig, err := UnB64URL(parts[2])
	if err != nil || len(sig) != 64 {
		t.Fatalf("signature length %d err %v", len(sig), err)
	}
	digest := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	r := new(big.Int).SetBytes(sig[:32])
	s := new(big.Int).SetBytes(sig[32:])
	if !ecdsa.Verify(&key.PublicKey, digest[:], r, s) {
		t.Fatal("JWT signature does not verify")
	}
}

// decrypt is the receiver side of RFC 8291, used to round-trip Encrypt.
func decrypt(t *testing.T, body, uaPrivate, authSecret []byte) []byte {
	t.Helper()
	salt := body[:16]
	idLen := int(body[20])
	asPublic := body[21 : 21+idLen]
	ciphertext := body[21+idLen:]
	ua, err := ecdh.P256().NewPrivateKey(uaPrivate)
	if err != nil {
		t.Fatal(err)
	}
	asPub, err := ecdh.P256().NewPublicKey(asPublic)
	if err != nil {
		t.Fatal(err)
	}
	secret, err := ua.ECDH(asPub)
	if err != nil {
		t.Fatal(err)
	}
	uaPublic := ua.PublicKey().Bytes()
	info := append(append([]byte("WebPush: info\x00"), uaPublic...), asPublic...)
	ikm, _ := hkdf.Key(sha256.New, secret, authSecret, string(info), 32)
	cek, _ := hkdf.Key(sha256.New, ikm, salt, "Content-Encoding: aes128gcm\x00", 16)
	nonce, _ := hkdf.Key(sha256.New, ikm, salt, "Content-Encoding: nonce\x00", 12)
	block, _ := aes.NewCipher(cek)
	gcm, _ := cipher.NewGCM(block)
	plain, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		t.Fatal(err)
	}
	if plain[len(plain)-1] != 0x02 {
		t.Fatal("missing last-record delimiter")
	}
	if binary.BigEndian.Uint32(body[16:20]) != RecordSize {
		t.Fatal("record size")
	}
	return plain[:len(plain)-1]
}

func TestRoundTrip(t *testing.T) {
	ua, err := NewPrivateKey()
	if err != nil {
		t.Fatal(err)
	}
	uaPublic := PublicRaw(ua)
	auth := []byte("0123456789abcdef")
	payload := []byte(`{"message": "hello"}`)
	body, err := Encrypt(payload, uaPublic, auth, nil, nil)
	if err != nil {
		t.Fatal(err)
	}
	uaECDH, err := ecdh.P256().NewPrivateKey(PrivateRaw(ua))
	if err != nil {
		t.Fatal(err)
	}
	if got := decrypt(t, body, uaECDH.Bytes(), auth); !bytes.Equal(got, payload) {
		t.Fatalf("round trip: %q", got)
	}
	if _, err := Encrypt(bytes.Repeat([]byte("x"), MaxPayload+1), uaPublic, auth, nil, nil); err == nil {
		t.Fatal("oversize payload accepted")
	}
}

func TestCheckPublicKeyRejectsBadPoint(t *testing.T) {
	if _, err := CheckPublicKey(make([]byte, 65)); err == nil {
		t.Fatal("zero point accepted")
	}
	if _, err := CheckPublicKey([]byte{4, 1}); err == nil {
		t.Fatal("short point accepted")
	}
}

// TestSendHeaders checks what a push service sees.
func TestSendHeaders(t *testing.T) {
	var got http.Header
	var body []byte
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Clone()
		body, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusCreated)
	}))
	defer srv.Close()
	key, _ := NewPrivateKey()
	ua, _ := NewPrivateKey()
	status, err := Send(srv.Client(), srv.URL+"/send/1", PublicRaw(ua), []byte("0123456789abcdef"),
		[]byte("hi"), key, "mailto:ops@example.org", 60, "high", time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if status != http.StatusCreated {
		t.Fatalf("status %d", status)
	}
	if got.Get("Content-Encoding") != "aes128gcm" || got.Get("TTL") != "60" || got.Get("Urgency") != "high" {
		t.Fatalf("headers %v", got)
	}
	if got.Get("Content-Type") != "application/octet-stream" {
		t.Fatal("content type")
	}
	if !strings.HasPrefix(got.Get("Authorization"), "vapid t=") || !strings.Contains(got.Get("Authorization"), ", k=") {
		t.Fatalf("authorization %q", got.Get("Authorization"))
	}
	if len(body) == 0 {
		t.Fatal("empty body")
	}
}

func TestSendRedirectIsNotFollowed(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/elsewhere", http.StatusFound)
	}))
	defer srv.Close()
	key, _ := NewPrivateKey()
	ua, _ := NewPrivateKey()
	client := &http.Client{CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	status, err := Send(client, srv.URL+"/x", PublicRaw(ua), []byte("0123456789abcdef"), []byte("hi"), key, "mailto:a@b.c", 60, "high", time.Now())
	if err != nil || status != http.StatusFound {
		t.Fatalf("status %d err %v", status, err)
	}
}

func TestSendTransportError(t *testing.T) {
	key, _ := NewPrivateKey()
	ua, _ := NewPrivateKey()
	_, err := Send(&http.Client{Timeout: time.Second}, "http://127.0.0.1:1/x", PublicRaw(ua), []byte("0123456789abcdef"), []byte("hi"), key, "mailto:a@b.c", 60, "high", time.Now())
	if err != ErrTransport {
		t.Fatalf("want ErrTransport, got %v", err)
	}
}
