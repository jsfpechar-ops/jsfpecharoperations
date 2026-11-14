package exports

// Brief 1607: POST /settings/workspace-export (exports.settings_workspace_export)
// and the zip it serves (workspace_export.build_workspace_zip). BuildWorkspaceZip
// is exported for brief 1510 (POST /admin/users/{id}/export, admin_accounts.py
// user_workspace_export), which serves the same zip to an administrator.

import (
	"archive/zip"
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// archivedHousebookSQL is housebook.housebook_archived_rows(owner_user_id=...).
const archivedHousebookSQL = `SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id,
	a.id AS apartment_id, a.internal_name, a.uby_idub
	FROM guest g
	JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE g.archived_at IS NOT NULL AND ($1::bigint IS NULL OR a.owner_user_id = $1)
	AND COALESCE(r.source, '') != 'demo'
	ORDER BY g.archived_at DESC, g.id DESC`

// The reads of workspace_export.build_workspace_zip. ORDER BY only makes the
// entry order repeatable (Python leaves it to the database).
const (
	workspaceGuestIDsSQL = `SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id
		JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id IS NOT DISTINCT FROM $1 ORDER BY g.id`
	workspaceReceiptsSQL = `SELECT s.id, s.receipt_pdf FROM submission s
		JOIN apartment a ON a.id = s.apartment_id
		WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND s.receipt_pdf IS NOT NULL ORDER BY s.id`
	workspaceStayFeesSQL = `SELECT f.apartment_id, f.period_key, f.version, f.pdf_enc, f.csv_enc FROM stay_fee_filing f
		JOIN apartment a ON a.id = f.apartment_id
		WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND f.superseded_at IS NULL ORDER BY f.id`
	workspaceInvoicesSQL = `SELECT id, pdf_blob FROM invoice WHERE owner_user_id IS NOT DISTINCT FROM $1 ORDER BY id`
)

// WorkspaceCounts is the "counts" object of the export's manifest.json.
type WorkspaceCounts struct {
	Guests         int // every guest row of the workspace (a form is written for each that renders)
	Receipts       int // Doručenka PDFs written
	Invoices       int // host invoice PDFs written
	StayFeeFilings int // current stay-fee filings with a PDF or a CSV
}

// BuildWorkspaceZip is workspace_export.build_workspace_zip(owner_user_id).
//
// It writes the zip of everything the workspace of ownerUserID holds to a new
// file in os.TempDir() and returns its path; the caller serves the file and
// removes it (os.Remove), also after an error of its own. Nothing in the
// database changes and nothing is deleted. now is db.utcnow() of the
// manifest and the "Generated" time of each registration form (server-local).
//
// Entries, in this order: housebook.csv (housebook_rows of the whole
// workspace), archived_housebook.csv (only when archived entries exist),
// guests/<id>.pdf (one registration form per guest row; a guest whose form
// fails is left out, as Python's try/continue does), receipts/<submission
// id>.pdf, stay_fees/<apartment>-<period>-v<version>.pdf and .csv,
// invoices/<id>.pdf and manifest.json. The error is non-nil for a database
// error, a guest field or a stay-fee file that no key decrypts, or a failed
// file write; the temporary file is then removed and path is "".
//
// The caller checks the gates itself (Python: a fresh login, identity data
// visible, and for the host route a scheduled deletion) and writes the
// workspace_exported audit row after a successful build.
func BuildWorkspaceZip(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, ownerUserID int64, now time.Time) (path string, err error) {
	d := deps{pool, getenv, func() time.Time { return now }}
	guests, err := housebookGuests(ctx, d, ownerUserID, 0, "", "")
	if err != nil {
		return "", err
	}
	housebook, err := housebookCSV(ctx, d, guests)
	if err != nil {
		return "", err
	}
	archived, _, err := queryRows(ctx, pool, archivedHousebookSQL, ownerUserID)
	if err != nil {
		return "", err
	}
	for _, g := range archived {
		if err := hydrate(getenv, g); err != nil {
			return "", err
		}
	}
	ids, err := int64s(ctx, pool, workspaceGuestIDsSQL, ownerUserID)
	if err != nil {
		return "", err
	}
	f, err := os.CreateTemp("", "workspace-*.zip")
	if err != nil {
		return "", err
	}
	defer func() {
		if cerr := f.Close(); err == nil {
			err = cerr
		}
		if err != nil {
			_ = os.Remove(f.Name())
			path = ""
		}
	}()
	if err := writeWorkspaceZip(ctx, d, f, ownerUserID, housebook, len(guests), archived, ids, now); err != nil {
		return "", err
	}
	return f.Name(), nil
}

// int64s reads one bigint column.
func int64s(ctx context.Context, pool *pgxpool.Pool, sql string, args ...any) ([]int64, error) {
	rows, err := pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []int64
	for rows.Next() {
		var n int64
		if err := rows.Scan(&n); err != nil {
			return nil, err
		}
		out = append(out, n)
	}
	return out, rows.Err()
}

// writeWorkspaceZip writes the entries of build_workspace_zip after the
// house-book reads.
func writeWorkspaceZip(ctx context.Context, d deps, out io.Writer, owner int64, housebook []byte, housebookRows int,
	archived []row, guestIDs []int64, now time.Time) error {
	counts := WorkspaceCounts{Guests: len(guestIDs)}
	stayFeeFiles := []string{}
	archive := zip.NewWriter(out)
	put := func(name string, body []byte) error {
		w, err := archive.CreateHeader(&zip.FileHeader{Name: name, Method: zip.Deflate, Modified: now.Local()})
		if err != nil {
			return err
		}
		_, err = w.Write(body)
		return err
	}
	if err := put("housebook.csv", housebook); err != nil {
		return err
	}
	if len(archived) > 0 {
		if err := put("archived_housebook.csv", archivedHousebookCSV(archived)); err != nil {
			return err
		}
	}
	for _, id := range guestIDs {
		form, err := registrationFormPDF(ctx, d, id, now)
		if err != nil {
			continue // except Exception: continue
		}
		if err := put(fmt.Sprintf("guests/%d.pdf", id), form); err != nil {
			return err
		}
	}
	rows, err := d.pool.Query(ctx, workspaceReceiptsSQL, owner)
	if err != nil {
		return err
	}
	type receipt struct {
		id  int64
		pdf string
	}
	var receipts []receipt
	for rows.Next() {
		var r receipt
		if err := rows.Scan(&r.id, &r.pdf); err != nil {
			rows.Close()
			return err
		}
		receipts = append(receipts, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, r := range receipts {
		// _safe_pdf: empty or undecodable base64 is no entry.
		pdf, ok := b64decode(r.pdf)
		if r.pdf == "" || !ok || len(pdf) == 0 {
			continue
		}
		if err := put(fmt.Sprintf("receipts/%d.pdf", r.id), pdf); err != nil {
			return err
		}
		counts.Receipts++
	}
	if err := writeStayFees(ctx, d, owner, now, put, &counts, &stayFeeFiles); err != nil {
		return err
	}
	rows, err = d.pool.Query(ctx, workspaceInvoicesSQL, owner)
	if err != nil {
		return err
	}
	type invoice struct {
		id   int64
		blob []byte
	}
	var invoices []invoice
	for rows.Next() {
		var inv invoice
		if err := rows.Scan(&inv.id, &inv.blob); err != nil {
			rows.Close()
			return err
		}
		invoices = append(invoices, inv)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, inv := range invoices {
		if len(inv.blob) == 0 {
			continue
		}
		if err := put(fmt.Sprintf("invoices/%d.pdf", inv.id), inv.blob); err != nil {
			return err
		}
		counts.Invoices++
	}
	if err := put("manifest.json", workspaceManifest(now, owner, counts, housebookRows, len(archived), stayFeeFiles)); err != nil {
		return err
	}
	return archive.Close()
}

// writeStayFees writes the current stay-fee filings (stay_fee_filing.pdf_bytes
// and csv_bytes: the stored files, decrypted; a token no key reads is an error).
func writeStayFees(ctx context.Context, d deps, owner int64, now time.Time, put func(string, []byte) error,
	counts *WorkspaceCounts, files *[]string) error {
	rows, err := d.pool.Query(ctx, workspaceStayFeesSQL, owner)
	if err != nil {
		return err
	}
	type filing struct {
		apartment int64
		period    string
		version   int64
		pdf, csv  []byte
	}
	var list []filing
	for rows.Next() {
		var f filing
		if err := rows.Scan(&f.apartment, &f.period, &f.version, &f.pdf, &f.csv); err != nil {
			rows.Close()
			return err
		}
		list = append(list, f)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	if len(list) == 0 {
		return nil
	}
	keys, err := secure.LoadDataKeys(d.getenv)
	if err != nil {
		return err
	}
	decrypt := func(token []byte) ([]byte, error) {
		if len(token) == 0 {
			return nil, nil
		}
		plain, err := keys.Decrypt(string(token), 0, now)
		if err != nil {
			return nil, errors.New("stored attachment could not be decrypted")
		}
		return plain, nil
	}
	for _, f := range list {
		pdf, err := decrypt(f.pdf)
		if err != nil {
			return err
		}
		csv, err := decrypt(f.csv)
		if err != nil {
			return err
		}
		base := fmt.Sprintf("stay_fees/%d-%s-v%d", f.apartment, f.period, f.version)
		if len(pdf) > 0 {
			if err := put(base+".pdf", pdf); err != nil {
				return err
			}
			*files = append(*files, base+".pdf")
		}
		if len(csv) > 0 {
			if err := put(base+".csv", csv); err != nil {
				return err
			}
			*files = append(*files, base+".csv")
		}
		if len(pdf) > 0 || len(csv) > 0 {
			counts.StayFeeFilings++
		}
	}
	return nil
}

// archivedHousebookCSV is iter_housebook_csv_rows(housebook_archived_rows(...)):
// an archived row only has the apartment, the stay dates and the names, so
// every other column is empty.
func archivedHousebookCSV(archived []row) []byte {
	var out bytes.Buffer
	out.WriteString(bom)
	writeCSVRow(&out, housebookHeader)
	for _, g := range archived {
		fields := make([]string, len(housebookHeader))
		fields[0] = g.str("internal_name")
		fields[2] = orStr(g.str("stay_from"), g.str("res_from"))
		fields[3] = orStr(g.str("stay_to"), g.str("res_to"))
		fields[4] = g.str("surname")
		fields[5] = g.str("first_name")
		for i := range fields {
			fields[i] = csvSafe(fields[i])
		}
		writeCSVRow(&out, fields)
	}
	return out.Bytes()
}

// workspaceManifest is the manifest.json of build_workspace_zip:
// json.dumps({...}, indent=2) with the keys in Python's order.
func workspaceManifest(now time.Time, owner int64, c WorkspaceCounts, housebookRows, archivedRows int, files []string) []byte {
	var b bytes.Buffer
	b.WriteString("{\n")
	b.WriteString("  \"generated_at\": ")
	pyString(&b, utcStamp(now))
	b.WriteString(",\n")
	fmt.Fprintf(&b, "  \"owner_user_id\": %d,\n", owner)
	fmt.Fprintf(&b, "  \"counts\": {\n    \"guests\": %d,\n    \"receipts\": %d,\n    \"invoices\": %d,\n    \"stay_fee_filings\": %d\n  },\n",
		c.Guests, c.Receipts, c.Invoices, c.StayFeeFilings)
	fmt.Fprintf(&b, "  \"housebook_rows\": %d,\n", housebookRows)
	fmt.Fprintf(&b, "  \"archived_rows\": %d,\n", archivedRows)
	if len(files) == 0 {
		b.WriteString("  \"stay_fee_files\": []\n")
	} else {
		b.WriteString("  \"stay_fee_files\": [\n")
		for i, f := range files {
			sep := ","
			if i == len(files)-1 {
				sep = ""
			}
			b.WriteString("    ")
			pyString(&b, f)
			b.WriteString(sep + "\n")
		}
		b.WriteString("  ]\n")
	}
	b.WriteString("}")
	return b.Bytes()
}

// beginPost is the start of a host POST route under /settings: the method,
// Cache-Control, hostweb.CSRF (security.protect_host_post runs before the
// route) and auth.require_login. /settings is in _READ_ONLY_OPEN_PREFIXES, so
// a paused workspace may still post here: hostweb.Login sees the method as
// GET (finding F1, as billing does for /predplatne).
func (d deps) beginPost(w http.ResponseWriter, r *http.Request) (*session.Host, time.Time, bool) {
	at := d.now()
	w.Header().Set("Cache-Control", "no-store, private")
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		writeText(w, http.StatusMethodNotAllowed, "application/json", `{"detail":"Method Not Allowed"}`)
		return nil, at, false
	}
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return nil, at, false
	}
	lr := r.Clone(r.Context())
	lr.Method = http.MethodGet
	h, err := hostweb.Login(w, lr, d.pool, d.getenv, at)
	if err != nil {
		serverError(w, err)
		return nil, at, false
	}
	if h == nil {
		return nil, at, false
	}
	return h, at, true
}

// WorkspaceExportHandler is exports.settings_workspace_export.
func WorkspaceExportHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		h, at, ok := d.beginPost(w, r)
		if !ok {
			return
		}
		if !sessionIsFresh(h, at) {
			backErr(w, r, "/settings/security#settings-security", "auth.error.recent_login", nil)
			return
		}
		if !identityVisible(h, nil) {
			backErr(w, r, "/settings", "flash.error.identity_hidden_export", nil)
			return
		}
		if _, ok := requireOwner(w, h); !ok {
			return
		}
		ctx := r.Context()
		owner := h.Workspace.ID
		var username string
		var due *string
		err := pool.QueryRow(ctx, `SELECT username, deletion_due_at FROM user_account WHERE id = $1`, owner).Scan(&username, &due)
		if errors.Is(err, pgx.ErrNoRows) || (err == nil && (due == nil || *due == "")) {
			backErr(w, r, "/settings", "flash.error.workspace_export_not_scheduled", nil)
			return
		}
		if err != nil {
			serverError(w, err)
			return
		}
		path, err := BuildWorkspaceZip(ctx, pool, getenv, owner, at)
		if err != nil {
			serverError(w, err)
			return
		}
		defer os.Remove(path)
		// db.audit("workspace_exported", ..., actor=<workspace username>,
		// owner_user_id=owner): the signed-in user fills the two user ids.
		var impersonator any
		if h.Impersonating {
			impersonator = h.Account.ID
		}
		if _, err := pool.Exec(ctx, auditSQL, utcStamp(at), username, "workspace_exported",
			fmt.Sprintf("user=%d", owner), owner, h.Account.ID, impersonator); err != nil {
			serverError(w, err)
			return
		}
		f, err := os.Open(path)
		if err != nil {
			serverError(w, err)
			return
		}
		defer f.Close()
		info, err := f.Stat()
		if err != nil {
			serverError(w, err)
			return
		}
		w.Header().Set("Content-Type", "application/zip")
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="workspace-%d.zip"`, owner))
		w.Header().Set("Content-Length", strconv.FormatInt(info.Size(), 10))
		w.WriteHeader(http.StatusOK)
		_, _ = io.Copy(w, f)
	}
}
