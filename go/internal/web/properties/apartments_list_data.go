package properties

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// setupChip is one apartments_list setup chip (admin.py ~1402).
type setupChip struct {
	Key, State, Href string
}

// Tone is the chip colour class (apartments.html: ok→g, bad→r, off→n).
func (c setupChip) Tone() string {
	switch c.State {
	case "ok":
		return "g"
	case "bad":
		return "r"
	default:
		return "n"
	}
}

// apartmentListRow is one enriched apartments_list row.
type apartmentListRow struct {
	Apt           detailApt
	Feeds         int64
	FeedErrors    int64
	ManualStays   int64
	Chips         []setupChip
	LinkKey       string
	LinkURL       string
	Address       string
	PhoneInitials string
	PhoneMissing  string // joined chip labels for apartments.phone.missing
	PhoneReady    bool
}

func (r apartmentListRow) Base() string { return "/apartments/" + strconv.FormatInt(r.Apt.ID, 10) }

const (
	apartmentsListSQL = `SELECT id, owner_user_id, COALESCE(legal_entity_id, 0), COALESCE(data_controller_entity_id, 0),
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
  leon_enabled, COALESCE(leon_terms_version, ''),
  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1),
  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1 AND f.last_status = 'error'),
  (SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = a.id AND r.status = 'active' AND r.source = 'manual')
FROM apartment a WHERE a.archived_at IS NULL AND a.owner_user_id IS NOT DISTINCT FROM $1 ORDER BY a.internal_name`
	ubyportAuthFailedSQL = `SELECT apartment_id FROM alert WHERE owner_user_id = $1 AND kind = 'ubyport_auth_failed' AND resolved_at IS NULL AND apartment_id IS NOT NULL`
)

func (s *Pages) apartmentListRows(ctx context.Context, owner int64, lang string, at time.Time) ([]apartmentListRow, error) {
	authFailed, err := s.ubyportAuthFailed(ctx, owner)
	if err != nil {
		return nil, err
	}
	rows, err := s.pool.Query(ctx, apartmentsListSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []apartmentListRow
	for rows.Next() {
		a, feeds, feedErrors, manualStays, err := scanListApt(rows)
		if err != nil {
			return nil, err
		}
		issues, err := s.detailIssues(&a, at)
		if err != nil {
			return nil, err
		}
		linkKey, err := listLinkKey(ctx, s.pool, a.ID, a.PermalinkToken)
		if err != nil {
			return nil, err
		}
		linkURL := ""
		if linkKey != "" {
			linkURL = hostweb.PublicBase(s.getenv) + "/l/" + linkKey
		}
		chips := listSetupChips(&a, validation.ErrorsOnly(issues), authFailed[a.ID], feeds, feedErrors, manualStays)
		missing := missingChipLabels(lang, chips)
		out = append(out, apartmentListRow{
			Apt: a, Feeds: feeds, FeedErrors: feedErrors, ManualStays: manualStays, Chips: chips,
			LinkKey: linkKey, LinkURL: linkURL, Address: listAddress(&a),
			PhoneInitials: listPhoneInitials(a.InternalName), PhoneMissing: missing, PhoneReady: missing == "",
		})
	}
	return out, rows.Err()
}

func (s *Pages) ubyportAuthFailed(ctx context.Context, owner int64) (map[int64]bool, error) {
	rows, err := s.pool.Query(ctx, ubyportAuthFailedSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[int64]bool{}
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		out[id] = true
	}
	return out, rows.Err()
}

func scanListApt(row pgx.Row) (detailApt, int64, int64, int64, error) {
	var a detailApt
	var feeds, feedErrors, manualStays int64
	err := row.Scan(&a.ID, &a.OwnerUserID, &a.LegalEntityID, &a.DataControllerEntityID,
		&a.InternalName, &a.CityEN, &a.AddrOkres, &a.AddrObec, &a.AddrObecCast, &a.AddrStreet, &a.AddrHouseNo, &a.AddrOrientNo, &a.AddrZip,
		&a.UbyIDUB, &a.UbyMark, &a.UbyName, &a.UbyContact, &a.UbyWSUser, &a.UbyWSPasswordEnc, &a.AutomationMode, &a.SubmitAfterHours,
		&a.PermalinkToken, &a.PermalinkPIN, &a.PermalinkWindowDays, &a.PermalinkReachbackDays, &a.DefaultPurpose, &a.GuestMessage, &a.Notes,
		&a.PassportPhotoPolicy, &a.OcrScan, &a.StayFeeRateCZK, &a.StayFeeCadence, &a.StayFeeCouncilAccount, &a.StayFeeCouncilIBAN,
		&a.StayFeeVS, &a.StayFeeAuthorityName, &a.StayFeeAuthorityAddress, &a.StayFeeAuthorityContact, &a.StayFeeAuthorityDatabox,
		&a.StayFeePayee, &a.StayFeeInstruction, &a.StayFeeCollect, &a.StayFeeGuestRails, &a.StayFeeGuestRevolutLink,
		&a.StayFeeGuestCashNote, &a.StayFeeGuestDefaultRail, &a.Active, &a.CreatedAt, &a.ArchivedAt, &a.LockProvider, &a.LockID,
		&a.CheckinHour, &a.CheckoutHour, &a.LeonEnabled, &a.LeonTermsVersion, &feeds, &feedErrors, &manualStays)
	return a, feeds, feedErrors, manualStays, err
}

func listLinkKey(ctx context.Context, pool *pgxpool.Pool, id int64, permalinkToken string) (string, error) {
	slug, err := guestSlugCurrent(ctx, pool, id)
	if err != nil {
		return "", err
	}
	if slug != "" {
		return slug, nil
	}
	return permalinkToken, nil
}

func listAddress(a *detailApt) string {
	line := strings.TrimSpace(a.AddrStreet + " " + a.AddrHouseNo)
	var parts []string
	if line != "" {
		parts = append(parts, line)
	}
	if obec := pyStrip(a.AddrObec); obec != "" {
		parts = append(parts, obec)
	}
	return strings.Join(parts, ", ")
}

func listPhoneInitials(name string) string {
	var b strings.Builder
	for i, word := range strings.Fields(name) {
		if i >= 2 {
			break
		}
		for _, r := range word {
			b.WriteRune(unicode.ToUpper(r))
			break
		}
	}
	return b.String()
}

func missingChipLabels(lang string, chips []setupChip) string {
	var names []string
	for _, c := range chips {
		if c.State == "bad" {
			names = append(names, catalog.T(lang, "apartments.chip."+c.Key, nil))
		}
	}
	return strings.Join(names, ", ")
}

func listSetupChips(a *detailApt, issues []validation.Issue, authFailed bool, feeds, feedErrors, manualStays int64) []setupChip {
	base := "/apartments/" + strconv.FormatInt(a.ID, 10)
	policeBad := len(issues) > 0 || authFailed
	lockOK := pyStrip(a.LockID) != ""
	feeOK := stayfee.IsActive(&stayfee.Apartment{StayFeeRateCZK: int(a.StayFeeRateCZK)})
	lockHref := base + "?view=settings&section=lock#door-code"
	if !lockOK {
		lockHref = base + "?view=settings&section=property#basics"
	}
	policeState := "ok"
	if policeBad {
		policeState = "bad"
	}
	lockState := "off"
	if lockOK {
		lockState = "ok"
	}
	feeState := "off"
	if feeOK {
		feeState = "ok"
	}
	return []setupChip{
		{Key: "police", State: policeState, Href: base + "?view=settings&section=reporting#ubyport"},
		{Key: "calendar", State: calendarChipState(feeds, feedErrors, manualStays), Href: base + "?view=bookings#calendars"},
		{Key: "lock", State: lockState, Href: lockHref},
		{Key: "fee", State: feeState, Href: base + "?view=settings&section=reporting#stay-fee-settings"},
	}
}

func calendarChipState(feeds, feedErrors, manualStays int64) string {
	hasFeeds := feeds > 0
	feedError := feedErrors > 0
	hasManual := manualStays > 0
	if hasFeeds && !feedError {
		return "ok"
	}
	if !hasFeeds && hasManual {
		return "off"
	}
	return "bad"
}

// PhoneCoverClass is apartments.html cover c{{ id % 3 }}.
func (r apartmentListRow) PhoneCoverClass() string {
	return fmt.Sprintf("c%d", r.Apt.ID%3)
}
