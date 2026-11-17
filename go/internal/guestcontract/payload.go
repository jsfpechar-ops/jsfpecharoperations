package guestcontract

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// MaxPayloadBytes caps the decompressed JSON. A signature is at most about
// 350 KB of base64 (validation.maxSignaturePayloadChars), so 1 MiB is ample.
const MaxPayloadBytes = 1 << 20

var (
	// ErrUnsupportedVersion: the row's contract version is not N or N-1.
	ErrUnsupportedVersion = errors.New("guestcontract: unsupported contract version")
	// ErrPayloadTooLarge: the decompressed payload exceeds MaxPayloadBytes.
	ErrPayloadTooLarge = errors.New("guestcontract: payload too large")
	// ErrBadIdempotencyKey: not 32 lower-case hex characters.
	ErrBadIdempotencyKey = errors.New("guestcontract: bad idempotency key")
)

// EncodePayload is the value of guest_inbox.payload_enc: JSON, gzip, then a
// Fernet token with the data keys (decision D4: the encryption of the _enc
// columns). Python reads it with gzip.decompress(db.decrypt_blob(value)).
func EncodePayload(keys *secure.MultiFernet, s Submission) ([]byte, error) {
	if !Supported(s.ContractVersion) {
		return nil, ErrUnsupportedVersion
	}
	if !ValidIdempotencyKey(s.IdempotencyKey) {
		return nil, ErrBadIdempotencyKey
	}
	plain, err := json.Marshal(s)
	if err != nil {
		return nil, err
	}
	if len(plain) > MaxPayloadBytes {
		return nil, ErrPayloadTooLarge
	}
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	if _, err := zw.Write(plain); err != nil {
		return nil, err
	}
	if err := zw.Close(); err != nil {
		return nil, err
	}
	token, err := keys.Encrypt(buf.Bytes())
	if err != nil {
		return nil, err
	}
	return []byte(token), nil
}

// DecodePayload reverses EncodePayload. It refuses a version other than N or
// N-1 and a payload over MaxPayloadBytes once decompressed.
func DecodePayload(keys *secure.MultiFernet, data []byte) (Submission, error) {
	var s Submission
	compressed, err := keys.Decrypt(string(data), 0, time.Now())
	if err != nil {
		return s, err
	}
	zr, err := gzip.NewReader(bytes.NewReader(compressed))
	if err != nil {
		return s, fmt.Errorf("guestcontract: payload is not gzip: %w", err)
	}
	plain, err := io.ReadAll(io.LimitReader(zr, MaxPayloadBytes+1))
	if err != nil {
		return s, fmt.Errorf("guestcontract: payload gzip: %w", err)
	}
	if len(plain) > MaxPayloadBytes {
		return s, ErrPayloadTooLarge
	}
	if err := json.Unmarshal(plain, &s); err != nil {
		return s, fmt.Errorf("guestcontract: payload json: %w", err)
	}
	if !Supported(s.ContractVersion) {
		return s, ErrUnsupportedVersion
	}
	return s, nil
}
