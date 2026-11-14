package exports

// Brief 1606: GET /housebook/pdfs.zip (exports.housebook_pdfs_download with
// housebook.build_housebook_pdfs_zip): one signed registration form per
// house-book entry of the filter, at most 100.

import (
	"archive/zip"
	"bytes"
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// maxInspectionPDFs is housebook.MAX_INSPECTION_PDFS.
const maxInspectionPDFs = 100

// pdfEntryName is housebook._pdf_entry_name for a house-book row.
func pdfEntryName(g row) string {
	var parts []string
	for _, p := range []string{orStr(g.str("stay_from"), g.str("res_from")), g.str("surname"), g.str("first_name")} {
		if p != "" {
			parts = append(parts, p)
		}
	}
	stem := strings.Trim(strings.Join(parts, "-"), "-")
	if stem == "" {
		stem = fmt.Sprintf("guest-%d", g.int("id"))
	}
	return firstRunes(wordSafe(stem), 96) + ".pdf"
}

// housebookPDFsZip is build_housebook_pdfs_zip: one deflated registration
// form per row, in row order. It returns the zip and the number of entries.
func housebookPDFsZip(ctx context.Context, d deps, guests []row, at time.Time) ([]byte, int, error) {
	var buf bytes.Buffer
	archive := zip.NewWriter(&buf)
	count := 0
	for _, g := range guests {
		id := g.int("id")
		if id == 0 {
			continue
		}
		form, err := registrationFormPDF(ctx, d, id, at)
		if err != nil {
			return nil, 0, err
		}
		f, err := archive.CreateHeader(&zip.FileHeader{Name: pdfEntryName(g), Method: zip.Deflate, Modified: at.Local()})
		if err != nil {
			return nil, 0, err
		}
		if _, err := f.Write(form); err != nil {
			return nil, 0, err
		}
		count++
	}
	if err := archive.Close(); err != nil {
		return nil, 0, err
	}
	return buf.Bytes(), count, nil
}

// HousebookPDFsHandler is exports.housebook_pdfs_download.
func HousebookPDFsHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
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
		owner, ok := requireOwner(w, h)
		if !ok {
			return
		}
		ctx := r.Context()
		guests, err := housebookGuests(ctx, d, owner, queryInt(r, "apartment"), queryDate(r, "from"), queryDate(r, "to"))
		if err != nil {
			serverError(w, err)
			return
		}
		if len(guests) == 0 {
			backErr(w, r, "/housebook", "flash.error.no_housebook_matches", nil)
			return
		}
		if len(guests) > maxInspectionPDFs {
			backErr(w, r, "/housebook", "flash.error.too_many_entries",
				map[string]any{"count": len(guests), "limit": maxInspectionPDFs})
			return
		}
		body, written, err := housebookPDFsZip(ctx, d, guests, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if written == 0 {
			backErr(w, r, "/housebook", "flash.error.no_housebook_matches", nil)
			return
		}
		if err := audit(ctx, pool, h, at, "export_housebook_pdfs", fmt.Sprintf("rows=%d", len(guests))); err != nil {
			serverError(w, err)
			return
		}
		attachment(w, "application/zip", "domovni-kniha-pdf-"+dayStamp(at)+".zip", body)
	}
}
