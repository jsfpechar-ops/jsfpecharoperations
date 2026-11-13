package signup

import (
	"bytes"
	"compress/zlib"
	"crypto/hmac"
	"crypto/sha1"
	"encoding/base64"
	"encoding/json"
	"io"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Click is a verified signed click value: the identifiers and when they
// were first seen (milliseconds since the epoch).
type Click struct {
	IDs    map[string]string
	SeenMS int64
}

// pyStrip is str.strip(): Go's unicode.IsSpace plus U+001C to U+001F.
func pyStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) })
}

// jsonString writes s as a JSON string the way json.dumps(ensure_ascii=False)
// does for the ASCII values signed here (ids, nonces).
func jsonString(s string) string {
	b, _ := json.Marshal(s)
	return string(b)
}

// plainSign is the HMAC-SHA1 signature of itsdangerous Signer (django-concat).
func plainSign(secret, salt, message string) string {
	derived := sha1.Sum([]byte(salt + "signer" + secret))
	mac := hmac.New(sha1.New, derived[:])
	mac.Write([]byte(message))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

// plainDumps is URLSafeSerializer(secret, salt).dumps for a ready JSON text:
// zlib when that is shorter, URL-safe base64, then "." and the signature.
func plainDumps(secret, salt, payload string) (string, error) {
	data := []byte(payload)
	prefix := ""
	var zb bytes.Buffer
	w, err := zlib.NewWriterLevel(&zb, zlib.DefaultCompression)
	if err != nil {
		return "", err
	}
	if _, err := w.Write(data); err != nil {
		return "", err
	}
	if err := w.Close(); err != nil {
		return "", err
	}
	if zb.Len() < len(data)-1 {
		data = zb.Bytes()
		prefix = "."
	}
	value := prefix + base64.RawURLEncoding.EncodeToString(data)
	return value + "." + plainSign(secret, salt, value), nil
}

// plainLoads is URLSafeSerializer(secret, salt).loads: the JSON object, with
// whole numbers as int64; ok is false wherever Python raises BadSignature.
func plainLoads(secret, salt, token string) (map[string]any, bool) {
	cut := strings.LastIndex(token, ".")
	if cut < 0 {
		return nil, false
	}
	value, sig := token[:cut], token[cut+1:]
	if !hmac.Equal([]byte(plainSign(secret, salt, value)), []byte(sig)) {
		return nil, false
	}
	compressed := strings.HasPrefix(value, ".")
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(value, "."))
	if err != nil {
		return nil, false
	}
	if compressed {
		r, err := zlib.NewReader(bytes.NewReader(raw))
		if err != nil {
			return nil, false
		}
		if raw, err = io.ReadAll(r); err != nil {
			return nil, false
		}
	}
	return decodeObject(raw)
}

// decodeObject decodes a JSON object with whole numbers as int64.
func decodeObject(raw []byte) (map[string]any, bool) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, false
	}
	m, ok := v.(map[string]any)
	if !ok || m == nil {
		return nil, false
	}
	for k, e := range m {
		m[k] = number(e)
	}
	return m, true
}

func number(v any) any {
	switch x := v.(type) {
	case json.Number:
		if i, err := x.Int64(); err == nil {
			return i
		}
	case map[string]any:
		for k, e := range x {
			x[k] = number(e)
		}
	}
	return v
}

// IssueClick is issue_click: the identifiers (in CLICK_PARAMS order) and the
// moment they were first seen, signed with salt ubyhost-signup-click.
func IssueClick(secret string, ids map[string]string, seenMS int64) (string, error) {
	var parts []string
	for _, p := range clickParams {
		if v, ok := ids[p.name]; ok {
			parts = append(parts, jsonString(p.name)+":"+jsonString(v))
		}
	}
	payload := `{"i":{` + strings.Join(parts, ",") + `},"t":` + strconv.FormatInt(seenMS, 10) + `}`
	return plainDumps(secret, clickSalt, payload)
}

// ReadClick is read_click: nil for a bad signature, a click time more than
// five minutes ahead or more than 90 days back, or any identifier that is
// not valid. nowMS is the current time in milliseconds.
func ReadClick(secret, token string, nowMS int64) *Click {
	if token == "" {
		return nil
	}
	payload, ok := plainLoads(secret, clickSalt, token)
	if !ok {
		return nil
	}
	rawIDs, ok := payload["i"].(map[string]any)
	if !ok {
		return nil
	}
	seen, ok := payload["t"].(int64)
	if !ok {
		return nil
	}
	if seen > nowMS+clickFutureSlackMS || seen < nowMS-ClickMaxAgeDays*86400*1000 {
		return nil
	}
	ids := map[string]string{}
	for _, p := range clickParams {
		v, present := rawIDs[p.name]
		if !present {
			continue
		}
		s, isString := v.(string)
		if !isString {
			return nil
		}
		if c := CleanClickID(p.name, s); c != "" {
			ids[p.name] = c
		}
	}
	if len(ids) == 0 || len(ids) != len(rawIDs) {
		return nil
	}
	return &Click{IDs: ids, SeenMS: seen}
}

// IssueToken is issue_token: {"uid", "n"} signed at now with salt
// ubyhost-signup-verify, valid for VerifyMaxAge.
func IssueToken(secret string, userID int64, nonce string, now time.Time) (string, error) {
	payload := `{"uid":` + strconv.FormatInt(userID, 10) + `,"n":` + jsonString(nonce) + `}`
	return secure.NewTimedSerializer(secret, verifySalt).Dumps(json.RawMessage(payload), now)
}

// readToken is the signature half of pending_account: the uid and nonce of
// a verify token at most 24 hours old, ok false otherwise.
func readToken(secret, token string, now time.Time) (int64, string, bool) {
	var raw json.RawMessage
	if err := secure.NewTimedSerializer(secret, verifySalt).Loads(token, VerifyMaxAge*time.Second, now, &raw); err != nil {
		return 0, "", false
	}
	payload, ok := decodeObject(raw)
	if !ok {
		return 0, "", false
	}
	uid, _ := payload["uid"].(int64)
	nonce, _ := payload["n"].(string)
	if uid == 0 || nonce == "" {
		return 0, "", false
	}
	return uid, nonce, true
}
