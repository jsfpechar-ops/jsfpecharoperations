package ubyport

// Brief 1702d2: the three read-only UbyPort calls of the police-letter
// connection test, App/app/ubyport/client.py test_availability,
// max_batch_size and code_list (190-210), with soap.build_simple_call and
// build_dej_mi_ciselnik (134-151), and codelists.store for the error list
// (App/app/codelists.py 29-86). None of them files anything: no
// ZapisUbytovane, no submission row. They reuse Post, so the host, the NTLM
// login and the error kinds are the ones of the filing path.

import (
	"context"
	"regexp"
	"strconv"
	"strings"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"
)

// CodeListErrors is codelists.WS_KINDS[KIND_ERRORS], what DejMiCiselnik is asked for.
const CodeListErrors = "Chyby"

// BuildSimpleCall mirrors soap.build_simple_call: extra is inserted as is.
func BuildSimpleCall(method, authCode, extra string, wsa bool) string {
	body := "<" + method + ` xmlns="` + nsMethod + `">` +
		"<AutentificationCode>" + xmlEscaper.Replace(authCode) + "</AutentificationCode>" +
		extra +
		"</" + method + ">"
	return buildEnvelope(method, body, wsa)
}

// BuildDejMiCiselnik mirrors soap.build_dej_mi_ciselnik.
func BuildDejMiCiselnik(kind, authCode string, wsa bool) string {
	return BuildSimpleCall("DejMiCiselnik", authCode, "<CoChci>"+xmlEscaper.Replace(kind)+"</CoChci>", wsa)
}

// TestAvailability is client.test_availability: TestDostupnosti answered "true".
func (c *Client) TestAvailability(ctx context.Context) (bool, error) {
	text, err := c.Post(ctx, "TestDostupnosti", BuildSimpleCall("TestDostupnosti", c.AuthCode, "", wsaHeaderOn()))
	if err != nil {
		return false, err
	}
	v, err := ParseScalarResponse([]byte(text), "TestDostupnosti")
	if err != nil {
		return false, err
	}
	return v != nil && strings.ToLower(*v) == "true", nil
}

// MaxBatchSize is client.max_batch_size: nil when the answer is empty or not a number.
func (c *Client) MaxBatchSize(ctx context.Context) (*int, error) {
	text, err := c.Post(ctx, "MaximalniDelkaSeznamu", BuildSimpleCall("MaximalniDelkaSeznamu", c.AuthCode, "", wsaHeaderOn()))
	if err != nil {
		return nil, err
	}
	v, err := ParseScalarResponse([]byte(text), "MaximalniDelkaSeznamu")
	if err != nil || v == nil || *v == "" {
		return nil, err
	}
	n, err := strconv.Atoi(*v)
	if err != nil {
		return nil, nil
	}
	return &n, nil
}

// CodeList is client.code_list: kind is one of Staty, UcelyPobytu, Chyby.
func (c *Client) CodeList(ctx context.Context, kind string) ([]map[string]string, error) {
	text, err := c.Post(ctx, "DejMiCiselnik", BuildDejMiCiselnik(kind, c.AuthCode, wsaHeaderOn()))
	if err != nil {
		return nil, err
	}
	return ParseCiselnikResponse([]byte(text))
}

// ciselnikFields is codelists.CISELNIK_FIELDS, in its order.
var ciselnikFields = []string{"Kod3", "Kod2", "TextKratkyCZ", "TextKratkyENG", "TextCZ", "TextENG"}

// codeLikeRE and errCodeRE are codelists._CODE_LIKE and _ERR_CODE (\d is
// Unicode in Python, so \p{Nd} here).
var (
	codeLikeRE = regexp.MustCompile(`(?i)^(?:[A-Z]+_[A-Z]+_)?\p{Nd}{1,4}$`)
	errCodeRE  = regexp.MustCompile(`(?i)^ERR_CZE_\p{Nd}{1,4}$`)
)

// errorCodeAndText is codelists._code_and_texts for KIND_ERRORS; the Czech
// and the English text are the same there.
func errorCodeAndText(row map[string]string) (string, string) {
	values := make([]string, len(ciselnikFields))
	for i, f := range ciselnikFields {
		values[i] = pyStrip(row[f])
	}
	kod2, kod3, textCZ := values[1], values[0], values[4]
	if errCodeRE.MatchString(kod2) {
		text := kod3
		if text == "" {
			text = textCZ
		}
		if text != "" {
			return kod2, text
		}
	}
	code := ""
	for _, v := range values {
		if codeLikeRE.MatchString(v) {
			code = v
			break
		}
	}
	text, best := "", -1
	for _, v := range values {
		if v != "" && v != code && !codeLikeRE.MatchString(v) {
			if n := len([]rune(v)); n > best {
				text, best = v, n
			}
		}
	}
	return code, text
}

// errorSeverity is codelists._extra for KIND_ERRORS: one digit or "".
func errorSeverity(row map[string]string) string {
	s := pyStrip(row["TextKratkyCZ"])
	if r := []rune(s); len(r) == 1 && unicode.IsDigit(r[0]) {
		return s
	}
	return ""
}

// StoreErrorCodelist is codelists.store(KIND_ERRORS, rows): the cached error
// list is replaced in one transaction; rows without a code are skipped. It
// returns the number of rows written. now is db.utcnow().
func StoreErrorCodelist(ctx context.Context, pool *pgxpool.Pool, rows []map[string]string, now string) (int, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, `DELETE FROM codelist WHERE kind = $1`, codelistErrors); err != nil {
		return 0, err
	}
	written := 0
	for _, row := range rows {
		code, text := errorCodeAndText(row)
		if code == "" {
			continue
		}
		if _, err := tx.Exec(ctx, `INSERT INTO codelist (kind, code, text_cs, text_en, extra, fetched_at) VALUES ($1, $2, $3, $4, $5, $6)
  ON CONFLICT (kind, code) DO UPDATE SET text_cs = excluded.text_cs, text_en = excluded.text_en, extra = excluded.extra, fetched_at = excluded.fetched_at`,
			codelistErrors, code, text, text, errorSeverity(row), now); err != nil {
			return 0, err
		}
		written++
	}
	return written, tx.Commit(ctx)
}
