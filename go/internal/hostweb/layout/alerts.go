package layout

// alerts.go is the host alert stack: alerts.open_alerts, shell_slice and
// present_many (App/app/alerts.py) and _host_alerts.html. Appendix 5 section
// 10.4(2) wants a filing failure shown on every screen, so this is filing
// code: keep it equal to the Python, line for line. Brief 1381.

import (
	"bytes"
	"context"
	"encoding/json"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// levelOrder is alerts.LEVEL_ORDER; an unknown level sorts as 9.
var levelOrder = map[string]int{"critical": 0, "warning": 1, "info": 2}

func levelRank(level string) int {
	if n, ok := levelOrder[level]; ok {
		return n
	}
	return 9
}

// computedKinds is alerts._COMPUTED_ALERT_KINDS, feedKinds _FEED_ALERT_KINDS.
var computedKinds = map[string]bool{
	"deadline": true, "guest_incomplete_checkin": true, "headcount_mismatch": true,
	"dates_changed_resign": true, "moved_after_report": true, "submission_stuck": true,
	"job_failed": true, "feed_incomplete": true, "feed_duplicate_uid": true, "feed_recurring_event": true,
}

var feedKinds = map[string]bool{"feed_incomplete": true, "feed_duplicate_uid": true, "feed_recurring_event": true}

// reasonKinds is alerts._REASON_KINDS: the only kinds whose card shows a reason
// line. Every one of them is computed, so a stored detail is never shown here.
var reasonKinds = map[string]bool{"deadline": true, "guest_incomplete_checkin": true, "headcount_mismatch": true}

// systemAlertKinds is alerts.SYSTEM_ALERT_KINDS (shown to every workspace).
const systemAlertKinds = `'job_failed', 'turnstile_unavailable', 'ttlock_budget'`

// shellAlertLimit is alerts.SHELL_ALERT_LIMIT.
const shellAlertLimit = 12

// actions is alerts._ACTIONS: label key and href pattern.
var actions = map[string][2]string{
	"ubyport_auth_failed":  {"notification.action.police_login", "/apartments/{apartment}?view=settings&section=reporting#ubyport"},
	"apartment_setup":      {"notification.action.police_setup", "/apartments/{apartment}?view=settings&section=reporting#ubyport"},
	"controller_missing":   {"notification.action.business", "/apartments/{apartment}?view=settings&section=property#operator-picker"},
	"feed_error":           {"notification.action.calendar", "/apartments/{apartment}?view=bookings#calendars"},
	"feed_incomplete":      {"notification.action.calendar", "/apartments/{apartment}?view=bookings#calendars"},
	"feed_duplicate_uid":   {"notification.action.calendar", "/apartments/{apartment}?view=bookings#calendars"},
	"feed_recurring_event": {"notification.action.calendar", "/apartments/{apartment}?view=bookings#calendars"},
	"guest_pin_rotated":    {"notification.action.guest_link", "/apartments/{apartment}?view=settings&section=guests#communication"},
	"guest_pin_abuse":      {"notification.action.guest_link", "/apartments/{apartment}?view=settings&section=guests#communication"},
	"guest_pin_locked_out": {"notification.action.guest_link", "/apartments/{apartment}?view=settings&section=guests#communication"},
	"guest_pin_challenged": {"notification.action.guest_link", "/apartments/{apartment}?view=settings&section=guests#communication"},
	"submission_stuck":     {"notification.action.guests", "/reservations/{reservation}#guests"},
	"guest_question":       {"notification.action.guest_questions", "/apartments/{apartment}/guide/questions"},
	"stay_fee_no_pay_way":  {"notification.action.stay_fee_pay", "/apartments/{apartment}?view=settings&section=reporting#stay-fee-settings"},
}

// foldableKinds is foldable_kinds in _host_alerts.html.
var foldableKinds = map[string]bool{
	"guest_pin_rotated": true, "guest_pin_abuse": true, "guest_pin_locked_out": true,
	"guest_pin_challenged": true, "guest_question": true, "ttlock_budget": true,
}

// alertStay is the reservation joined to its apartment (alerts._reservation_row).
type alertStay struct {
	calendar.AlertStay
	Property string `json:"property"` // internal_name or ""
}

// alertRow is one open alert row with what its card reads from other tables.
type alertRow struct {
	ID            int64      `json:"id"`
	Level         string     `json:"level"`
	Kind          string     `json:"kind"`
	ApartmentID   *int64     `json:"apartment_id"`
	ReservationID *int64     `json:"reservation_id"`
	DedupeKey     string     `json:"dedupe_key"`
	Message       string     `json:"message"`
	Detail        string     `json:"detail"`
	Params        string     `json:"params"`
	FeedProperty  string     `json:"feed_property"` // apartment.internal_name of apartment_id, "" when none
	Stay          *alertStay `json:"stay"`          // nil: no reservation_id or the row is gone
}

// alertCard is alerts.present's card, the fields _host_alerts.html reads.
type alertCard struct {
	ID            int64
	Level, Kind   string
	ApartmentID   *int64
	ReservationID *int64
	Title         string // display_title or message
	Reason        string // display_reason
	ActionKey     string
	ActionHref    string
}

// openAlertsSQL is alerts.open_alerts(owner) with the rows its cards read in
// the same statement: the stay of a computed card (reservation JOIN apartment,
// as _reservation_row) and the property of a feed card. The order is the
// Python one; id breaks created_at ties so the result is repeatable.
const openAlertsSQL = `SELECT al.id, al.level, al.kind, al.apartment_id, al.reservation_id,
       COALESCE(al.dedupe_key, ''), COALESCE(al.message, ''), COALESCE(al.detail, ''), COALESCE(al.params, ''),
       COALESCE(fa.internal_name, ''),
       ra.id IS NOT NULL, r.id, COALESCE(r.date_from, ''), COALESCE(r.date_to, ''),
       r.declared_guests, r.expected_guests_override, r.lead_reduced_guests, COALESCE(ra.internal_name, '')
  FROM alert al
  LEFT JOIN apartment fa ON fa.id = al.apartment_id
  LEFT JOIN reservation r ON r.id = al.reservation_id
  LEFT JOIN apartment ra ON ra.id = r.apartment_id
 WHERE al.resolved_at IS NULL AND (al.owner_user_id = $1 OR al.kind IN (` + systemAlertKinds + `))
 ORDER BY al.created_at DESC, al.id DESC`

// loadAlerts is alerts.open_alerts(owner): unresolved rows of the workspace
// and the system kinds, newest first, then stably by level.
func loadAlerts(ctx context.Context, pool *pgxpool.Pool, owner int64) ([]alertRow, error) {
	rows, err := pool.Query(ctx, openAlertsSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []alertRow
	for rows.Next() {
		var a alertRow
		var found bool
		var resID *int64
		var s alertStay
		if err := rows.Scan(&a.ID, &a.Level, &a.Kind, &a.ApartmentID, &a.ReservationID,
			&a.DedupeKey, &a.Message, &a.Detail, &a.Params, &a.FeedProperty,
			&found, &resID, &s.DateFrom, &s.DateTo, &s.Declared, &s.Override, &s.Reduced, &s.Property); err != nil {
			return nil, err
		}
		if found && resID != nil {
			s.ID = *resID
			a.Stay = &s
		}
		out = append(out, a)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	sortAlerts(out)
	return out, nil
}

func sortAlerts(rows []alertRow) {
	sort.SliceStable(rows, func(i, j int) bool { return levelRank(rows[i].Level) < levelRank(rows[j].Level) })
}

// shellSlice is alerts.shell_slice: every critical row plus the next twelve.
func shellSlice(rows []alertRow) ([]alertRow, int) {
	critical := 0
	for _, r := range rows {
		if r.Level == "critical" {
			critical++
		}
	}
	keep := critical + shellAlertLimit
	if keep >= len(rows) {
		return rows, 0
	}
	return rows[:keep], len(rows) - keep
}

// progressStays is the stays _preload_stays reads: computed rows with a stay.
func progressStays(rows []alertRow) []calendar.AlertStay {
	seen := map[int64]bool{}
	var out []calendar.AlertStay
	for _, r := range rows {
		if computedKinds[r.Kind] && r.Stay != nil && !seen[r.Stay.ID] {
			seen[r.Stay.ID] = true
			out = append(out, r.Stay.AlertStay)
		}
	}
	return out
}

// formsComplete is alerts.forms_complete.
func formsComplete(p calendar.AlertProgress) bool {
	if p.Status == "reported" || p.Status == "not_required" {
		return true
	}
	return p.Expected != nil && p.Filled >= *p.Expected && p.Incomplete == 0
}

// alertText is the request's language and clock for the cards.
type alertText struct {
	lang string
	now  time.Time // the request instant
}

func (x alertText) t(key string, params map[string]any) string {
	return Strings.T(x.lang, key, params)
}

// own is host_i18n.STRINGS[lang] without the English fallback.
func (x alertText) own(key string) (string, bool) {
	s, ok := Strings[x.lang][key]
	return s, ok
}

// presentMany is alerts.present_many: one card per stay, most severe first.
func presentMany(rows []alertRow, progress map[int64]calendar.AlertProgress, x alertText) []alertCard {
	var cards []alertCard
	seen := map[int64]int{}
	for _, a := range rows {
		if a.Kind == "guest_incomplete_checkin" && a.Stay != nil {
			if p, ok := progress[a.Stay.ID]; ok && !p.Unreadable && formsComplete(p) {
				continue
			}
		}
		card := present(a, progress, x)
		if card.ReservationID == nil || *card.ReservationID == 0 {
			cards = append(cards, card)
			continue
		}
		idx, ok := seen[*card.ReservationID]
		if !ok {
			seen[*card.ReservationID] = len(cards)
			cards = append(cards, card)
			continue
		}
		if levelRank(card.Level) < levelRank(cards[idx].Level) {
			cards[idx] = card
		}
	}
	return cards
}

// present is alerts.present: the title, the reason line and the action.
func present(a alertRow, progress map[int64]calendar.AlertProgress, x alertText) alertCard {
	c := alertCard{ID: a.ID, Level: a.Level, Kind: a.Kind, ApartmentID: a.ApartmentID, ReservationID: a.ReservationID}
	var title, detail string
	if computedKinds[a.Kind] {
		title, detail = presentComputed(a, progress, x)
	} else {
		title = presentStored(a, x)
	}
	c.Title = title
	if c.Title == "" {
		c.Title = a.Message // display_title or message
	}
	if reasonKinds[a.Kind] {
		c.Reason = detail
	}
	c.ActionKey, c.ActionHref = actionFor(a)
	return c
}

func positive(p *int64) bool { return p != nil && *p != 0 }

// actionFor is alerts.action_for: (label key, href), or empty.
func actionFor(a alertRow) (string, string) {
	if known, ok := actions[a.Kind]; ok {
		pattern := known[1]
		if (!strings.Contains(pattern, "{reservation}") || positive(a.ReservationID)) &&
			(!strings.Contains(pattern, "{apartment}") || positive(a.ApartmentID)) {
			href := strings.ReplaceAll(pattern, "{reservation}", idText(a.ReservationID))
			href = strings.ReplaceAll(href, "{apartment}", idText(a.ApartmentID))
			return known[0], href
		}
	}
	if positive(a.ReservationID) {
		return "notification.open_stay", "/reservations/" + idText(a.ReservationID)
	}
	if positive(a.ApartmentID) {
		return "notification.open_property", "/apartments/" + idText(a.ApartmentID)
	}
	return "", ""
}

func idText(p *int64) string {
	if p == nil {
		return "None"
	}
	return strconv.FormatInt(*p, 10)
}

// storedParams is alerts.stored_params: the JSON object, else empty. Numbers
// keep Python's int/float split, booleans print as Python's True/False.
func storedParams(raw string) map[string]any {
	if raw == "" {
		return map[string]any{}
	}
	dec := json.NewDecoder(bytes.NewReader([]byte(raw)))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil || dec.More() {
		return map[string]any{}
	}
	m, ok := v.(map[string]any)
	if !ok {
		return map[string]any{}
	}
	for k, val := range m {
		switch t := val.(type) {
		case json.Number:
			if i, err := t.Int64(); err == nil {
				m[k] = i
			} else if f, err := t.Float64(); err == nil {
				m[k] = f
			}
		case bool:
			if t {
				m[k] = "True"
			} else {
				m[k] = "False"
			}
		}
	}
	return m
}

// localised is alerts._localised: the key in the language's own table, else
// the stored text; a text with placeholders and no params keeps the stored one.
func (x alertText) localised(key, stored string, params map[string]any) string {
	text, ok := x.own(key)
	if !ok {
		return stored
	}
	if strings.Contains(text, "%(") && len(params) == 0 {
		return stored
	}
	return Strings.T(x.lang, key, params)
}

// presentStored is alerts._present_stored, the title only: the detail of a
// stored kind is never shown in the shell (reasonKinds are all computed).
func presentStored(a alertRow, x alertText) string {
	params := storedParams(a.Params)
	if a.Kind == "mail_failed" && truthy(params["kind"]) {
		kind := pyStr(params["kind"])
		if _, ok := x.own("notification.mail_kind." + kind); ok {
			kind = x.t("notification.mail_kind."+kind, nil)
		}
		params["kind"] = kind
	}
	key := "notification." + a.Kind + ".title"
	if v := params["variant"]; truthy(v) {
		if _, ok := x.own(key + "." + pyStr(v)); ok {
			key = key + "." + pyStr(v)
		}
	}
	return x.localised(key, a.Message, params)
}

// presentComputed is alerts._present_computed: (display_title, display_detail).
func presentComputed(a alertRow, progress map[int64]calendar.AlertProgress, x alertText) (string, string) {
	if a.Kind == "job_failed" {
		job := a.DedupeKey
		if i := strings.Index(job, ":"); i >= 0 {
			job = job[i+1:]
		}
		name := ""
		if job != "" {
			name = x.t("notification.job_name."+job, nil)
		}
		return x.t("notification.job_failed.title", map[string]any{"job": name}), x.t("notification.job_failed.detail", nil)
	}
	if feedKinds[a.Kind] {
		return x.t("notification."+a.Kind+".title", map[string]any{"property": a.FeedProperty}),
			x.t("notification.reason."+a.Kind, nil)
	}
	if !positive(a.ReservationID) || a.Stay == nil {
		return a.Message, a.Detail
	}
	s := a.Stay
	title := x.t("notification.stay_title", map[string]any{"property": s.Property, "dates": fmtDateRange(s.DateFrom, s.DateTo)})
	switch a.Kind {
	case "dates_changed_resign", "moved_after_report", "submission_stuck":
		return title, x.t("notification.reason."+a.Kind, nil)
	case "guest_incomplete_checkin":
		return title, x.checkinIncompleteReason(s.DateFrom)
	}
	p, ok := progress[s.ID]
	if !ok {
		p = calendar.AlertProgressNoGuests(s.AlertStay)
	}
	if p.Unreadable {
		// Python raises DecryptionError here and the page fails. The card stays,
		// with the English detail stored when it was raised (brief 1381 §Risks).
		return title, a.Detail
	}
	filled, expected := formsCount(p)
	if a.Kind == "headcount_mismatch" {
		return title, x.t("notification.reason.headcount_mismatch", map[string]any{"filled": filled, "expected": expected})
	}
	if p.HasAnchor {
		return title, x.deadlineReason(p.Anchor, filled, expected)
	}
	return title, x.t("notification.reason.urgent_forms", map[string]any{"filled": filled, "expected": expected})
}

// formsCount is alerts._forms_count.
func formsCount(p calendar.AlertProgress) (string, string) {
	expected := "?"
	if p.Expected != nil {
		expected = strconv.Itoa(*p.Expected)
	}
	return strconv.Itoa(p.Filled), expected
}

// deadlineReason is alerts.deadline_reason.
func (x alertText) deadlineReason(checkIn time.Time, filled, expected string) string {
	kind, amount := deadlines.TimeLeftParts(checkIn, deadlines.LocalNow(x.now))
	switch kind {
	case "overdue_days":
		return x.t(pluralKey("notification.reason.overdue_forms", amount), map[string]any{"n": amount, "filled": filled, "expected": expected})
	case "overdue_hours":
		return x.t("notification.reason.overdue_hours_forms", map[string]any{"n": amount, "filled": filled, "expected": expected})
	}
	return x.t("notification.reason.urgent_forms", map[string]any{"filled": filled, "expected": expected})
}

// checkinIncompleteReason is alerts.checkin_incomplete_reason with today the
// Prague date of the request.
func (x alertText) checkinIncompleteReason(arrival string) string {
	now := deadlines.LocalNow(x.now)
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	if d, ok := validation.ParseISODate(arrival); ok && d.Before(today) {
		return x.t("notification.reason.checkin_incomplete_past", map[string]any{"date": d.Format("02.01.2006")})
	}
	return x.t("notification.reason.checkin_incomplete", nil)
}

// fmtDate is validation.fmt_date, fmtDateRange fmt_date_range.
func fmtDate(v string) string {
	if d, ok := validation.ParseISODate(v); ok {
		return d.Format("02.01.2006")
	}
	return v
}

func fmtDateRange(from, to string) string {
	start, end := fmtDate(from), fmtDate(to)
	if start != "" && end != "" {
		return start + " – " + end
	}
	if start != "" {
		return start
	}
	return end
}

// alertLine is one article of _host_alerts.html.
type alertLine struct {
	alertCard
	PhHide, Outside, Compact, ShowAction, Dismiss bool
}

// alertStack is _host_alerts.html's computed state.
type alertStack struct {
	Show                   bool
	AsideHide              bool
	Lines                  []alertLine
	Summary                bool
	SummaryLevel, SummaryT string
}

// buildAlertStack is the logic at the top of _host_alerts.html.
func buildAlertStack(cards []alertCard, more int, path, apartmentQuery string, expanded, phHidePin bool, t func(string, ...any) string) alertStack {
	st := alertStack{Show: len(cards) > 0 || more != 0}
	if !st.Show {
		return st
	}
	scope := ""
	if path == "/reservations" {
		scope = apartmentQuery
	}
	compact := !expanded && path != "/" && path != "/reservations" &&
		!strings.HasPrefix(path, "/reservations/") && !strings.HasPrefix(path, "/apartments/")
	outside := map[int64]bool{}
	var shown, folded []alertCard
	for _, item := range cards {
		if scope != "" && positive(item.ApartmentID) && strconv.FormatInt(*item.ApartmentID, 10) != scope {
			outside[item.ID] = true
		}
		if (compact || outside[item.ID]) && foldableKinds[item.Kind] {
			folded = append(folded, item)
		} else {
			shown = append(shown, item)
		}
	}
	var red, rest, restPin []alertCard
	for _, c := range shown {
		if c.Level == "critical" {
			red = append(red, c)
		} else {
			rest = append(rest, c)
		}
	}
	nonPin := 0
	for _, c := range rest {
		if c.Kind == "guest_pin_rotated" {
			restPin = append(restPin, c)
		} else {
			nonPin++
		}
	}
	restCount := nonPin + len(folded) + more
	if len(restPin) > 0 {
		restCount++
	}
	restInline := expanded || (restCount == 1 && len(folded) == 0 && more == 0)
	lines := append([]alertCard{}, red...)
	if restInline {
		lines = append(lines, rest...)
	}
	linesNonPin := 0
	for _, c := range lines {
		if c.Kind != "guest_pin_rotated" {
			linesNonPin++
		}
	}
	st.AsideHide = phHidePin && linesNonPin == 0
	for _, c := range lines {
		if c.Kind == "guest_pin_rotated" && len(restPin) > 0 && c.ID != restPin[0].ID {
			continue
		}
		out := outside[c.ID]
		st.Lines = append(st.Lines, alertLine{
			alertCard:  c,
			PhHide:     phHidePin && c.Kind == "guest_pin_rotated",
			Outside:    out,
			Compact:    compact || out,
			ShowAction: c.ActionKey != "" && !compact && !out && !(path == "/reservations" && c.Kind == "headcount_mismatch"),
			Dismiss:    c.Kind != "dates_changed_resign",
		})
	}
	if restCount > 0 && !restInline {
		st.Summary = true
		st.SummaryLevel = "warning"
		if all := append(append([]alertCard{}, folded...), rest...); len(all) > 0 {
			st.SummaryLevel = all[0].Level
		}
		key := "notification.summary.count"
		if len(red) > 0 {
			key = "notification.summary.more"
		}
		st.SummaryT = t(key, "n", restCount)
	}
	return st
}
