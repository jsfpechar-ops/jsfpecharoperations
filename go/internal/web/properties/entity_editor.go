package properties

// Brief 1523: the business editor of GET /entities?edit=N and the forms'
// "Fill from register" answer (admin.py entities ~858, _entities_page ~903,
// _entities_ares_rerender ~1108, _entity_form_values, _entity_linked_properties,
// invoices.invoice_bank_view) plus the partials _entity_business_fields.html and
// _entity_invoice_fields.html (templates/entity_editor.tmpl).

import (
	"context"
	_ "embed"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

func itoa64(n int64) string { return strconv.FormatInt(n, 10) }

//go:embed bank_codes.csv
var bankCodesCSV string

// bankBIC is payments._bank_bic_by_code: 4-digit code to upper-case BIC.
var bankBIC = func() map[string]string {
	m := map[string]string{}
	for _, line := range strings.Split(bankCodesCSV, "\n") {
		line = pyStrip(line)
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(strings.ToLower(line), "code;") {
			continue
		}
		row := strings.Split(line, ";")
		if len(row) < 3 {
			continue
		}
		code, bic := pyStrip(row[0]), strings.ToUpper(pyStrip(row[2]))
		if len(code) == 4 && allDigits(code) && bic != "" {
			m[code] = bic
		}
	}
	return m
}()

// accountParts is payments.czech_account_parts: the three editor fields, or an IBAN-only value.
type accountParts struct{ Prefix, Number, Bank, IBAN string }

func czechAccountParts(raw string) accountParts {
	text := strings.ToUpper(strings.Join(strings.Fields(raw), ""))
	if m := accountRE.FindStringSubmatch(text); m != nil {
		return accountParts{Prefix: m[1], Number: m[2], Bank: m[3]}
	}
	if ibanRE.MatchString(text) {
		return accountParts{IBAN: text}
	}
	return accountParts{}
}

// bicForAccount is payments.bic_for_account: the BIC of a domestic account or CZ IBAN, or "".
func bicForAccount(account string) string {
	parts := czechAccountParts(account)
	bank := pyStrip(parts.Bank)
	if bank == "" && strings.HasPrefix(parts.IBAN, "CZ") && len(parts.IBAN) >= 8 {
		bank = parts.IBAN[4:8]
	}
	if len(bank) != 4 || !allDigits(bank) {
		return ""
	}
	return bankBIC[bank]
}

var phoneCodeSizes = map[string]bool{}

func init() {
	for _, c := range strings.Fields("20 27 30 31 32 33 34 36 39 40 41 43 44 45 46 47 48 49 51 52 53 54 55 56 57 58 60 61 62 63 64 65 66 81 82 84 86 90 91 92 93 94 95 98") {
		phoneCodeSizes[c] = true
	}
}

// phoneFormParts is contact_phone.form_parts: the country code (with its +) and the number.
func phoneFormParts(value string) (code, number string) {
	raw := pyStrip(value)
	compact := phoneCompact.ReplaceAllString(raw, "")
	if strings.HasPrefix(compact, "00") {
		compact = "+" + compact[2:]
	}
	if strings.HasPrefix(compact, "+") && allDigits(compact[1:]) {
		digits := compact[1:]
		size := 3
		switch {
		case digits[:1] == "1" || digits[:1] == "7":
			size = 1
		case len(digits) >= 2 && phoneCodeSizes[digits[:2]]:
			size = 2
		}
		if len(digits) > size {
			return "+" + digits[:size], digits[size:]
		}
	}
	if raw == "" {
		return "", ""
	}
	if allDigits(compact) && len(compact) == 9 {
		return "+420", compact
	}
	return "", raw
}

// businessForm is one business_form_body: its id prefix, the values and the register messages.
type businessForm struct {
	Prefix                                           string
	ICO, DIC, Name, Seat, Email, PhoneCode, PhoneNum string
	AresError, AresNote                              string
}

func newBusinessForm(prefix string, v map[string]string, accountEmail, aresErr, aresNote string) *businessForm {
	f := &businessForm{Prefix: prefix, ICO: v["ico"], DIC: v["dic"], Name: v["name"], Seat: v["seat"], Email: v["contact_email"], AresError: aresErr, AresNote: aresNote}
	if f.Email == "" && prefix == "new_" {
		f.Email = accountEmail
	}
	code, num := phoneFormParts(v["contact_phone"])
	f.PhoneCode, f.PhoneNum = strings.ReplaceAll(code, "+", ""), num
	return f
}

// invoiceForm is the Invoice details state of the editor (invoices.invoice_bank_view
// and, for brief 1524's rerenders, the register lookup state).
type invoiceForm struct {
	BIC, VATStatus, Registry, Prefix string
	NextNumber                       string // "" when not set
	DueDays                          string
	BankParts                        accountParts
	BICFromBank                      bool
	AccountError                     string
	AresError, AresNote, AresSource  string
	AresVatFound                     bool
	RegisterAccounts                 []string
	VATUnreliable, VATNeedsDIC       bool
	ICO                              string // the saved IČO the lookup button sends
	Existing                         string // _invoice_account_existing
}

type linkedProperty struct {
	ID   int64
	Name string
}

// editorView is the open editor card.
type editorView struct {
	ID       int64
	Name     string
	Form     *businessForm
	Linked   []linkedProperty
	Invoice  *invoiceForm // nil for an archived business
	NextPath string
}

// entityFull is a legal_entity row as the editor reads it.
type entityFull struct {
	ID                                                  int64
	Name, Seat, ICO, DIC, Email, Phone, SignatureName   string
	BankAccount, IBAN, BIC, VATStatus, Registry, Prefix string
	NextNumber                                          *int64
	DueDays                                             int64
	Archived                                            bool
}

const entityFullSQL = `SELECT id, name, COALESCE(seat, ''), COALESCE(ico, ''), COALESCE(dic, ''), COALESCE(contact_email, ''),
  COALESCE(contact_phone, ''), COALESCE(signature_name, ''), COALESCE(bank_account, ''), COALESCE(iban, ''), COALESCE(bic, ''),
  vat_status, COALESCE(registry_entry, ''), COALESCE(invoice_prefix, ''), invoice_next_number, invoice_due_days, COALESCE(archived_at, '') <> ''
  FROM legal_entity WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`

const linkedSQL = `SELECT id, internal_name FROM apartment WHERE (legal_entity_id = $1 OR data_controller_entity_id = $1) AND archived_at IS NULL
  AND owner_user_id IS NOT DISTINCT FROM $2 ORDER BY internal_name`

func loadEntityFull(ctx context.Context, q interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}, id, owner int64) (*entityFull, error) {
	var e entityFull
	err := q.QueryRow(ctx, entityFullSQL, id, owner).Scan(&e.ID, &e.Name, &e.Seat, &e.ICO, &e.DIC, &e.Email, &e.Phone, &e.SignatureName,
		&e.BankAccount, &e.IBAN, &e.BIC, &e.VATStatus, &e.Registry, &e.Prefix, &e.NextNumber, &e.DueDays, &e.Archived)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return &e, err
}

// values is the entity as the form fields (the keys of _entity_form_values).
func (e *entityFull) values() map[string]string {
	return map[string]string{"name": e.Name, "seat": e.Seat, "ico": e.ICO, "dic": e.DIC, "contact_email": e.Email,
		"contact_phone": e.Phone, "signature_name": e.SignatureName}
}

// bankView is invoices.invoice_bank_view.
func (e *entityFull) bankView() (accountParts, bool) {
	account := e.BankAccount
	if account == "" {
		account = e.IBAN
	}
	derived := bicForAccount(account)
	return czechAccountParts(e.BankAccount), derived != "" && strings.ToUpper(pyStrip(e.BIC)) == derived
}

// storedInvoice is the Invoice details of a business as stored.
func (e *entityFull) storedInvoice() *invoiceForm {
	parts, fromBank := e.bankView()
	f := &invoiceForm{BIC: e.BIC, VATStatus: e.VATStatus, Registry: e.Registry, Prefix: e.Prefix, DueDays: itoa64(e.DueDays),
		BankParts: parts, BICFromBank: fromBank, ICO: e.ICO, Existing: e.BankAccount, AresSource: "ares.source_note"}
	if f.Existing == "" {
		f.Existing = e.IBAN
	}
	if e.NextNumber != nil && *e.NextNumber != 0 {
		f.NextNumber = itoa64(*e.NextNumber)
	}
	return f
}

// editorOf builds the editor card for entity e with the typed values (nil: stored ones).
func (s *Pages) editorOf(ctx context.Context, e *entityFull, form *businessForm, invoice *invoiceForm, next string, owner int64) (*editorView, error) {
	rows, err := s.pool.Query(ctx, linkedSQL, e.ID, owner)
	if err != nil {
		return nil, err
	}
	linked, err := pgx.CollectRows(rows, func(r pgx.CollectableRow) (linkedProperty, error) {
		var p linkedProperty
		return p, r.Scan(&p.ID, &p.Name)
	})
	if err != nil {
		return nil, err
	}
	v := &editorView{ID: e.ID, Name: e.Name, Form: form, Linked: linked, NextPath: next}
	if form == nil {
		v.Form = newBusinessForm("edit_", e.values(), "", "", "")
	}
	if !e.Archived {
		v.Invoice = invoice
		if v.Invoice == nil {
			v.Invoice = e.storedInvoice()
		}
	}
	return v, nil
}

// openEditor fills d.Editor for GET /entities?edit=N. An id that is not the
// host's own leaves the list without an editor, as Python does.
func (s *Pages) openEditor(ctx context.Context, d *entitiesData, owner int64, raw string) error {
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return nil // a number past int64 matches no row
	}
	e, err := loadEntityFull(ctx, s.pool, id, owner)
	if err != nil || e == nil {
		return err
	}
	d.Editor, err = s.editorOf(ctx, e, nil, nil, d.NextPath, owner)
	return err
}

// entityFormValues is _entity_form_values: the posted fields, else the stored
// ones, else "" (phone composed with its country code).
func entityFormValues(r *http.Request, base *entityFull) map[string]string {
	vals := map[string]string{}
	var stored map[string]string
	if base != nil {
		stored = base.values()
	}
	for _, f := range []string{"name", "seat", "ico", "dic", "contact_email", "contact_phone", "signature_name"} {
		if has(r, f) {
			vals[f] = formStr(r, f)
		} else {
			vals[f] = stored[f]
		}
	}
	if has(r, "contact_phone") && has(r, "contact_phone_country_code") {
		vals["contact_phone"] = withCountryCode(formStr(r, "contact_phone_country_code"), vals["contact_phone"])
	}
	return vals
}

func init() { fillFromRegister = fillFromRegisterAnswer }

// fillFromRegisterAnswer is _entities_ares_rerender: look the typed IČO up in
// ARES, fill the blank name, seat and DIČ, and render the page again (200)
// with the typed values.
func fillFromRegisterAnswer(s *server, w http.ResponseWriter, r *http.Request, q *request, edit *entityEdit) {
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	var base *entityFull
	if edit != nil {
		var err error
		if base, err = loadEntityFull(r.Context(), s.pool, edit.ID, q.host.Workspace.ID); err != nil || base == nil {
			fail(w, err)
			return
		}
	}
	values := entityFormValues(r, base)
	owner := q.host.Workspace.ID
	data, aresErr, err := registerLookup(r.Context(), s.pool, owner, q.lang, pyStrip(values["ico"]), q.at)
	if err != nil {
		fail(w, err)
		return
	}
	note := ""
	if data != nil {
		note = registerFilledNote(q.lang, mergeBlank(values, data, "name", "seat", "dic"))
	}
	next := safeLocalPath(formStr(r, "next"), "")
	var email string
	if err := s.pool.QueryRow(r.Context(), accountEmailSQL, q.host.Account.ID).Scan(&email); err != nil && !errors.Is(err, pgx.ErrNoRows) {
		fail(w, err)
		return
	}
	d := &entitiesData{NextPath: next, AccountEmail: email}
	if base != nil {
		merged := *base
		merged.Name, merged.Seat, merged.ICO, merged.DIC = values["name"], values["seat"], values["ico"], values["dic"]
		merged.Email, merged.Phone, merged.SignatureName = values["contact_email"], values["contact_phone"], values["signature_name"]
		form := newBusinessForm("edit_", values, "", aresErr, note)
		if d.Editor, err = p.editorOf(r.Context(), &merged, form, nil, next, owner); err != nil {
			fail(w, err)
			return
		}
	} else {
		d.NewForm = newBusinessForm("new_", values, email, aresErr, note)
	}
	if err := p.renderEntities(w, r, q.host, q.at, d); err != nil {
		fail(w, err)
	}
}

// renderEntities loads the lists and renders entities.html (the one renderer, _entities_page).
func (p *Pages) renderEntities(w http.ResponseWriter, r *http.Request, host *session.Host, now time.Time, d *entitiesData, status ...int) error {
	ctx, ws := r.Context(), host.Workspace.ID
	var err error
	if d.Entities, err = p.entityRows(ctx, liveEntitiesSQL, ws); err != nil {
		return err
	}
	if d.Archived, err = p.entityRows(ctx, archivedEntitiesSQL, ws); err != nil {
		return err
	}
	if d.Banner, err = p.onboardingBanner(ctx, ws, "/entities"); err != nil {
		return err
	}
	if d.NewForm == nil {
		d.NewForm = newBusinessForm("new_", map[string]string{}, d.AccountEmail, "", "")
	}
	title := catalog.T(hostweb.Lang(r), "entities.title", nil)
	if i := strings.LastIndex(title, " "); i >= 0 {
		d.TitleHead, d.TitleLast = title[:i], title[i+1:]
	} else {
		d.TitleLast = title
	}
	page := layout.Page{Title: title, Nav: "entities", BodyKind: "list", V2: true}
	if len(status) > 0 {
		page.Status = status[0]
	}
	return layout.Render(w, r, layout.Env{Pool: p.pool, Getenv: p.getenv, Now: now}, host, page, pages, "entities", d)
}
