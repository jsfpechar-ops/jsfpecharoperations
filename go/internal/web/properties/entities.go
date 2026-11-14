package properties

// Brief 1522: POST /entities (create_entity, admin.py ~1195) and
// POST /entities/{id} (update_entity, ~1230), with the helpers they use:
// _entity_post_payload, _entity_details_payload, _signature_payload,
// _drawn_signature, _resolve_controller_alerts, _reconcile_pay_way_alerts and
// invoices.py invoice_detail_payload / apply_account_payload.
// The "Fill from register" button (fill_from_register) is a hook, see
// fillFromRegister.

import (
	"encoding/base64"
	"errors"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeemail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// RegisterEntities adds the two entity save routes. It does not touch the pool.
func RegisterEntities(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &server{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /entities", wrap("/entities", s.createEntity))
	mux.Handle("POST /entities/{id}", wrap("/entities/{id}", s.updateEntity))
}

// fillFromRegister answers the "Fill from register" button of both forms
// (form field fill_from_register). Brief 1523 replaces it from an init() in its
// own file; until then the button answers 501 like the other branches that are
// not ported yet.
var fillFromRegister = func(s *server, w http.ResponseWriter, r *http.Request, q *request, edit *entityEdit) {
	notPorted(w, "the ARES lookup (Fill from register)")
}

// entityEdit is the stored row an update starts from (nil for a new entity).
type entityEdit struct {
	ID                                                int64
	Name, Seat, ICO, DIC, Email, Phone                string
	BankAccount, IBAN, BIC, Registry, Prefix, Archive string
	SignatureEnc, SignatureName                       string
}

const entityOwnedRowSQL = `SELECT id, name, COALESCE(seat, ''), COALESCE(ico, ''), COALESCE(dic, ''), COALESCE(contact_email, ''),
  COALESCE(contact_phone, ''), COALESCE(bank_account, ''), COALESCE(iban, ''), COALESCE(bic, ''), COALESCE(registry_entry, ''),
  COALESCE(invoice_prefix, ''), COALESCE(archived_at, ''), COALESCE(signature_png_enc, ''), COALESCE(signature_name, '')
  FROM legal_entity WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`

func (s *server) loadEntity(r *http.Request, id, owner int64) (*entityEdit, error) {
	var e entityEdit
	err := s.pool.QueryRow(r.Context(), entityOwnedRowSQL, id, owner).Scan(&e.ID, &e.Name, &e.Seat, &e.ICO, &e.DIC, &e.Email,
		&e.Phone, &e.BankAccount, &e.IBAN, &e.BIC, &e.Registry, &e.Prefix, &e.Archive, &e.SignatureEnc, &e.SignatureName)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return &e, err
}

// enterNew is enter for a path with no id: CSRF, then the login gate, then the form.
func (s *server) enterNew(w http.ResponseWriter, r *http.Request) (*request, bool) {
	at := s.now()
	if !hostweb.CSRF(w, r, s.getenv, at) {
		return nil, false
	}
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		fail(w, err)
		return nil, false
	}
	if h == nil {
		return nil, false
	}
	_ = r.ParseMultipartForm(32 << 20)
	return &request{host: h, lang: hostweb.Lang(r), at: at}, true
}

// has is `field in form`: the field was posted, even empty.
func has(r *http.Request, key string) bool { _, ok := r.PostForm[key]; return ok }

// truthy is Starlette's form.get(key) used as a condition: the last value is not empty.
func truthy(r *http.Request, key string) bool {
	v := r.PostForm[key]
	return len(v) > 0 && v[len(v)-1] != ""
}

var phoneCompact = regexp.MustCompile(`[\s().-]`)
var phonePrefix = regexp.MustCompile(`^\+[1-9][0-9]{0,2}$`)

// withCountryCode is contact_phone.with_country_code.
func withCountryCode(code, number string) string {
	raw := pyStrip(number)
	if raw == "" {
		return ""
	}
	compact := phoneCompact.ReplaceAllString(raw, "")
	if strings.HasPrefix(compact, "00") {
		compact = "+" + compact[2:]
	}
	if strings.HasPrefix(compact, "+") {
		return compact
	}
	prefix := pyStrip(code)
	if prefix != "" && !strings.HasPrefix(prefix, "+") {
		prefix = "+" + prefix
	}
	if phonePrefix.MatchString(prefix) && allDigits(compact) {
		return prefix + compact
	}
	return raw
}

func allDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

var (
	accountRE = regexp.MustCompile(`^(?:([0-9]{1,6})-)?([0-9]{2,10})/([0-9]{4})$`)
	ibanRE    = regexp.MustCompile(`^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$`)
	mod11W    = [10]int{6, 3, 7, 9, 10, 5, 8, 4, 2, 1}
)

func mod11OK(digits string) bool {
	padded := strings.Repeat("0", 10-len(digits)) + digits
	sum := 0
	for i, c := range padded {
		sum += int(c-'0') * mod11W[i]
	}
	return sum%11 == 0
}

func ibanChecksumOK(iban string) bool {
	moved := iban[4:] + iban[:4]
	mod := 0
	for _, c := range moved {
		if c >= 'A' && c <= 'Z' {
			mod = (mod*100 + int(c-'A') + 10) % 97
		} else {
			mod = (mod*10 + int(c-'0')) % 97
		}
	}
	return mod == 1
}

// normaliseAccount is payments.normalise_account: the display form and the IBAN,
// ok false where Python raises ValueError.
func normaliseAccount(raw string) (display, iban string, ok bool) {
	text := strings.ToUpper(strings.Join(strings.Fields(raw), ""))
	if ibanRE.MatchString(text) {
		if !ibanChecksumOK(text) {
			return "", "", false
		}
		return text, text, true
	}
	m := accountRE.FindStringSubmatch(text)
	if m == nil {
		return "", "", false
	}
	prefix, number, bank := m[1], m[2], m[3]
	if (prefix != "" && !mod11OK(prefix)) || !mod11OK(number) {
		return "", "", false
	}
	bban := bank + strings.Repeat("0", 6-len(prefix)) + prefix + strings.Repeat("0", 10-len(number)) + number
	mod := 0
	for _, c := range bban + "123500" {
		mod = (mod*10 + int(c-'0')) % 97
	}
	display = number + "/" + bank
	if prefix != "" {
		display = prefix + "-" + display
	}
	check := 98 - mod
	return display, "CZ" + strconv.Itoa(check/10) + strconv.Itoa(check%10) + bban, true
}

// column is one value to write: nil is SQL NULL.
type column struct {
	name  string
	value any
}

// setColumn is dict assignment: a later value for the same column replaces the earlier one.
func setColumn(cols []column, name string, value any) []column {
	for i := range cols {
		if cols[i].name == name {
			cols[i].value = value
			return cols
		}
	}
	return append(cols, column{name, value})
}

func orNil(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// invoiceDetailPayload is invoices.invoice_detail_payload: presence-checked
// invoice details (a sent field updates, a blank one clears, an absent one is
// kept). bank_account stays raw for applyAccountPayload. year is date.today().year.
func invoiceDetailPayload(r *http.Request, year int) map[string]any {
	d := map[string]any{}
	if has(r, "bank_account") {
		d["bank_account"] = formStr(r, "bank_account")
	}
	if has(r, "bic") {
		d["bic"] = orNil(strings.ToUpper(strings.ReplaceAll(formStr(r, "bic"), " ", "")))
	}
	if has(r, "vat_status") {
		vat := formStr(r, "vat_status")
		if vat != "non_payer" && vat != "identified" && vat != "payer" {
			vat = "non_payer"
		}
		d["vat_status"] = vat
	}
	if has(r, "registry_entry") {
		d["registry_entry"] = orNil(formStr(r, "registry_entry"))
	}
	if has(r, "invoice_prefix") {
		var b []rune
		for _, c := range strings.ToUpper(formStr(r, "invoice_prefix")) {
			if unicode.IsLetter(c) || unicode.IsNumber(c) {
				b = append(b, c)
			}
		}
		if len(b) > 6 {
			b = b[:6]
		}
		d["invoice_prefix"] = orNil(string(b))
	}
	if has(r, "invoice_next_number") {
		raw := formStr(r, "invoice_next_number")
		if n, err := strconv.ParseInt(raw, 10, 64); allDigits(raw) && err == nil && n > 0 {
			d["invoice_next_number"] = n
			d["invoice_next_number_year"] = int64(year)
		} else {
			d["invoice_next_number"] = nil
			d["invoice_next_number_year"] = nil
		}
	}
	if has(r, "invoice_due_days") {
		raw := formStr(r, "invoice_due_days")
		due := int64(14)
		if allDigits(raw) {
			n, err := strconv.ParseInt(raw, 10, 64)
			if err != nil {
				n = 365 // past int64 is past 365 too
			}
			due = n
		}
		d["invoice_due_days"] = max(0, min(due, 365))
	}
	return d
}

// applyAccountPayload is invoices.apply_account_payload with accept_parts=False:
// the account in d becomes bank_account and iban. False for an invalid account.
func applyAccountPayload(d map[string]any) bool {
	raw, ok := d["bank_account"]
	if !ok {
		return true
	}
	account, _ := raw.(string)
	if account == "" {
		d["bank_account"], d["iban"] = nil, nil
		return true
	}
	display, iban, good := normaliseAccount(account)
	if !good {
		delete(d, "bank_account")
		return false
	}
	d["bank_account"], d["iban"] = display, iban
	return true
}

const maxSignatureBytes = 300 * 1024

// drawnSignature is _drawn_signature: a data URL of a PNG or JPEG, or "" when it is not one.
func drawnSignature(value string) string {
	var magic []byte
	switch {
	case strings.HasPrefix(value, "data:image/png;base64,"):
		magic = []byte("\x89PNG")
	case strings.HasPrefix(value, "data:image/jpeg;base64,"):
		magic = []byte("\xff\xd8\xff")
	default:
		return ""
	}
	encoded := value[strings.Index(value, ",")+1:]
	if strings.ContainsAny(encoded, "\r\n") {
		return ""
	}
	content, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil || !strings.HasPrefix(string(content), string(magic)) || len(content) > maxSignatureBytes {
		return ""
	}
	return value
}

// signaturePayload is _signature_payload: the columns the signature fields
// change, or ok false when a field is invalid (the caller answers
// flash.entities.signature_invalid). keys encrypts the image at rest, as
// db.encrypt_field does.
func signaturePayload(r *http.Request, keys func() (*secure.MultiFernet, error)) (cols []column, ok bool, err error) {
	var upload io.ReadCloser
	if r.MultipartForm != nil {
		if files := r.MultipartForm.File["signature_file"]; len(files) > 0 && files[len(files)-1].Filename != "" {
			if upload, err = files[len(files)-1].Open(); err != nil {
				return nil, false, err
			}
			defer upload.Close()
		}
	}
	drawnRaw := formStr(r, "signature_drawn")
	drawn := drawnSignature(drawnRaw)
	if drawnRaw != "" && drawn == "" && !truthy(r, "signature_remove") {
		return nil, false, nil
	}
	enc := func(plain string) (any, error) {
		k, err := keys()
		if err != nil {
			return nil, err
		}
		return k.EncryptString(plain)
	}
	switch {
	case truthy(r, "signature_remove") && upload == nil:
		cols = setColumn(cols, "signature_png_enc", nil)
	case drawn != "":
		token, err := enc(drawn)
		if err != nil {
			return nil, false, err
		}
		cols = setColumn(cols, "signature_png_enc", token)
	}
	if upload != nil {
		content, err := io.ReadAll(io.LimitReader(upload, maxSignatureBytes+1))
		if err != nil {
			return nil, false, err
		}
		if len(content) > maxSignatureBytes {
			return nil, false, nil
		}
		var kind string
		switch {
		case strings.HasPrefix(string(content), "\x89PNG"):
			kind = "png"
		case strings.HasPrefix(string(content), "\xff\xd8\xff"):
			kind = "jpeg"
		default:
			return nil, false, nil
		}
		token, err := enc("data:image/" + kind + ";base64," + base64.StdEncoding.EncodeToString(content))
		if err != nil {
			return nil, false, err
		}
		cols = setColumn(cols, "signature_png_enc", token)
	}
	if has(r, "signature_name") {
		name := []rune(formStr(r, "signature_name"))
		if len(name) > 80 {
			name = name[:80]
		}
		cols = setColumn(cols, "signature_name", orNil(pyStrip(string(name))))
	}
	return cols, true, nil
}

// entityPayload reads the form into the columns to write, or answers the
// redirect itself and returns ok false. It is the shared middle of
// create_entity and update_entity.
func (s *server) entityPayload(w http.ResponseWriter, r *http.Request, q *request) ([]column, bool) {
	var cols []column
	for _, f := range []string{"name", "seat", "ico", "dic", "contact_email", "contact_phone"} {
		if has(r, f) {
			cols = append(cols, column{f, formStr(r, f)})
		}
	}
	if has(r, "contact_phone") && has(r, "contact_phone_country_code") {
		for i := range cols {
			if cols[i].name == "contact_phone" {
				cols[i].value = withCountryCode(formStr(r, "contact_phone_country_code"), formStr(r, "contact_phone"))
			}
		}
	}
	name := formStr(r, "name")
	if name == "" {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.name_required", nil))
		return nil, false
	}
	if ico := formStr(r, "ico"); ico != "" && !billing.ICOOK(ico) {
		q.back(w, r, "/entities", hostweb.Flash{}, hostweb.Flash{Text: catalog.T(q.lang, "entities.ico.invalid", nil)})
		return nil, false
	}
	detail := invoiceDetailPayload(r, q.at.Year())
	if !applyAccountPayload(detail) {
		q.back(w, r, "/entities", hostweb.Flash{}, hostweb.Flash{Text: catalog.T(q.lang, "entities.bank.invalid", nil)})
		return nil, false
	}
	for _, k := range []string{"bank_account", "iban", "bic", "vat_status", "registry_entry", "invoice_prefix", "invoice_next_number", "invoice_next_number_year", "invoice_due_days"} {
		if v, ok := detail[k]; ok {
			cols = append(cols, column{k, v})
		}
	}
	// The keys are read only when a signature is written, as db._fernet is.
	sig, ok, err := signaturePayload(r, func() (*secure.MultiFernet, error) { return secure.LoadDataKeys(s.getenv) })
	if err != nil {
		fail(w, err)
		return nil, false
	}
	if !ok {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.entities.signature_invalid", nil))
		return nil, false
	}
	return append(cols, sig...), true
}

const (
	entityApartmentsSQL = `SELECT id, COALESCE(NULLIF(data_controller_entity_id, 0), legal_entity_id)
		FROM apartment WHERE legal_entity_id = $1 OR data_controller_entity_id = $1 ORDER BY id`
	controllerSQL = `SELECT name <> '' AND COALESCE(contact_email, '') <> '' AND (COALESCE(ico, '') <> '' OR COALESCE(seat, '') <> '')
		FROM legal_entity WHERE id = $1`
	operatorApartmentsSQL = `SELECT id FROM apartment WHERE legal_entity_id = $1 ORDER BY id`
	anyApartmentSQL       = `SELECT 1 FROM apartment WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL LIMIT 1`
)

// resolveControllerAlerts is _resolve_controller_alerts: clear controller_missing
// for each property whose controller identity is now complete.
func (s *server) resolveControllerAlerts(r *http.Request, entityID int64) error {
	ctx := r.Context()
	rows, err := s.pool.Query(ctx, entityApartmentsSQL, entityID)
	if err != nil {
		return err
	}
	type pair struct{ apt, controller int64 }
	var list []pair
	for rows.Next() {
		var p pair
		var c *int64
		if err := rows.Scan(&p.apt, &c); err != nil {
			rows.Close()
			return err
		}
		if c != nil {
			p.controller = *c
		}
		list = append(list, p)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, p := range list {
		if p.controller == 0 {
			continue
		}
		var complete bool
		if err := s.pool.QueryRow(ctx, controllerSQL, p.controller).Scan(&complete); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				continue
			}
			return err
		}
		if complete {
			if err := ubyport.ResolveAlert(ctx, s.pool, "controller_missing:"+strconv.FormatInt(p.apt, 10)); err != nil {
				return err
			}
		}
	}
	return nil
}

// reconcilePayWayAlerts is _reconcile_pay_way_alerts for the properties this business operates.
func (s *server) reconcilePayWayAlerts(r *http.Request, entityID int64) error {
	rows, err := s.pool.Query(r.Context(), operatorApartmentsSQL, entityID)
	if err != nil {
		return err
	}
	ids, err := pgx.CollectRows(rows, pgx.RowTo[int64])
	if err != nil {
		return err
	}
	for _, id := range ids {
		if err := stayfeemail.ReconcileNoPayWay(r.Context(), s.pool, s.getenv, id); err != nil {
			return err
		}
	}
	return nil
}

func insertSQL(table string, cols []column) (string, []any) {
	names := make([]string, len(cols))
	marks := make([]string, len(cols))
	args := make([]any, len(cols))
	for i, c := range cols {
		names[i], marks[i], args[i] = c.name, "$"+strconv.Itoa(i+1), c.value
	}
	return "INSERT INTO " + table + " (" + strings.Join(names, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ") RETURNING id", args
}

func updateSQL(table string, cols []column, id int64) (string, []any) {
	sets := make([]string, len(cols))
	args := make([]any, len(cols)+1)
	for i, c := range cols {
		sets[i], args[i] = c.name+" = $"+strconv.Itoa(i+1), c.value
	}
	args[len(cols)] = id
	return "UPDATE " + table + " SET " + strings.Join(sets, ", ") + " WHERE id = $" + strconv.Itoa(len(cols)+1), args
}

// createEntity is POST /entities (admin.py create_entity).
func (s *server) createEntity(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enterNew(w, r)
	if !ok {
		return
	}
	if truthy(r, "fill_from_register") {
		fillFromRegister(s, w, r, q, nil)
		return
	}
	cols, ok := s.entityPayload(w, r, q)
	if !ok {
		return
	}
	owner := q.host.Workspace.ID
	cols = append(cols, column{"created_at", stamp(q.at)}, column{"owner_user_id", owner})
	sql, args := insertSQL("legal_entity", cols)
	var id int64
	if err := s.pool.QueryRow(r.Context(), sql, args...).Scan(&id); err != nil {
		fail(w, err)
		return
	}
	if err := s.resolveControllerAlerts(r, id); err != nil {
		fail(w, err)
		return
	}
	name := formStr(r, "name")
	added := q.flash("flash.entities.added", map[string]any{"name": name})
	if next := safeLocalPath(formStr(r, "next"), ""); next != "" {
		// 0884: "Fill from register" on the wizard's property step returns there.
		q.back(w, r, next, added, hostweb.Flash{})
		return
	}
	var one int
	err := s.pool.QueryRow(r.Context(), anyApartmentSQL, owner).Scan(&one)
	if errors.Is(err, pgx.ErrNoRows) {
		q.back(w, r, "/apartments/new?legal_entity_id="+strconv.FormatInt(id, 10),
			q.flash("flash.entities.added_first", map[string]any{"name": name}), hostweb.Flash{})
		return
	}
	if err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, "/entities", added, hostweb.Flash{})
}

// updateEntity is POST /entities/{id} (admin.py update_entity).
func (s *server) updateEntity(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	edit, err := s.loadEntity(r, q.id, q.host.Workspace.ID)
	if err != nil {
		fail(w, err)
		return
	}
	if edit == nil {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.no_such_entity", nil))
		return
	}
	if truthy(r, "fill_from_register") {
		fillFromRegister(s, w, r, q, edit)
		return
	}
	cols, ok := s.entityPayload(w, r, q)
	if !ok {
		return
	}
	sql, args := updateSQL("legal_entity", cols, q.id)
	if _, err := s.pool.Exec(r.Context(), sql, args...); err != nil {
		fail(w, err)
		return
	}
	if err := s.resolveControllerAlerts(r, q.id); err != nil {
		fail(w, err)
		return
	}
	if err := s.reconcilePayWayAlerts(r, q.id); err != nil {
		fail(w, err)
		return
	}
	// 0076: back to where the editor was opened from (property, invoice), if any.
	next := safeLocalPath(formStr(r, "next"), "")
	if next == "" {
		next = "/entities"
	}
	q.back(w, r, next, q.flash("flash.entities.saved", nil), hostweb.Flash{})
}
