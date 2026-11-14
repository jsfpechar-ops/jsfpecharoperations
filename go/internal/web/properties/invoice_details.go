package properties

// Brief 1524: POST /entities/{id}/invoice (admin.py entity_invoice_details
// ~966 and _invoice_details_response ~950) with invoices.py save_invoice_details,
// lookup_invoice_details, _fill_register_account, _typed_bank_parts,
// _settings_entity_from_form, derive_missing_bic and apply_account_payload with
// accept_parts=True.

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// RegisterInvoiceDetails adds POST /entities/{id}/invoice.
func RegisterInvoiceDetails(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &server{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /entities/{id}/invoice", wrap("/entities/{id}/invoice", s.invoiceDetails))
}

var accountPartFields = []string{"account_prefix", "account_number", "account_bank"}

func anyPart(r *http.Request) bool {
	for _, k := range accountPartFields {
		if has(r, k) {
			return true
		}
	}
	return false
}

// typedBankParts is _typed_bank_parts: what was typed, else what is stored.
func typedBankParts(r *http.Request, e *entityFull) accountParts {
	if !anyPart(r) {
		return czechAccountParts(e.BankAccount)
	}
	p := accountParts{Prefix: formStr(r, "account_prefix"), Number: formStr(r, "account_number"), Bank: formStr(r, "account_bank")}
	if composeCzechAccount(p.Prefix, p.Number, p.Bank) == "" {
		existing := e.BankAccount
		if existing == "" {
			existing = e.IBAN
		}
		p.IBAN = czechAccountParts(existing).IBAN
	}
	return p
}

// formInvoice is _settings_entity_from_form as the editor's invoice state:
// the stored values with every field the form carried.
func formInvoice(r *http.Request, e *entityFull) *invoiceForm {
	f := e.storedInvoice()
	if has(r, "bic") {
		f.BIC = formStr(r, "bic")
	}
	if has(r, "vat_status") {
		f.VATStatus = formStr(r, "vat_status")
	}
	if has(r, "registry_entry") {
		f.Registry = formStr(r, "registry_entry")
	}
	if has(r, "invoice_prefix") {
		f.Prefix = formStr(r, "invoice_prefix")
	}
	if has(r, "invoice_next_number") {
		f.NextNumber = formStr(r, "invoice_next_number")
	}
	if has(r, "invoice_due_days") {
		f.DueDays = formStr(r, "invoice_due_days")
	}
	return f
}

// applyAccountParts is apply_account_payload(accept_parts=True): compose the
// three domestic fields first (an all-empty set never wipes a stored IBAN-only
// account), then validate.
func applyAccountParts(r *http.Request, d map[string]any, e *entityFull) bool {
	if anyPart(r) {
		prefix, number, bank := formStr(r, "account_prefix"), formStr(r, "account_number"), formStr(r, "account_bank")
		existing := e.BankAccount
		if existing == "" {
			existing = e.IBAN
		}
		keep := composeCzechAccount(prefix, number, bank) == "" && czechAccountParts(existing).IBAN != ""
		if !keep {
			d["bank_account"] = composeCzechAccount(prefix, number, bank)
		}
	}
	return applyAccountPayload(d)
}

// deriveMissingBIC is derive_missing_bic: an absent BIC with none stored comes from the bank code.
func deriveMissingBIC(r *http.Request, d map[string]any, e *entityFull) {
	if has(r, "bic") || pyStrip(e.BIC) != "" {
		return
	}
	account, iban := e.BankAccount, e.IBAN
	if v, ok := d["bank_account"]; ok {
		account, _ = v.(string)
	}
	if v, ok := d["iban"]; ok {
		iban, _ = v.(string)
	}
	if account == "" {
		account = iban
	}
	if bic := bicForAccount(account); bic != "" {
		d["bic"] = bic
	}
}

// lookupInvoiceDetails is lookup_invoice_details: the click-only register lookup; saves nothing.
func (s *server) lookupInvoiceDetails(r *http.Request, q *request, e *entityFull) (*invoiceForm, error) {
	st := formInvoice(r, e)
	st.BankParts = typedBankParts(r, e)
	st.BICFromBank = false
	ico := pyStrip(formStr(r, "ico"))
	if ico == "" {
		ico = pyStrip(e.ICO)
	}
	data, aresErr, err := registerLookup(r.Context(), s.pool, q.host.Workspace.ID, q.lang, ico, q.at)
	if err != nil {
		return nil, err
	}
	st.AresError = aresErr
	if data == nil {
		return st, nil
	}
	row := map[string]string{"registry_entry": st.Registry}
	filled := mergeBlank(row, data, "registry_entry")
	st.Registry = row["registry_entry"]
	current := formStr(r, "vat_status")
	if current == "" {
		current = e.VATStatus
	}
	if current == "" {
		current = "non_payer"
	}
	dic := data.DIC
	if dic == "" {
		dic = e.DIC
	}
	var vat *vatData
	if dicDigits(dic) != "" {
		vat = vatLookup(r.Context(), dic)
	}
	status := ""
	switch {
	case vat != nil:
		status = vat.Status
	case data.VATPayer:
		status = "payer"
	}
	st.AresVatFound = status == "payer"
	if status != "" && current == "non_payer" {
		st.VATStatus = status
		filled = append(filled, "vat_status")
	}
	if vat != nil {
		st.AresSource = "vat_register.source_note"
		st.VATUnreliable = vat.Unreliable
		filled = append(filled, fillRegisterAccount(r, st, vat.Accounts)...)
	} else if dicDigits(dic) == "" {
		p := st.BankParts
		st.VATNeedsDIC = composeCzechAccount(p.Prefix, p.Number, p.Bank) == ""
	}
	st.AresNote = registerFilledNote(q.lang, filled)
	return st, nil
}

// fillRegisterAccount is _fill_register_account: a published account goes into
// empty account fields, or is the one the host picked; a typed account is never
// replaced and the other published accounts become "Use ..." buttons.
func fillRegisterAccount(r *http.Request, st *invoiceForm, accounts []string) []string {
	var filled []string
	p := st.BankParts
	typed := composeCzechAccount(p.Prefix, p.Number, p.Bank)
	picked := formStr(r, "use_register_account")
	inList := func(a string) bool {
		for _, x := range accounts {
			if x == a {
				return true
			}
		}
		return false
	}
	choice := ""
	switch {
	case picked != "" && inList(picked):
		choice = picked
	case typed == "" && len(accounts) > 0:
		choice = accounts[0]
	}
	if choice != "" && choice != typed {
		np := czechAccountParts(choice)
		np.IBAN = ""
		st.BankParts = np
		typed = choice
		filled = append(filled, "bank_account")
		if pyStrip(st.BIC) == "" {
			if bic := bicForAccount(choice); bic != "" {
				st.BIC = bic
				st.BICFromBank = true
				filled = append(filled, "bic")
			}
		}
	}
	st.RegisterAccounts = nil
	for _, a := range accounts {
		if a != typed {
			st.RegisterAccounts = append(st.RegisterAccounts, a)
		}
	}
	return filled
}

// invoiceDetails is POST /entities/{id}/invoice.
func (s *server) invoiceDetails(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx, owner := r.Context(), q.host.Workspace.ID
	e, err := loadEntityFull(ctx, s.pool, q.id, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if e == nil || e.Archived {
		q.back(w, r, "/entities", hostweb.Flash{}, q.flash("flash.error.no_such_entity", nil))
		return
	}
	next := safeLocalPath(formStr(r, "next"), "")
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	render := func(st *invoiceForm, status int) {
		var email string
		_ = s.pool.QueryRow(ctx, accountEmailSQL, q.host.Account.ID).Scan(&email)
		d := &entitiesData{NextPath: next, AccountEmail: email}
		if d.Editor, err = p.editorOf(ctx, e, nil, st, next, owner); err != nil {
			fail(w, err)
			return
		}
		if err := p.renderEntities(w, r, q.host, q.at, d, status); err != nil {
			fail(w, err)
		}
	}
	if truthy(r, "fill_from_register") || truthy(r, "use_register_account") {
		st, err := s.lookupInvoiceDetails(r, q, e)
		if err != nil {
			fail(w, err)
			return
		}
		render(st, http.StatusOK)
		return
	}
	detail := invoiceDetailPayload(r, q.at.Year())
	if !applyAccountParts(r, detail, e) {
		st := formInvoice(r, e)
		st.BankParts, st.BICFromBank = typedBankParts(r, e), false
		st.AccountError = catalog.T(q.lang, "entities.bank.invalid", nil)
		render(st, http.StatusUnprocessableEntity)
		return
	}
	deriveMissingBIC(r, detail, e)
	var cols []column
	for _, k := range []string{"bank_account", "iban", "bic", "vat_status", "registry_entry", "invoice_prefix", "invoice_next_number", "invoice_next_number_year", "invoice_due_days"} {
		if v, ok := detail[k]; ok {
			cols = append(cols, column{k, v})
		}
	}
	if len(cols) > 0 {
		sql, args := updateSQL("legal_entity", cols, q.id)
		if _, err := s.pool.Exec(ctx, sql, args...); err != nil {
			fail(w, err)
			return
		}
	}
	if err := s.audit(ctx, q, "entity_invoice_details_saved", "id="+itoa64(q.id)); err != nil {
		fail(w, err)
		return
	}
	if next == "" {
		next = "/entities?edit=" + itoa64(q.id) + "#entity-invoice"
	}
	q.back(w, r, next, q.flash("flash.entities.saved", nil), hostweb.Flash{})
}
