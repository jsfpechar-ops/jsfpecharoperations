package billingweb

// /admin/fakturace storno and the two zip exports (routes/admin_billing.py
// lines 104-143), brief 1559.

import (
	"archive/zip"
	"bytes"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// stornoRefusals are the ValueError messages billing_invoices.storno and issue raise.
var stornoRefusals = []error{billingjob.ErrNotAnInvoice, billingjob.ErrAlreadyVoided, billingjob.ErrPaid,
	billingjob.ErrWorkspaceDeleted, billingjob.ErrBuyerMissing, billingjob.ErrNoPlan, billingjob.ErrBelowMinimum}

// adminStorno serves POST /admin/fakturace/{invoice_id}/storno (billing_admin_storno, lines 104-120).
func (d deps) adminStorno(w http.ResponseWriter, r *http.Request) {
	if !d.csrf(w, r) {
		return
	}
	id, ok := invoiceIDParam(w, r)
	if !ok {
		return
	}
	c := d.login(w, r, gate{admin: true})
	if c == nil {
		return
	}
	reason := strings.TrimSpace(lastForm(r, "reason"))
	if rs := []rune(reason); len(rs) > 200 {
		reason = string(rs[:200])
	}
	if reason == "" {
		c.back(adminPage, hostweb.Flash{}, c.flash("billing.admin.storno.reason_missing", nil))
		return
	}
	// Not mailed: the invoice mail asks for payment. The host sees the storno on /predplatne.
	inv := &billingjob.Invoicer{Pool: d.pool}
	if _, err := inv.Storno(r.Context(), id, reason, c.today()); err != nil {
		for _, e := range stornoRefusals {
			if errors.Is(err, e) {
				c.back(adminPage, hostweb.Flash{}, c.flash("billing.admin.storno.refused_"+e.Error(), nil))
				return
			}
		}
		fail(w, err)
		return
	}
	c.back(adminPage, c.flash("billing.admin.storno.done", nil), hostweb.Flash{})
}

func writeZip(w http.ResponseWriter, blob []byte, name string) {
	w.Header().Set("Content-Type", "application/zip")
	w.Header().Set("Content-Disposition", `attachment; filename="`+name+`"`)
	w.Header().Set("Content-Length", strconv.Itoa(len(blob)))
	_, _ = w.Write(blob)
}

// adminExportAll serves GET /admin/fakturace/export-vse (billing_admin_export_all, lines 123-130).
func (d deps) adminExportAll(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{admin: true})
	if c == nil {
		return
	}
	blob, err := ExportAllZip(r.Context(), d.pool, c.today())
	if err != nil {
		fail(w, err)
		return
	}
	writeZip(w, blob, "ubyhost-billing-all.zip")
}

// ExportZip is billing_admin.export_zip (lines 103-110): faktury-YYYY-MM.csv and
// one PDF per document, exactly as stored. A document without its stored PDF is an error (a 500).
func ExportZip(r *http.Request, pool DB, month string) ([]byte, error) {
	csvData, err := ExportCSV(r.Context(), pool, month)
	if err != nil {
		return nil, err
	}
	rows, err := Invoices(r.Context(), pool, month)
	if err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	put := func(name string, data []byte) error {
		w, err := zw.Create(name)
		if err != nil {
			return err
		}
		_, err = w.Write(data)
		return err
	}
	if err := put("faktury-"+month+".csv", csvData); err != nil {
		return nil, err
	}
	for _, row := range rows {
		f, err := getInvoiceFile(r.Context(), pool, row.ID)
		if err != nil {
			return nil, err
		}
		if f == nil {
			return nil, errors.New("platform_invoice_pdf_missing")
		}
		blob, err := f.pdfBytes()
		if err != nil {
			return nil, err
		}
		if err := put("pdf/"+row.Number+".pdf", blob); err != nil {
			return nil, err
		}
	}
	if err := zw.Close(); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// adminExport serves GET /admin/fakturace/export (billing_admin_export, lines 133-143).
func (d deps) adminExport(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{admin: true})
	if c == nil {
		return
	}
	month := MonthOrCurrent(lastQuery(r, "mesic"), c.today())
	blob, err := ExportZip(r, d.pool, month)
	if err != nil {
		fail(w, err)
		return
	}
	writeZip(w, blob, "ubyhost-faktury-"+month+".zip")
}
