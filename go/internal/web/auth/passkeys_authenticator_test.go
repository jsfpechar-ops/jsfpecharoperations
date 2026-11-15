package auth

// A software authenticator for the passkey tests: one ES256 key, the answers
// a browser would send for navigator.credentials.create() and get(). Nothing
// here is a real device; the key and credential id are random per test.

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"testing"

	"github.com/fxamacker/cbor/v2"
)

// Authenticator data flags (WebAuthn section 6.1).
const (
	flagUP byte = 0x01 // user present
	flagUV byte = 0x04 // user verified
	flagBE byte = 0x08 // backup eligible
	flagBS byte = 0x10 // backed up
	flagAT byte = 0x40 // attested credential data follows
)

type softAuthenticator struct {
	key    *ecdsa.PrivateKey
	credID []byte
}

func newSoftAuthenticator(t *testing.T) *softAuthenticator {
	t.Helper()
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	id := make([]byte, 32)
	if _, err := rand.Read(id); err != nil {
		t.Fatal(err)
	}
	return &softAuthenticator{key: key, credID: id}
}

// ID is the credential id as the browser sends it: base64url, no padding.
func (a *softAuthenticator) ID() string { return base64.RawURLEncoding.EncodeToString(a.credID) }

// ceremonyInput is what the test controls about one ceremony: the challenge
// (base64url, as the options carried it), and the origin and rpId the browser
// reports. Wrong values here must be rejected by the server.
type ceremonyInput struct {
	Challenge string
	Origin    string
	RPID      string
}

// assertionInput adds what a login answer can vary: the counter, the flags
// and the userHandle (nil means the response omits it).
type assertionInput struct {
	ceremonyInput
	Counter    uint32
	Flags      byte
	UserHandle []byte
}

// assertion is a well-formed assertion for the given ceremony: user present
// and verified, counter 0, no userHandle.
func assertion(in ceremonyInput) assertionInput {
	return assertionInput{ceremonyInput: in, Flags: flagUP | flagUV}
}

type clientDataJSON struct {
	Type        string `json:"type"`
	Challenge   string `json:"challenge"`
	Origin      string `json:"origin"`
	CrossOrigin bool   `json:"crossOrigin"`
}

func clientData(typ, challenge, origin string) []byte {
	raw, _ := json.Marshal(clientDataJSON{Type: typ, Challenge: challenge, Origin: origin})
	return raw
}

func rpIDHash(rpID string) []byte {
	sum := sha256.Sum256([]byte(rpID))
	return sum[:]
}

func b64url(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

// Register returns the credential object a registration posts: id, rawId,
// type and response (clientDataJSON, attestationObject, transports). The
// attestation format is "none", the AAGUID is zero, the COSE key is EC2 P-256
// with alg -7 (ES256).
func (a *softAuthenticator) Register(t *testing.T, in ceremonyInput, counter uint32) map[string]any {
	t.Helper()
	x := a.key.PublicKey.X.FillBytes(make([]byte, 32))
	y := a.key.PublicKey.Y.FillBytes(make([]byte, 32))
	cose, err := cbor.Marshal(map[int]any{1: 2, 3: -7, -1: 1, -2: x, -3: y})
	if err != nil {
		t.Fatal(err)
	}
	authData := append([]byte{}, rpIDHash(in.RPID)...)
	authData = append(authData, flagUP|flagUV|flagAT)
	authData = binary.BigEndian.AppendUint32(authData, counter)
	authData = append(authData, make([]byte, 16)...) // AAGUID
	authData = binary.BigEndian.AppendUint16(authData, uint16(len(a.credID)))
	authData = append(authData, a.credID...)
	authData = append(authData, cose...)
	attObj, err := cbor.Marshal(map[string]any{"fmt": "none", "attStmt": map[string]any{}, "authData": authData})
	if err != nil {
		t.Fatal(err)
	}
	return map[string]any{
		"id":    a.ID(),
		"rawId": a.ID(),
		"type":  "public-key",
		"response": map[string]any{
			"clientDataJSON":    b64url(clientData("webauthn.create", in.Challenge, in.Origin)),
			"attestationObject": b64url(attObj),
			"transports":        []string{"internal"},
		},
	}
}

// Assert returns the credential object a login posts: the signature is
// ASN.1 DER ECDSA over authenticatorData || SHA-256(clientDataJSON).
func (a *softAuthenticator) Assert(t *testing.T, in assertionInput) map[string]any {
	t.Helper()
	cd := clientData("webauthn.get", in.Challenge, in.Origin)
	authData := append([]byte{}, rpIDHash(in.RPID)...)
	authData = append(authData, in.Flags)
	authData = binary.BigEndian.AppendUint32(authData, in.Counter)
	cdHash := sha256.Sum256(cd)
	digest := sha256.Sum256(append(append([]byte{}, authData...), cdHash[:]...))
	sig, err := ecdsa.SignASN1(rand.Reader, a.key, digest[:])
	if err != nil {
		t.Fatal(err)
	}
	response := map[string]any{
		"clientDataJSON":    b64url(cd),
		"authenticatorData": b64url(authData),
		"signature":         b64url(sig),
	}
	if in.UserHandle != nil {
		response["userHandle"] = b64url(in.UserHandle)
	}
	return map[string]any{"id": a.ID(), "rawId": a.ID(), "type": "public-key", "response": response}
}
