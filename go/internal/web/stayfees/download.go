package stayfees

// Brief 1583: the two sealed PDF downloads of App/app/routes/stay_fees.py,
// stay_fee_pdf_download (936-977) and stay_fee_pdfs_zip (733-773). Both serve
// the stored encrypted PDF (stay_fee_filing.pdf_bytes: decrypt pdf_enc, empty
// when the column is NULL). They mirror CSVHandler in handlers.go.

import (
	"archive/zip"
	"bytes"
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// pdfBytes is stay_fee_filing.pdf_bytes: nothing for a NULL or empty column,
// else the decrypted blob. A token that does not decrypt is Python's 500.
func (c *call) pdfBytes(filingID int64) ([]byte, error) {
	var enc []byte
	if err := c.pool.QueryRow(c.r.Context(), `SELECT pdf_enc FROM stay_fee_filing WHERE id = $1`, filingID).Scan(&enc); err != nil {
		return nil, err
	}
	if len(enc) == 0 {
		return nil, nil
	}
	keys, err := secure.LoadDataKeys(c.getenv)
	if err != nil {
		return nil, err
	}
	data, err := keys.Decrypt(string(enc), 0, c.at)
	if err != nil {
		return nil, errors.New("stored attachment could not be decrypted")
	}
	return data, nil
}

// lastQuery is request.query_params.get: the last value of a repeated key.
func lastQuery(r *http.Request, key string) string {
	if q := r.URL.Query()[key]; len(q) > 0 {
		return q[len(q)-1]
	}
	return ""
}

// PDFHandler serves GET /stay-fees/{apartment_id}/pdf (stay_fee_pdf_download).
func PDFHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		// The FastAPI route lists GET only: HEAD is a 405 before any dependency.
		if r.Method == http.MethodHead {
			methodNotAllowed(w, http.MethodGet)
			return
		}
		c := d.enter(w, r)
		if c == nil {
			return
		}
		apartmentID, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		aptText := apartmentID.text
		today := pragueDay(c.at)
		defMonth := defaultMonth(today)
		selected := defMonth
		if m, ok := parseMonth(lastQuery(r, "month")); ok {
			selected = m
			if selected.After(defMonth) {
				w.Header().Set("Location", "/stay-fees/"+aptText+"/pdf?month="+monthKey(defMonth))
				w.WriteHeader(http.StatusSeeOther)
				return
			}
		}
		ctx := r.Context()
		apt, err := c.pathApartment(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		var row *stayfee.FilingRow
		if apt != nil {
			if row, err = stayfee.Covering(ctx, pool, apt.ID, selected); err != nil {
				c.fail(err)
				return
			}
		}
		if apt == nil || (row == nil && !isActive(apt.Rate)) {
			c.noSuchApartment()
			return
		}
		if row == nil {
			c.back(monthPath(apt.ID, selected), hostweb.Flash{}, c.flash("flash.stay_fees.not_saved", nil))
			return
		}
		full, err := stayfee.LoadApartment(ctx, pool, apt.ID)
		if err != nil {
			c.fail(err)
			return
		}
		data, err := c.pdfBytes(row.ID)
		if err != nil {
			c.fail(err)
			return
		}
		detail := "apartment_id=" + strconv.FormatInt(apt.ID, 10) + " period=" + row.PeriodKey +
			" total=" + strconv.Itoa(row.TotalDueCZK)
		if err := c.audit("stay_fee_pdf", detail); err != nil {
			c.fail(err)
			return
		}
		w.Header().Set("Content-Type", "application/pdf")
		w.Header().Set("Content-Disposition", `attachment; filename="hlaseni-poplatek-z-pobytu-`+row.PeriodKey+"-"+stayfee.VSOf(full)+`.pdf"`)
		w.Header().Set("Cache-Control", "no-store")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(data)
	}
}

// PDFsZipHandler serves GET /stay-fees/pdfs.zip (stay_fee_pdfs_zip): every
// saved report of one month in one ZIP, the same bytes as each PDF button.
func PDFsZipHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodHead {
			methodNotAllowed(w, http.MethodGet)
			return
		}
		c := d.enter(w, r)
		if c == nil {
			return
		}
		defMonth := defaultMonth(pragueDay(c.at))
		month := defMonth
		if m, ok := parseMonth(lastQuery(r, "month")); ok {
			month = m
		}
		// A month after this one falls back to the default month (no redirect).
		if month.After(defMonth) {
			month = defMonth
		}
		ctx := r.Context()
		rs, err := pool.Query(ctx,
			`SELECT id FROM apartment WHERE owner_user_id = $1 AND archived_at IS NULL ORDER BY internal_name, id`, c.owner)
		if err != nil {
			c.fail(err)
			return
		}
		var ids []int64
		for rs.Next() {
			var id int64
			if err := rs.Scan(&id); err != nil {
				rs.Close()
				c.fail(err)
				return
			}
			ids = append(ids, id)
		}
		rs.Close()
		if err := rs.Err(); err != nil {
			c.fail(err)
			return
		}
		var buffer bytes.Buffer
		archive := zip.NewWriter(&buffer)
		names := map[string]bool{}
		count := 0
		for _, id := range ids {
			row, err := stayfee.Covering(ctx, pool, id, month)
			if err != nil {
				c.fail(err)
				return
			}
			if row == nil {
				continue
			}
			apt, err := stayfee.LoadApartment(ctx, pool, id)
			if err != nil {
				c.fail(err)
				return
			}
			name := "hlaseni-poplatek-z-pobytu-" + row.PeriodKey + "-" + stayfee.VSOf(apt) + "-" + strconv.FormatInt(id, 10) + ".pdf"
			if names[name] {
				continue
			}
			names[name] = true
			data, err := c.pdfBytes(row.ID)
			if err != nil {
				c.fail(err)
				return
			}
			entry, err := archive.CreateHeader(&zip.FileHeader{Name: name, Method: zip.Deflate, Modified: c.at})
			if err != nil {
				c.fail(err)
				return
			}
			if _, err := entry.Write(data); err != nil {
				c.fail(err)
				return
			}
			count++
		}
		if err := archive.Close(); err != nil {
			c.fail(err)
			return
		}
		if count == 0 {
			c.back("/stay-fees?month="+monthKey(month), hostweb.Flash{}, c.flash("flash.stay_fees.not_saved", nil))
			return
		}
		if err := c.audit("stay_fee_pdf_zip", "month="+monthKey(month)+" files="+strconv.Itoa(count)); err != nil {
			c.fail(err)
			return
		}
		w.Header().Set("Content-Type", "application/zip")
		w.Header().Set("Content-Disposition", `attachment; filename="poplatek-z-pobytu-`+monthKey(month)+`.zip"`)
		w.Header().Set("Cache-Control", "no-store")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(buffer.Bytes())
	}
}

// DownloadRoutes are the two PDF routes of brief 1583. The ZIP pattern is a
// literal segment, so it wins over a "GET /stay-fees/{apartment_id}" detail
// page registered next to it.
func DownloadRoutes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	return []Route{
		{"GET /stay-fees/pdfs.zip", PDFsZipHandler(pool, getenv, now)},
		{"GET /stay-fees/{apartment_id}/pdf", PDFHandler(pool, getenv, now)},
	}
}
