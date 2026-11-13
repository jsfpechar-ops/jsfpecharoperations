package session

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha1"
	"encoding/base32"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Authenticator-app second factor, ported from App/app/auth.py (pyotp 2.10
// defaults: SHA-1, 6 digits, 30-second steps).
const (
	totpInterval = 30
	totpIssuer   = "UbyHost"
	base32Chars  = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
)

var errBadPayload = errors.New("session: payload value is not an integer")

// NewTOTPSecret is pyotp.random_base32(): 32 characters from the base32 alphabet.
func NewTOTPSecret() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	for i := range b {
		b[i] = base32Chars[b[i]&31]
	}
	return string(b)
}

// TOTPURI is pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="UbyHost").
func TOTPURI(secret, username string) string {
	return "otpauth://totp/" + pyQuote(totpIssuer, "/") + ":" + pyQuote(username, "/") +
		"?secret=" + pyQuote(secret, "") + "&issuer=" + pyQuote(totpIssuer, "")
}

// totpAt is pyotp.TOTP(secret).at(step * 30): HOTP-SHA1 of the step counter.
// The secret is padded to a multiple of 8 and decoded case-insensitively.
func totpAt(secret string, step int64) (string, error) {
	if step < 0 {
		return "", errors.New("session: negative TOTP step")
	}
	if pad := len(secret) % 8; pad != 0 {
		secret += strings.Repeat("=", 8-pad)
	}
	key, err := base32.StdEncoding.DecodeString(strings.ToUpper(secret))
	if err != nil {
		return "", err
	}
	var msg [8]byte
	binary.BigEndian.PutUint64(msg[:], uint64(step))
	mac := hmac.New(sha1.New, key)
	mac.Write(msg[:])
	sum := mac.Sum(nil)
	off := sum[len(sum)-1] & 0xf
	code := binary.BigEndian.Uint32(sum[off:off+4]) & 0x7fffffff
	return fmt.Sprintf("%06d", code%1000000), nil
}

// RecoveryCodeHash is auth.recovery_code_hash.
func RecoveryCodeHash(secret, code string) string {
	return secure.RecoveryCodeHash(secret, code)
}

// NewRecoveryCodes is new_recovery_codes(count): "XXXX-XXXX", upper-case hex.
func NewRecoveryCodes(count int) []string {
	codes := make([]string, count)
	for i := range codes {
		b := make([]byte, 4)
		if _, err := rand.Read(b); err != nil {
			panic(err)
		}
		codes[i] = strings.ToUpper(hex.EncodeToString(b[:2]) + "-" + hex.EncodeToString(b[2:]))
	}
	return codes
}

// recoveryHashesJSON is json.dumps([recovery_code_hash(c) for c in codes]).
func recoveryHashesJSON(secret string, codes []string) string {
	hashes := make([]string, len(codes))
	for i, c := range codes {
		hashes[i] = RecoveryCodeHash(secret, c)
	}
	return pyDumpsList(hashes)
}

// encryptSecret is db.encrypt_secret: "" stays "", else Fernet with the first data key.
func encryptSecret(getenv func(string) string, plain string) (string, error) {
	if plain == "" {
		return "", nil
	}
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		return "", err
	}
	return keys.EncryptString(plain)
}

// EnableTOTP is enable_totp.
func EnableTOTP(ctx context.Context, db *pgxpool.Pool, getenv func(string) string, userID int64, totpSecret string, codes []string) error {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return err
	}
	enc, err := encryptSecret(getenv, totpSecret)
	if err != nil {
		return err
	}
	_, err = db.Exec(ctx, `UPDATE user_account SET totp_secret_enc = $1, totp_enabled = 1, `+
		`recovery_codes_hash = $2, totp_last_step = NULL, `+
		`session_version = session_version + 1 WHERE id = $3`,
		enc, recoveryHashesJSON(secret, codes), userID)
	return err
}

// StageTOTP is stage_totp.
func StageTOTP(ctx context.Context, db *pgxpool.Pool, getenv func(string) string, userID int64, totpSecret string) error {
	enc, err := encryptSecret(getenv, totpSecret)
	if err != nil {
		return err
	}
	_, err = db.Exec(ctx, `UPDATE user_account SET totp_secret_enc = $1, totp_enabled = 0, `+
		`totp_last_step = NULL WHERE id = $2`, enc, userID)
	return err
}

// ResetTOTP is reset_totp.
func ResetTOTP(ctx context.Context, db *pgxpool.Pool, userID int64) error {
	_, err := db.Exec(ctx, `UPDATE user_account SET totp_secret_enc = NULL, totp_enabled = 0, `+
		`recovery_codes_hash = NULL, totp_last_step = NULL, `+
		`session_version = session_version + 1 WHERE id = $1`, userID)
	return err
}

// VerifySecondFactor is verify_second_factor: a TOTP code for the step before,
// at or after now (each step accepted once, via totp_last_step), else a
// recovery code, spent by compare-and-set on recovery_codes_hash.
func VerifySecondFactor(ctx context.Context, db *pgxpool.Pool, getenv func(string) string, account *LoginAccount, code string, now time.Time) (bool, error) {
	normalized := pyRemoveSpace(code)
	if !isASCII(normalized) {
		return false, nil
	}
	// db.decrypt_secret: a missing data key raises, which Python turns into
	// False; a token no key opens reads as "" and falls through to recovery.
	totpSecret := ""
	if account.TOTPSecretEnc != nil && *account.TOTPSecretEnc != "" {
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return false, nil
		}
		if plain, err := keys.Decrypt(*account.TOTPSecretEnc, 0, now); err == nil {
			totpSecret = string(plain)
		}
	}
	if totpSecret != "" && normalized != "" {
		current := now.Unix() / totpInterval
		for _, step := range []int64{current - 1, current, current + 1} {
			want, err := totpAt(totpSecret, step)
			if err != nil {
				return false, err
			}
			if hmac.Equal([]byte(want), []byte(normalized)) {
				tag, err := db.Exec(ctx, `UPDATE user_account SET totp_last_step = $1 WHERE id = $2 `+
					`AND (totp_last_step IS NULL OR totp_last_step < $3)`, step, account.ID, step)
				if err != nil {
					return false, err
				}
				return tag.RowsAffected() == 1, nil
			}
		}
	}
	sessionSecret, err := secure.LoadSecret(getenv)
	if err != nil {
		return false, err
	}
	candidate := RecoveryCodeHash(sessionSecret, normalized)
	raw := ""
	if account.RecoveryCodesHash != nil {
		raw = *account.RecoveryCodesHash
	}
	if raw == "" {
		raw = "[]"
	}
	var stored []any
	if err := json.Unmarshal([]byte(raw), &stored); err != nil {
		stored = nil
	}
	for i, s := range stored {
		h, ok := s.(string)
		if !ok || !hmac.Equal([]byte(candidate), []byte(h)) {
			continue
		}
		rest := make([]string, 0, len(stored)-1)
		for j, o := range stored {
			if j != i {
				str, _ := o.(string)
				rest = append(rest, str)
			}
		}
		tag, err := db.Exec(ctx, `UPDATE user_account SET recovery_codes_hash = $1 WHERE id = $2 `+
			`AND recovery_codes_hash IS NOT DISTINCT FROM $3`, pyDumpsList(rest), account.ID, account.RecoveryCodesHash)
		if err != nil {
			return false, err
		}
		return tag.RowsAffected() == 1, nil
	}
	return false, nil
}
