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
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/dococr"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
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
	return draftIsSentGuestAt(values, guests, time.Now())
}

func (d draftScanDeps) reservationGuests(ctx context.Context, reservationID int64) ([]map[string]string, error) {
	rows, err := d.pool.Query(ctx,
		`SELECT COALESCE(first_name,''), COALESCE(surname,''), COALESCE(birth_date_enc,''), COALESCE(birth_date,''), COALESCE(doc_number_enc,''), COALESCE(doc_number,'')
		 FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, reservationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []map[string]string
	for rows.Next() {
		var fn, sn, bdEnc, bdPlain, dnEnc, dnPlain string
		if err := rows.Scan(&fn, &sn, &bdEnc, &bdPlain, &dnEnc, &dnPlain); err != nil {
			return nil, err
		}
		bd := bdPlain
		if bdEnc != "" {
			if plain, derr := decryptGuestField(d.getenv, d.now, bdEnc, bdPlain); derr == nil {
				bd = plain
			}
		}
		dn := dnPlain
		if dnEnc != "" {
			if plain, derr := decryptGuestField(d.getenv, d.now, dnEnc, dnPlain); derr == nil {
				dn = plain
			}
		}
		out = append(out, map[string]string{
			"first_name": fn, "surname": sn, "birth_date": bd, "doc_number": dn,
		})
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

func (d draftScanDeps) save() saveDeps {
	return saveDeps{pool: d.pool, getenv: d.getenv, now: d.now}
}

func (d draftScanDeps) form() formPageDeps {
	return formPageDeps{pool: d.pool, getenv: d.getenv, now: d.now}
}

func (d draftScanDeps) draftClaimBlocked(ctx context.Context, r *http.Request, apt *Apartment, resID int64, status string) (blocked bool, hostOwned bool, err error) {
	hostOwned = d.form().access().hostOwns(ctx, r, apt.OwnerUserID)
	if !billingjob.MailEnabled() || hostOwned {
		return false, hostOwned, nil
	}
	row, err := EnsureClaimRow(ctx, d.pool, resID, isoNow(d.now()))
	if err != nil {
		return false, false, err
	}
	if !GuestAccessOpen(status, row.guestAccessLock) || !DeviceHoldsClaim(r, d.getenv, resID, row.tokenVersion) {
		return true, false, nil
	}
	return false, false, nil
}

func draftPostHandler(d draftScanDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		lang := langFromRequest(r)
		token := r.PathValue("token")
		rid, _ := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
		apt, token, early := OpenLink(r, d.pool, token, lang)
		if early != nil {
			early.ServeHTTP(w, r)
			return
		}
		if requirePin(w, r, d.save().shell(), token, lang, apt) {
			return
		}
		_, resMeta, status, ok, err := guestSaveReservation(ctx, d.save(), r, apt, rid, token)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if !ok {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		res := &draftReservation{id: rid, apartment: resMeta.apartmentID, dateTo: resMeta.dateTo, status: status}
		rlKey := clientip.Key(r, d.getenv, "guest_draft:"+apt.PermalinkToken)
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
		claimBlocked, hostOwned, err := d.draftClaimBlocked(ctx, r, apt, rid, status)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if claimBlocked {
			w.WriteHeader(http.StatusForbidden)
			return
		}
		if hostOwned {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if cl := r.Header.Get("Content-Length"); cl != "" {
			n, _ := strconv.Atoi(cl)
			if n > draftMaxBodyBytes {
				w.WriteHeader(http.StatusRequestEntityTooLarge)
				return
			}
		}
		dateTo := strings.TrimSpace(res.dateTo)
		if len(dateTo) >= 10 && dateTo[:10] < pragueTodayISO(d.now()) {
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
		if draftIsSentGuestAt(fields, guests, d.now()) {
			if !newKey {
				_ = d.deleteDraft(ctx, rid, keyHash(deviceKey))
			}
			w.WriteHeader(http.StatusNoContent)
			return
		}
		owned := clampOwned(r.FormValue("draft_owned"))
		gen := draftGeneration(ctx, d.pool, rid, d.now)
		stored, err := d.saveDraft(ctx, rid, keyHash(deviceKey), gen, owned, fields)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if stored {
			http.SetCookie(w, &http.Cookie{
				Name: draftCookieName, Value: deviceKey, Path: "/",
				MaxAge: draftCookieMaxAge, HttpOnly: true, SameSite: http.SameSiteLaxMode,
				Secure: hostweb.SecureCookies(d.getenv),
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
	return ocrAvailableForApartment(ctx, d.pool, d.getenv, apartmentID)
}

func scanMessage(lang, key string) string {
	if msg := stringsCatalog.T(lang, key, nil); msg != "" && msg != key {
		return msg
	}
	return scanMessages[key]
}

func readUploadLimited(f multipart.File) ([]byte, error) {
	lim := int64(maxPDFBytes + 1)
	return io.ReadAll(io.LimitReader(f, lim))
}

func scanPostHandler(d draftScanDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		lang := langFromRequest(r)
		token := r.PathValue("token")
		rid, _ := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
		apt, token, early := OpenLink(r, d.pool, token, lang)
		if early != nil {
			early.ServeHTTP(w, r)
			return
		}
		if requirePin(w, r, d.save().shell(), token, lang, apt) {
			return
		}
		cfg, resMeta, status, ok, err := guestSaveReservation(ctx, d.save(), r, apt, rid, token)
		if err != nil {
			http.Error(w, "", http.StatusInternalServerError)
			return
		}
		if !ok {
			scanJSON(w, http.StatusNotFound, map[string]any{"kind": "error", "message": "This stay is no longer available."})
			return
		}
		if throttleGuestPost(w, r, d.save(), token, "guest_scan", lang) {
			return
		}
		if d.form().formPagesRequireClaim(w, r, apt, formResRow{id: rid, apartmentID: resMeta.apartmentID, ownerUserID: cfg.ownerUserID, status: status, dateFrom: resMeta.dateFrom, dateTo: resMeta.dateTo, declaredGuests: resMeta.declaredGuests, overrideGuests: resMeta.overrideGuests, reducedGuests: resMeta.reducedGuests}, token, lang) {
			return
		}
		if !d.ocrAvailable(ctx, resMeta.apartmentID) {
			scanJSON(w, http.StatusServiceUnavailable, map[string]any{"kind": "unavailable"})
			return
		}
		if err := r.ParseMultipartForm(maxPDFBytes + 1024); err != nil {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessage(lang, "ocr_no_file")})
			return
		}
		file, header, err := r.FormFile("passport_photo")
		if err != nil || header == nil {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessage(lang, "ocr_no_file")})
			return
		}
		defer file.Close()
		raw, err := readUploadLimited(file)
		if err != nil {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessage(lang, "ocr_bad_file")})
			return
		}
		ct := header.Header.Get("Content-Type")
		if strings.Contains(strings.ToLower(ct), "pdf") || strings.HasSuffix(strings.ToLower(header.Filename), ".pdf") {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessage(lang, "ocr_bad_file")})
			return
		}
		if len(raw) > maxImageBytes {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessage(lang, "ocr_bad_file")})
			return
		}
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
		prepared, perr := dococr.PrepareImage(raw, ct)
		if perr != nil {
			scanJSON(w, http.StatusBadRequest, map[string]any{"kind": "error", "message": scanMessage(lang, "ocr_bad_file")})
			return
		}
		values, rerr := dococr.ReadDocument(ctx, prepared)
		if rerr != nil {
			switch {
			case errors.Is(rerr, dococr.ErrNothingRead):
				scanJSON(w, http.StatusUnprocessableEntity, map[string]any{"kind": "error", "message": scanMessage(lang, "ocr_nothing_read")})
			case errors.Is(rerr, dococr.ErrNoEngine):
				scanJSON(w, http.StatusServiceUnavailable, map[string]any{"kind": "unavailable"})
			default:
				scanJSON(w, http.StatusBadGateway, map[string]any{"kind": "error", "message": scanMessage(lang, "ocr_failed")})
			}
			return
		}
		scanJSON(w, http.StatusOK, map[string]any{"kind": "values", "values": values})
	}
}
