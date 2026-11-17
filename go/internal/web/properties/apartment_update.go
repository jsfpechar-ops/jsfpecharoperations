package properties

// Brief 1702c1: POST /apartments/{id}, the property settings save without a
// wizard step: routes/admin.py apartment_update (2535-2601) and
// _save_apartment_form (2791-3046). It writes the police filing fields
// (rule 1). App/scripts/go_apartment_update_golden.py records what the Python
// route writes and answers; apartment_update_test.go replays it.
//
// Answered 501 with the Caddy fallback header (notPorted), always before
// anything is written:
//   - a wizard post: setup_step, or a return_to under /apartments/{id}/setup/
//     (brief 1702e);
//   - the fee signature section, fee_return_to and police-letter fields
//     (brief 1702d);
//   - the guest-pay block and the data box (as POST /apartments);
//   - a non-ASCII digit or a 64-bit overflow in a number, and a
//     stay_fee_rate_from that is set but not YYYY-MM-DD (Python's int(),
//     str.isdigit() and date.fromisoformat() read more than this port does);
//   - until brief 1702c2, every refusal Python answers by drawing the page
//     again (_refuse_apartment_save, refuse_fee_save, operator_refresh): see
//     refuseApartmentSave.
//
// Python writes the row, then the dated rate; here both share one transaction.
// The alert, the guest link, the audit rows and the pay-way alert follow in
// Python's order. Nothing routes here until the owner adds the path to
// UBYHOST_GO_PATHS (brief 1705).

import (
	"context"
	_ "embed"
	"fmt"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/palette"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeemail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/privacy"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees"
)

//go:embed apartmentupdate/i18n.json
var apartmentUpdateJSON []byte

// apartmentUpdateStrings is this route's catalog (apartmentupdate/i18n_keys.txt,
// written by App/scripts/go_host_i18n.py).
var apartmentUpdateStrings = hostweb.Load(apartmentUpdateJSON)

// isoDayRE is the one date.fromisoformat spelling this port reads.
var isoDayRE = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`)

// apartmentHourNames are the two shared hour columns (admin._property_hour_changes).
var apartmentHourNames = []string{"checkin_hour", "checkout_hour"}

const (
	apartmentUpdateRatesSQL = `SELECT effective_from::text, rate_czk FROM stay_fee_rate WHERE apartment_id = $1 ORDER BY effective_from`
	apartmentUpdateRateSQL  = `INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at) VALUES ($1, $2, $3, $4)
  ON CONFLICT (apartment_id, effective_from) DO UPDATE SET rate_czk = excluded.rate_czk`
)

// RegisterApartmentUpdate adds POST /apartments/{id}. It only builds the
// handler; the pool is first used inside a request.
func RegisterApartmentUpdate(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &server{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /apartments/{id}", wrap("/apartments/{id}", s.apartmentUpdate))
}

// apartmentRefusal is what _refuse_apartment_save and refuse_fee_save are
// called with; brief 1702c2 draws the page from it.
type apartmentRefusal struct {
	operatorError   string            // an i18n key from apartmentOperatorError, never from the form
	addressErrors   map[string]string // apartmentAddressErrors
	sharedTimeError string            // an i18n key set by this file, never from the form
	lockTimesError  bool
	feeAccountError bool // refuse_fee_save: the council account did not normalise
}

// refuseApartmentSave is the page Python draws again for a refused save.
// Brief 1702c1 leaves it to Python; nothing has been written.
func (s *server) refuseApartmentSave(w http.ResponseWriter, _ *http.Request, _ *request, _ *detailApt, _ apartmentRefusal) {
	notPorted(w, "a refused settings save that draws the page again (brief 1702c2)")
}

// apartmentUpdateNotPorted names the first posted branch this port leaves to
// Python, or "".
func apartmentUpdateNotPorted(r *http.Request, id int64) string {
	if formStr(r, "setup_step") != "" {
		return "a wizard step (brief 1702e)"
	}
	wizard := fmt.Sprintf("/apartments/%d/setup/", id)
	if strings.HasPrefix(formReturnTo(r, "", false), wizard) || strings.HasPrefix(formStr(r, "return_to"), wizard) {
		return "a return_to inside the setup wizard (brief 1702e)"
	}
	if formStr(r, "fee_signature_section") == "1" {
		return "the fee signature section (brief 1702d)"
	}
	if formStr(r, "fee_return_to") != "" {
		return "fee_return_to (brief 1702d)"
	}
	for _, part := range strings.Split(formStr(r, "letter_fields"), ",") {
		if pyStrip(part) != "" {
			return "police-letter fields (brief 1702d)"
		}
	}
	for _, key := range apartmentNotPortedFields {
		if has(r, key) {
			return "the form field " + key
		}
	}
	for _, key := range []string{"permalink_pin", "checkin_hour", "checkout_hour", "lock_checkin_hour", "lock_checkout_hour"} {
		if pyDigitUnsure(formStr(r, key)) {
			return "a non-ASCII digit in " + key
		}
	}
	if from := formStr(r, "stay_fee_rate_from"); from != "" && !isoDayRE.MatchString(from) {
		return "a stay_fee_rate_from that is not YYYY-MM-DD"
	}
	return ""
}

// apartmentLockTabHours is _with_lock_tab_hours: a Door lock tab time the host
// changed (lock_checkin_hour, lock_checkout_hour) replaces the Property tab's.
func apartmentLockTabHours(r *http.Request, a *detailApt) {
	for i, name := range apartmentHourNames {
		lockName := "lock_" + name
		if !has(r, lockName) {
			continue
		}
		value := formStr(r, lockName)
		saved := ""
		if stored := []*int64{a.CheckinHour, a.CheckoutHour}[i]; stored != nil {
			saved = strconv.FormatInt(*stored, 10)
		}
		if !has(r, name) || value != saved {
			r.PostForm[name] = []string{value}
		}
	}
}

// apartmentHour is int(raw) for an hour: ok is false when Python's int()
// fails or the value is outside 0..23 (flash.error.door_code_hours).
func apartmentHour(raw string) (int64, bool) {
	if !apartmentNewIntRE.MatchString(raw) {
		return 0, false
	}
	v, err := strconv.ParseInt(strings.ReplaceAll(raw, "_", ""), 10, 64)
	if err != nil || v < 0 || v > 23 {
		return 0, false
	}
	return v, true
}

// dropColumns is dict.pop for each name.
func dropColumns(cols []column, names ...string) []column {
	kept := cols[:0:0]
	for _, c := range cols {
		drop := false
		for _, n := range names {
			drop = drop || c.name == n
		}
		if !drop {
			kept = append(kept, c)
		}
	}
	return kept
}

func updateFlash(q *request, key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: apartmentUpdateStrings.T(q.lang, key, params), Key: key}
}

// apartmentUpdate is POST /apartments/{id} (admin.py apartment_update).
func (s *server) apartmentUpdate(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx, ws := r.Context(), q.host.Workspace.ID
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	// access.apartment: only a property of the signed-in workspace.
	a, err := p.detailLoad(ctx, ws, q.id)
	if err != nil {
		fail(w, err)
		return
	}
	if a == nil {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	if what := apartmentUpdateNotPorted(r, a.ID); what != "" {
		notPorted(w, what)
		return
	}
	apartmentLockTabHours(r, a)
	pay, ok := newApartmentPayload(r)
	if !ok {
		notPorted(w, "a non-ASCII digit or an integer past 64 bits in the form")
		return
	}
	// _property_hour_changes: only the hours this form posted; "" is NULL.
	hours := map[string]*int64{}
	for _, name := range apartmentHourNames {
		if !has(r, name) {
			continue
		}
		raw := formStr(r, name)
		if raw == "" {
			hours[name] = nil
			continue
		}
		v, ok := apartmentHour(raw)
		if !ok {
			s.refuseApartmentSave(w, r, q, a, apartmentRefusal{sharedTimeError: "flash.error.door_code_hours"})
			return
		}
		hours[name] = &v
	}
	editsLock := false
	if formStr(r, "door_code_section") == "1" {
		if editsLock, err = p.detailLockAllowed(ctx, a.OwnerUserID); err != nil {
			fail(w, err)
			return
		}
	}
	turnOff := editsLock && has(r, "door_codes_fields") && formStr(r, "door_codes") != "1"
	enable := editsLock && formStr(r, "door_codes") == "1"
	lockWillBeEnabled := enable || (a.LockProvider == "ttlock" && !turnOff)
	if lockWillBeEnabled && (len(hours) > 0 || enable) {
		for i, name := range apartmentHourNames {
			v, posted := hours[name]
			if !posted {
				v = []*int64{a.CheckinHour, a.CheckoutHour}[i]
			}
			if v == nil || *v < 0 || *v > 23 {
				ref := apartmentRefusal{sharedTimeError: "flash.error.door_code_hours"}
				if strings.Contains(formStr(r, "return_to"), "section=lock") {
					ref = apartmentRefusal{lockTimesError: true}
				}
				s.refuseApartmentSave(w, r, q, a, ref)
				return
			}
		}
	}
	if has(r, "operator_refresh") {
		s.refuseApartmentSave(w, r, q, a, apartmentRefusal{})
		return
	}
	operatorError, email, err := s.apartmentOperatorError(ctx, r, ws, pay)
	if err != nil {
		fail(w, err)
		return
	}
	if operatorError != "" {
		s.refuseApartmentSave(w, r, q, a, apartmentRefusal{operatorError: operatorError})
		return
	}
	cols := applyPoliceDefaults(pay, email)
	// 0088: an ordinary save never switches a property off; archived stays off.
	cols = setColumn(cols, "active", map[bool]int{true: 0, false: 1}[a.ArchivedAt != ""])
	if !has(r, "automation_mode") {
		cols = dropColumns(cols, "automation_mode", "submit_after_hours", "default_purpose")
	}
	for _, name := range apartmentHourNames {
		if v, posted := hours[name]; posted {
			cols = setColumn(cols, name, orNull(v))
		}
	}
	if !has(r, "data_controller_entity_id") {
		// A form without the controller selector must not clear an override.
		cols = dropColumns(cols, "data_controller_entity_id")
	} else if int64Of(pay.controller) == int64Of(pay.legal) {
		cols = setColumn(cols, "data_controller_entity_id", nil)
	}
	// A section form without address inputs must not blank the address; no
	// town posted keeps the guest-facing city (0204).
	addressPosted := false
	merged := map[string]string{"addr_okres": a.AddrOkres, "addr_obec": a.AddrObec, "addr_obec_cast": a.AddrObecCast,
		"addr_street": a.AddrStreet, "addr_house_no": a.AddrHouseNo, "addr_orient_no": a.AddrOrientNo, "addr_zip": a.AddrZip}
	for _, field := range apartmentAddressFields {
		if has(r, field) {
			addressPosted, merged[field] = true, pay.text[field]
		} else {
			cols = dropColumns(cols, field)
		}
	}
	if !has(r, "addr_obec") {
		cols = dropColumns(cols, "city_en")
	}
	if addressPosted {
		// The address stays complete once the property exists.
		if errs := apartmentAddressErrors(merged, q.lang); len(errs) > 0 {
			s.refuseApartmentSave(w, r, q, a, apartmentRefusal{addressErrors: errs})
			return
		}
	}
	if pay.password != "" {
		keys, err := secure.LoadDataKeys(s.getenv)
		if err != nil {
			fail(w, err)
			return
		}
		enc, err := keys.EncryptString(pay.password)
		if err != nil {
			fail(w, err)
			return
		}
		cols = setColumn(cols, "uby_ws_password_enc", enc)
	}
	if pin := formStr(r, "permalink_pin"); pin != "" {
		// auth.normalise_permalink_pin: six digits (non-ASCII ones were sent to Python above).
		if len(pin) != 6 || strings.Trim(pin, "0123456789") != "" {
			q.back(w, r, fmt.Sprintf("/apartments/%d", a.ID), hostweb.Flash{}, updateFlash(q, "flash.error.pin_six_digits", nil))
			return
		}
		cols = setColumn(cols, "permalink_pin", pin)
	}
	if pay.feePosted {
		var ok bool
		if cols, ok = apartmentFeeAccount(r, cols); !ok {
			s.refuseApartmentSave(w, r, q, a, apartmentRefusal{feeAccountError: true})
			return
		}
	}
	// AR-18: only new credentials lift the refused-login pause.
	credentialsChanged := pay.password != "" || pay.text["uby_ws_user"] != a.UbyWSUser
	lockSet, lockProvider := false, ""
	if editsLock {
		lockID := formStr(r, "lock_id")
		if formStr(r, "door_codes") == "1" {
			door, err := p.detailDoorContext(ctx, a)
			if err != nil {
				fail(w, err)
				return
			}
			listed := false
			if door != nil {
				for _, l := range door.Locks {
					listed = listed || l.LockID == lockID
				}
			}
			lockPage := fmt.Sprintf("/apartments/%d?view=settings&section=lock#door-code", a.ID)
			if !listed {
				q.back(w, r, lockPage, hostweb.Flash{}, doorCodesFlash(q, "flash.error.door_code_lock"))
				return
			}
			if a.LockProvider != "ttlock" || a.LockID != lockID {
				users, err := p.detailLockUsers(ctx, *a.OwnerUserID, lockID, a.ID)
				if err != nil {
					fail(w, err)
					return
				}
				if users != "" {
					q.back(w, r, lockPage, hostweb.Flash{}, doorCodesFlash(q, "flash.error.door_code_lock_taken"))
					return
				}
			}
			lockSet, lockProvider = true, "ttlock"
			cols = setColumn(setColumn(cols, "lock_provider", "ttlock"), "lock_id", lockID)
		} else if has(r, "door_codes_fields") {
			// Unticked means off; the hidden section flag alone (no account,
			// no locks) must not switch codes off.
			lockSet = true
			cols = setColumn(cols, "lock_provider", nil)
			if lockID != "" {
				cols = setColumn(cols, "lock_id", lockID)
			}
		}
	}
	if err := s.writeApartmentSave(ctx, q, a, cols, pay, formStr(r, "stay_fee_rate_from")); err != nil {
		fail(w, err)
		return
	}
	if credentialsChanged {
		if err := privacy.ResolveAlert(ctx, s.pool, fmt.Sprintf("ubyport_auth_failed:%d", a.ID), stamp(q.at)); err != nil {
			fail(w, err)
			return
		}
	}
	if pay.text["internal_name"] != a.InternalName {
		// 0096: the readable part of the guest link follows the name.
		if err := palette.FollowGuestSlugName(ctx, s.pool, a.ID, a.PermalinkToken, pay.text["internal_name"]); err != nil {
			fail(w, err)
			return
		}
	}
	if err := s.audit(ctx, q, "apartment_updated", fmt.Sprintf("id=%d", a.ID)); err != nil {
		fail(w, err)
		return
	}
	if err := stayfeemail.ReconcileNoPayWay(ctx, s.pool, s.getenv, a.ID); err != nil {
		fail(w, err)
		return
	}
	if lockSet && lockProvider != a.LockProvider {
		action := "door_codes_off"
		if lockProvider == "ttlock" {
			action = "door_codes_on"
		}
		if err := s.audit(ctx, q, action, fmt.Sprintf("apartment=%d", a.ID)); err != nil {
			fail(w, err)
			return
		}
	}
	s.apartmentSaved(w, r, q, p, a.ID)
}

// apartmentFeeAccount is the account half of stay_fees.fee_form_values and
// apply_fee_account: the three domestic fields (unless an all-empty form
// would wipe a stored IBAN-only account) or stay_fee_council_account, stored
// as display form and IBAN. ok is false where Python raises ValueError.
func apartmentFeeAccount(r *http.Request, cols []column) ([]column, bool) {
	var raw string
	switch {
	case has(r, "account_prefix") || has(r, "account_number") || has(r, "account_bank"):
		raw = composeCzechAccount(formStr(r, "account_prefix"), formStr(r, "account_number"), formStr(r, "account_bank"))
		if raw == "" && czechAccountParts(formStr(r, "_stay_fee_account_existing")).IBAN != "" {
			return cols, true // payments.preserve_iban_only_account
		}
	case has(r, "stay_fee_council_account"):
		raw = formStr(r, "stay_fee_council_account")
	default:
		return cols, true
	}
	if pyStrip(raw) == "" {
		return setColumn(setColumn(cols, "stay_fee_council_account", nil), "stay_fee_council_iban", nil), true
	}
	display, iban, ok := normaliseAccount(raw)
	if !ok {
		return cols, false
	}
	return setColumn(setColumn(cols, "stay_fee_council_account", display), "stay_fee_council_iban", iban), true
}

// writeApartmentSave is db.update("apartment", id, payload) and, when the
// fee was posted, stay_fee_routes.record_rate_change, in one transaction.
// The update repeats the workspace check of detailLoad.
func (s *server) writeApartmentSave(ctx context.Context, q *request, a *detailApt, cols []column, pay apartmentPayload, rawFrom string) error {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	sql, args := updateSQL("apartment", cols, a.ID)
	sql += " AND owner_user_id IS NOT DISTINCT FROM $" + strconv.Itoa(len(args)+1)
	if _, err := tx.Exec(ctx, sql, append(args, q.host.Workspace.ID)...); err != nil {
		return err
	}
	if pay.feePosted {
		if err := recordRateChange(ctx, tx, a.ID, pay.rate, a.StayFeeRateCZK, rawFrom, q.at); err != nil {
			return err
		}
	}
	return tx.Commit(ctx)
}

// recordRateChange is stay_fee_routes.record_rate_change with
// stay_fee_rate.record: a changed rate gets a dated row from
// stay_fee_rate_from (never before today in Prague); a property with no
// history first gets its previous rate from EPOCH. An unchanged rate writes nothing.
func recordRateChange(ctx context.Context, tx pgx.Tx, id int64, rate int, previous int64, rawFrom string, at time.Time) error {
	if previous == int64(rate) {
		return nil
	}
	today := stayfees.PragueToday(at)
	from := today
	if _, err := time.Parse("2006-01-02", rawFrom); err == nil && rawFrom > today {
		from = rawFrom
	}
	rows, err := tx.Query(ctx, apartmentUpdateRatesSQL, id)
	if err != nil {
		return err
	}
	type step struct {
		from string
		rate int
	}
	schedule, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (step, error) {
		var st step
		err := row.Scan(&st.from, &st.rate)
		return st, err
	})
	if err != nil {
		return err
	}
	if len(schedule) == 0 {
		base := int(previous)
		if base <= 0 {
			base = rate
		}
		if base <= 0 {
			return nil // no fee set up and none being set: nothing to date
		}
		if _, err := tx.Exec(ctx, apartmentCreateRateSQL, id, base, stayFeeRateEpoch, stamp(at)); err != nil {
			return err
		}
		schedule = []step{{stayFeeRateEpoch, base}}
	}
	current := schedule[0].rate // stay_fee_rate.rate_on
	for _, st := range schedule {
		if st.from > from {
			break
		}
		current = st.rate
	}
	if current == rate {
		return nil
	}
	_, err = tx.Exec(ctx, apartmentUpdateRateSQL, id, rate, from, stamp(at))
	return err
}

// apartmentSaved is the tail of apartment_update after a save: the
// confirmation names the police fields still missing (_missing_report_labels)
// and the page opens again with ?saved=1 (1024).
func (s *server) apartmentSaved(w http.ResponseWriter, r *http.Request, q *request, p *Pages, id int64) {
	saved, err := p.detailLoad(r.Context(), q.host.Workspace.ID, id)
	if err != nil {
		fail(w, err)
		return
	}
	if saved == nil {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	issues, err := p.detailIssues(saved, q.at)
	if err != nil {
		fail(w, err)
		return
	}
	missing := map[string]bool{}
	for _, issue := range validation.ErrorsOnly(issues) {
		missing[issue.Field] = true
	}
	var labels []string
	for _, f := range detailReportFields {
		if missing[f.Field] {
			labels = append(labels, detailT(q.lang, "apartment.form.readiness.item."+f.Key))
		}
	}
	msg := updateFlash(q, "flash.apartments.saved_ready", nil)
	if len(labels) > 0 {
		msg = updateFlash(q, "flash.apartments.saved", map[string]any{"fields": strings.Join(labels, ", ")})
	}
	path, fragment, found := strings.Cut(formReturnTo(r, fmt.Sprintf("/apartments/%d", id), false), "#")
	if strings.Contains(path, "?") {
		path += "&saved=1"
	} else {
		path += "?saved=1"
	}
	if found {
		path += "#" + fragment
	}
	q.back(w, r, path, msg, hostweb.Flash{})
}
