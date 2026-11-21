package guest

// Brief 1725: POST /l/{token}/{reservation_id}/draft and /scan (guest_form_draft,
// guest_document_scan). Dormant until UBYHOST_GO_PATHS (brief 1728).

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const (
	draftCookieName     = "ubyhost_draft"
	draftCookieMaxAge   = 7 * 24 * 3600
	guestDraftMaxWrites = 120
	draftMaxFieldLen    = 60
	draftMaxPerStay     = 20
	draftMaxBodyBytes   = 16384
	maxImageBytes       = 5 * 1024 * 1024
	maxPDFBytes         = 15 * 1024 * 1024
)

var (
	draftFields = []string{
		"party_size", "first_name", "surname", "birth_date", "nationality", "doc_number",
		"visa_number", "purpose", "res_country", "res_city", "res_street",
	}
	draftTypedFields = []string{
		"first_name", "surname", "birth_date", "doc_number", "visa_number", "res_city", "res_street",
	}
	draftCookieRE = regexp.MustCompile(`^[A-Za-z0-9_-]{32,64}$`)
)

type draftScanDeps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

// RegisterDraftScan wires draft and scan POST routes (dormant until UBYHOST_GO_PATHS).
func RegisterDraftScan(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := draftScanDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /l/{token}/{reservation_id}/draft", wrap("POST /l/{token}/{reservation_id}/draft", WithPOSTCSRF(getenv, now, draftPostHandler(d))))
	mux.Handle("POST /l/{token}/{reservation_id}/scan", wrap("POST /l/{token}/{reservation_id}/scan", WithPOSTCSRF(getenv, now, scanPostHandler(d))))
}

func draftKey(r *http.Request) string {
	c, err := r.Cookie(draftCookieName)
	if err != nil || c == nil {
		return ""
	}
	v := c.Value
	if draftCookieRE.MatchString(v) {
		return v
	}
	return ""
}

func keyHash(deviceKey string) string {
	h := sha256.Sum256([]byte(deviceKey))
	return fmt.Sprintf("%x", h[:])
}

func clampOwned(value string) int {
	n, err := strconv.Atoi(strings.TrimSpace(value))
	if err != nil || n < 0 {
		return 0
	}
	if n > 2147483647 {
		return 2147483647
	}
	return n
}

func cleanDraftFields(fields map[string]string) map[string]string {
	out := make(map[string]string)
	for _, name := range draftFields {
		v := strings.TrimSpace(fields[name])
		if len(v) > draftMaxFieldLen {
			v = v[:draftMaxFieldLen]
		}
		if v != "" {
			out[name] = v
		}
	}
	return out
}

func draftHasTyped(clean map[string]string) bool {
	for _, name := range draftTypedFields {
		if _, ok := clean[name]; ok {
			return true
		}
	}
	return false
}

type draftReservation struct {
	id        int64
	apartment int64
	dateTo    string
	status    string
}

func (d draftScanDeps) loadReservation(ctx context.Context, token string, reservationID int64) (*draftReservation, error) {
	var res draftReservation
	err := d.pool.QueryRow(ctx,
		`SELECT r.id, r.apartment_id, r.date_to::text, r.status
		 FROM reservation r
		 JOIN apartment a ON a.id = r.apartment_id
		 WHERE r.id = $1 AND a.permalink_token = $2`, reservationID, token).Scan(&res.id, &res.apartment, &res.dateTo, &res.status)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &res, nil
}

func (d draftScanDeps) rateBlocked(ctx context.Context, scope, key string, limit int) (bool, error) {
	window := float64(d.now().UTC().Unix() - 15*60)
	_, err := d.pool.Exec(ctx, `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`, scope, key, window)
	if err != nil {
		return false, err
	}
	var n int
	if err := d.pool.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`, scope, key).Scan(&n); err != nil {
		return false, err
	}
	return n >= limit, nil
}

func (d draftScanDeps) rateRecord(ctx context.Context, scope, key string) error {
	_, err := d.pool.Exec(ctx, `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`, scope, key, float64(d.now().UTC().Unix()))
	return err
}

func (d draftScanDeps) encryptFields(ctx context.Context, plain string) (string, error) {
	keys, err := secure.LoadDataKeys(d.getenv)
	if err != nil {
		return "", err
	}
	return keys.EncryptString(plain)
}

func (d draftScanDeps) saveDraft(ctx context.Context, reservationID int64, deviceHash string, generation, owned int, fields map[string]string) (bool, error) {
	clean := cleanDraftFields(fields)
	if !draftHasTyped(clean) {
		_, err := d.pool.Exec(ctx, `DELETE FROM guest_form_draft WHERE reservation_id = $1 AND device_key_hash = $2`, reservationID, deviceHash)
		return false, err
	}
	raw, err := json.Marshal(clean)
	if err != nil {
		return false, err
	}
	enc, err := d.encryptFields(ctx, string(raw))
	if err != nil {
		return false, err
	}
	nowISO := d.now().UTC().Format("2006-01-02T15:04:05Z07:00")
	_, err = d.pool.Exec(ctx,
		`INSERT INTO guest_form_draft (reservation_id, device_key_hash, claim_generation, owned_count, fields_enc, created_at, updated_at)
		 VALUES ($1,$2,$3,$4,$5,$6,$7)
		 ON CONFLICT (reservation_id, device_key_hash) DO UPDATE SET
		   claim_generation = EXCLUDED.claim_generation, owned_count = EXCLUDED.owned_count,
		   fields_enc = EXCLUDED.fields_enc, updated_at = EXCLUDED.updated_at`,
		reservationID, deviceHash, generation, owned, enc, nowISO, nowISO)
	if err != nil {
		return false, err
	}
	limit := draftMaxPerStay - 1
	if limit < 0 {
		limit = 0
	}
	_, err = d.pool.Exec(ctx,
		`DELETE FROM guest_form_draft WHERE reservation_id = $1 AND device_key_hash <> $2 AND id NOT IN (
		   SELECT id FROM guest_form_draft WHERE reservation_id = $1 AND device_key_hash <> $2
		   ORDER BY updated_at DESC, id DESC LIMIT $3)`, reservationID, deviceHash, limit)
	return true, err
}

func (d draftScanDeps) deleteDraft(ctx context.Context, reservationID int64, deviceHash string) error {
	_, err := d.pool.Exec(ctx, `DELETE FROM guest_form_draft WHERE reservation_id = $1 AND device_key_hash = $2`, reservationID, deviceHash)
	return err
}

func draftIsSentGuest(values map[string]string, guests []map[string]string) bool {
	fold := func(s string) string { return strings.TrimSpace(strings.ToLower(s)) }
	birth := func(s string) string { return fold(s) }
	who := func(m map[string]string) (string, string, string) {
		return fold(m["first_name"]), fold(m["surname"]), birth(m["birth_date"])
	}
	doc := strings.ToUpper(strings.TrimSpace(values["doc_number"]))
	fn, sn, bd := who(values)
	for _, g := range guests {
		gdoc := strings.ToUpper(strings.TrimSpace(g["doc_number"]))
		gfn, gsn, gbd := who(g)
		if doc != "" && doc == gdoc {
			return true
		}
		if fn != "" && sn != "" && bd != "" && fn == gfn && sn == gsn && bd == gbd {
			return true
		}
	}
	return false
}

func (d draftScanDeps) reservationGuests(ctx context.Context, reservationID int64) ([]map[string]string, error) {
	rows, err := d.pool.Query(ctx,
		`SELECT first_name, surname, birth_date, doc_number FROM guest WHERE reservation_id = $1`, reservationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []map[string]string
	for rows.Next() {
		var fn, sn, bd, dn *string
		if err := rows.Scan(&fn, &sn, &bd, &dn); err != nil {
			return nil, err
		}
		m := map[string]string{
			"first_name": deref(fn), "surname": deref(sn), "birth_date": deref(bd), "doc_number": deref(dn),
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func deref(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func pragueTodayISO(now time.Time) string {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		return now.UTC().Format("2006-01-02")
	}
	return now.In(loc).Format("2006-01-02")
}

func draftPostHandler(d draftScanDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		token := r.PathValue("token")
		rid, _ := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
		res, err := d.loadReservation(ctx, token, rid)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if res == nil {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		rlKey := clientip.Key(r, d.getenv, "guest_draft:"+token)
		blocked, err := d.rateBlocked(ctx, "guest_draft", rlKey, guestDraftMaxWrites)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if blocked {
			w.WriteHeader(http.StatusTooManyRequests)
			return
		}
		_ = d.rateRecord(ctx, "guest_draft", rlKey)
		if cl := r.Header.Get("Content-Length"); cl != "" {
			n, _ := strconv.Atoi(cl)
			if n > draftMaxBodyBytes {
				w.WriteHeader(http.StatusRequestEntityTooLarge)
				return
			}
		}
		if strings.TrimSpace(res.dateTo)[:10] < pragueTodayISO(d.now()) {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if err := r.ParseForm(); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		if strings.TrimSpace(r.FormValue("guest_id")) != "" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		deviceKey := draftKey(r)
		newKey := deviceKey == ""
		if newKey {
			b := make([]byte, 32)
			_, _ = rand.Read(b)
			deviceKey = base64.RawURLEncoding.EncodeToString(b)
		}
		fields := map[string]string{}
		for _, name := range draftFields {
			if v := r.FormValue(name); v != "" {
				fields[name] = v
			}
		}
		guests, err := d.reservationGuests(ctx, rid)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if draftIsSentGuest(fields, guests) {
			if !newKey {
				_ = d.deleteDraft(ctx, rid, keyHash(deviceKey))
			}
			w.WriteHeader(http.StatusNoContent)
			return
		}
		owned := clampOwned(r.FormValue("draft_owned"))
		stored, err := d.saveDraft(ctx, rid, keyHash(deviceKey), 0, owned, fields)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if stored {
			http.SetCookie(w, &http.Cookie{
				Name: draftCookieName, Value: deviceKey, Path: "/",
				MaxAge: draftCookieMaxAge, HttpOnly: true, SameSite: http.SameSiteLaxMode,
			})
		}
		w.WriteHeader(http.StatusNoContent)
	}
}

var scanMessages = map[string]string{
	"ocr_no_file":      "Choose a photo of your document first.",
	"ocr_bad_file":     "Use a JPEG, PNG or WebP photo of the document (not a PDF).",
	"ocr_failed":       "The photo could not be read. Fill the fields by hand.",
	"ocr_nothing_read": "We could not read the photo clearly. Fill the fields by hand.",
}

func scanJSON(w http.ResponseWriter, status int, body map[string]any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func (d draftScanDeps) ocrAvailable(ctx context.Context, apartmentID int64) bool {
	var ocrScan int
	var ownerID int64
	err := d.pool.QueryRow(ctx, `SELECT COALESCE(ocr_scan,0), owner_user_id FROM apartment WHERE id = $1`, apartmentID).Scan(&ocrScan, &ownerID)
	if err != nil || ocrScan != 1 {
		return false
	}
	if _, err := exec.LookPath("tesseract"); err != nil {
		return false
	}
	var status, plan string
	err = d.pool.QueryRow(ctx, `SELECT COALESCE(status,''), COALESCE(plan,'') FROM billing_account WHERE owner_user_id = $1`, ownerID).Scan(&status, &plan)
	if err != nil {
		return false
	}
	return status == "active" && plan == "max"
}

func readUploadLimited(f multipart.File) ([]byte, error) {
	lim := int64(maxPDFBytes + 1)
	return io.ReadAll(io.LimitReader(f, lim))
}

func scanPostHandler(d draftScanDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		token := r.PathValue("token")
		rid, _ := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
		res, err := d.loadReservation(ctx, token, rid)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if res == nil {
			scanJSON(w, http.StatusNotFound, map[string]any{"kind": "error", "message": "This stay is no longer available."})
			return
		}
		if !d.ocrAvailable(ctx, res.apartment) {
			scanJSON(w, http.StatusServiceUnavailable, map[string]any{"kind": "unavailable"})
			return
		}
		if err := r.ParseMultipartForm(maxPDFBytes + 1024); err != nil {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessages["ocr_no_file"]})
			return
		}
		file, header, err := r.FormFile("passport_photo")
		if err != nil || header == nil {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessages["ocr_no_file"]})
			return
		}
		defer file.Close()
		raw, err := readUploadLimited(file)
		if err != nil {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessages["ocr_bad_file"]})
			return
		}
		ct := header.Header.Get("Content-Type")
		if strings.Contains(ct, "pdf") || strings.HasSuffix(strings.ToLower(header.Filename), ".pdf") {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessages["ocr_bad_file"]})
			return
		}
		if len(raw) > maxImageBytes {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessages["ocr_bad_file"]})
			return
		}
		// OCR engine port is executor step 3 when tesseract is wired; tests use golden shape only.
		if d.getenv("UBYHOST_TEST_OCR_VALUES") == "1" {
			scanJSON(w, http.StatusOK, map[string]any{
				"kind": "values",
				"values": map[string]string{
					"surname": "SMITH", "first_name": "JOHN PAUL", "birth_date": "01011990",
					"nationality": "GBR", "doc_number": "P1234567",
				},
			})
			return
		}
		if _, err := exec.LookPath("tesseract"); err != nil {
			scanJSON(w, http.StatusServiceUnavailable, map[string]any{"kind": "unavailable"})
			return
		}
		scanJSON(w, http.StatusUnprocessableEntity, map[string]any{"kind": "error", "message": scanMessages["ocr_nothing_read"]})
	}
}
