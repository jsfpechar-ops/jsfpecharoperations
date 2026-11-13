package exports

import (
	"archive/zip"
	"bytes"
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// ownedSubmissionSQL is access.submission. Python selects s.*, so its query
// helper decrypts request_xml_enc (db._hydrate); only that column is read here.
const ownedSubmissionSQL = `SELECT s.request_xml, s.request_xml_enc FROM submission s JOIN apartment a ON a.id = s.apartment_id
	WHERE s.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`

// ownedReservationSQL is access.reservation(request, id, "r.id, r.apartment_id").
const ownedReservationSQL = `SELECT r.apartment_id FROM reservation r JOIN apartment a ON a.id = r.apartment_id
	WHERE r.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`

// stayReceiptsSQL is the query in exports.stay_receipts.
const stayReceiptsSQL = `SELECT id, created_at, receipt_pdf FROM submission WHERE id IN (
	  SELECT DISTINCT submission_id FROM guest WHERE reservation_id = $1 AND submission_id IS NOT NULL
	  UNION SELECT DISTINCT receipt_submission_id FROM guest
	  WHERE reservation_id = $2 AND receipt_submission_id IS NOT NULL
	) AND apartment_id = $3 AND receipt_pdf IS NOT NULL AND TRIM(receipt_pdf) != ''
	ORDER BY created_at DESC`

// receiptRow is one submission a receipt zip reads.
type receiptRow struct {
	id          int64
	createdAt   string
	pseudoStamp *string
	receiptPDF  *string
}

// ownedSubmission is access.submission(request, id): whether the workspace
// owns the submission. A request_xml_enc token that will not decrypt is an
// error (a 500), as the Python read raises before the route goes on.
func ownedSubmission(ctx context.Context, d deps, id int64, h *session.Host) (bool, error) {
	var plainXML, token *string
	err := d.pool.QueryRow(ctx, ownedSubmissionSQL, id, ownerID(h)).Scan(&plainXML, &token)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if _, err := decryptField(d.getenv, token, plainXML); err != nil {
		return false, err
	}
	return true, nil
}

func owned(ctx context.Context, pool *pgxpool.Pool, query string, id int64, h *session.Host) (bool, int64, error) {
	var v int64
	err := pool.QueryRow(ctx, query, id, ownerID(h)).Scan(&v)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, 0, nil
	}
	return err == nil, v, err
}

// whileSupporting is the " while_supporting=1" suffix the PDF routes add
// when auth.impersonating is true.
func whileSupporting(h *session.Host, detail string) string {
	if h.Impersonating {
		return detail + " while_supporting=1"
	}
	return detail
}

// SubmissionPDFHandler is exports.submission_receipt (column receipt_pdf,
// which "receipt", file dorucenka-<id>.pdf) and exports.submission_errors
// (error_pdf, "errors", dorucenka-chyby-<id>.pdf).
func SubmissionPDFHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, which string) http.HandlerFunc {
	column, prefix := "receipt_pdf", "dorucenka-"
	if which == "errors" {
		column, prefix = "error_pdf", "dorucenka-chyby-"
	}
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		if !identityVisible(h, nil) {
			backErr(w, r, fmt.Sprintf("/submissions/%d", id), "flash.error.identity_hidden_export", nil)
			return
		}
		ctx := r.Context()
		isOwned, err := ownedSubmission(ctx, d, id, h)
		if err != nil {
			serverError(w, err)
			return
		}
		var value *string
		if isOwned {
			if err := pool.QueryRow(ctx, "SELECT "+column+" FROM submission WHERE id = $1", id).Scan(&value); err != nil && !errors.Is(err, pgx.ErrNoRows) {
				serverError(w, err)
				return
			}
			detail := whileSupporting(h, fmt.Sprintf("submission_id=%d which=%s", id, which))
			if err := audit(ctx, pool, h, at, "export_submission_pdf", detail); err != nil {
				serverError(w, err)
				return
			}
		}
		pdfResponse(w, value, fmt.Sprintf("%s%d.pdf", prefix, id))
	}
}

// SubmissionFileHandler serves GET /submissions/{id}/{file}: exports.submission_xml
// for "<which>.xml". Any other file name is not a Python route of this
// module and gets the same 404 as the Go "/" catch-all.
func SubmissionFileHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		file := r.PathValue("file")
		which, isXML := strings.CutSuffix(file, ".xml")
		if !isXML || which == "" {
			http.NotFound(w, r)
			return
		}
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		if which != "request" && which != "response" {
			plain(w, http.StatusNotFound, "Unknown document.")
			return
		}
		if !identityVisible(h, nil) {
			backErr(w, r, fmt.Sprintf("/submissions/%d", id), "flash.error.identity_hidden_export", nil)
			return
		}
		ctx := r.Context()
		isOwned, err := ownedSubmission(ctx, d, id, h)
		if err != nil {
			serverError(w, err)
			return
		}
		if !isOwned {
			plain(w, http.StatusNotFound, "Not found.")
			return
		}
		var reqPlain, reqEnc, resp *string
		err = pool.QueryRow(ctx, "SELECT request_xml, request_xml_enc, response_xml FROM submission WHERE id = $1", id).Scan(&reqPlain, &reqEnc, &resp)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			serverError(w, err)
			return
		}
		// The query helper decrypts request_xml_enc whenever it is selected
		// (db._hydrate), so a broken token fails the response envelope too.
		request, err := decryptField(getenv, reqEnc, reqPlain)
		if err != nil {
			serverError(w, err)
			return
		}
		if err := audit(ctx, pool, h, at, "export_submission_xml", fmt.Sprintf("submission_id=%d which=%s", id, which)); err != nil {
			serverError(w, err)
			return
		}
		body := resp
		if which == "request" {
			body = request
		}
		text := ""
		if body != nil {
			text = *body
		}
		writeText(w, http.StatusOK, "application/xml", text)
	}
}

// decryptField is db.decrypt_field: no token gives the plaintext column
// (nil included); a token that will not decrypt is an error.
func decryptField(getenv func(string) string, token, fallback *string) (*string, error) {
	if token == nil || *token == "" {
		return fallback, nil
	}
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		return nil, err
	}
	b, err := keys.Decrypt(*token, 0, time.Now())
	if err != nil {
		return nil, errors.New("stored guest document field could not be decrypted")
	}
	s := string(b)
	return &s, nil
}

// ReceiptsZipHandler is exports.submissions_receipts_zip.
func ReceiptsZipHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		if !identityVisible(h, nil) {
			backErr(w, r, "/submissions", "flash.error.identity_hidden_export", nil)
			return
		}
		query := `SELECT s.id, s.created_at, s.pseudo_stamp, s.receipt_pdf
			FROM submission s JOIN apartment a ON a.id = s.apartment_id
			WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND s.receipt_pdf IS NOT NULL AND TRIM(s.receipt_pdf) != ''`
		args := []any{ownerID(h)}
		if from := queryDate(r, "from"); from != "" {
			args = append(args, from)
			query += fmt.Sprintf(" AND ubyhost_sqlite_date(s.created_at) >= $%d", len(args))
		}
		if to := queryDate(r, "to"); to != "" {
			args = append(args, to)
			query += fmt.Sprintf(" AND ubyhost_sqlite_date(s.created_at) <= $%d", len(args))
		}
		query += " ORDER BY s.created_at DESC"
		ctx := r.Context()
		rows, err := pool.Query(ctx, query, args...)
		if err != nil {
			serverError(w, err)
			return
		}
		var list []receiptRow
		for rows.Next() {
			var row receiptRow
			if err := rows.Scan(&row.id, &row.createdAt, &row.pseudoStamp, &row.receiptPDF); err != nil {
				rows.Close()
				serverError(w, err)
				return
			}
			list = append(list, row)
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			serverError(w, err)
			return
		}
		if len(list) == 0 {
			backErr(w, r, "/submissions", "flash.error.no_receipts", nil)
			return
		}
		if len(list) > maxReceiptDownloads {
			backErr(w, r, "/submissions", "flash.error.too_many_receipts",
				map[string]any{"count": len(list), "limit": maxReceiptDownloads})
			return
		}
		body, written, err := buildZip(list, receiptZipName, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if written == 0 {
			backErr(w, r, "/submissions", "flash.error.no_receipts", nil)
			return
		}
		if err := audit(ctx, pool, h, at, "export_receipts_zip", fmt.Sprintf("rows=%d", len(list))); err != nil {
			serverError(w, err)
			return
		}
		attachment(w, "application/zip", "dorucenky-"+dayStamp(at)+".zip", body)
	}
}

// StayReceiptsHandler is exports.stay_receipts.
func StayReceiptsHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		if !identityVisible(h, nil) {
			backErr(w, r, fmt.Sprintf("/reservations/%d", id), "flash.error.identity_hidden_export", nil)
			return
		}
		ctx := r.Context()
		isOwned, apartmentID, err := owned(ctx, pool, ownedReservationSQL, id, h)
		if err != nil {
			serverError(w, err)
			return
		}
		var list []receiptRow
		if isOwned {
			rows, err := pool.Query(ctx, stayReceiptsSQL, id, id, apartmentID)
			if err != nil {
				serverError(w, err)
				return
			}
			for rows.Next() {
				var row receiptRow
				if err := rows.Scan(&row.id, &row.createdAt, &row.receiptPDF); err != nil {
					rows.Close()
					serverError(w, err)
					return
				}
				list = append(list, row)
			}
			rows.Close()
			if err := rows.Err(); err != nil {
				serverError(w, err)
				return
			}
		}
		if isOwned && len(list) > 0 {
			detail := whileSupporting(h, fmt.Sprintf("reservation_id=%d which=receipts count=%d", id, len(list)))
			if err := audit(ctx, pool, h, at, "export_submission_pdf", detail); err != nil {
				serverError(w, err)
				return
			}
		}
		if len(list) == 1 {
			pdfResponse(w, list[0].receiptPDF, fmt.Sprintf("dorucenka-%d.pdf", list[0].id))
			return
		}
		if len(list) > 0 {
			body, written, err := buildZip(list, stayReceiptName, at)
			if err != nil {
				serverError(w, err)
				return
			}
			if written > 0 {
				attachment(w, "application/zip", fmt.Sprintf("dorucenky-%d-%s.zip", id, dayStamp(at)), body)
				return
			}
		}
		pdfResponse(w, nil, fmt.Sprintf("dorucenka-%d.pdf", id))
	}
}

// buildZip is reporting.build_receipts_zip and exports._build_stay_receipts_zip:
// one deflated entry per row whose receipt decodes, in row order.
func buildZip(list []receiptRow, name func(receiptRow) string, at time.Time) ([]byte, int, error) {
	var buf bytes.Buffer
	archive := zip.NewWriter(&buf)
	count := 0
	for _, row := range list {
		if row.receiptPDF == nil || *row.receiptPDF == "" {
			continue
		}
		raw, ok := b64decode(*row.receiptPDF)
		if !ok {
			continue
		}
		f, err := archive.CreateHeader(&zip.FileHeader{Name: name(row), Method: zip.Deflate, Modified: at.Local()})
		if err != nil {
			return nil, 0, err
		}
		if _, err := f.Write(raw); err != nil {
			return nil, 0, err
		}
		count++
	}
	if err := archive.Close(); err != nil {
		return nil, 0, err
	}
	return buf.Bytes(), count, nil
}

// datePart is (row["created_at"] or "")[:10] or "report".
func datePart(createdAt string) string {
	if part := firstRunes(createdAt, 10); part != "" {
		return part
	}
	return "report"
}

func firstRunes(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		r = r[:n]
	}
	return string(r)
}

// receiptZipName is reporting.receipt_zip_name.
func receiptZipName(row receiptRow) string {
	stamp := fmt.Sprint(row.id)
	if row.pseudoStamp != nil && *row.pseudoStamp != "" {
		stamp = *row.pseudoStamp
	}
	return fmt.Sprintf("dorucenka-%s-%d-%s.pdf", datePart(row.createdAt), row.id, wordSafe(firstRunes(stamp, 36)))
}

// stayReceiptName is the entry name in exports._build_stay_receipts_zip.
func stayReceiptName(row receiptRow) string {
	return fmt.Sprintf("dorucenka-%d-%s.pdf", row.id, datePart(row.createdAt))
}

// wordSafe is re.sub(r"[^\w.\-]+", "_", s) with Python's Unicode \w.
func wordSafe(s string) string {
	var b strings.Builder
	inRun := false
	for _, r := range s {
		if r == '_' || r == '.' || r == '-' || unicode.IsLetter(r) || unicode.IsNumber(r) {
			b.WriteRune(r)
			inRun = false
			continue
		}
		if !inRun {
			b.WriteByte('_')
			inRun = true
		}
	}
	return b.String()
}
