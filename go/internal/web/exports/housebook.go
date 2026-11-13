package exports

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// housebookHeader is the label row of housebook.HOUSEBOOK_COLUMNS.
var housebookHeader = []string{"Apartment", "IDUB", "Stay from", "Stay to", "Surname", "Given name(s)",
	"Date of birth", "Nationality", "Travel document no.", "Visa no.", "Permanent residence abroad",
	"Purpose of stay", "Note", "Signed", "Reported to police", "Reported at", "Receipt stamp"}

// purposeCS is the Czech label of validation.PURPOSES (purpose_label(code, "cs")).
var purposeCS = map[string]string{
	"00": "Zdravotní", "01": "Obchodní", "02": "Kulturní", "03": "Návštěva rodiny nebo přátel",
	"04": "Pozvání", "05": "Oficiální (politický)", "06": "Podnikání (OSVČ)", "07": "Sportovní",
	"10": "Turistika", "11": "Studium (školení, stáž)", "12": "Tranzit (průjezd)",
	"13": "Letištní tranzit", "27": "Zaměstnání", "93": "Vízum ADS (občané Číny)", "99": "Ostatní",
}

// reportedText is the "reported" mapping in housebook._housebook_export_row.
var reportedText = map[string]string{
	"sent":         "yes",
	"not_required": "not required (Czech national)",
	"error":        "NO - rejected",
	"blocked":      "NO - rejected, cannot be corrected",
	"pending":      "not yet",
}

// signedText is the "signed" mapping of reporting.signature_record kinds.
var signedText = map[string]string{"own": "yes", "imported": "yes", "signed_for": "by adult", "exempt": "not required"}

// encryptedGuestPairs is db.ENCRYPTED_GUEST_COLUMNS: db._hydrate decrypts
// every pair a guest row selected, so a broken token in any of them fails
// the read.
var encryptedGuestPairs = [][2]string{
	{"doc_number", "doc_number_enc"},
	{"visa_number", "visa_number_enc"},
	{"signature_png", "signature_png_enc"},
	{"fee_host_reason", "fee_host_reason_enc"},
	{"birth_date", "birth_date_enc"},
	{"res_street", "res_street_enc"},
	{"res_city", "res_city_enc"},
}

// row is one result row by column name, values as pgx returns them.
type row map[string]any

func (r row) str(k string) string {
	if s, ok := r[k].(string); ok {
		return s
	}
	return ""
}

func (r row) int(k string) int64 {
	if n, ok := r[k].(int64); ok {
		return n
	}
	return 0
}

// queryRows runs a query and returns each row by name, plus the column order.
func queryRows(ctx context.Context, pool *pgxpool.Pool, query string, args ...any) ([]row, []string, error) {
	rows, err := pool.Query(ctx, query, args...)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	var names []string
	for _, f := range rows.FieldDescriptions() {
		names = append(names, f.Name)
	}
	var out []row
	for rows.Next() {
		values, err := rows.Values()
		if err != nil {
			return nil, nil, err
		}
		r := row{}
		for i, n := range names {
			r[n] = values[i]
		}
		out = append(out, r)
	}
	return out, names, rows.Err()
}

// hydrate is db._hydrate for a guest row: each plaintext field becomes
// decrypt_field(its token, the plaintext column).
func hydrate(getenv func(string) string, r row) error {
	for _, pair := range encryptedGuestPairs {
		token, present := r[pair[1]]
		if !present {
			continue
		}
		tok, _ := token.(string)
		if tok == "" {
			continue
		}
		var fallback *string
		value, err := decryptField(getenv, &tok, fallback)
		if err != nil {
			return err
		}
		r[pair[0]] = *value
	}
	return nil
}

// orStr is Python's `a or b` on two text values.
func orStr(a, b string) string {
	if a != "" {
		return a
	}
	return b
}

// formatBirthDate is validation.format_birth_date.
func formatBirthDate(s string) string {
	r := []rune(s)
	if len(r) != 8 {
		return s
	}
	return string(r[:2]) + "." + string(r[2:4]) + "." + string(r[4:])
}

// composeResidence is validation.compose_residence with lang "cs".
func composeResidence(street, city, country string) string {
	var parts []string
	if street != "" {
		parts = append(parts, street)
	}
	if city != "" {
		parts = append(parts, city)
	}
	if country != "" {
		parts = append(parts, country+"-"+countries.Name(country, "cs"))
	}
	return firstRunes(strings.Join(parts, ", "), 255)
}

// purposeLabel is validation.purpose_label(code, "cs").
func purposeLabel(code string) string {
	if label, ok := purposeCS[code]; ok {
		return label
	}
	return code
}

// birthBound is validation._birth_bounds on a stored DDMMYYYY value (stored
// birth dates are already normalised, as go/internal/validation assumes).
func birthBound(raw string, latest bool) (time.Time, bool) {
	if len(raw) != 8 {
		return time.Time{}, false
	}
	for i := 0; i < 8; i++ {
		if raw[i] < '0' || raw[i] > '9' {
			return time.Time{}, false
		}
	}
	day, _ := strconv.Atoi(raw[0:2])
	month, _ := strconv.Atoi(raw[2:4])
	year, _ := strconv.Atoi(raw[4:8])
	if year == 0 {
		return time.Time{}, false
	}
	if latest {
		if month == 0 {
			month = 12
		}
		if month > 12 {
			return time.Time{}, false
		}
		if day == 0 {
			day = time.Date(year, time.Month(month)+1, 0, 0, 0, 0, 0, time.UTC).Day()
		}
	}
	if month == 0 {
		month = 1
	}
	if day == 0 {
		day = 1
	}
	t := time.Date(year, time.Month(month), day, 0, 0, 0, 0, time.UTC)
	if t.Year() != year || int(t.Month()) != month || t.Day() != day {
		return time.Time{}, false
	}
	return t, true
}

// ageOn is validation.age_on.
func ageOn(birth, when time.Time) int {
	years := when.Year() - birth.Year()
	if when.Month() < birth.Month() || (when.Month() == birth.Month() && when.Day() < birth.Day()) {
		years--
	}
	return years
}

// stayStart is the first of reporting._stay_dates.
func stayStart(guestFrom, reservationFrom string) (time.Time, bool) {
	if t, ok := validation.ParseISODate(guestFrom); ok {
		return t, true
	}
	return validation.ParseISODate(reservationFrom)
}

// isValidSignature is validation.is_valid_signature: the value parses as a
// signature data URL. GuestIssues raises the "signature" issue exactly when
// parse_signature_data_url fails, except that it accepts "imported".
func isValidSignature(v string) bool {
	if strings.TrimSpace(v) == "imported" {
		return false
	}
	for _, issue := range validation.GuestIssues(validation.GuestRow{SignaturePNG: v}, "", "", time.Now()) {
		if issue.Field == "signature" {
			return false
		}
	}
	return true
}

// signatureKind is reporting.signature_record(...)["kind"].
func signatureKind(ctx context.Context, d deps, g row) (string, error) {
	value := strings.TrimSpace(g.str("signature_png"))
	if value == "imported" {
		return "imported", nil
	}
	if strings.HasPrefix(value, "data:image/") {
		return "own", nil
	}
	start, ok := stayStart(g.str("stay_from"), g.str("res_from"))
	if !ok {
		return "missing", nil
	}
	birth, ok := birthBound(g.str("birth_date"), false)
	if !ok || ageOn(birth, start) >= 15 {
		return "missing", nil
	}
	if signer := g.int("signed_for_guest_id"); signer != 0 {
		adults, _, err := queryRows(ctx, d.pool, `SELECT * FROM guest WHERE id = $1 AND reservation_id = $2
			AND archived_at IS NULL`, signer, g.int("reservation_id"))
		if err != nil {
			return "", err
		}
		if len(adults) > 0 {
			adult := adults[0]
			if err := hydrate(d.getenv, adult); err != nil {
				return "", err
			}
			adultStart, ok := stayStart(adult.str("stay_from"), g.str("res_from"))
			adultBirth, born := birthBound(adult.str("birth_date"), true)
			if isValidSignature(adult.str("signature_png")) && ok && born && ageOn(adultBirth, adultStart) >= 18 {
				return "signed_for", nil
			}
		}
	}
	return "exempt", nil
}

// housebookRow is housebook._housebook_export_row, the CSV columns only.
func housebookRow(ctx context.Context, d deps, g row) ([]string, error) {
	state := g.str("submit_state")
	reported, known := reportedText[state]
	if !known {
		reported = state
	}
	byHand := state == "sent" && g.str("manual_filed_at") != ""
	if byHand {
		reported = "yes - filed by hand in UbyPort"
	}
	stamp := ""
	if byHand {
		stamp = g.str("manual_reference")
	} else if sub := g.int("submission_id"); sub != 0 {
		var ps *string
		err := d.pool.QueryRow(ctx, "SELECT pseudo_stamp FROM submission WHERE id = $1", sub).Scan(&ps)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return nil, err
		}
		stamp = str(ps)
	}
	kind, err := signatureKind(ctx, d, g)
	if err != nil {
		return nil, err
	}
	signed, ok := signedText[kind]
	if !ok {
		signed = "no"
	}
	reportedAt := g.str("submitted_at")
	if byHand {
		reportedAt = g.str("manual_filed_at")
	}
	country := strings.ToUpper(g.str("res_country"))
	return []string{
		g.str("internal_name"),
		g.str("uby_idub"),
		orStr(g.str("stay_from"), g.str("res_from")),
		orStr(g.str("stay_to"), g.str("res_to")),
		g.str("surname"),
		g.str("first_name"),
		formatBirthDate(g.str("birth_date")),
		g.str("nationality"),
		g.str("doc_number"),
		g.str("visa_number"),
		composeResidence(g.str("res_street"), g.str("res_city"), country),
		purposeLabel(g.str("purpose")),
		g.str("note"),
		signed,
		reported,
		reportedAt,
		stamp,
	}, nil
}

// HousebookCSVHandler is exports.housebook_download with housebook.housebook_rows
// and iter_housebook_csv_rows.
func HousebookCSVHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		if !identityVisible(h, nil) {
			backErr(w, r, "/housebook", "flash.error.identity_hidden_export", nil)
			return
		}
		// housebook._housebook_sql
		query := `SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id,
			a.id AS apartment_id, a.internal_name, a.uby_idub
			FROM guest g
			JOIN reservation r ON r.id = g.reservation_id
			JOIN apartment a ON a.id = r.apartment_id
			WHERE r.status != 'ignored' AND g.archived_at IS NULL
			AND g.restricted_at IS NULL
			AND COALESCE(r.source, '') != 'demo'
			AND ($1::bigint IS NULL OR a.owner_user_id = $1)`
		owner, ok := requireOwner(w, h)
		if !ok {
			return
		}
		args := []any{owner}
		if apartment := queryInt(r, "apartment"); apartment != 0 {
			args = append(args, apartment)
			query += fmt.Sprintf(" AND a.id = $%d", len(args))
		}
		if from := queryDate(r, "from"); from != "" {
			args = append(args, from)
			query += fmt.Sprintf(" AND COALESCE(g.stay_from, r.date_from) >= $%d", len(args))
		}
		if to := queryDate(r, "to"); to != "" {
			args = append(args, to)
			query += fmt.Sprintf(" AND COALESCE(g.stay_from, r.date_from) <= $%d", len(args))
		}
		query += " ORDER BY COALESCE(g.stay_from, r.date_from), g.id"
		ctx := r.Context()
		guests, _, err := queryRows(ctx, pool, query, args...)
		if err != nil {
			serverError(w, err)
			return
		}
		var out bytes.Buffer
		out.WriteString(bom)
		writeCSVRow(&out, housebookHeader)
		for _, g := range guests {
			if err := hydrate(getenv, g); err != nil {
				serverError(w, err)
				return
			}
			fields, err := housebookRow(ctx, d, g)
			if err != nil {
				serverError(w, err)
				return
			}
			for i := range fields {
				fields[i] = csvSafe(fields[i])
			}
			writeCSVRow(&out, fields)
		}
		if err := audit(ctx, pool, h, at, "export_housebook_csv", fmt.Sprintf("rows=%d", len(guests))); err != nil {
			serverError(w, err)
			return
		}
		attachment(w, "text/csv; charset=utf-8", "domovni-kniha-"+dayStamp(at)+".csv", out.Bytes())
	}
}
