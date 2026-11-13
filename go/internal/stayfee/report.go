package stayfee

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"golang.org/x/text/unicode/norm"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	inpassDoc = "INPASS"
	// maxResidence is validation.MAX_RESIDENCE.
	maxResidence = 255
)

// Group is stay_fee.report_group: one hlášení and register per facility.
type Group struct {
	Anchor       *Apartment
	VS           string
	Cadence      string
	First, Last  time.Time
	Label        string
	Periods      []*Period
	LiableNights int
	ExemptNights int
	TotalCZK     int
}

// ReportGroup is stay_fee.report_group with the period given (nil for an
// inactive property). cadence is only read when period is nil.
func ReportGroup(ap *Apartment, month time.Time, period *Period, cadence string) *Group {
	g := &Group{Anchor: ap, VS: VSOf(ap), Periods: []*Period{}}
	if period != nil {
		g.Periods = append(g.Periods, period)
		g.Cadence, g.First, g.Last = period.Cadence, period.First, period.Last
		g.Label = period.Label
		if g.Label == "" {
			g.Label = PeriodLabelCS(g.Cadence, g.First)
		}
	} else {
		g.Cadence = ChooseCadence(ap, cadence)
		g.First, g.Last = PeriodBounds(g.Cadence, month)
		g.Label = PeriodLabelCS(g.Cadence, month)
	}
	for _, p := range g.Periods {
		g.LiableNights += p.LiableNights
		g.ExemptNights += p.ExemptNights
		g.TotalCZK += p.TotalCZK
	}
	return g
}

// IssueContext is what report_issues reads from the database: the payer row
// (nil when the apartment has none) and whether a sealed filing that is not
// this period intersects it (stay_fee_filing.foreign_overlap).
type IssueContext struct {
	Entity         *Entity
	ForeignOverlap bool
}

// ReportIssues is stay_fee.report_issues: the host-UI keys that block
// finalization, in Python's order, without duplicates. Empty means ready.
func ReportIssues(g *Group, today time.Time, ic IssueContext) []string {
	anchor := g.Anchor
	issues := []string{}
	if !PeriodComplete(g.Cadence, g.First, today) {
		issues = append(issues, "stay_fees.issue.period_running")
	}
	if g.VS == "" {
		issues = append(issues, "stay_fees.issue.no_vs")
	}
	if strings.TrimSpace(anchor.AuthorityName) == "" {
		issues = append(issues, "stay_fees.issue.no_authority")
	}
	if ic.Entity == nil || strings.TrimSpace(ic.Entity.Name) == "" {
		issues = append(issues, "stay_fees.issue.no_payer")
	}
	for _, p := range g.Periods {
		for _, line := range p.Lines {
			if line.ThresholdNights {
				rule := strings.TrimSpace(anchor.ScopeRule)
				ref := strings.TrimSpace(anchor.ScopeReference)
				if !inList(ScopeRules, rule) || len([]rune(ref)) < 3 {
					issues = append(issues, "stay_fees.issue.scope_ruling")
				}
			}
		}
	}
	if ic.ForeignOverlap {
		issues = append(issues, "stay_fees.issue.overlaps_saved")
	}
	seen := map[string]bool{}
	out := []string{}
	for _, i := range issues {
		if !seen[i] {
			seen[i] = true
			out = append(out, i)
		}
	}
	return out
}

// --- payment ------------------------------------------------------------------

// Payment is stay_fee.payment_details without the QR image.
type Payment struct {
	Account     string `json:"account"`
	IBAN        string `json:"iban"`
	IBANDisplay string `json:"iban_display"`
	VS          string `json:"vs"`
	SPAYD       string `json:"spayd"`
}

// PaymentDetails is stay_fee.payment_details: nil when the council account is
// unset. The QR image (payments.qr_data_uri) is not part of this port: render
// SPAYD with the payments package.
func PaymentDetails(g *Group) *Payment {
	iban := g.Anchor.CouncilIBAN
	if iban == "" {
		return nil
	}
	payload := ""
	if g.VS != "" && g.TotalCZK > 0 {
		payload = SPAYD(iban, g.TotalCZK, g.VS, "POPLATEK Z POBYTU "+g.VS)
	}
	return &Payment{Account: g.Anchor.CouncilAccount, IBAN: iban, IBANDisplay: FormatIBAN(iban),
		VS: g.VS, SPAYD: payload}
}

// FormatIBAN is payments.format_iban: groups of four characters.
func FormatIBAN(iban string) string {
	runes := []rune(iban)
	var parts []string
	for i := 0; i < len(runes); i += 4 {
		parts = append(parts, string(runes[i:min(i+4, len(runes))]))
	}
	return strings.Join(parts, " ")
}

const qrChars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $+-./:"

// ASCIIUpper is payments.ascii_upper: NFKD, drop combining marks, upper, keep
// only the QR character set (others become spaces), collapse spaces, cut to
// limit characters.
func ASCIIUpper(text string, limit int) string {
	var up strings.Builder
	for _, r := range norm.NFKD.String(text) {
		if norm.NFC.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		up.WriteString(pyUpper(string(r)))
	}
	var b strings.Builder
	lastSpace := false
	for _, r := range up.String() {
		if !strings.ContainsRune(qrChars, r) {
			r = ' '
		}
		if r == ' ' {
			if lastSpace {
				continue
			}
			lastSpace = true
		} else {
			lastSpace = false
		}
		b.WriteRune(r)
	}
	plain := []rune(strings.TrimSpace(b.String()))
	if len(plain) > limit {
		plain = plain[:limit]
	}
	return strings.TrimRight(string(plain), " ")
}

// SPAYD is payments.spayd without a BIC: the QR Platba string for a whole-CZK amount.
func SPAYD(iban string, amountCZK int, vs, message string) string {
	return strings.Join([]string{"SPD", "1.0", "ACC:" + iban, "AM:" + strconv.Itoa(amountCZK) + ".00",
		"CC:CZK", "X-VS:" + vs, "MSG:" + ASCIIUpper(message, 60)}, "*")
}

// --- pay ways (brief 1071) ---------------------------------------------------

var (
	accountRE = regexp.MustCompile(`^(?:([0-9]{1,6})-)?([0-9]{2,10})/([0-9]{4})$`)
	ibanRE    = regexp.MustCompile(`^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$`)
	weights   = [10]int{6, 3, 7, 9, 10, 5, 8, 4, 2, 1}
	railOrder = []string{"iban", "revolut", "cash"}
)

func mod11OK(digits string) bool {
	padded := strings.Repeat("0", max(0, 10-len(digits))) + digits
	sum := 0
	for i, c := range padded {
		sum += int(c-'0') * weights[i]
	}
	return sum%11 == 0
}

func ibanOK(iban string) bool {
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

// NormaliseAccount is payments.normalise_account: the IBAN of a Czech account
// or IBAN string; ok false where Python raises ValueError.
func NormaliseAccount(raw string) (string, bool) {
	text := strings.ToUpper(strings.Map(func(r rune) rune {
		if unicode.IsSpace(r) {
			return -1
		}
		return r
	}, raw))
	if ibanRE.MatchString(text) {
		return text, ibanOK(text)
	}
	m := accountRE.FindStringSubmatch(text)
	if m == nil {
		return "", false
	}
	prefix, number, bank := m[1], m[2], m[3]
	if (prefix != "" && !mod11OK(prefix)) || !mod11OK(number) {
		return "", false
	}
	bban := bank + strings.Repeat("0", 6-len(prefix)) + prefix + strings.Repeat("0", 10-len(number)) + number
	mod := 0
	for _, c := range bban + "123500" {
		mod = (mod*10 + int(c-'0')) % 97
	}
	return fmt.Sprintf("CZ%02d%s", 98-mod, bban), true
}

// PayoutAccount is stay_fee.payout_account: (account, payee) of the operator
// guests pay, or empty strings. entity is the apartment's legal entity or nil.
func PayoutAccount(entity *Entity) (string, string) {
	if entity == nil {
		return "", ""
	}
	payee := strings.TrimSpace(entity.Name)
	account := ""
	if entity.IBAN != "" {
		account = entity.IBAN
	} else if entity.BankAccount != "" {
		if iban, ok := NormaliseAccount(entity.BankAccount); ok {
			account = iban
		}
	}
	return account, payee
}

// UsableRailKeys is stay_fee.usable_rail_keys: the guest pay ways that work for
// the property, in the order the guest sees them.
func UsableRailKeys(ap *Apartment, entity *Entity) []string {
	enabled := map[string]bool{}
	for _, part := range strings.Split(ap.GuestRails, ",") {
		if part != "" {
			enabled[part] = true
		}
	}
	if enabled["qr"] {
		enabled["iban"] = true
	}
	first := ap.GuestDefaultRail
	if first == "qr" {
		first = "iban"
	}
	order := []string{}
	if inList(railOrder, first) {
		order = append(order, first)
	}
	for _, k := range railOrder {
		if k != first {
			order = append(order, k)
		}
	}
	account, _ := PayoutAccount(entity)
	usable := []string{}
	for _, key := range order {
		if !enabled[key] || (key == "iban" && account == "") || (key == "revolut" && ap.RevolutLink == "") {
			continue
		}
		usable = append(usable, key)
	}
	return usable
}

// NoPayWay is stay_fee.no_pay_way. guestPay is config.STAY_FEE_GUEST_PAY
// (UBYHOST_STAY_FEE_GUEST_PAY=on).
func NoPayWay(ap *Apartment, entity *Entity, guestPay bool) bool {
	return ap.Collect && IsActive(ap) && guestPay && ap.ArchivedAt == "" && len(UsableRailKeys(ap, entity)) == 0
}

// --- hlášení (the PDF input) --------------------------------------------------

// Rate-row of the hlášení: one per facility and rate.
type HlaseniRow struct {
	PropertyName    string `json:"property_name"`
	PropertyAddress string `json:"property_address"`
	LiableNights    int    `json:"liable_nights"`
	RateCZK         int    `json:"rate_czk"`
	AmountCZK       int    `json:"amount_czk"`
}

// NotCharged is a "not charged" bucket of the hlášení.
type NotCharged struct {
	Reason string `json:"reason"`
	Count  int    `json:"count"`
	Nights int    `json:"nights"`
}

// Hlaseni is stay_fee.hlaseni: the report object the remittance PDF draws.
type Hlaseni struct {
	PayerName        string       `json:"payer_name"`
	PayerSeat        string       `json:"payer_seat"`
	PayerICO         string       `json:"payer_ico"`
	PayerContact     string       `json:"payer_contact"`
	VS               string       `json:"vs"`
	RecipientName    string       `json:"recipient_name"`
	RecipientAddress string       `json:"recipient_address"`
	RecipientContact string       `json:"recipient_contact"`
	Payee            string       `json:"payee"`
	Instruction      string       `json:"instruction"`
	Cadence          string       `json:"cadence"`
	PeriodStart      string       `json:"period_start"`
	PeriodEnd        string       `json:"period_end"`
	IssuedOn         string       `json:"issued_on"`
	Rows             []HlaseniRow `json:"rows"`
	LiableNights     int          `json:"liable_nights"`
	ExemptNights     int          `json:"exempt_nights"`
	TotalCZK         int          `json:"total_czk"`
	NotCharged       []NotCharged `json:"not_charged"`
	SignaturePNG     string       `json:"signature_png"`
	SignatureName    string       `json:"signature_name"`
}

const (
	exemptLabelMinor = "Mladší 18 let"
	exemptLabelHost  = "Osvobozeno ubytovatelem (důvod v evidenční knize)"
	// RegisterHostLine is the register line for bed-days the host entered without guest records.
	RegisterHostLine = "přenocování bez záznamu hosta (doplněno ubytovatelem)"
	// RestrictedNote is appended to the exemption reason of a restricted guest.
	RestrictedNote = "zpracování omezeno (čl. 18 GDPR)"
)

func joinNonEmpty(sep string, parts ...string) string {
	var out []string
	for _, p := range parts {
		if p != "" {
			out = append(out, p)
		}
	}
	return strings.Join(out, sep)
}

// PropertyAddress is stay_fee.property_address.
func PropertyAddress(ap *Apartment) string {
	number := joinNonEmpty("/", ap.AddrHouseNo, ap.AddrOrientNo)
	street := joinNonEmpty(" ", ap.AddrStreet, number)
	town := joinNonEmpty(" ", ap.AddrZip, ap.AddrObec)
	return joinNonEmpty(", ", street, town)
}

// MakeHlaseni is stay_fee.hlaseni(group, issued_on). entity is the payer
// (SignaturePNG decrypted); nil is an error, as the Python call raises.
func MakeHlaseni(g *Group, issuedOn time.Time, entity *Entity) (*Hlaseni, error) {
	if entity == nil {
		return nil, fmt.Errorf("stayfee: apartment %d has no legal entity", g.Anchor.ID)
	}
	anchor := g.Anchor
	rows := []HlaseniRow{}
	minors, hosts := NotCharged{Reason: exemptLabelMinor}, NotCharged{Reason: exemptLabelHost}
	for _, p := range g.Periods {
		segments := p.RateSegments
		if len(segments) == 0 {
			segments = [][2]int{{p.RateCZK, p.LiableNights}}
		}
		for _, seg := range segments {
			rows = append(rows, HlaseniRow{PropertyName: p.Apartment.InternalName,
				PropertyAddress: PropertyAddress(p.Apartment), LiableNights: seg[1], RateCZK: seg[0],
				AmountCZK: seg[1] * seg[0]})
		}
		for _, line := range p.Lines {
			if line.ExemptNights > 0 {
				bucket := &hosts
				if line.AutoMinor || line.Status == "liable" {
					bucket = &minors
				}
				bucket.Count++
				bucket.Nights += line.ExemptNights
			}
		}
	}
	notCharged := []NotCharged{}
	for _, b := range []NotCharged{minors, hosts} {
		if b.Count > 0 {
			notCharged = append(notCharged, b)
		}
	}
	return &Hlaseni{
		PayerName: entity.Name, PayerSeat: entity.Seat, PayerICO: entity.ICO, PayerContact: entity.ContactEmail,
		VS: g.VS, RecipientName: anchor.AuthorityName, RecipientAddress: anchor.AuthorityAddress,
		RecipientContact: anchor.AuthorityContact, Payee: strings.TrimSpace(anchor.Payee),
		Instruction: anchor.Instruction, Cadence: g.Cadence, PeriodStart: ISO(g.First), PeriodEnd: ISO(g.Last),
		IssuedOn: ISO(issuedOn), Rows: rows, LiableNights: g.LiableNights, ExemptNights: g.ExemptNights,
		TotalCZK: g.TotalCZK, NotCharged: notCharged, SignaturePNG: entity.SignaturePNG,
		SignatureName: entity.SignatureName,
	}, nil
}

// --- the register (evidenční kniha, §3g) ---------------------------------------

// RegisterRow is one register line; the JSON tags are the Python dict keys.
type RegisterRow struct {
	Property       string `json:"property"`
	Period         string `json:"period"`
	StayFrom       string `json:"stay_from"`
	StayTo         string `json:"stay_to"`
	Surname        string `json:"surname"`
	FirstName      string `json:"first_name"`
	HomeAddress    string `json:"home_address"`
	BirthDate      string `json:"birth_date"`
	DocType        string `json:"doc_type"`
	DocNumber      string `json:"doc_number"`
	Nights         int    `json:"nights"`
	RateCZK        int    `json:"rate_czk"`
	AmountCZK      int    `json:"amount_czk"`
	ExemptReason   string `json:"exempt_reason"`
	VS             string `json:"vs"`
	CouncilAccount string `json:"council_account"`
}

// RegisterColumns is stay_fee.REGISTER_COLUMNS: the CSV header labels in order.
var RegisterColumns = []string{"Zařízení", "Období", "Den počátku pobytu", "Den konce pobytu", "Příjmení",
	"Jméno", "Adresa místa přihlášení / v zahraničí", "Datum narození", "Druh průkazu", "Číslo průkazu",
	"Nocí v období", "Sazba (Kč)", "Poplatek (Kč)", "Důvod osvobození", "Variabilní symbol", "Účet obce"}

// fmtDate is validation.fmt_date: DD.MM.YYYY, an unparseable value unchanged.
func fmtDate(value string) string {
	if t, ok := validation.ParseISODate(value); ok {
		return t.Format("02.01.2006")
	}
	return value
}

// composeResidence is validation.compose_residence in Czech.
func composeResidence(street, city, country string) string {
	var parts []string
	if street != "" {
		parts = append(parts, street)
	}
	if city != "" {
		parts = append(parts, city)
	}
	if country != "" {
		parts = append(parts, country+"-"+countries.Name(country, "cs"))
	}
	out := []rune(strings.Join(parts, ", "))
	if len(out) > maxResidence {
		out = out[:maxResidence]
	}
	return string(out)
}

// formatBirthDate is validation.format_birth_date.
func formatBirthDate(v string) string {
	if len(v) != 8 {
		return v
	}
	return v[:2] + "." + v[2:4] + "." + v[4:]
}

// RegisterRows is stay_fee.register_rows. guests maps every line's guest id to
// its full row (archived guests included, as Python reads them by id).
func RegisterRows(p *Period, guests map[int64]GuestRow) ([]RegisterRow, error) {
	ap := p.Apartment
	vs := VSOf(ap)
	rows := []RegisterRow{}
	for _, line := range p.Lines {
		g, ok := guests[line.GuestID]
		if !ok {
			return nil, fmt.Errorf("stayfee: guest %d not loaded", line.GuestID)
		}
		reason := ""
		switch line.Status {
		case "exempt":
			reason = line.Reason
			if reason == "" && line.AutoMinor {
				reason = "mladší 18 let"
			}
		case "not_subject":
			reason = "pobyt delší než 60 dnů (není předmětem poplatku)"
		}
		docNumber := g.DocNumber
		if docNumber == inpassDoc {
			docNumber = "zapsán v dokladu rodiče"
		}
		row := RegisterRow{
			Property: ap.InternalName, Period: p.Label,
			StayFrom: fmtDate(line.StayFrom), StayTo: fmtDate(line.StayTo),
			Surname: g.Surname, FirstName: g.FirstName,
			HomeAddress: composeResidence(g.ResStreet, g.ResCity, strings.ToUpper(g.ResCountry)),
			BirthDate:   formatBirthDate(g.BirthDate), DocType: DocTypeLabelsCS[DocTypeOf(g)],
			DocNumber: docNumber, Nights: line.Nights, RateCZK: p.RateCZK, AmountCZK: line.AmountCZK,
			ExemptReason: reason, VS: vs, CouncilAccount: ap.CouncilAccount,
		}
		if line.Restricted {
			row.ExemptReason = strings.Trim(row.ExemptReason+"; "+RestrictedNote, "; ")
		}
		rows = append(rows, row)
	}
	if delta := p.AdjustmentBedDays; delta != 0 {
		rows = append(rows, RegisterRow{Property: ap.InternalName, Period: p.Label, Nights: delta,
			RateCZK: p.RateCZK, AmountCZK: delta * p.RateCZK, ExemptReason: RegisterHostLine, VS: vs,
			CouncilAccount: ap.CouncilAccount})
	}
	return rows, nil
}

// csvSafe is csv_safety.csv_safe: a text cell Excel would evaluate gets an apostrophe.
func csvSafe(v string) string {
	trimmed := strings.TrimLeft(v, " ")
	for _, prefix := range []string{"=", "+", "-", "@", "\t", "\r", "\n", nbsp} {
		if strings.HasPrefix(trimmed, prefix) {
			return "'" + v
		}
	}
	return v
}

// csvField is csv.writer's QUOTE_MINIMAL for ";" and \r\n.
func csvField(v string) string {
	if strings.ContainsAny(v, ";\"\r\n") {
		return "\"" + strings.ReplaceAll(v, "\"", "\"\"") + "\""
	}
	return v
}

// RegisterCSV is stay_fee.register_csv: ";"-separated, \r\n line ends, UTF-8
// with a byte order mark.
func RegisterCSV(rows []RegisterRow) []byte {
	var b strings.Builder
	b.WriteString(bom)
	writeRow := func(cells []string) {
		for i, c := range cells {
			if i > 0 {
				b.WriteByte(';')
			}
			b.WriteString(csvField(c))
		}
		b.WriteString("\r\n")
	}
	writeRow(RegisterColumns)
	for _, r := range rows {
		writeRow([]string{csvSafe(r.Property), csvSafe(r.Period), csvSafe(r.StayFrom), csvSafe(r.StayTo),
			csvSafe(r.Surname), csvSafe(r.FirstName), csvSafe(r.HomeAddress), csvSafe(r.BirthDate),
			csvSafe(r.DocType), csvSafe(r.DocNumber), strconv.Itoa(r.Nights), strconv.Itoa(r.RateCZK),
			strconv.Itoa(r.AmountCZK), csvSafe(r.ExemptReason), csvSafe(r.VS), csvSafe(r.CouncilAccount)})
	}
	return []byte(b.String())
}
