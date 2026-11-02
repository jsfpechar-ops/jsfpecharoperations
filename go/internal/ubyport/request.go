// Package ubyport builds the police filing request (ZapisUbytovane) for
// UbyPort. The bytes must equal the Python builder in App/app/ubyport/soap.py
// and the payload mapping in App/app/reporting.py. The golden test in
// request_test.go, against App/tests/golden/ubyport/cases.json, is the contract.
package ubyport

import (
	_ "embed"
	"regexp"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
)

// Apartment holds the apartment fields of the payload (JSON keys as in cases.json).
type Apartment struct {
	UbyIdub      string `json:"uby_idub"`
	UbyMark      string `json:"uby_mark"`
	UbyName      string `json:"uby_name"`
	UbyContact   string `json:"uby_contact"`
	AddrOkres    string `json:"addr_okres"`
	AddrObec     string `json:"addr_obec"`
	AddrObecCast string `json:"addr_obec_cast"`
	AddrStreet   string `json:"addr_street"`
	AddrHouseNo  string `json:"addr_house_no"`
	AddrOrientNo string `json:"addr_orient_no"`
	AddrZip      string `json:"addr_zip"`
}

// Reservation holds the reservation dates used as fallback for each guest stay.
type Reservation struct {
	DateFrom string `json:"date_from"`
	DateTo   string `json:"date_to"`
}

// Guest holds one guest row (JSON keys as in cases.json).
type Guest struct {
	StayFrom    string `json:"stay_from"`
	StayTo      string `json:"stay_to"`
	Surname     string `json:"surname"`
	FirstName   string `json:"first_name"`
	BirthDate   string `json:"birth_date"`
	Nationality string `json:"nationality"`
	DocNumber   string `json:"doc_number"`
	VisaNumber  string `json:"visa_number"`
	ResStreet   string `json:"res_street"`
	ResCity     string `json:"res_city"`
	ResCountry  string `json:"res_country"`
	Purpose     string `json:"purpose"`
	Note        string `json:"note"`
}

// Element order is alphabetical (ordinal), as the Python builder serialises it.
var headerFields = []string{
	"uCont", "uHomN", "uIdub", "uMark", "uName", "uOb", "uObCa", "uOkr", "uOriN", "uPsc", "uStr",
}

var guestFields = []string{
	"cDate", "cDocN", "cFirstN", "cFrom", "cNati", "cNote", "cPlac", "cPurp",
	"cResi", "cSpz", "cSurN", "cUntil", "cVisN",
}

const (
	nsSOAP       = "http://schemas.xmlsoap.org/soap/envelope/"
	nsMethod     = "http://UBY.pcr.cz/WS_UBY"
	nsData       = "http://schemas.datacontract.org/2004/07/WS_UBY"
	nsXSI        = "http://www.w3.org/2001/XMLSchema-instance"
	nsWSANone    = "http://schemas.microsoft.com/ws/2005/05/addressing/none"
	actionPrefix = "http://UBY.pcr.cz/WS_UBY/IWS_UBY/"
	maxResidence = 255
)

// xmlEscaper matches xml.sax.saxutils.escape: only & < > (quotes stay raw).
// Go's encoding/xml escapes more, so it must not be used here.
var xmlEscaper = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;")

var isoDate = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`)

// truncRunes cuts s to at most n characters (runes), as Python slicing does.
func truncRunes(s string, n int) string {
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n])
}

// pyUpper mirrors Python str.upper for the values here; only the sharp s differs
// from Go's ToUpper, so it is mapped to SS first.
func pyUpper(s string) string {
	return strings.ToUpper(strings.ReplaceAll(s, "ß", "SS"))
}

// nilIfEmpty is Python's "value or None" for strings.
func nilIfEmpty(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// optStr is "value or None" for the guest map, where nil means a nil element.
func optStr(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func normaliseZip(s string) string {
	var b strings.Builder
	for _, r := range s {
		if unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// parseISODate mirrors validation.parse_iso_date: the first 10 characters as
// YYYY-MM-DD, returned in the same form, or "" when that is not a date.
func parseISODate(s string) string {
	if s == "" {
		return ""
	}
	head := truncRunes(s, 10)
	if !isoDate.MatchString(head) || strings.HasPrefix(head, "0000") {
		return ""
	}
	t, err := time.Parse("2006-01-02", head)
	if err != nil {
		return ""
	}
	return t.Format("2006-01-02")
}

// purposeField mirrors "int(purpose) if purpose.isdigit() else None". The value
// is kept as its normalised decimal text, which is what Python str() writes.
func purposeField(s string) any {
	p := strings.TrimSpace(s)
	if p == "" {
		return nil
	}
	for _, r := range p {
		if r < '0' || r > '9' {
			return nil
		}
	}
	p = strings.TrimLeft(p, "0")
	if p == "" {
		p = "0"
	}
	return p
}

// Header maps an apartment onto the SeznamUbytovanych header fields.
func Header(a Apartment) map[string]*string {
	return map[string]*string{
		"uIdub": nilIfEmpty(strings.TrimSpace(a.UbyIdub)),
		"uMark": nilIfEmpty(pyUpper(strings.TrimSpace(a.UbyMark))),
		"uName": nilIfEmpty(truncRunes(strings.TrimSpace(a.UbyName), 35)),
		"uCont": nilIfEmpty(truncRunes(strings.TrimSpace(a.UbyContact), 50)),
		"uOkr":  nilIfEmpty(truncRunes(strings.TrimSpace(a.AddrOkres), 32)),
		"uOb":   nilIfEmpty(truncRunes(strings.TrimSpace(a.AddrObec), 48)),
		"uObCa": nilIfEmpty(truncRunes(strings.TrimSpace(a.AddrObecCast), 48)),
		"uStr":  nilIfEmpty(truncRunes(strings.TrimSpace(a.AddrStreet), 48)),
		"uHomN": nilIfEmpty(pyUpper(strings.TrimSpace(a.AddrHouseNo))),
		"uOriN": nilIfEmpty(pyUpper(strings.TrimSpace(a.AddrOrientNo))),
		"uPsc":  nilIfEmpty(normaliseZip(a.AddrZip)),
	}
}

// GuestFields maps one guest onto the Ubytovany fields; nil is Python None.
func GuestFields(g Guest, r Reservation) map[string]any {
	start := parseISODate(g.StayFrom)
	if start == "" {
		start = parseISODate(r.DateFrom)
	}
	end := parseISODate(g.StayTo)
	if end == "" {
		end = parseISODate(r.DateTo)
	}
	var cFrom, cUntil any
	if start != "" {
		cFrom = start + "T00:00:00"
	}
	if end != "" {
		cUntil = end + "T00:00:00"
	}

	code := pyUpper(g.ResCountry)
	parts := []string{}
	if g.ResStreet != "" {
		parts = append(parts, g.ResStreet)
	}
	if g.ResCity != "" {
		parts = append(parts, g.ResCity)
	}
	if code != "" {
		parts = append(parts, code+"-"+CountryName(code, "cs"))
	}
	residence := truncRunes(strings.Join(parts, ", "), maxResidence)

	return map[string]any{
		"cFrom":   cFrom,
		"cUntil":  cUntil,
		"cSurN":   optStr(g.Surname),
		"cFirstN": optStr(g.FirstName),
		"cDate":   optStr(g.BirthDate),
		"cPlac":   nil,
		"cNati":   optStr(pyUpper(g.Nationality)),
		"cDocN":   optStr(g.DocNumber),
		"cVisN":   optStr(g.VisaNumber),
		"cResi":   optStr(residence),
		"cPurp":   purposeField(g.Purpose),
		"cSpz":    nil,
		"cNote":   optStr(g.Note),
	}
}

// sanitize turns XML 1.0 illegal control characters into one space each,
// as the Python _XML_ILLEGAL substitution does.
func sanitize(s string) string {
	return strings.Map(func(r rune) rune {
		if r <= 0x08 || r == 0x0b || r == 0x0c || (r >= 0x0e && r <= 0x1f) || r == 0x7f {
			return ' '
		}
		return r
	}, s)
}

// node mirrors soap._node: nil gives a nil element, anything else is escaped text.
func node(prefix, name string, value any) string {
	if value == nil {
		return "<" + prefix + ":" + name + ` i:nil="true" />`
	}
	text := xmlEscaper.Replace(sanitize(value.(string)))
	return "<" + prefix + ":" + name + ">" + text + "</" + prefix + ":" + name + ">"
}

func buildEnvelope(method, body string, wsa bool) string {
	header := ""
	if wsa {
		header = `<Action s:mustUnderstand="1" xmlns="` + nsWSANone + `">` + actionPrefix + method + "</Action>"
	}
	return `<?xml version="1.0" encoding="utf-8"?>` +
		`<s:Envelope xmlns:s="` + nsSOAP + `">` +
		"<s:Header>" + header + "</s:Header>" +
		"<s:Body>" + body + "</s:Body>" +
		"</s:Envelope>"
}

// BuildZapisUbytovane serialises a ZapisUbytovane call: one header plus 1..N guests.
func BuildZapisUbytovane(header map[string]*string, guests []map[string]any, authCode string, wsa bool) string {
	var guestXML strings.Builder
	for _, g := range guests {
		guestXML.WriteString("<d:Ubytovany>")
		for _, name := range guestFields {
			guestXML.WriteString(node("d", name, g[name]))
		}
		guestXML.WriteString("</d:Ubytovany>")
	}

	var headerXML strings.Builder
	for _, name := range headerFields {
		var v any
		if p := header[name]; p != nil {
			v = *p
		}
		headerXML.WriteString(node("d", name, v))
	}

	seznam := `<Seznam xmlns:d="` + nsData + `" xmlns:i="` + nsXSI + `">` +
		"<d:Ubytovani>" + guestXML.String() + "</d:Ubytovani>" +
		"<d:VracetPDF>true</d:VracetPDF>" +
		headerXML.String() +
		"</Seznam>"
	body := `<ZapisUbytovane xmlns="` + nsMethod + `">` +
		"<AutentificationCode>" + xmlEscaper.Replace(authCode) + "</AutentificationCode>" +
		seznam +
		"</ZapisUbytovane>"
	return buildEnvelope("ZapisUbytovane", body, wsa)
}

// CountryName mirrors validation.country_name; the table lives in
// internal/countries so validation does not import this package.
func CountryName(code, lang string) string {
	return countries.Name(code, lang)
}
