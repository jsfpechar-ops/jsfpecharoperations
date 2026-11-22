package stays

// Brief 2018: the host guest form (/reservations/{id}/guests/new and
// /guests/{id}) as a real page on the shell. The markup is
// templates/guest_form_admin.tmpl, a block-for-block port of Python's
// App/app/templates/guest_form_admin.html; this file builds its data.

import (
	"html/template"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices"
)

// guestFormRes is the reservation the Python template receives.
type guestFormRes struct {
	ID           int64
	InternalName string
	DateFrom     string
	DateTo       string
}

// guestFormValues is the guest row as the form echoes it back. BirthDate is
// already the display form (DD.MM.YYYY) and the stamp fields are local time.
type guestFormValues struct {
	ID          int64
	SubmitState string
	LastErrors  string
	Surname     string
	FirstName   string
	BirthDate   string
	Nationality string
	DocNumber   string
	VisaNumber  string
	ResStreet   string
	ResCity     string
	ResCountry  string
	Purpose     string
	Note        string
	SignedAt    string
	SubmittedAt string
	ManualFiled string
	Restricted  bool
}

// guestFormCode is one <option>: the value, its visible label and, for the doc
// types, the i18n key the label comes from.
type guestFormCode struct {
	Code     string
	Label    string
	Key      string
	Selected bool
}

// guestFormData is the template's dot.
type guestFormData struct {
	Reservation       guestFormRes
	Guest             *guestFormValues
	Issues            []validation.Issue
	Editing           bool
	IdentityHidden    bool
	Filed             bool
	SignatureValue    string
	DocNumberShown    string
	VisaNumberShown   string
	DocTypes          []guestFormCode
	SelectedDocType   string
	Countries         []guestFormCode
	Purposes          []guestFormCode
	HasPassportPhoto  bool
	PassportIsPDF     bool
	NeedsVerification bool
	StayFrom          string
	StayTo            string
	CSRF              string
	MetaText          string
}

// guestFormView is what the four handlers hand over; writeHostGuestForm turns
// it into the template data above.
type guestFormView struct {
	Reservation    hostReservation
	Guest          *hostGuest
	Issues         []validation.Issue
	Editing        bool
	Lang           string
	CSRF           string
	Access         guestRevealAccess
	IdentityHidden bool
}

// guestVal is field_val: the guest's value, or empty when there is no guest.
func guestVal(g *guestFormValues, field string) string {
	if g == nil {
		return ""
	}
	switch field {
	case "surname":
		return g.Surname
	case "first_name":
		return g.FirstName
	case "doc_number":
		return g.DocNumber
	case "visa_number":
		return g.VisaNumber
	case "res_street":
		return g.ResStreet
	case "res_city":
		return g.ResCity
	case "note":
		return g.Note
	}
	return ""
}

// guestBad is bad(field): "bad" when an error-severity issue names the field.
func guestBad(issues []validation.Issue, field string) string {
	for _, i := range issues {
		if i.Field == field && i.Severity == "error" {
			return "bad"
		}
	}
	return ""
}

// guestErrFor is err_for(field): one div per issue of that field.
func guestErrFor(issues []validation.Issue, field string) template.HTML {
	var b strings.Builder
	for _, i := range issues {
		if i.Field != field {
			continue
		}
		class := "ui-help"
		if i.Severity == "error" {
			class = "ui-error"
		}
		b.WriteString(`<div class="` + class + `">` + template.HTMLEscapeString(i.Message) + `</div>`)
	}
	return template.HTML(b.String())
}

// displayBirthDate is validation.display_birth_date: DD.MM.YYYY for a stored
// DDMMYYYY, otherwise the value as typed.
func displayBirthDate(value string) string {
	normalised := normaliseBirthDate(value)
	if len(normalised) == 8 && asciiDigits(normalised) {
		return normalised[:2] + "." + normalised[2:4] + "." + normalised[4:]
	}
	return strings.TrimSpace(value)
}

func asciiDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

// normaliseBirthDate is validation.normalise_birth_date: DDMMYYYY, separator
// tolerant, 0 keeping an unknown day or month.
func normaliseBirthDate(value string) string {
	raw := strings.TrimSpace(value)
	if raw == "" {
		return ""
	}
	separated := strings.NewReplacer("/", ".", "-", ".").Replace(raw)
	var kept strings.Builder
	for _, r := range separated {
		if (r >= '0' && r <= '9') || r == '.' {
			kept.WriteRune(r)
		}
	}
	if strings.Contains(kept.String(), ".") {
		var parts []string
		for _, p := range strings.Split(kept.String(), ".") {
			if p != "" {
				parts = append(parts, p)
			}
		}
		if len(parts) == 3 {
			day, month, year := atoiOr0(parts[0]), atoiOr0(parts[1]), parts[2]
			if len(year) == 2 {
				year = expandTwoDigitYear(year)
			}
			return pad2(day) + pad2(month) + padLeft4(year)
		}
	}
	var digits strings.Builder
	for _, r := range raw {
		if r >= '0' && r <= '9' {
			digits.WriteRune(r)
		}
	}
	switch digits.Len() {
	case 8:
		return digits.String()
	case 6:
		d := digits.String()
		return d[:4] + expandTwoDigitYear(d[4:])
	}
	return digits.String()
}

func atoiOr0(s string) int {
	n := 0
	for _, r := range s {
		if r < '0' || r > '9' {
			return 0
		}
		n = n*10 + int(r-'0')
	}
	return n
}

func pad2(n int) string { return strconv.Itoa(100 + n)[1:] }

func padLeft4(s string) string {
	for len(s) < 4 {
		s = "0" + s
	}
	return s
}

// expandTwoDigitYear is validation's window: 00-29 is the 2000s, the rest the
// 1900s.
func expandTwoDigitYear(s string) string {
	if len(s) != 2 {
		return padLeft4(s)
	}
	if atoiOr0(s) <= 29 {
		return "20" + s
	}
	return "19" + s
}

// guestStamp is datetime_local for the banner and the signature note.
func guestStamp(value string) string {
	text := strings.TrimSpace(value)
	if text == "" || text == "None" {
		return ""
	}
	for _, iso := range []string{
		"2006-01-02T15:04:05", "2006-01-02 15:04:05",
		"2006-01-02T15:04", "2006-01-02 15:04", "2006-01-02",
	} {
		parsed, err := time.Parse(iso, text)
		if err != nil {
			continue
		}
		return parsed.In(prague).Format("2006-01-02 15:04")
	}
	r := []rune(text)
	if len(r) > 16 {
		r = r[:16]
	}
	return strings.ReplaceAll(string(r), "T", " ")
}

// guestFormStayFrom is the stay_from input: the guest's own date, else the
// reservation's.
func guestFormStayFrom(g *hostGuest, res hostReservation) string {
	if g != nil && g.stayFrom != "" {
		return g.stayFrom
	}
	return res.dateFrom
}

func guestFormStayTo(g *hostGuest, res hostReservation) string {
	if g != nil && g.stayTo != "" {
		return g.stayTo
	}
	return res.dateTo
}

// guestPurposes is codelists.purpose_options("en"): the bundled sentence-case
// label, so the select never shows "10 - TURISTIKA". A code the bundle does
// not carry keeps the code, as Python's fallback does for an unknown row.
func guestPurposes(fetched [][2]string) []guestFormCode {
	out := make([]guestFormCode, 0, len(guestPurposeCodes)+len(fetched))
	bundled := make(map[string]string, len(guestPurposeCodes))
	for _, p := range guestPurposeCodes {
		bundled[p[0]] = p[1]
	}
	for _, p := range fetched {
		code := p[0]
		label := bundled[code]
		if label == "" {
			label = p[1]
		}
		if label == "" {
			label = code
		}
		out = append(out, guestFormCode{Code: code, Label: label})
	}
	if len(out) == 0 {
		for _, p := range guestPurposeCodes {
			out = append(out, guestFormCode{Code: p[0], Label: p[1]})
		}
	}
	return out
}

// guestPurposeCodes is validation.PURPOSES: code, sentence-case label.
var guestPurposeCodes = [][2]string{
	{"00", "Medical"},
	{"01", "Business"},
	{"02", "Cultural"},
	{"03", "Visiting family or friends"},
	{"04", "Invitation"},
	{"05", "Official (political)"},
	{"06", "Self-employment"},
	{"07", "Sport"},
	{"10", "Tourism"},
	{"11", "Study (training, internship)"},
	{"12", "Transit"},
	{"13", "Airport transit"},
	{"27", "Employment"},
	{"93", "ADS visa (Chinese nationals)"},
	{"99", "Other"},
}

// guestDocTypes is validation.DOC_TYPES with its i18n key.
func guestDocTypes() []guestFormCode {
	out := make([]guestFormCode, len(stayfee.DocTypes))
	for i, code := range stayfee.DocTypes {
		out[i] = guestFormCode{Code: code, Key: "guest.doc_type." + code}
	}
	return out
}

// guestSelectedDocType is stay_fee.doc_type_of(guest), else the default.
func guestSelectedDocType(g *hostGuest) string {
	if g != nil && g.docType != "" {
		for _, code := range stayfee.DocTypes {
			if code == g.docType {
				return code
			}
		}
	}
	return stayfee.DefaultDocType("")
}

// maskIdentifier is access.mask_identifier: all but the last three hidden.
func maskIdentifier(value string) string {
	const keep = 3
	if value == "" {
		return ""
	}
	if len(value) <= keep {
		return strings.Repeat("\u2022", keep)
	}
	return strings.Repeat("\u2022", keep) + value[len(value)-keep:]
}

// passportPhotoOnDisk is passport_photos.has_photo.
func passportPhotoOnDisk(getenv func(string) string, guestID int64) bool {
	for _, ext := range []string{".jpg", ".png", ".webp"} {
		for _, name := range []string{
			strconv.FormatInt(guestID, 10) + ext + ".enc",
			strconv.FormatInt(guestID, 10) + ext,
		} {
			if info, err := os.Stat(filepath.Join(photosDir(getenv), name)); err == nil && info.Mode().IsRegular() {
				return true
			}
		}
	}
	return false
}

// passportPhotoIsPDF is passport_photos.is_pdf_attachment.
func passportPhotoIsPDF(getenv func(string) string, guestID int64) bool {
	base := strconv.FormatInt(guestID, 10) + ".pdf"
	for _, name := range []string{base, base + ".enc"} {
		if info, err := os.Stat(filepath.Join(photosDir(getenv), name)); err == nil && info.Mode().IsRegular() {
			return true
		}
	}
	return false
}

func photosDir(getenv func(string) string) string {
	dir := ""
	if getenv != nil {
		dir = getenv("UBYHOST_DATA_DIR")
	}
	if dir == "" {
		dir = "data"
	}
	return filepath.Join(dir, "passport_photos")
}

// guestSignatureValue is _signature_for_display: what the hidden field may post
// back, blank when the stored value would only be refused again.
func guestSignatureValue(g *hostGuest) string {
	if g == nil || g.signaturePNG == "" {
		return ""
	}
	if validation.GuestFormSignatureIssue(g.signaturePNG, false) != nil {
		return ""
	}
	return g.signaturePNG
}

// guestFormData builds the template's dot from the handler's view.
func (c *guestEditCall) guestFormData(v guestFormView) (guestFormData, error) {
	countries, err := guestCountries(c)
	if err != nil {
		return guestFormData{}, err
	}
	purposes := guestPurposes(nil)
	data := guestFormData{
		Reservation: guestFormRes{
			ID:           v.Reservation.id,
			InternalName: v.Reservation.internalName,
			DateFrom:     v.Reservation.dateFrom,
			DateTo:       v.Reservation.dateTo,
		},
		Issues:          v.Issues,
		Editing:         v.Editing,
		IdentityHidden:  v.IdentityHidden,
		Filed:           v.Editing && v.Guest != nil && v.Guest.submitState == submitStateSent,
		SignatureValue:  guestSignatureValue(v.Guest),
		DocTypes:        guestDocTypes(),
		SelectedDocType: guestSelectedDocType(v.Guest),
		Countries:       countries,
		CSRF:            v.CSRF,
		StayFrom:        guestFormStayFrom(v.Guest, v.Reservation),
		StayTo:          guestFormStayTo(v.Guest, v.Reservation),
		MetaText: v.Reservation.internalName + " · " + dateCZ(v.Reservation.dateFrom) +
			" – " + dateCZ(v.Reservation.dateTo),
	}
	// A saved guest keeps its own purpose, even an empty one: only the blank
	// form falls back to the property's default.
	purpose := v.Reservation.defaultPurp
	if v.Guest != nil {
		purpose = v.Guest.purpose
	}
	for i := range purposes {
		purposes[i].Selected = purposes[i].Code == purpose
	}
	data.Purposes = purposes
	if g := v.Guest; g != nil {
		data.Guest = &guestFormValues{
			ID:          g.id,
			SubmitState: g.submitState,
			LastErrors:  g.lastErrors,
			Surname:     g.surname,
			FirstName:   g.firstName,
			BirthDate:   displayBirthDate(g.birthDate),
			Nationality: strings.ToUpper(g.nationality),
			DocNumber:   g.docNumber,
			VisaNumber:  g.visaNum,
			ResStreet:   g.resStreet,
			ResCity:     g.resCity,
			ResCountry:  strings.ToUpper(g.resCountry),
			Purpose:     g.purpose,
			Note:        g.note,
			SignedAt:    guestStamp(g.signedAt),
			SubmittedAt: guestStamp(g.submittedAt),
			ManualFiled: guestStamp(g.manualFiledAt),
			Restricted:  g.restrictedAt != "",
		}
		data.NeedsVerification = validation.GuestIsReportable(g.nationality) &&
			g.identityVerifiedAt == ""
		data.HasPassportPhoto = c.hasPassportPhoto(g)
		if data.HasPassportPhoto {
			data.PassportIsPDF = passportPhotoIsPDF(c.getenv, g.id)
		}
		if v.IdentityHidden {
			data.DocNumberShown = maskIdentifier(g.docNumber)
			data.VisaNumberShown = maskIdentifier(g.visaNum)
		}
	}
	return data, nil
}

// hasPassportPhoto is reporting.guest_has_passport_photo.
func (c *guestEditCall) hasPassportPhoto(g *hostGuest) bool {
	if g == nil || !validation.GuestIsReportable(g.nationality) {
		return false
	}
	entered := g.enteredBy
	if entered == "" {
		entered = "guest"
	}
	if entered == "host" {
		return false
	}
	if g.id == 0 || g.passportPhotoAt == "" {
		return false
	}
	return passportPhotoOnDisk(c.getenv, g.id)
}

// guestCountries is codelists.nationality_options("en").
func guestCountries(c *guestEditCall) ([]guestFormCode, error) {
	list, err := invoices.CountryOptions(c.r.Context(), c.pool, "en")
	if err != nil {
		return nil, err
	}
	out := make([]guestFormCode, len(list))
	for i, o := range list {
		out[i] = guestFormCode{Code: o.Code, Label: o.Label}
	}
	return out, nil
}

// writeHostGuestForm renders the guest form on the host shell.
func (c *guestEditCall) writeHostGuestForm(w http.ResponseWriter, v guestFormView) {
	data, err := c.guestFormData(v)
	if err != nil {
		guestEditServerError(w, err)
		return
	}
	titleKey := "guest.admin.title_add"
	if v.Editing {
		titleKey = "guest.admin.title_edit"
	}
	page := layout.Page{
		Title:    catalog.T(c.lang, titleKey, nil),
		Nav:      "reservations",
		BodyKind: "form",
		V2:       true,
		BackURL:  "/reservations/" + strconv.FormatInt(v.Reservation.id, 10),
	}
	env := layout.Env{Pool: c.pool, Getenv: c.getenv, Now: c.at}
	if err := layout.Render(w, c.r, env, c.host, page, pages, "guest_form_admin", data); err != nil {
		guestEditServerError(w, err)
	}
}
