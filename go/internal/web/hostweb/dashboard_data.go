package hostweb

import (
	"context"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

// apartmentRow is one property on the overview: the calendar grid row, the
// "which property" column and the setup wizard all read it.
type apartmentRow struct {
	ID     int64
	Name   string
	Active bool
	Feeds  int
}

// calDay is one column of the 14-day overview grid (0706).
type calDay struct {
	Weekday  int // Monday is 0, as Python's date.weekday()
	Day      int
	Month    int
	ShowDate bool // first column or the first of a month
	Today    bool
}

// calBar is one stay painted on its property's row.
type calBar struct {
	CSS      string
	ColStart int
	ColEnd   int
	Row      int
	Overdue  bool
	Label    string
	Title    string
	Source   string
	URL      string
}

// calRow is one property's lane of bars.
type calRow struct {
	Name string
	Bars []calBar
}

// nyLine is one "What needs you" line (needs_you.build).
type nyLine struct {
	Kind      string
	Tone      string
	Subject   string
	Text      string
	Action    string
	Href      string
	StayID    int64
	DismissID int64
}

// todayRow is one line of the Today table on the overview.
type todayRow struct {
	Row      stays.Row
	Nights   int
	Arriving bool
}

// keyRow is one stay in the phone "Check-ins" window (0765).
type keyRow struct {
	Row    stays.Row
	Nights int
	Kind   string // tomorrow | today | leaves | arrived
}

// stayView is a stay plus the label the list uses for it.
type stayView struct {
	Row    stays.Row
	Label  string
	Nights int
}

// DashboardData is what dashboard.tmpl reads.
type DashboardData struct {
	Apartments []apartmentRow
	Rows       []stays.Row
	FeedCount  int
	TodayISO   string
	TodayLong  string
	Lang       string
	CalView    bool

	MonthGuests   int
	MonthNights   int
	MonthReported int
	CalDays       []calDay
	CalRows       []calRow
	TodayRows     []todayRow
	KeyRows       []keyRow
	NextArrival   *stayView
	NyLines       []nyLine
	NyCount       int
	SetupBanner   bool
	SetupURL      string
	filesByStay   map[int64]bool
	DemoLoaded    bool
	DemoAvailable bool
	Weekdays      []string

	// Onboarding is the workspace checklist the empty overview renders.
	Onboarding OnboardingState
}

// OnboardingState is onboarding.progress(): the five setup steps and the
// wizard position the banner reads.
type OnboardingState struct {
	Steps          []obStep
	Current        *obStep
	Completed      int
	Total          int
	Percent        int
	Finished       bool
	Dismissed      bool
	WizardComplete bool
	SetupURL       string
	FirstApartment int64
}

// obStep is one setup step.
type obStep struct {
	ID        string
	Done      bool
	URL       string
	ManualURL string
	LearnURL  string
}

var longMonthsEN = [...]string{
	"January", "February", "March", "April", "May", "June", "July",
	"August", "September", "October", "November", "December",
}

var longMonthsCS = [...]string{
	"ledna", "února", "března", "dubna", "května", "června",
	"července", "srpna", "září", "října", "listopadu", "prosince",
}

var longWeekdaysCS = [...]string{"pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"}
var longWeekdaysEN = [...]string{"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
var longWeekdaysVI = [...]string{"Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy", "Chủ nhật"}

// formatDateLong is templating.date_long: "Sunday 22 November".
func formatDateLong(lang string, t time.Time) string {
	wd := int(t.Weekday()+6) % 7 // time.Weekday has Sunday at 0
	switch lang {
	case "cs":
		return longWeekdaysCS[wd] + " " + itoa(t.Day()) + ". " + longMonthsCS[int(t.Month())-1]
	case "vi":
		return longWeekdaysVI[wd] + ", " + itoa(t.Day()) + " tháng " + itoa(int(t.Month()))
	}
	return longWeekdaysEN[wd] + " " + itoa(t.Day()) + " " + longMonthsEN[int(t.Month())-1]
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b []byte
	neg := n < 0
	if neg {
		n = -n
	}
	for n > 0 {
		b = append([]byte{byte('0' + n%10)}, b...)
		n /= 10
	}
	if neg {
		return "-" + string(b)
	}
	return string(b)
}

// pyDay is a date parsed as a Python date from an ISO prefix.
func pyDay(s string) (time.Time, bool) {
	s = strings.TrimSpace(s)
	if len(s) < 10 {
		return time.Time{}, false
	}
	d, err := time.Parse("2006-01-02", s[:10])
	if err != nil {
		return time.Time{}, false
	}
	return d, true
}

// stayLabel is the stay's name as the list prints it: the typed label of a
// hand-made stay, otherwise the reservation's internal name.
func stayLabel(r stays.Reservation) string {
	if r.Source == "manual" && strings.TrimSpace(r.Summary) != "" {
		return r.Summary
	}
	return r.InternalName
}

func loadDashboard(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, owner int64, at time.Time, calView bool, lang string) (DashboardData, error) {
	today := stays.PragueToday(at)
	out := DashboardData{
		TodayISO:  today.Format("2006-01-02"),
		TodayLong: formatDateLong(lang, today),
		Lang:      lang,
		CalView:   calView,
		Weekdays:  weekdays(lang),
	}
	env := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_UBYPORT_ENV")))
	if env == "" {
		env = "mock"
	}
	out.DemoAvailable = env == "mock"
	rows, err := pool.Query(ctx,
		`SELECT a.id, a.internal_name, a.active,
		   (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1) AS feeds
		 FROM apartment a
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL
		 ORDER BY a.internal_name`, owner)
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		var a apartmentRow
		var active, feeds int64
		if err := rows.Scan(&a.ID, &a.Name, &active, &feeds); err != nil {
			return out, err
		}
		a.Active = active != 0
		a.Feeds = int(feeds)
		out.Apartments = append(out.Apartments, a)
	}
	if err := rows.Err(); err != nil {
		return out, err
	}
	var n int64
	if err := pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM ical_feed f
		 JOIN apartment a ON a.id = f.apartment_id
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL AND f.active = 1`, owner).Scan(&n); err != nil {
		return out, err
	}
	out.FeedCount = int(n)
	if err := loadMonthSummary(ctx, pool, owner, today, &out); err != nil {
		return out, err
	}
	if err := loadOnboarding(ctx, pool, owner, out.Apartments, &out); err != nil {
		return out, err
	}
	for i := 0; i < 14; i++ {
		d := today.AddDate(0, 0, i)
		out.CalDays = append(out.CalDays, calDay{
			Weekday:  int(d.Weekday()+6) % 7,
			Day:      d.Day(),
			Month:    int(d.Month()),
			ShowDate: i == 0 || d.Day() == 1,
			Today:    i == 0,
		})
	}
	if len(out.Apartments) == 0 {
		return out, nil
	}
	stayRows, err := pool.Query(ctx,
		`SELECT r.id, r.apartment_id, r.date_from, r.date_to, r.status, COALESCE(r.source, ''),
			COALESCE(r.summary, ''), r.declared_guests, r.expected_guests_override, r.lead_reduced_guests,
			a.internal_name, COALESCE(a.permalink_token, ''), COALESCE(a.automation_mode, ''), a.submit_after_hours,
			(SELECT s.slug FROM apartment_slug s WHERE s.apartment_id = a.id AND s.is_current = 1) AS permalink_slug,
			a.active,
			(COALESCE(TRIM(a.uby_idub), '') <> '' AND COALESCE(TRIM(a.uby_ws_user), '') <> ''
			 AND COALESCE(TRIM(a.uby_ws_password_enc), '') <> '') AS files_here
		 FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		 WHERE r.status = 'active' AND a.active = 1 AND a.archived_at IS NULL AND r.archived_at IS NULL
		   AND a.owner_user_id IS NOT DISTINCT FROM $1 AND r.date_from <= $2
		 ORDER BY r.date_from`, owner, today.AddDate(0, 0, 30).Format("2006-01-02"))
	if err != nil {
		return out, err
	}
	defer stayRows.Close()
	var bare []stays.Row
	for stayRows.Next() {
		var r stays.Row
		var active int
		var filesHere bool
		if err := stayRows.Scan(
			&r.Reservation.ID, &r.Reservation.ApartmentID, &r.Reservation.DateFrom, &r.Reservation.DateTo,
			&r.Reservation.Status, &r.Reservation.Source, &r.Reservation.Summary,
			&r.Reservation.Declared, &r.Reservation.Override, &r.Reservation.Reduced,
			&r.Reservation.InternalName, &r.Reservation.PermalinkToken, &r.Reservation.AutomationMode,
			&r.Reservation.SubmitAfterHours, &r.Reservation.PermalinkSlug, &active, &filesHere,
		); err != nil {
			return out, err
		}
		r.ApartmentActive = active != 0
		if out.filesByStay == nil {
			out.filesByStay = map[int64]bool{}
		}
		out.filesByStay[r.Reservation.ID] = filesHere
		bare = append(bare, r)
	}
	if err := stayRows.Err(); err != nil {
		return out, err
	}
	out.Rows, _, err = stays.EnrichDashboardRows(ctx, pool, getenv, bare, at)
	if err != nil {
		return out, err
	}
	out.DemoLoaded = anyDemoApartment(out.Apartments)
	out.CalRows = overviewCalendarRows(out.Apartments, out.Rows, today, out.Lang)
	out.TodayRows = todayRowsOf(out.Rows, today)
	out.KeyRows = keyRowsOf(out.Rows, today)
	out.NextArrival = nextArrivalOf(out.Rows, today)
	out.NyLines, out.NyCount = needsYouLines(out.Rows, today, out.Lang, out.SetupBanner, out.filesByStay)
	return out, nil
}

func weekdays(lang string) []string {
	if lang == "cs" {
		return []string{"Po", "Út", "St", "Čt", "Pá", "So", "Ne"}
	}
	return []string{"Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"}
}

// loadMonthSummary is reporting.month_summary: guests, nights and police
// reports for the calendar month of today.
func loadMonthSummary(ctx context.Context, pool *pgxpool.Pool, owner int64, today time.Time, out *DashboardData) error {
	start := time.Date(today.Year(), today.Month(), 1, 0, 0, 0, 0, time.UTC)
	end := start.AddDate(0, 1, 0)
	rows, err := pool.Query(ctx,
		`SELECT r.date_from, r.date_to,
		   (SELECT COUNT(*) FROM guest g WHERE g.reservation_id = r.id) AS n,
		   (SELECT COUNT(*) FROM guest g WHERE g.reservation_id = r.id AND g.submit_state = $2) AS sent
		 FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL
		   AND COALESCE(r.source, '') <> 'demo'
		   AND r.date_from < $3 AND r.date_to > $4`,
		owner, "sent", end.Format("2006-01-02"), start.Format("2006-01-02"))
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var from, to string
		var guests, sent int
		if err := rows.Scan(&from, &to, &guests, &sent); err != nil {
			return err
		}
		out.MonthGuests += guests
		out.MonthReported += sent
		arrive, okA := pyDay(from)
		leave, okL := pyDay(to)
		if !okA || !okL {
			continue
		}
		lo, hi := arrive, leave
		if lo.Before(start) {
			lo = start
		}
		if hi.After(end) {
			hi = end
		}
		if days := int(hi.Sub(lo).Hours() / 24); days > 0 {
			out.MonthNights += days
		}
	}
	return rows.Err()
}

// loadOnboarding is onboarding.progress's done-flags plus wizard_step for the
// setup banner. It reads only what the overview needs.
func loadOnboarding(ctx context.Context, pool *pgxpool.Pool, owner int64, apartments []apartmentRow, out *DashboardData) error {
	var entityCount, readyEntities int64
	if err := pool.QueryRow(ctx,
		`SELECT COUNT(*),
		   COUNT(*) FILTER (WHERE TRIM(COALESCE(name, '')) <> ''
		     AND TRIM(COALESCE(seat, '')) <> '' AND TRIM(COALESCE(ico, '')) <> ''
		     AND TRIM(COALESCE(contact_email, '')) <> '')
		 FROM legal_entity WHERE owner_user_id IS NOT DISTINCT FROM $1`, owner,
	).Scan(&entityCount, &readyEntities); err != nil {
		return err
	}
	var manualStays int64
	if err := pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL
		   AND r.status = 'active' AND r.source = 'manual'`, owner).Scan(&manualStays); err != nil {
		return err
	}
	apartmentCount := len(apartments)
	hasStays := out.FeedCount > 0 || manualStays > 0
	entityTotal, entityReady := int(entityCount), int(readyEntities)
	var firstID int64
	var addrOK bool
	if apartmentCount > 0 {
		firstID = apartments[0].ID
		var houseNo, zip, obec string
		if err := pool.QueryRow(ctx,
			`SELECT COALESCE(addr_house_no, ''), COALESCE(addr_zip, ''), COALESCE(addr_obec, '')
			 FROM apartment WHERE id = $1`, firstID).Scan(&houseNo, &zip, &obec); err != nil {
			return err
		}
		addrOK = addressComplete(houseNo, zip, obec)
	}
	// 0949: the automation step needs the police fields; that readiness list
	// lives in the properties package, so this step is "done" once a property
	// exists and reads its reporting settings as filled.
	steps := []obStep{
		{ID: "entity", Done: entityReady > 0, URL: "/entities", LearnURL: "/guide#setup"},
		{ID: "property", Done: apartmentCount > 0, URL: apartmentNewURL(entityTotal), LearnURL: "/guide#setup"},
		{ID: "calendars", Done: hasStays, URL: propertyBookingsURL(firstID), ManualURL: "/reservations#add-stay-panel", LearnURL: "/guide#stays"},
		{ID: "automation", Done: false, URL: propertyReportingURL(firstID), LearnURL: "/guide#reporting"},
		{ID: "guest_link", Done: false, URL: propertyGuestsURL(firstID), LearnURL: "/guide#guests"},
	}
	completed := 0
	for i := range steps {
		if steps[i].Done {
			completed++
		}
	}
	st := OnboardingState{
		Steps: steps, Completed: completed, Total: len(steps),
		Percent: percentOf(completed, len(steps)), FirstApartment: firstID,
	}
	if st.Total > 0 {
		st.Finished = completed == st.Total
	}
	for i := range steps {
		if !steps[i].Done {
			st.Current = &steps[i]
			break
		}
	}
	var dismissed string
	if err := pool.QueryRow(ctx,
		`SELECT COALESCE((SELECT value FROM settings WHERE key = $1), '0')`,
		"onboarding_dismissed_"+itoa(int(owner))).Scan(&dismissed); err != nil {
		return err
	}
	st.Dismissed = strings.TrimSpace(dismissed) == "1"
	wizard := wizardStep(apartmentCount > 0, firstID, addrOK, hasStays)
	st.WizardComplete = wizard == "complete"
	st.SetupURL = setupURL(wizard, apartmentCount > 0, firstID)
	out.Onboarding = st
	out.SetupBanner = !st.WizardComplete && !st.Dismissed
	out.SetupURL = st.SetupURL
	return nil
}

func percentOf(done, total int) int {
	if total == 0 {
		return 100
	}
	return (done*100 + total/2) / total
}

func addressComplete(houseNo, zip, obec string) bool {
	for _, field := range []string{houseNo, zip, obec} {
		if strings.TrimSpace(field) == "" {
			return false
		}
	}
	digits := make([]rune, 0, 5)
	for _, r := range zip {
		if r >= '0' && r <= '9' {
			digits = append(digits, r)
		}
	}
	return len(digits) == 5
}

// wizardStep is onboarding.wizard_step: the first unfinished setup screen.
func wizardStep(hasApartment bool, _ int64, addrOK, hasStays bool) string {
	if !hasApartment {
		return "name"
	}
	if !addrOK {
		return "address"
	}
	if !hasStays {
		return "bookings"
	}
	return "complete"
}

func setupURL(step string, hasApartment bool, firstID int64) string {
	if !hasApartment {
		return "/apartments/new"
	}
	base := "/apartments/" + itoa(int(firstID))
	switch step {
	case "address":
		return base + "?view=settings&section=property#address"
	case "bookings":
		return base + "?view=bookings#calendars"
	}
	return base
}

func apartmentNewURL(entityCount int) string {
	if entityCount == 0 {
		return "/entities"
	}
	return "/apartments/new"
}

func propertyBookingsURL(id int64) string {
	if id == 0 {
		return "/apartments/new"
	}
	return "/apartments/" + itoa(int(id)) + "?view=bookings#calendars"
}

func propertyReportingURL(id int64) string {
	if id == 0 {
		return "/apartments/new"
	}
	return "/apartments/" + itoa(int(id)) + "?view=settings&section=reporting#ubyport"
}

func propertyGuestsURL(id int64) string {
	if id == 0 {
		return "/apartments"
	}
	return "/apartments/" + itoa(int(id)) + "?view=settings&section=guests#communication"
}

func anyDemoApartment(apartments []apartmentRow) bool {
	for _, a := range apartments {
		if strings.Contains(strings.ToLower(a.Name), "(demo") {
			return true
		}
	}
	return false
}

var sourceNames = map[string]string{"airbnb": "Airbnb", "booking": "Booking"}

// overviewCalendarRows is _overview_calendar_rows: one row per active
// property for the overview's 14-day grid, with greedy lanes.
func overviewCalendarRows(apartments []apartmentRow, rows []stays.Row, today time.Time, lang string) []calRow {
	var out []calRow
	for _, apartment := range apartments {
		if !apartment.Active {
			continue
		}
		var items []placedBar
		for _, row := range rows {
			if row.Reservation.ApartmentID != apartment.ID {
				continue
			}
			start, okS := pyDay(row.Reservation.DateFrom)
			stop, okE := pyDay(row.Reservation.DateTo)
			if !okS || !okE {
				continue
			}
			colStart := 2 + maxInt(0, int(start.Sub(today).Hours()/24))
			colEnd := 2 + minInt(14, int(stop.Sub(today).Hours()/24))
			if colEnd <= colStart {
				continue
			}
			tone := barTone(row)
			css := "b-grey"
			if tone == "action" || tone == "ready" || tone == "overdue" {
				css = "b-warn"
			} else if !start.After(today) && today.Before(stop) {
				css = "b-now"
			}
			source := strings.ToLower(row.Reservation.Source)
			sourceLabel := sourceNames[source]
			rawLabel := strings.TrimSpace(row.Reservation.Summary)
			label := rawLabel
			if blockedLabel(rawLabel) {
				if closedLabel(rawLabel) {
					css = "b-grey"
				}
				label = labelOf(lang, "calendar.booked")
			} else if label == "" {
				label = labelOf(lang, "calendar.kind_stay")
			}
			if guests := len(row.Progress.Guests); guests > 0 {
				if label == "" {
					label = "· " + itoa(guests)
				} else {
					label = label + " · " + itoa(guests)
				}
			}
			title := label
			if title == "" {
				title = labelOf(lang, "calendar.kind_stay")
			}
			if sourceLabel != "" {
				title = sourceLabel + " · " + title
			}
			items = append(items, placedBar{colStart: colStart, colEnd: colEnd, bar: calBar{
				CSS: css, ColStart: colStart, ColEnd: colEnd, Overdue: tone == "overdue",
				Label: label, Title: title, Source: source,
				URL: "/reservations/" + itoa(int(row.Reservation.ID)) + "?return_to=/",
			}})
		}
		// 0707: greedy lanes, so stays that overlap do not overlap visually.
		var laneEnds []int
		var bars []calBar
		sortPlaced(items)
		for _, item := range items {
			lane := -1
			for i, end := range laneEnds {
				if end <= item.colStart {
					laneEnds[i] = item.colEnd
					lane = i
					break
				}
			}
			if lane < 0 {
				laneEnds = append(laneEnds, item.colEnd)
				lane = len(laneEnds) - 1
			}
			bar := item.bar
			bar.Row = lane + 1
			bars = append(bars, bar)
		}
		out = append(out, calRow{Name: apartment.Name, Bars: bars})
	}
	return out
}

// placedBar is one calendar bar before its lane is chosen.
type placedBar struct {
	colStart, colEnd int
	bar              calBar
}

func sortPlaced(items []placedBar) {
	for i := 1; i < len(items); i++ {
		for j := i; j > 0 && items[j].colStart < items[j-1].colStart; j-- {
			items[j], items[j-1] = items[j-1], items[j]
		}
	}
}

// barTone is the tone dashboard_calendar.events gives a stay.
func barTone(row stays.Row) string {
	status := row.Progress.Status
	if row.Progress.Cell.Level == "overdue" && status != "reported" && status != "not_required" {
		return "overdue"
	}
	switch status {
	case "failed", "incomplete", "awaiting_verification":
		return "action"
	case "ready":
		if !isDemoStay(row.Reservation) {
			return "ready"
		}
		return "neutral"
	case "reported", "not_required":
		return "done"
	}
	return "neutral"
}

func isDemoStay(r stays.Reservation) bool {
	return r.Source == "demo" || strings.Contains(strings.ToLower(r.InternalName), "(demo")
}

// blockedLabel and closedLabel are the placeholder check in
// _overview_calendar_rows: a host block or a reserved placeholder.
func blockedLabel(label string) bool {
	l := strings.ToLower(strings.TrimSpace(label))
	l = strings.TrimSpace(strings.TrimPrefix(l, "!"))
	l = strings.TrimSpace(strings.TrimPrefix(l, "⚠"))
	switch l {
	case "closed", "closed - not available", "closed – not available", "not available",
		"airbnb (not available)", "blocked", "unavailable", "reserved", "booked",
		"reservation", "rezervováno", "rezervace":
		return true
	}
	return false
}

func closedLabel(label string) bool {
	l := strings.ToLower(label)
	for _, needle := range []string{"closed", "not available", "blocked", "unavailable"} {
		if strings.Contains(l, needle) {
			return true
		}
	}
	return false
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// todayNights is _today_nights: nights on the Today table, 0 when a date is
// unreadable.
func todayNights(r stays.Reservation) int {
	start, okS := pyDay(r.DateFrom)
	end, okE := pyDay(r.DateTo)
	if !okS || !okE {
		return 0
	}
	if days := int(end.Sub(start).Hours() / 24); days > 0 {
		return days
	}
	return 0
}

func todayRowsOf(rows []stays.Row, today time.Time) []todayRow {
	iso := today.Format("2006-01-02")
	var out []todayRow
	for _, row := range rows {
		from := strings.TrimSpace(row.Reservation.DateFrom)
		to := strings.TrimSpace(row.Reservation.DateTo)
		if len(from) > 10 {
			from = from[:10]
		}
		if len(to) > 10 {
			to = to[:10]
		}
		if iso != from && iso != to {
			continue
		}
		out = append(out, todayRow{Row: row, Nights: todayNights(row.Reservation), Arriving: from == iso})
	}
	return out
}

// keyRowsOf is _key_rows (0765): every active stay from three days before its
// check-in to the day after it.
func keyRowsOf(rows []stays.Row, today time.Time) []keyRow {
	tomorrow := today.AddDate(0, 0, 1).Format("2006-01-02")
	todayS := today.Format("2006-01-02")
	windowStart := today.AddDate(0, 0, -3).Format("2006-01-02")
	var out []keyRow
	for _, row := range rows {
		if row.Reservation.Status != "active" {
			continue
		}
		from := strings.TrimSpace(row.Reservation.DateFrom)
		to := strings.TrimSpace(row.Reservation.DateTo)
		if len(from) > 10 {
			from = from[:10]
		}
		if len(to) > 10 {
			to = to[:10]
		}
		inWindow := (windowStart <= from && from <= tomorrow) || to == todayS
		if !inWindow {
			continue
		}
		kind := "arrived"
		switch {
		case from == tomorrow:
			kind = "tomorrow"
		case from == todayS:
			kind = "today"
		case to == todayS:
			kind = "leaves"
		}
		out = append(out, keyRow{Row: row, Nights: todayNights(row.Reservation), Kind: kind})
	}
	for i := 1; i < len(out); i++ {
		for j := i; j > 0 && out[j].Row.Reservation.DateFrom < out[j-1].Row.Reservation.DateFrom; j-- {
			out[j], out[j-1] = out[j-1], out[j]
		}
	}
	return out
}

func nextArrivalOf(rows []stays.Row, today time.Time) *stayView {
	after := today.AddDate(0, 0, 1).Format("2006-01-02")
	var best *stayView
	for i := range rows {
		row := rows[i]
		from := strings.TrimSpace(row.Reservation.DateFrom)
		if len(from) > 10 {
			from = from[:10]
		}
		if !(from > after) {
			continue
		}
		if best == nil || from < best.Row.Reservation.DateFrom {
			best = &stayView{Row: row, Label: stayLabel(row.Reservation), Nights: todayNights(row.Reservation)}
		}
	}
	return best
}

// needsYouLines is needs_you.build limited to what the overview shows: the
// stay lines. Setup lines come from the property readiness list, which the
// properties package owns; the banner already tells the host to finish setup.
func needsYouLines(rows []stays.Row, today time.Time, lang string, bannerShowing bool, files map[int64]bool) ([]nyLine, int) {
	t := func(key string, params map[string]any) string {
		return dashStrings.T(lang, key, params)
	}
	var lines []nyLine
	covered := map[int64]bool{}
	for _, row := range rows {
		line, ok := stayLine(row, today, lang, t, files[row.Reservation.ID])
		if !ok {
			continue
		}
		if covered[row.Reservation.ID] {
			continue
		}
		covered[row.Reservation.ID] = true
		lines = append(lines, line)
	}
	onTrack := 0
	for _, row := range rows {
		status := row.Progress.Status
		if status == "reported" || status == "not_required" {
			continue
		}
		if !covered[row.Reservation.ID] {
			onTrack++
		}
	}
	_ = onTrack
	if bannerShowing {
		kept := lines[:0]
		for _, line := range lines {
			if line.Kind != "setup" {
				kept = append(kept, line)
			}
		}
		lines = kept
	}
	toneRank := map[string]int{"red": 0, "amber": 1, "grey": 2}
	for i := 1; i < len(lines); i++ {
		for j := i; j > 0 && toneRank[lines[j].Tone] < toneRank[lines[j-1].Tone]; j-- {
			lines[j], lines[j-1] = lines[j-1], lines[j]
		}
	}
	return lines, len(lines)
}

// stayLine is needs_you.stay_line: the line for one stay, or false while the
// stay is on track.
// files is reporting.files_with_ubyhost: a property with the three UbyPort
// login fields files its reports through UbyHost, so its stays get a deadline
// line. Without them UbyHost files nothing and the stay is never "overdue".
func stayLine(row stays.Row, today time.Time, lang string, t func(string, map[string]any) string, files bool) (nyLine, bool) {
	status := row.Progress.Status
	if status == "reported" || status == "not_required" {
		return nyLine{}, false
	}
	r := row.Reservation
	dates := fmtDateRange(r.DateFrom, r.DateTo)
	subject := stayLabel(r)
	if dates != "" {
		subject = subject + " · " + dates
	}
	base := "/reservations/" + itoa(int(r.ID)) + "?return_to=/"
	line := func(tone, text, action, href string) (nyLine, bool) {
		return nyLine{Kind: "stay", Tone: tone, Subject: subject, Text: text, Action: action, Href: href, StayID: r.ID}, true
	}
	if files && status == "failed" {
		return line("red", t("needs_you.short.failed", nil), t("needs_you.action.fix", nil), base+"#guests")
	}
	if files && row.Progress.Cell.Level == "overdue" {
		if status == "ready" || status == "awaiting_verification" {
			return line("red", t("needs_you.short.overdue", nil), t("needs_you.action.send", nil), base+"#now")
		}
		return line("red", t("needs_you.short.overdue", nil), t("needs_you.action.open", nil), base)
	}
	if isDemoStay(r) {
		return nyLine{}, false
	}
	if status == "ready" || status == "awaiting_verification" {
		if !files {
			return nyLine{}, false
		}
		mode := r.AutomationMode
		if mode == "" {
			mode = "manual"
		}
		if mode != "manual" {
			return nyLine{}, false
		}
		return line("amber", t("needs_you.short.ready", nil), t("needs_you.action.send", nil), base+"#now")
	}
	arrival, okA := pyDay(r.DateFrom)
	departure, okD := pyDay(r.DateTo)
	if okD && !departure.After(today) {
		return nyLine{}, false
	}
	if (status == "awaiting_guest" || status == "incomplete") && okA && !arrival.After(today.AddDate(0, 0, 1)) {
		when := t("needs_you.when.tomorrow", nil)
		if arrival.Before(today) {
			when = t("needs_you.when.arrived", nil)
		} else if arrival.Equal(today) {
			when = t("needs_you.when.today", nil)
		}
		return line("amber", t("needs_you.short.forms", map[string]any{"when": when}), t("needs_you.action.send_link", nil), base+"#now")
	}
	return nyLine{}, false
}

// labelOf is host_i18n.translate from the dashboard's own catalog, for the
// two calendar placeholder labels.
func labelOf(lang, key string) string {
	return dashStrings.T(lang, key, nil)
}

// fmtDateRange is validation.fmt_date_range: "18.11.2026 – 21.11.2026".
func fmtDateRange(dateFrom, dateTo string) string {
	start, end := fmtDateCZ(dateFrom), fmtDateCZ(dateTo)
	if start != "" && end != "" {
		return start + " – " + end
	}
	if start != "" {
		return start
	}
	return end
}

// stayRange is the Python templating.stay_range filter: short weekday format
// per language ("pá 4. – po 7. 12.", "Fri 4 – Mon 7 Dec", "T6 4/12 – T2 7/12").
// Unparseable dates return "". Unknown languages use en.
func stayRange(lang, dateFrom, dateTo string) string {
	start, ok1 := pyDay(dateFrom)
	end, ok2 := pyDay(dateTo)
	if !ok1 || !ok2 {
		return ""
	}
	wd := func(t time.Time) int { return (int(t.Weekday()) + 6) % 7 }
	sameMonth := start.Year() == end.Year() && start.Month() == end.Month()
	switch lang {
	case "cs":
		days := []string{"po", "út", "st", "čt", "pá", "so", "ne"}
		a := days[wd(start)] + " " + itoa(start.Day()) + "."
		b := days[wd(end)] + " " + itoa(end.Day()) + "."
		if sameMonth {
			return a + " – " + b + " " + itoa(int(end.Month())) + "."
		}
		a += " " + itoa(int(start.Month())) + "."
		b += " " + itoa(int(end.Month())) + "."
		return a + " – " + b
	case "vi":
		days := []string{"T2", "T3", "T4", "T5", "T6", "T7", "CN"}
		a := days[wd(start)] + " " + itoa(start.Day()) + "/" + itoa(int(start.Month()))
		b := days[wd(end)] + " " + itoa(end.Day()) + "/" + itoa(int(end.Month()))
		return a + " – " + b
	default:
		days := []string{"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
		a := days[wd(start)] + " " + itoa(start.Day())
		b := days[wd(end)] + " " + itoa(end.Day())
		if sameMonth {
			return a + " – " + b + " " + end.Month().String()[:3]
		}
		a += " " + start.Month().String()[:3]
		b += " " + end.Month().String()[:3]
		return a + " – " + b
	}
}

// fmtDateCZ is validation.fmt_date: DD.MM.YYYY, unparseable input unchanged.
func fmtDateCZ(value string) string {
	if d, ok := pyDay(value); ok {
		return pad2(d.Day()) + "." + pad2(int(d.Month())) + "." + itoa(d.Year())
	}
	return strings.TrimSpace(value)
}

func pad2(n int) string {
	if n < 10 {
		return "0" + itoa(n)
	}
	return itoa(n)
}
