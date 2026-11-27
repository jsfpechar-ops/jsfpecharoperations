package properties

// The data half of GET /apartments/{id} (brief 1701): the apartment row, the
// operators, the calendar feeds, the readiness lists, the health rows, the
// door-code state, the guide state and the guest link. Every function is named
// after the Python helper it ports (routes/admin.py, property_health.py,
// workflow.py, guest_slug.py, ttlock.py). The apartment is always read through
// detailLoad, which scopes it to the workspace; every other read starts from
// that row's id.

import (
	"context"
	"errors"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/palette"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

// detailApt is the apartment row (access.apartment: the workspace's row,
// archived or not). A NULL text column is "", a NULL number is 0.
type detailApt struct {
	ID                                                         int64
	OwnerUserID                                                *int64
	LegalEntityID, DataControllerEntityID                      int64
	InternalName, CityEN                                       string
	AddrOkres, AddrObec, AddrObecCast, AddrStreet, AddrHouseNo string
	AddrOrientNo, AddrZip                                      string
	UbyIDUB, UbyMark, UbyName, UbyContact, UbyWSUser           string
	UbyWSPasswordEnc                                           string
	AutomationMode                                             string
	SubmitAfterHours                                           int64
	PermalinkToken, PermalinkPIN                               string
	PermalinkWindowDays, PermalinkReachbackDays                int64
	DefaultPurpose, GuestMessage, Notes, PassportPhotoPolicy   string
	OcrScan                                                    int64
	StayFeeRateCZK                                             int64
	StayFeeCadence, StayFeeCouncilAccount, StayFeeCouncilIBAN  string
	StayFeeVS, StayFeeAuthorityName, StayFeeAuthorityAddress   string
	StayFeeAuthorityContact, StayFeeAuthorityDatabox           string
	StayFeePayee, StayFeeInstruction                           string
	StayFeeCollect                                             int64
	StayFeeGuestRails, StayFeeGuestRevolutLink                 string
	StayFeeGuestCashNote, StayFeeGuestDefaultRail              string
	Active                                                     int64
	CreatedAt, ArchivedAt                                      string
	LockProvider, LockID                                       string
	CheckinHour, CheckoutHour                                  *int64
	LeonEnabled                                                int64
	LeonTermsVersion                                           string
}

const detailAptSQL = `SELECT id, owner_user_id, COALESCE(legal_entity_id, 0), COALESCE(data_controller_entity_id, 0),
  internal_name, COALESCE(city_en, ''), COALESCE(addr_okres, ''), COALESCE(addr_obec, ''), COALESCE(addr_obec_cast, ''),
  COALESCE(addr_street, ''), COALESCE(addr_house_no, ''), COALESCE(addr_orient_no, ''), COALESCE(addr_zip, ''),
  COALESCE(uby_idub, ''), COALESCE(uby_mark, ''), COALESCE(uby_name, ''), COALESCE(uby_contact, ''), COALESCE(uby_ws_user, ''),
  COALESCE(uby_ws_password_enc, ''), automation_mode, submit_after_hours, COALESCE(permalink_token, ''), COALESCE(permalink_pin, ''),
  permalink_window_days, permalink_reachback_days, default_purpose, COALESCE(guest_message, ''), COALESCE(notes, ''),
  passport_photo_policy, ocr_scan, stay_fee_rate_czk, stay_fee_cadence, COALESCE(stay_fee_council_account, ''),
  COALESCE(stay_fee_council_iban, ''), COALESCE(stay_fee_vs, ''), COALESCE(stay_fee_authority_name, ''),
  COALESCE(stay_fee_authority_address, ''), COALESCE(stay_fee_authority_contact, ''), COALESCE(stay_fee_authority_databox, ''),
  COALESCE(stay_fee_payee, ''), COALESCE(stay_fee_instruction, ''), stay_fee_collect, stay_fee_guest_rails,
  COALESCE(stay_fee_guest_revolut_link, ''), COALESCE(stay_fee_guest_cash_note, ''), stay_fee_guest_default_rail,
  active, created_at, COALESCE(archived_at, ''), COALESCE(lock_provider, ''), COALESCE(lock_id, ''), checkin_hour, checkout_hour,
  leon_enabled, COALESCE(leon_terms_version, '')
FROM apartment WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`

// detailLoad is access.apartment(request, id): nil when it is not the workspace's.
func (s *Pages) detailLoad(ctx context.Context, owner, id int64) (*detailApt, error) {
	var a detailApt
	err := s.pool.QueryRow(ctx, detailAptSQL, id, owner).Scan(&a.ID, &a.OwnerUserID, &a.LegalEntityID, &a.DataControllerEntityID,
		&a.InternalName, &a.CityEN, &a.AddrOkres, &a.AddrObec, &a.AddrObecCast, &a.AddrStreet, &a.AddrHouseNo, &a.AddrOrientNo, &a.AddrZip,
		&a.UbyIDUB, &a.UbyMark, &a.UbyName, &a.UbyContact, &a.UbyWSUser, &a.UbyWSPasswordEnc, &a.AutomationMode, &a.SubmitAfterHours,
		&a.PermalinkToken, &a.PermalinkPIN, &a.PermalinkWindowDays, &a.PermalinkReachbackDays, &a.DefaultPurpose, &a.GuestMessage, &a.Notes,
		&a.PassportPhotoPolicy, &a.OcrScan, &a.StayFeeRateCZK, &a.StayFeeCadence, &a.StayFeeCouncilAccount, &a.StayFeeCouncilIBAN,
		&a.StayFeeVS, &a.StayFeeAuthorityName, &a.StayFeeAuthorityAddress, &a.StayFeeAuthorityContact, &a.StayFeeAuthorityDatabox,
		&a.StayFeePayee, &a.StayFeeInstruction, &a.StayFeeCollect, &a.StayFeeGuestRails, &a.StayFeeGuestRevolutLink,
		&a.StayFeeGuestCashNote, &a.StayFeeGuestDefaultRail, &a.Active, &a.CreatedAt, &a.ArchivedAt, &a.LockProvider, &a.LockID,
		&a.CheckinHour, &a.CheckoutHour, &a.LeonEnabled, &a.LeonTermsVersion)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// detailEnsurePIN is _ensure_apartment_pin: a property made before PINs existed
// gets one, and the row is read again.
func (s *Pages) detailEnsurePIN(ctx context.Context, owner int64, a *detailApt) (*detailApt, error) {
	if a.PermalinkPIN != "" {
		return a, nil
	}
	pin, err := newPermalinkPIN()
	if err != nil {
		return nil, err
	}
	if _, err := s.pool.Exec(ctx, aptPINSQL, pin, a.ID); err != nil {
		return nil, err
	}
	return s.detailLoad(ctx, owner, a.ID)
}

// setup is the property_setup view of the row.
func (a *detailApt) setup() onboarding.Apartment {
	return onboarding.Apartment{ID: a.ID, InternalName: a.InternalName, LegalEntityID: a.LegalEntityID, AddrObec: a.AddrObec,
		AddrHouseNo: a.AddrHouseNo, AddrZip: a.AddrZip, StayFeeRateCZK: a.StayFeeRateCZK, LockProvider: a.LockProvider}
}

// --- the copy from another property (_property_copy_values, _apply_property_copy) ---

// detailCopyEmptyInt and detailCopyEmptyText are _property_copy_value_empty:
// a number is empty at 0, a text when it is blank.
func detailCopyEmptyText(v string) bool { return pyStrip(v) == "" }

// detailApplyCopy is _apply_property_copy of the 15 _COPY_PROPERTY_KEYS: a
// value of the source fills a field of the page's property only where that
// field is empty. The stored row is not changed; only the page shows it.
func detailApplyCopy(a, src *detailApt) {
	if a.LegalEntityID == 0 {
		a.LegalEntityID = src.LegalEntityID
	}
	if a.DataControllerEntityID == 0 {
		a.DataControllerEntityID = src.DataControllerEntityID
	}
	for _, f := range []struct{ dst, from *string }{
		{&a.AutomationMode, &src.AutomationMode}, {&a.DefaultPurpose, &src.DefaultPurpose},
		{&a.StayFeeCadence, &src.StayFeeCadence}, {&a.StayFeeAuthorityName, &src.StayFeeAuthorityName},
		{&a.StayFeeAuthorityAddress, &src.StayFeeAuthorityAddress}, {&a.StayFeeAuthorityContact, &src.StayFeeAuthorityContact},
		{&a.StayFeePayee, &src.StayFeePayee}, {&a.StayFeeInstruction, &src.StayFeeInstruction},
		{&a.StayFeeCouncilAccount, &src.StayFeeCouncilAccount},
	} {
		if detailCopyEmptyText(*f.dst) && !detailCopyEmptyText(*f.from) {
			*f.dst = *f.from
		}
	}
	for _, f := range []struct{ dst, from *int64 }{
		{&a.SubmitAfterHours, &src.SubmitAfterHours}, {&a.PermalinkWindowDays, &src.PermalinkWindowDays},
		{&a.PermalinkReachbackDays, &src.PermalinkReachbackDays}, {&a.StayFeeRateCZK, &src.StayFeeRateCZK},
	} {
		if *f.dst == 0 && *f.from != 0 {
			*f.dst = *f.from
		}
	}
}

// detailPeer is one row of access.apartments (the copy dialog's list).
type detailPeer struct {
	ID   int64
	Name string
}

// detailEntity is one row of access.entities: the workspace's operators that
// are not archived, by name.
type detailEntity struct {
	ID                            int64
	Name, ContactEmail, ICO, Seat string
	SignatureName                 string
}

const (
	detailPeersSQL    = `SELECT id, COALESCE(internal_name, '') FROM apartment WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL AND id <> $2 ORDER BY internal_name`
	detailEntitiesSQL = `SELECT id, name, COALESCE(contact_email, ''), COALESCE(ico, ''), COALESCE(seat, ''), COALESCE(signature_name, '')
FROM legal_entity WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL ORDER BY name`
	detailControllerSQL = `SELECT name, COALESCE(seat, ''), COALESCE(ico, ''), COALESCE(contact_email, '') FROM legal_entity WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
)

func (s *Pages) detailPeers(ctx context.Context, owner, self int64) ([]detailPeer, error) {
	rows, err := s.pool.Query(ctx, detailPeersSQL, owner, self)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (detailPeer, error) {
		var p detailPeer
		err := row.Scan(&p.ID, &p.Name)
		return p, err
	})
}

func (s *Pages) detailEntities(ctx context.Context, owner int64) ([]detailEntity, error) {
	rows, err := s.pool.Query(ctx, detailEntitiesSQL, owner)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (detailEntity, error) {
		var e detailEntity
		err := row.Scan(&e.ID, &e.Name, &e.ContactEmail, &e.ICO, &e.Seat, &e.SignatureName)
		return e, err
	})
}

// detailControllerComplete is guest.controller_complete: the configured
// controller (the separate one, else the operator) has a name, an e-mail and an
// IČO or a seat.
func (s *Pages) detailControllerComplete(ctx context.Context, owner int64, a *detailApt) (bool, error) {
	id := a.DataControllerEntityID
	if id == 0 {
		id = a.LegalEntityID
	}
	if id == 0 {
		return false, nil
	}
	var name, seat, ico, email string
	err := s.pool.QueryRow(ctx, detailControllerSQL, id, owner).Scan(&name, &seat, &ico, &email)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return name != "" && email != "" && (ico != "" || seat != ""), nil
}

// --- the calendar feeds (_feed_display) ---

// detailFeed is a stored feed with the display name and portal.
type detailFeed struct {
	ID                                               int64
	URL, Label, OwnName                              string
	LastSyncAt, LastStatus, LastError, LastCheckedAt string
	Active                                           bool
	DisplayName, DisplayPortal, PlatformKey, Checked string
}

const detailFeedsSQL = `SELECT id, url, COALESCE(label, ''), COALESCE(own_name, ''), COALESCE(last_sync_at, ''), COALESCE(last_status, ''),
  COALESCE(last_error, ''), active, COALESCE(last_checked_at, '') FROM ical_feed WHERE apartment_id = $1 ORDER BY id`

// detailDetectedPlatforms is admin._DETECTED_PLATFORM_NAMES.
var detailDetectedPlatforms = map[string]string{
	"booking": "Booking.com", "airbnb": "Airbnb", "vrbo": "Vrbo", "agoda": "Agoda", "echalupy": "e-chalupy",
	"expedia": "Expedia", "tripadvisor": "Tripadvisor", "trip": "Trip.com", "google": "Google Calendar", "apple": "iCloud",
}

// detailFeeds is the feed rows of one property with _feed_display applied.
// fallbackName and otherPortal are the host texts of calendar.fallback_name
// and calendar.platform.other.
func (s *Pages) detailFeeds(ctx context.Context, apartmentID int64, fallbackName, otherPortal string) ([]detailFeed, error) {
	rows, err := s.pool.Query(ctx, detailFeedsSQL, apartmentID)
	if err != nil {
		return nil, err
	}
	feeds, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (detailFeed, error) {
		var f detailFeed
		var active int64
		err := row.Scan(&f.ID, &f.URL, &f.Label, &f.OwnName, &f.LastSyncAt, &f.LastStatus, &f.LastError, &active, &f.LastCheckedAt)
		f.Active = active != 0
		return f, err
	})
	if err != nil {
		return nil, err
	}
	for i := range feeds {
		f := &feeds[i]
		label := pyStrip(f.Label)
		f.PlatformKey = ical.PlatformOf(f.URL, "")
		detected := detailDetectedPlatforms[f.PlatformKey]
		f.DisplayName = firstText(pyStrip(f.OwnName), label, detected, fallbackName)
		f.DisplayPortal = firstText(label, detected, otherPortal)
		if f.LastCheckedAt != "" {
			f.Checked = f.LastCheckedAt
		} else {
			f.Checked = f.LastSyncAt
		}
	}
	return feeds, nil
}

// firstText is Python's `a or b or c`: the first non-empty text.
func firstText(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

// --- readiness (_apartment_issues, _readiness) ---

// detailItem is one line of the readiness checklist.
type detailItem struct {
	Key, Anchor string
	Done        bool
	Message     string // the validation message of a reporting line, English
}

// detailReadiness is the dict _readiness returns.
type detailReadiness struct {
	Invite, Report []detailItem
	InviteReady    bool
}

// detailReportFields is admin._READINESS_REPORT_FIELDS.
var detailReportFields = []struct{ Key, Field, Anchor string }{
	{"idub", "uby_idub", "ubyport"}, {"mark", "uby_mark", "ubyport"}, {"facility_name", "uby_name", "ubyport"},
	{"house_no", "addr_house_no", "address"}, {"zip", "addr_zip", "address"}, {"obec", "addr_obec", "address"},
	{"ws_user", "uby_ws_user", "ubyport"}, {"password", "uby_ws_password", "ubyport"},
}

// detailSecret is db.decrypt_secret: "" for an empty or unreadable token.
func (s *Pages) detailSecret(token string, at time.Time) (string, error) {
	if token == "" {
		return "", nil
	}
	keys, err := secure.LoadDataKeys(s.getenv)
	if err != nil {
		return "", err
	}
	plain, err := keys.Decrypt(token, 0, at)
	if err != nil {
		return "", nil
	}
	return string(plain), nil
}

// detailIssues is _apartment_issues: validate_apartment of the row with the
// decrypted password.
func (s *Pages) detailIssues(a *detailApt, at time.Time) ([]validation.Issue, error) {
	password, err := s.detailSecret(a.UbyWSPasswordEnc, at)
	if err != nil {
		return nil, err
	}
	values := map[string]string{
		"internal_name": a.InternalName, "city_en": a.CityEN, "addr_okres": a.AddrOkres, "addr_obec": a.AddrObec,
		"addr_obec_cast": a.AddrObecCast, "addr_street": a.AddrStreet, "addr_house_no": a.AddrHouseNo,
		"addr_orient_no": a.AddrOrientNo, "addr_zip": a.AddrZip, "uby_idub": a.UbyIDUB, "uby_mark": a.UbyMark,
		"uby_name": a.UbyName, "uby_contact": a.UbyContact, "uby_ws_user": a.UbyWSUser, "uby_ws_password": password,
	}
	if a.LegalEntityID != 0 {
		values["legal_entity_id"] = strconv.FormatInt(a.LegalEntityID, 10)
	}
	if a.DataControllerEntityID != 0 {
		values["data_controller_entity_id"] = strconv.FormatInt(a.DataControllerEntityID, 10)
	}
	return validation.ValidateApartment(values), nil
}

// detailReadinessOf is _readiness. entity is the operator among entities, nil
// when there is none; controllerOK is guest.controller_complete.
func detailReadinessOf(a *detailApt, entity *detailEntity, issues []validation.Issue, hasStays, controllerOK, invite bool) detailReadiness {
	byField := map[string]string{}
	for _, issue := range validation.ErrorsOnly(issues) {
		if _, ok := byField[issue.Field]; !ok {
			byField[issue.Field] = issue.Message
		}
	}
	var r detailReadiness
	if invite {
		r.Invite = []detailItem{
			{Key: "name", Anchor: "basics", Done: pyStrip(a.InternalName) != ""},
			{Key: "operator", Anchor: "basics", Done: entity != nil && pyStrip(entity.ContactEmail) != ""},
			{Key: "controller", Anchor: "basics", Done: controllerOK},
			{Key: "stays", Anchor: "calendars", Done: hasStays},
		}
	}
	r.InviteReady = true
	for _, item := range r.Invite {
		if !item.Done {
			r.InviteReady = false
		}
	}
	for _, f := range detailReportFields {
		msg, bad := byField[f.Field]
		r.Report = append(r.Report, detailItem{Key: f.Key, Anchor: f.Anchor, Done: !bad, Message: msg})
	}
	return r
}

func (r detailReadiness) reportComplete() bool {
	for _, item := range r.Report {
		if !item.Done {
			return false
		}
	}
	return true
}

// --- health (property_health.checks) ---

// detailHealthRow is one row of property_health.checks.
type detailHealthRow struct {
	Key, State, TextKey string
}

var (
	detailFeedKinds  = map[string]bool{"feed_error": true, "feed_incomplete": true, "feed_duplicate_uid": true, "feed_recurring_event": true}
	detailLoginKinds = map[string]bool{"ubyport_auth_failed": true}
)

// detailHealth is property_health.checks: calendar, guest link, police,
// business and, when a lock is offered, door. guestUsed and linkDue are the
// two workflow facts.
func (s *Pages) detailHealth(ctx context.Context, a *detailApt, feeds []detailFeed, r detailReadiness, door *detailDoor, now time.Time) (map[string]detailHealthRow, error) {
	rows, err := s.pool.Query(ctx, `SELECT kind FROM alert WHERE apartment_id = $1 AND resolved_at IS NULL`, a.ID)
	if err != nil {
		return nil, err
	}
	kinds, err := pgx.CollectRows(rows, pgx.RowTo[string])
	if err != nil {
		return nil, err
	}
	open := map[string]bool{}
	for _, k := range kinds {
		open[k] = true
	}
	any := func(set map[string]bool) bool {
		for k := range open {
			if set[k] {
				return true
			}
		}
		return false
	}
	out := map[string]detailHealthRow{}
	activeFeeds, feedError := 0, false
	for _, f := range feeds {
		if f.Active {
			activeFeeds++
			if f.LastStatus == "error" {
				feedError = true
			}
		}
	}
	switch {
	case feedError || any(detailFeedKinds):
		out["calendar"] = detailHealthRow{"calendar", "bad", "health.calendar.error"}
	case activeFeeds == 0:
		out["calendar"] = detailHealthRow{"calendar", "warn", "health.calendar.none"}
	default:
		out["calendar"] = detailHealthRow{"calendar", "ok", "health.calendar.ok"}
	}
	used, err := s.detailGuestUsedLink(ctx, a.ID)
	if err != nil {
		return nil, err
	}
	if used {
		out["guest_link"] = detailHealthRow{"guest_link", "ok", "health.guest_link.ok"}
	} else {
		due, err := s.detailLinkDue(ctx, a, now)
		if err != nil {
			return nil, err
		}
		if due {
			out["guest_link"] = detailHealthRow{"guest_link", "warn", "health.guest_link.unused"}
		} else {
			out["guest_link"] = detailHealthRow{"guest_link", "off", "health.guest_link.waiting"}
		}
	}
	var missing []detailItem
	for _, item := range r.Report {
		if !item.Done {
			missing = append(missing, item)
		}
	}
	switch {
	case any(detailLoginKinds):
		out["police"] = detailHealthRow{"police", "bad", "health.police.login"}
	case len(missing) > 0:
		out["police"] = detailHealthRow{"police", "warn", "health.police.missing"}
	default:
		out["police"] = detailHealthRow{"police", "ok", "health.police.ok"}
	}
	business := open["controller_missing"]
	for _, item := range r.Invite {
		if (item.Key == "operator" || item.Key == "controller") && !item.Done {
			business = true
		}
	}
	if business {
		out["business"] = detailHealthRow{"business", "warn", "health.business.missing"}
	} else {
		out["business"] = detailHealthRow{"business", "ok", "health.business.ok"}
	}
	if door != nil {
		switch door.State {
		case "on":
			out["door"] = detailHealthRow{"door", "ok", "health.door.ok"}
		case "times":
			out["door"] = detailHealthRow{"door", "bad", "health.door.times"}
		case "offline":
			out["door"] = detailHealthRow{"door", "bad", "health.door.offline"}
		default:
			out["door"] = detailHealthRow{"door", "off", "health.door.off"}
		}
	}
	return out, nil
}

// detailGuestUsedLink is workflow.guest_used_link.
func (s *Pages) detailGuestUsedLink(ctx context.Context, apartmentID int64) (bool, error) {
	var used bool
	err := s.pool.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM reservation r JOIN reservation_claim c ON c.reservation_id = r.id
 WHERE r.apartment_id = $1 AND COALESCE(r.source, '') != 'demo'
   AND (c.state IN ('provisional', 'claimed') OR c.claimed_at IS NOT NULL))`, apartmentID).Scan(&used)
	return used, err
}

// detailLinkDue is bool(workflow.link_unused([apartment])): a live property
// with a link whose next real stay lies inside the link window, since the
// property was added.
func (s *Pages) detailLinkDue(ctx context.Context, a *detailApt, at time.Time) (bool, error) {
	if a.Active == 0 || a.ArchivedAt != "" || a.PermalinkToken == "" {
		return false, nil
	}
	demo, err := s.detailIsDemo(ctx, a)
	if err != nil || demo {
		return false, err
	}
	added := "0000-00-00"
	if len(a.CreatedAt) >= 10 {
		added = a.CreatedAt[:10]
	}
	days := a.PermalinkWindowDays
	if days == 0 {
		days = 1
	}
	today := detailToday(at)
	horizon := today.AddDate(0, 0, int(days)).Format("2006-01-02")
	var due bool
	err = s.pool.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM reservation WHERE apartment_id = $1 AND status = 'active'
 AND archived_at IS NULL AND COALESCE(source, '') != 'demo' AND date_from >= $2 AND date_from <= $3)`,
		a.ID, added, horizon).Scan(&due)
	return due, err
}

// detailToday is claim.prague_today.
func detailToday(at time.Time) time.Time {
	l := deadlines.LocalNow(at)
	return time.Date(l.Year(), l.Month(), l.Day(), 0, 0, 0, 0, time.UTC)
}

// detailDemoNames are demo.DEMO_APARTMENT and DEMO_LOFT; detailDemoEntities
// are DEMO_ENTITY and DEMO_CONTROLLER.
var (
	detailDemoNames    = map[string]bool{"Vinohrady Studio (demo)": true, "Karlín Loft (demo)": true}
	detailDemoEntities = map[string]bool{"Josef Novák (demo)": true, "Demo Controller s.r.o.": true}
)

// detailIsDemo is demo.is_demo_apartment.
func (s *Pages) detailIsDemo(ctx context.Context, a *detailApt) (bool, error) {
	if detailDemoNames[a.InternalName] {
		return true, nil
	}
	env := strings.ToLower(s.getenv("UBYHOST_UBYPORT_ENV"))
	if env == "" {
		env = "mock"
	}
	if env != "mock" || a.LegalEntityID == 0 {
		return false, nil
	}
	var name string
	err := s.pool.QueryRow(ctx, `SELECT name FROM legal_entity WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`, a.LegalEntityID, a.OwnerUserID).Scan(&name)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return detailDemoEntities[name], err
}

// --- door codes (_door_code_context) ---

// detailLock is one lock of the stored list with the names of the properties
// that already use it.
type detailLock struct {
	LockID, Alias string
	TZOffsetMS    any
	UsedBy        string   // the other properties on this lock, "#id" for a nameless one (_door_code_context)
	Using         []string // every property on this lock by name (_smart_lock_panel_context properties_using)
	TZWrong       bool
	Battery       string // "" for a lock that reports none
}

// detailLockAccount is the lock_account row.
type detailLockAccount struct {
	ID                      int64
	Username, Status        string
	LocksJSON, LocksFetched string
}

// detailDoor is the dict _door_code_context returns; nil where door codes are
// not offered to the owner.
type detailDoor struct {
	Account                   *detailLockAccount
	Locks                     []detailLock
	Enabled                   bool
	State                     string // off | times | offline | on
	FirstLock                 bool
	LockID, DefaultLockID     string
	FreeLockCount             int
	CheckinHour, CheckoutHour *int64
	TZWarning, Overlap        bool
	Buffer                    int
	TestMode                  bool
	StateKey                  string // the smart_locks.state_* text of the state
	Reauth                    bool   // the account needs the owner to sign in again
	PanelReturn               string // lock_panel.return_to
}

// detailDoorCodesEnabled is ttlock.enabled().
func detailDoorCodesEnabled(getenv func(string) string) bool {
	switch getenv("UBYHOST_DOOR_CODES") {
	case "1", "true", "yes":
	default:
		return false
	}
	return pyStrip(getenv("UBYHOST_TTLOCK_CLIENT_ID")) != "" && pyStrip(getenv("UBYHOST_TTLOCK_CLIENT_SECRET")) != ""
}

// detailLockAllowed is ttlock.allowed_for(owner): door codes are on and
// billing.entitlements(owner).ttlock.
func (s *Pages) detailLockAllowed(ctx context.Context, owner *int64) (bool, error) {
	if !detailDoorCodesEnabled(s.getenv) || owner == nil {
		return false, nil
	}
	switch strings.ToLower(s.getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
	default:
		return true, nil // UNBILLED
	}
	var status, plan string
	var addon int64
	err := s.pool.QueryRow(ctx, `SELECT status, COALESCE(plan, ''), COALESCE(addon_ttlock, 0) FROM billing_account WHERE owner_user_id = $1`, *owner).Scan(&status, &plan, &addon)
	if errors.Is(err, pgx.ErrNoRows) {
		return true, nil // UNBILLED
	}
	if err != nil {
		return false, err
	}
	switch status {
	case "paused":
		return false, nil
	case "trial_pending", "trialing":
		return true, nil
	}
	if plan == "" {
		plan = "standard"
	}
	return plan == "max" || addon != 0, nil
}

// detailPragueOffsets is admin._PRAGUE_TZ_OFFSETS_MS.
func detailLockTZWrong(offset any) bool {
	var n int64
	switch v := offset.(type) {
	case nil:
		return false
	case float64:
		n = int64(v)
	case string:
		parsed, err := strconv.ParseInt(strings.TrimSpace(v), 10, 64)
		if err != nil {
			return false
		}
		n = parsed
	default:
		return false
	}
	return n != 3_600_000 && n != 7_200_000
}

// detailHoursOverlap is admin._door_code_hours_overlap.
func detailHoursOverlap(in, out *int64, buffer int) bool {
	if in == nil || out == nil {
		return false
	}
	needed := int64(2 * buffer)
	var gap int64
	if *in >= *out {
		gap = *in - *out
	} else {
		gap = (24 - *out) + *in
	}
	return gap < needed
}

// detailDoorContext is _door_code_context: nil unless door codes are offered
// to the property's owner.
func (s *Pages) detailDoorContext(ctx context.Context, a *detailApt) (*detailDoor, error) {
	allowed, err := s.detailLockAllowed(ctx, a.OwnerUserID)
	if err != nil || !allowed {
		return nil, err
	}
	d := &detailDoor{Buffer: 1, CheckinHour: a.CheckinHour, CheckoutHour: a.CheckoutHour, LockID: a.LockID}
	switch s.getenv("UBYHOST_DOOR_CODES_LIVE") {
	case "1", "true", "yes":
	default:
		d.TestMode = true
	}
	var acc detailLockAccount
	err = s.pool.QueryRow(ctx, `SELECT id, username, status, COALESCE(locks_json, ''), COALESCE(locks_fetched_at, '')
 FROM lock_account WHERE owner_user_id = $1 AND provider = 'ttlock'`, *a.OwnerUserID).Scan(&acc.ID, &acc.Username, &acc.Status, &acc.LocksJSON, &acc.LocksFetched)
	switch {
	case errors.Is(err, pgx.ErrNoRows):
	case err != nil:
		return nil, err
	default:
		d.Account = &acc
		parsed, err := ttlock.ParseLocks([]byte(acc.LocksJSON))
		if err != nil {
			return nil, err
		}
		for _, l := range parsed {
			lock := detailLock{LockID: l.LockID, Alias: l.Alias, TZOffsetMS: l.TZOffsetMS, TZWrong: detailLockTZWrong(l.TZOffsetMS), Battery: detailBattery(l.Battery)}
			if lock.UsedBy, err = s.detailLockUsers(ctx, *a.OwnerUserID, l.LockID, a.ID); err != nil {
				return nil, err
			}
			if lock.Using, err = s.detailLockNames(ctx, *a.OwnerUserID, l.LockID); err != nil {
				return nil, err
			}
			d.Locks = append(d.Locks, lock)
		}
	}
	var free []detailLock
	var selected *detailLock
	for i := range d.Locks {
		if d.Locks[i].UsedBy == "" {
			free = append(free, d.Locks[i])
		}
		if a.LockID != "" && d.Locks[i].LockID == a.LockID {
			selected = &d.Locks[i]
		}
	}
	d.Enabled = a.LockProvider == "ttlock"
	online := d.Account != nil && d.Account.Status == "ok" && selected != nil
	switch {
	case !d.Enabled:
		d.State = "off"
	case a.CheckinHour == nil || a.CheckoutHour == nil:
		d.State = "times"
	case !online:
		d.State = "offline"
	default:
		d.State = "on"
	}
	d.StateKey = map[string]string{"off": "smart_locks.state_off", "times": "smart_locks.state_times", "offline": "smart_locks.state_offline"}[d.State]
	if d.StateKey == "" {
		d.StateKey = "smart_locks.state_on"
	}
	d.Reauth = d.Account != nil && d.Account.Status != "ok"
	d.PanelReturn = "/apartments/" + strconv.FormatInt(a.ID, 10) + "?view=settings&section=lock"
	d.FirstLock = a.LockProvider != "ttlock" && a.LockID == "" && len(free) == 1
	if len(free) == 1 {
		d.DefaultLockID = free[0].LockID
	}
	d.FreeLockCount = len(free)
	d.TZWarning = selected != nil && detailLockTZWrong(selected.TZOffsetMS)
	d.Overlap = detailHoursOverlap(a.CheckinHour, a.CheckoutHour, d.Buffer)
	return d, nil
}

// detailBattery is a lock's battery as Jinja prints it: "" for none, a whole
// number without a decimal point.
func detailBattery(v any) string {
	switch n := v.(type) {
	case float64:
		if n == float64(int64(n)) {
			return strconv.FormatInt(int64(n), 10)
		}
		return strconv.FormatFloat(n, 'g', -1, 64)
	case string:
		return n
	}
	return ""
}

// detailLockNames is the names in _smart_lock_panel_context properties_using:
// the owner's properties on this lock, by internal name.
func (s *Pages) detailLockNames(ctx context.Context, owner int64, lockID string) ([]string, error) {
	rows, err := s.pool.Query(ctx, `SELECT COALESCE(internal_name, '') FROM apartment
 WHERE owner_user_id IS NOT DISTINCT FROM $1 AND lock_provider = 'ttlock' AND lock_id = $2 ORDER BY id`, owner, lockID)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, pgx.RowTo[string])
}

// detailLockUsers is ", ".join(_properties_using_lock(owner, lock, except)).
func (s *Pages) detailLockUsers(ctx context.Context, owner int64, lockID string, except int64) (string, error) {
	rows, err := s.pool.Query(ctx, `SELECT id, COALESCE(internal_name, '') FROM apartment
 WHERE owner_user_id IS NOT DISTINCT FROM $1 AND lock_provider = 'ttlock' AND lock_id = $2 ORDER BY id`, owner, lockID)
	if err != nil {
		return "", err
	}
	names, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (string, error) {
		var id int64
		var name string
		err := row.Scan(&id, &name)
		if id == except {
			return "", err
		}
		if name == "" {
			name = "#" + strconv.FormatInt(id, 10)
		}
		return name, err
	})
	var kept []string
	for _, n := range names {
		if n != "" {
			kept = append(kept, n)
		}
	}
	return strings.Join(kept, ", "), err
}

// --- the guest link (guest_slug.link_key) ---

// detailLinkKey is guest_slug.link_key: the current slug (made from the name
// when there is none yet; palette.EnsureGuestSlug is the one generator), else
// the permanent token; "" without a token.
func (s *Pages) detailLinkKey(ctx context.Context, a *detailApt) (string, error) {
	slug, err := palette.EnsureGuestSlug(ctx, s.pool, a.ID, a.PermalinkToken, a.InternalName)
	if err != nil || slug != "" {
		return slug, err
	}
	return a.PermalinkToken, nil
}

// --- the next stay on the link (workflow.next_stay_window) ---

// detailLinkNext is the part of next_stay_window the page reads.
type detailLinkNext struct {
	HasStay       bool
	DateFrom      string
	Window, Opens string // "", "now" or "from"; Opens is an ISO date
	Days          int
}

func (s *Pages) detailNextStay(ctx context.Context, a *detailApt, at time.Time) (detailLinkNext, error) {
	today := detailToday(at)
	days := int(a.PermalinkWindowDays)
	if days == 0 {
		days = 1
	}
	out := detailLinkNext{Days: days}
	var from string
	err := s.pool.QueryRow(ctx, `SELECT date_from FROM reservation WHERE apartment_id = $1 AND status = 'active'
 AND archived_at IS NULL AND COALESCE(source, '') != 'demo' AND date_from >= $2 ORDER BY date_from LIMIT 1`,
		a.ID, today.Format("2006-01-02")).Scan(&from)
	if errors.Is(err, pgx.ErrNoRows) {
		return out, nil
	}
	if err != nil {
		return out, err
	}
	out.HasStay, out.DateFrom = true, from
	start, perr := time.Parse("2006-01-02", from)
	if perr != nil || start.Before(today) {
		return out, nil
	}
	opens := start.AddDate(0, 0, -days)
	if !opens.After(today) {
		out.Window, out.Opens = "now", today.Format("2006-01-02")
	} else {
		out.Window, out.Opens = "from", opens.Format("2006-01-02")
	}
	return out, nil
}

// --- the setup guide (_setup_facts, _setup_state, _setup_guide_bundle, _setup_progress) ---

// detailGuide is what _setup_guide_bundle returns.
type detailGuide struct {
	Facts onboarding.Facts
	State *onboarding.State
	Guide *onboarding.Guide
}

// detailSetupFacts is _setup_facts: stays and registered guests outside the
// guide's own demo stay.
func (s *Pages) detailSetupFacts(ctx context.Context, apartmentID int64) (stays int, registered bool, err error) {
	if err = s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = $1
 AND r.archived_at IS NULL AND COALESCE(r.source, '') != 'demo'`, apartmentID).Scan(&stays); err != nil {
		return 0, false, err
	}
	err = s.pool.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM guest g JOIN reservation r ON r.id = g.reservation_id
 WHERE r.apartment_id = $1 AND g.entered_by = 'guest' AND COALESCE(r.source, '') != 'demo')`, apartmentID).Scan(&registered)
	return stays, registered, err
}

// detailSetupState is _setup_state: the stored guide, or the guide of a
// property made before it (a legacy one that is now set up is finished).
func (s *Pages) detailSetupState(ctx context.Context, settings onboarding.Settings, a *detailApt, f onboarding.Facts) (*onboarding.State, error) {
	state, err := onboarding.Load(ctx, settings, a.ID)
	if err != nil {
		return nil, err
	}
	setUp := f.ReportComplete && (f.Feeds > 0 || f.Stays > 0)
	if state != nil {
		if state.Legacy && setUp && !state.Finished {
			if err := onboarding.Finish(ctx, settings, a.ID); err != nil {
				return nil, err
			}
			return onboarding.Load(ctx, settings, a.ID)
		}
		return state, nil
	}
	if a.ArchivedAt != "" || a.Active == 0 {
		return nil, nil
	}
	demo, err := s.detailIsDemo(ctx, a)
	if err != nil || demo {
		return nil, err
	}
	if setUp {
		return nil, nil
	}
	return onboarding.LegacyState(), nil
}

// detailGuideBundle is _setup_guide_bundle.
func (s *Pages) detailGuideBundle(ctx context.Context, settings onboarding.Settings, a *detailApt, feedCount int, reportComplete, lockAvailable bool) (detailGuide, error) {
	stays, registered, err := s.detailSetupFacts(ctx, a.ID)
	if err != nil {
		return detailGuide{}, err
	}
	g := detailGuide{Facts: onboarding.Facts{Feeds: feedCount, Stays: stays, GuestsRegistered: registered, ReportComplete: reportComplete}}
	if g.State, err = s.detailSetupState(ctx, settings, a, g.Facts); err != nil {
		return g, err
	}
	if g.State != nil && !g.State.Finished {
		g.Guide = onboarding.Current(a.setup(), g.State, g.Facts, lockAvailable)
	}
	return g, nil
}

// detailProgress is the dict _setup_progress returns (the Overview card).
type detailProgress struct {
	Hidden           bool
	Done, Total      int
	ContinueURL      string
	ReportingWaiting bool
}

// detailSetupProgress is _setup_progress: nil when there is no card.
func detailSetupProgress(ctx context.Context, settings onboarding.Settings, a *detailApt, g detailGuide, lockAvailable bool) (*detailProgress, error) {
	state := g.State
	if state == nil || state.Finished {
		return nil, nil
	}
	if state.Hidden {
		return &detailProgress{Hidden: true, Done: onboarding.DoneCount(state, a.setup(), g.Facts, lockAvailable),
			Total: onboarding.TotalSteps, ContinueURL: onboarding.WizardURL(a.ID, "calendar")}, nil
	}
	if g.Guide == nil {
		stored, err := onboarding.Load(ctx, settings, a.ID)
		if err != nil {
			return nil, err
		}
		if stored != nil && (state.Legacy || state.Tested) {
			return nil, onboarding.Finish(ctx, settings, a.ID)
		}
		return nil, nil
	}
	return &detailProgress{Done: g.Guide.DoneCount, Total: g.Guide.Total, ContinueURL: g.Guide.URL, ReportingWaiting: g.Guide.ReportingWaiting}, nil
}

// --- the purposes select (codelists.purpose_options("en")) ---

// detailPurpose is one option of the default-purpose select.
type detailPurpose struct{ Code, Label string }

// detailBundledPurposes is validation.PURPOSES in its order, as (code, en).
var detailBundledPurposes = []detailPurpose{
	{"00", "Medical"}, {"01", "Business"}, {"02", "Cultural"}, {"03", "Visiting family or friends"}, {"04", "Invitation"},
	{"05", "Official (political)"}, {"06", "Self-employment"}, {"07", "Sport"}, {"10", "Tourism"},
	{"11", "Study (training, internship)"}, {"12", "Transit"}, {"13", "Airport transit"}, {"27", "Employment"},
	{"93", "ADS visa (Chinese nationals)"}, {"99", "Other"},
}

// detailBundledPurposesCS is validation.PURPOSES localized to Czech.
var detailBundledPurposesCS = []detailPurpose{
	{"00", "Zdravotní"}, {"01", "Obchodní"}, {"02", "Kulturní"}, {"03", "Návštěva rodiny nebo přátel"}, {"04", "Pozvání"},
	{"05", "Oficiální (politický)"}, {"06", "Podnikání"}, {"07", "Sportovní"}, {"10", "Turistika"},
	{"11", "Studium (stáž, školení)"}, {"12", "Tranzit"}, {"13", "Letištní tranzit"}, {"27", "Zaměstnání"},
	{"93", "Vízum ADS (občané Číny)"}, {"99", "Jiný"},
}

// detailPurposes returns localized purpose-of-stay options (Czech when lang == "cs", English otherwise).
func (s *Pages) detailPurposes(ctx context.Context, lang string) ([]detailPurpose, error) {
	rows, err := s.pool.Query(ctx, `SELECT code, COALESCE(extra, ''), COALESCE(text_cs, ''), COALESCE(text_en, '') FROM codelist WHERE kind = 'ucely' ORDER BY code`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	list := detailBundledPurposes
	if lang == "cs" {
		list = detailBundledPurposesCS
	}
	bundled := map[string]string{}
	for _, p := range list {
		bundled[p.Code] = p.Label
	}
	var out []detailPurpose
	for rows.Next() {
		var code, extra, cs, en string
		if err := rows.Scan(&code, &extra, &cs, &en); err != nil {
			return nil, err
		}
		if extra != "" {
			code = extra
		}
		label := firstText(bundled[code], en, cs, code)
		if lang == "cs" {
			label = firstText(bundled[code], cs, en, code)
		}
		out = append(out, detailPurpose{Code: code, Label: label})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(out) == 0 {
		return list, nil
	}
	return out, nil
}
