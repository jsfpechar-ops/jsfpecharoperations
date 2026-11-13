package exports

import (
	"bytes"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// bom starts every CSV download (Excel in a Czech locale reads UTF-8 then).
const bom = "\xef\xbb\xbf"

// stayHeader is the label row of stays_export.STAY_COLUMNS.
var stayHeader = []string{"Apartment", "Arrival", "Departure", "Number of guests", "Label", "Guest e-mail"}

// formulaPrefixes is csv_safety._FORMULA_PREFIXES.
var formulaPrefixes = []string{"=", "+", "-", "@", "\t", "\r", "\n", " "}

// csvSafe is csv_safety.csv_safe for a text cell.
func csvSafe(v string) string {
	trimmed := strings.TrimLeft(v, " ")
	for _, p := range formulaPrefixes {
		if strings.HasPrefix(trimmed, p) {
			return "'" + v
		}
	}
	return v
}

// writeCSVRow is csv.writer(delimiter=";", quoting=QUOTE_MINIMAL).writerow:
// a field holding ";", '"', "\r" or "\n" is quoted with quotes doubled, a
// row ends in "\r\n".
func writeCSVRow(b *bytes.Buffer, fields []string) {
	if len(fields) == 1 && fields[0] == "" {
		b.WriteString("\"\"\r\n")
		return
	}
	for i, f := range fields {
		if i > 0 {
			b.WriteByte(';')
		}
		if strings.ContainsAny(f, ";\"\r\n") {
			b.WriteByte('"')
			b.WriteString(strings.ReplaceAll(f, `"`, `""`))
			b.WriteByte('"')
			continue
		}
		b.WriteString(f)
	}
	b.WriteString("\r\n")
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// expectedGuestCount is reporting.expected_guest_count; 0 is None or zero.
func expectedGuestCount(override, declared, reduced *int64) *int64 {
	base := declared
	if override != nil && *override != 0 {
		base = override
	}
	if reduced != nil && *reduced != 0 && (base == nil || *reduced < *base) {
		return reduced
	}
	return base
}

// ReservationsCSVHandler is exports.reservations_export with stays_export.
func ReservationsCSVHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		from, to := queryDate(r, "from"), queryDate(r, "to")
		if from == "" || to == "" {
			backErr(w, r, "/reservations", "flash.error.export_range_required", nil)
			return
		}
		// stays_export._export_sql
		query := `SELECT a.internal_name, r.date_from, r.date_to, r.expected_guests_override,
			r.declared_guests, r.lead_reduced_guests, r.summary, r.guest_email
			FROM reservation r JOIN apartment a ON a.id = r.apartment_id
			WHERE r.archived_at IS NULL AND ($1::bigint IS NULL OR a.owner_user_id = $1)
			AND COALESCE(r.source, '') != 'demo'`
		args := []any{ownerID(h)}
		if apartment := queryInt(r, "apartment"); apartment != 0 {
			args = append(args, apartment)
			query += fmt.Sprintf(" AND r.apartment_id = $%d", len(args))
		}
		args = append(args, from)
		query += fmt.Sprintf(" AND r.date_to >= $%d", len(args))
		args = append(args, to)
		query += fmt.Sprintf(" AND r.date_from <= $%d", len(args))
		query += " ORDER BY r.date_from, a.internal_name"
		ctx := r.Context()
		rows, err := pool.Query(ctx, query, args...)
		if err != nil {
			serverError(w, err)
			return
		}
		var out bytes.Buffer
		out.WriteString(bom)
		writeCSVRow(&out, stayHeader)
		n := 0
		for rows.Next() {
			var name, dateFrom, dateTo string
			var override, declared, reduced *int64
			var summary, email *string
			if err := rows.Scan(&name, &dateFrom, &dateTo, &override, &declared, &reduced, &summary, &email); err != nil {
				rows.Close()
				serverError(w, err)
				return
			}
			guests := ""
			if g := expectedGuestCount(override, declared, reduced); g != nil && *g != 0 {
				guests = strconv.FormatInt(*g, 10)
			}
			writeCSVRow(&out, []string{csvSafe(name), csvSafe(dateFrom), csvSafe(dateTo),
				csvSafe(guests), csvSafe(str(summary)), csvSafe(str(email))})
			n++
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			serverError(w, err)
			return
		}
		if err := audit(ctx, pool, h, at, "export_reservations_csv", fmt.Sprintf("rows=%d", n)); err != nil {
			serverError(w, err)
			return
		}
		attachment(w, "text/csv; charset=utf-8", "stays-"+dayStamp(at)+".csv", out.Bytes())
	}
}
