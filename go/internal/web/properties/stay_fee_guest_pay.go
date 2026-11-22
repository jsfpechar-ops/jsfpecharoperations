package properties

// Guest-pay fields on property create and update (brief 2030), ported from
// App/app/routes/stay_fees.py guest_pay_values, apply_fee_account (link half),
// check_guest_pay_setup and apply_guest_operator_account.

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"slices"
	"sort"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

const guestNoteMax = 300

var guestRailsOrder = []string{"iban", "revolut", "cash"}

const (
	guestLinkRaw                = "_stay_fee_guest_link_raw"
	guestOperatorAccountRaw     = "_stay_fee_guest_operator_account_raw"
	guestLinkInvalid            = "stay_fee_guest_link_invalid"
	guestOperatorAccountInvalid = "stay_fee_guest_operator_account_invalid"
	guestRateRequired           = "stay_fee_guest_rate_required"
	guestRailsRequired          = "stay_fee_guest_rails_required"
	guestRevolutRequired        = "stay_fee_guest_revolut_required"
)

var (
	errGuestLinkInvalid            = errors.New(guestLinkInvalid)
	errGuestOperatorAccountInvalid = errors.New(guestOperatorAccountInvalid)
	errGuestRateRequired           = errors.New(guestRateRequired)
	errGuestRailsRequired          = errors.New(guestRailsRequired)
	errGuestRevolutRequired        = errors.New(guestRevolutRequired)
)

var guestSetupFlash = map[string]string{
	guestRateRequired:    "flash.stay_fees.rate_required",
	guestRailsRequired:   "flash.stay_fees.rails_required",
	guestRevolutRequired: "flash.stay_fees.revolut_required",
}

func stayFeeGuestPayOn(getenv func(string) string) bool {
	return strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STAY_FEE_GUEST_PAY"))) == "on"
}

func revolutLinkOK(raw string) bool {
	return booking.RevolutLinkOK(raw)
}

func guestPayValues(r *http.Request) map[string]any {
	posted := map[string]struct{}{}
	for _, v := range r.PostForm["stay_fee_guest_rails"] {
		if v == "qr" {
			v = "iban"
		}
		if slices.Contains(guestRailsOrder, v) {
			posted[v] = struct{}{}
		}
	}
	rails := make([]string, 0, len(posted))
	for v := range posted {
		rails = append(rails, v)
	}
	sort.Strings(rails)
	link := formStr(r, "stay_fee_guest_revolut_link")
	if link != "" && revolutLinkOK(link) && !slices.Contains(rails, "revolut") {
		rails = append(rails, "revolut")
		sort.Strings(rails)
	}
	note := pyStrip(firstRunes(formStr(r, "stay_fee_guest_cash_note"), guestNoteMax))
	defaultRail := formStr(r, "stay_fee_guest_default_rail")
	if defaultRail == "qr" {
		defaultRail = "iban"
	}
	if !slices.Contains(rails, defaultRail) {
		defaultRail = ""
		for _, rail := range guestRailsOrder {
			if slices.Contains(rails, rail) {
				defaultRail = rail
				break
			}
		}
	}
	collect := 0
	if formStr(r, "stay_fee_collect") == "1" {
		collect = 1
	}
	values := map[string]any{
		"stay_fee_guest_default_rail": defaultRail,
		"stay_fee_collect":            collect,
		"stay_fee_guest_rails":        strings.Join(rails, ","),
		"stay_fee_guest_revolut_link": orNil(link),
		"stay_fee_guest_cash_note":    orNil(note),
		guestLinkRaw:                  link,
	}
	if has(r, "stay_fee_guest_operator_account") {
		values[guestOperatorAccountRaw] = formStr(r, "stay_fee_guest_operator_account")
	}
	return values
}

func guestPayColumns(v map[string]any) []column {
	var cols []column
	for _, name := range []string{"stay_fee_guest_default_rail", "stay_fee_collect", "stay_fee_guest_rails",
		"stay_fee_guest_revolut_link", "stay_fee_guest_cash_note"} {
		if val, ok := v[name]; ok {
			cols = append(cols, column{name, val})
		}
	}
	return cols
}

func mergeGuestPayForm(cols []column, r *http.Request, getenv func(string) string) []column {
	if !stayFeeGuestPayOn(getenv) || !has(r, "stay_fee_guest_form") {
		return cols
	}
	out := cols
	for _, c := range guestPayColumns(guestPayValues(r)) {
		out = setColumn(out, c.name, c.value)
	}
	return out
}

func stripGuestPayInternals(v map[string]any) {
	delete(v, guestLinkRaw)
	delete(v, guestOperatorAccountRaw)
}

func applyGuestFeeLink(values map[string]any) error {
	raw, _ := values[guestLinkRaw].(string)
	delete(values, guestLinkRaw)
	if raw != "" && !revolutLinkOK(raw) {
		return errGuestLinkInvalid
	}
	return nil
}

func guestPayRailsNeedAccount(railsCSV string) bool {
	for _, part := range strings.Split(railsCSV, ",") {
		part = strings.TrimSpace(part)
		if part == "qr" || part == "iban" {
			return true
		}
	}
	return false
}

func operatorIDAfterSave(a *detailApt, cols []column) int64 {
	for _, c := range cols {
		if c.name != "legal_entity_id" {
			continue
		}
		switch v := c.value.(type) {
		case nil:
			return 0
		case int:
			return int64(v)
		case int64:
			return v
		case *int64:
			if v != nil {
				return *v
			}
			return 0
		}
	}
	return a.LegalEntityID
}

func entityPaymentAccount(bank, iban string) string {
	if iban != "" {
		return iban
	}
	return bank
}

func accountIBAN(account string) string {
	if pyStrip(account) == "" {
		return ""
	}
	_, iban, ok := normaliseAccount(account)
	if !ok {
		return ""
	}
	return iban
}

func postedAccountIsPreviousPrefill(ctx context.Context, pool interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}, a *detailApt, entityID int64, posted string) bool {
	sourceID := a.LegalEntityID
	if posted == "" || sourceID == 0 || sourceID == entityID {
		return false
	}
	postedIBAN := accountIBAN(posted)
	if postedIBAN == "" {
		return false
	}
	var bank, iban string
	err := pool.QueryRow(ctx, `SELECT COALESCE(bank_account, ''), COALESCE(iban, '') FROM legal_entity WHERE id = $1`, sourceID).
		Scan(&bank, &iban)
	if err != nil {
		return false
	}
	return postedIBAN == accountIBAN(entityPaymentAccount(bank, iban))
}

type guestPaySaveRefusal struct {
	linkError, operatorAccountError, rateError bool
	setupFlash                                 string
}

func guestPaySaveError(err error) *guestPaySaveRefusal {
	msg := err.Error()
	switch msg {
	case guestLinkInvalid:
		return &guestPaySaveRefusal{linkError: true}
	case guestOperatorAccountInvalid:
		return &guestPaySaveRefusal{operatorAccountError: true}
	case guestRateRequired:
		return &guestPaySaveRefusal{rateError: true}
	default:
		if key := guestSetupFlash[msg]; key != "" {
			return &guestPaySaveRefusal{setupFlash: key}
		}
	}
	return nil
}

func columnInt64(cols []column, name string, fallback int64) int64 {
	for _, c := range cols {
		if c.name != name {
			continue
		}
		switch v := c.value.(type) {
		case int:
			return int64(v)
		case int64:
			return v
		}
	}
	return fallback
}

func columnString(cols []column, name, fallback string) string {
	for _, c := range cols {
		if c.name != name {
			continue
		}
		if s, ok := c.value.(string); ok {
			return s
		}
	}
	return fallback
}

func collectGuest(values map[string]any) int {
	switch v := values["stay_fee_collect"].(type) {
	case int:
		return v
	case int64:
		return int(v)
	default:
		return 0
	}
}

func checkGuestPaySetup(ctx context.Context, s *server, a *detailApt, cols []column, values map[string]any, getenv func(string) string) error {
	if !stayFeeGuestPayOn(getenv) || collectGuest(values) == 0 {
		return nil
	}
	rate := columnInt64(cols, "stay_fee_rate_czk", a.StayFeeRateCZK)
	if rate <= 0 {
		return errGuestRateRequired
	}
	railsCSV, _ := values["stay_fee_guest_rails"].(string)
	rails := map[string]struct{}{}
	for _, part := range strings.Split(railsCSV, ",") {
		if part = strings.TrimSpace(part); part != "" {
			rails[part] = struct{}{}
		}
	}
	if len(rails) == 0 {
		return errGuestRailsRequired
	}
	link := columnString(cols, "stay_fee_guest_revolut_link", a.StayFeeGuestRevolutLink)
	if link == "" {
		if v := values["stay_fee_guest_revolut_link"]; v != nil {
			if s, ok := v.(string); ok {
				link = s
			}
		}
	}
	if _, ok := rails["revolut"]; ok && link == "" {
		return errGuestRevolutRequired
	}
	if _, ok := rails["iban"]; ok {
		if !operatorAccountOnFile(ctx, s, a, cols, values) {
			return errGuestOperatorAccountInvalid
		}
	}
	return nil
}

func operatorAccountOnFile(ctx context.Context, s *server, a *detailApt, cols []column, values map[string]any) bool {
	posted, _ := values[guestOperatorAccountRaw].(string)
	if posted = pyStrip(posted); posted != "" {
		entityID := operatorIDAfterSave(a, cols)
		if !postedAccountIsPreviousPrefill(ctx, s.pool, a, entityID, posted) {
			return true
		}
	}
	entityID := operatorIDAfterSave(a, cols)
	if entityID == 0 {
		return false
	}
	var bank, iban string
	err := s.pool.QueryRow(ctx, `SELECT COALESCE(bank_account, ''), COALESCE(iban, '') FROM legal_entity WHERE id = $1`, entityID).
		Scan(&bank, &iban)
	if err != nil {
		return false
	}
	return entityPaymentAccount(bank, iban) != ""
}

func (s *server) applyGuestOperatorAccount(ctx context.Context, r *http.Request, q *request, a *detailApt, cols []column, values map[string]any) error {
	if !stayFeeGuestPayOn(s.getenv) || collectGuest(values) == 0 {
		delete(values, guestOperatorAccountRaw)
		return nil
	}
	railsCSV, _ := values["stay_fee_guest_rails"].(string)
	if !guestPayRailsNeedAccount(railsCSV) {
		delete(values, guestOperatorAccountRaw)
		return nil
	}
	rawVal, hasRaw := values[guestOperatorAccountRaw]
	delete(values, guestOperatorAccountRaw)
	entityID := operatorIDAfterSave(a, cols)
	if entityID == 0 {
		return errGuestOperatorAccountInvalid
	}
	entityRow, err := s.loadEntity(r, entityID, q.host.Workspace.ID)
	if entityRow == nil || err != nil {
		return errGuestOperatorAccountInvalid
	}
	bank, iban := entityRow.BankAccount, entityRow.IBAN
	entity := entityPaymentAccount(bank, iban)
	if !hasRaw {
		if entity == "" {
			return errGuestOperatorAccountInvalid
		}
		return nil
	}
	raw, _ := rawVal.(string)
	if pyStrip(raw) == "" {
		if entity != "" {
			return nil
		}
		return errGuestOperatorAccountInvalid
	}
	if postedAccountIsPreviousPrefill(ctx, s.pool, a, entityID, raw) {
		if entity == "" {
			return errGuestOperatorAccountInvalid
		}
		return nil
	}
	detail := map[string]any{"bank_account": pyStrip(raw)}
	if !applyAccountPayload(detail) {
		return errGuestOperatorAccountInvalid
	}
	newBank, _ := detail["bank_account"].(string)
	newIBAN, _ := detail["iban"].(string)
	existingIBAN := accountIBAN(entity)
	if entity != "" && existingIBAN == newIBAN {
		return nil
	}
	_, err = s.pool.Exec(ctx, `UPDATE legal_entity SET bank_account = $1, iban = $2 WHERE id = $3 AND owner_user_id IS NOT DISTINCT FROM $4`,
		newBank, newIBAN, entityID, q.host.Workspace.ID)
	if err != nil {
		return err
	}
	oldTail := entity
	if t := accountIBAN(entity); t != "" {
		oldTail = t
	}
	if len(oldTail) > 4 {
		oldTail = oldTail[len(oldTail)-4:]
	} else if oldTail == "" {
		oldTail = "none"
	}
	newTail := newIBAN
	if newTail == "" {
		newTail = newBank
	}
	if len(newTail) > 4 {
		newTail = newTail[len(newTail)-4:]
	}
	return s.audit(ctx, q, "guest_operator_account_changed", fmt.Sprintf("entity=%d old=...%s new=...%s", entityID, oldTail, newTail))
}

func (s *server) validateGuestPaySave(ctx context.Context, r *http.Request, q *request, a *detailApt, cols []column) ([]column, *guestPaySaveRefusal, error) {
	if !stayFeeGuestPayOn(s.getenv) || !has(r, "stay_fee_guest_form") {
		return cols, nil, nil
	}
	values := guestPayValues(r)
	cols = mergeGuestPayForm(cols, r, s.getenv)
	if err := applyGuestFeeLink(values); err != nil {
		return cols, guestPaySaveError(err), nil
	}
	if err := checkGuestPaySetup(ctx, s, a, cols, values, s.getenv); err != nil {
		return cols, guestPaySaveError(err), nil
	}
	if err := s.applyGuestOperatorAccount(ctx, r, q, a, cols, values); err != nil {
		return cols, guestPaySaveError(err), err
	}
	stripGuestPayInternals(values)
	return cols, nil, nil
}

// prepareGuestPayCreate strips operator persistence and clears invalid Revolut
// links, as apartment_create does in Python.
func prepareGuestPayCreate(r *http.Request, getenv func(string) string, cols []column) []column {
	if !stayFeeGuestPayOn(getenv) || !has(r, "stay_fee_guest_form") {
		return cols
	}
	values := guestPayValues(r)
	delete(values, guestOperatorAccountRaw)
	if err := applyGuestFeeLink(values); err != nil {
		values["stay_fee_guest_revolut_link"] = nil
	}
	cols = mergeGuestPayForm(cols, r, getenv)
	return cols
}

func guestPayFeeSaveErrors(ref guestPaySaveRefusal) []detailSaveError {
	if ref.setupFlash != "" {
		return nil
	}
	var out []detailSaveError
	if !ref.linkError && !ref.operatorAccountError && !ref.rateError {
		return out
	}
	if ref.operatorAccountError {
		out = append(out, detailSaveError{"fee", "stay_fee_guest_operator_account"})
	}
	if ref.linkError {
		out = append(out, detailSaveError{"fee", "stay_fee_guest_revolut_link"})
	}
	if ref.rateError {
		out = append(out, detailSaveError{"fee", "stay_fee_collect"})
	}
	return out
}

func applyGuestPayDraft(draft *detailApt, r *http.Request, getenv func(string) string) {
	if !stayFeeGuestPayOn(getenv) || !has(r, "stay_fee_guest_form") {
		return
	}
	for _, c := range guestPayColumns(guestPayValues(r)) {
		switch c.name {
		case "stay_fee_guest_default_rail":
			draft.StayFeeGuestDefaultRail, _ = c.value.(string)
		case "stay_fee_collect":
			switch v := c.value.(type) {
			case int:
				draft.StayFeeCollect = int64(v)
			case int64:
				draft.StayFeeCollect = v
			}
		case "stay_fee_guest_rails":
			draft.StayFeeGuestRails, _ = c.value.(string)
		case "stay_fee_guest_revolut_link":
			if s, ok := c.value.(string); ok {
				draft.StayFeeGuestRevolutLink = s
			} else {
				draft.StayFeeGuestRevolutLink = ""
			}
		case "stay_fee_guest_cash_note":
			if s, ok := c.value.(string); ok {
				draft.StayFeeGuestCashNote = s
			} else {
				draft.StayFeeGuestCashNote = ""
			}
		}
	}
}

func (s *server) refuseGuestFeeSave(w http.ResponseWriter, r *http.Request, q *request, a *detailApt, ref guestPaySaveRefusal) {
	ctx := r.Context()
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	draft := *a
	view := &detailView{Base: "/apartments/" + strconv.FormatInt(a.ID, 10), CopyOpen: queryLast(r, "copy") == "choose",
		PropertyView: "settings", SettingsSection: "reporting", Status: http.StatusBadRequest,
		FeeLinkError: ref.linkError, FeeOperatorAccountError: ref.operatorAccountError, FeeRateError: ref.rateError,
		SaveErrors: guestPayFeeSaveErrors(ref)}
	for _, field := range apartmentTextFields {
		if has(r, field) {
			*detailDraftField(&draft, field) = formStr(r, field)
		}
	}
	legal, _ := apartmentFormInt(r, "legal_entity_id")
	controller, _ := apartmentFormInt(r, "data_controller_entity_id")
	if has(r, "legal_entity_id") {
		draft.LegalEntityID = int64Of(legal)
	}
	if has(r, "data_controller_entity_id") {
		draft.DataControllerEntityID = int64Of(controller)
	}
	pay, _ := newApartmentPayload(r)
	for _, c := range pay.cols {
		text, _ := c.value.(string)
		switch c.name {
		case "stay_fee_rate_czk":
			draft.StayFeeRateCZK = int64(c.value.(int))
		case "stay_fee_vs":
			draft.StayFeeVS = text
		case "stay_fee_cadence":
			draft.StayFeeCadence = text
		case "stay_fee_authority_name":
			draft.StayFeeAuthorityName = text
		case "stay_fee_authority_address":
			draft.StayFeeAuthorityAddress = text
		case "stay_fee_authority_contact":
			draft.StayFeeAuthorityContact = text
		case "stay_fee_authority_databox":
			draft.StayFeeAuthorityDatabox = text
		case "stay_fee_payee":
			draft.StayFeePayee = text
		case "stay_fee_instruction":
			draft.StayFeeInstruction = text
		}
	}
	applyGuestPayDraft(&draft, r, s.getenv)
	if has(r, "stay_fee_council_account") {
		draft.StayFeeCouncilAccount, draft.StayFeeCouncilIBAN = formStr(r, "stay_fee_council_account"), ""
	}
	r = r.Clone(ctx)
	query := r.URL.Query()
	switch {
	case ref.linkError:
		query.Set("err", detailT(q.lang, "flash.stay_fees.link_invalid"))
	case ref.setupFlash != "":
		query.Set("err", detailT(q.lang, ref.setupFlash))
	case ref.operatorAccountError:
		query.Set("err", detailT(q.lang, "flash.stay_fees.operator_account_required"))
	default:
		query.Set("err", detailT(q.lang, "flash.stay_fees.account_invalid"))
	}
	query.Del("return_to")
	r.URL.RawQuery = query.Encode()
	var err error
	if view.CopyPeers, err = p.detailPeers(ctx, q.host.Workspace.ID, a.ID); err != nil {
		fail(w, err)
		return
	}
	p.detailRender(w, r, q.host, &draft, view, onboarding.PoolSettings(s.pool), q.at)
}
