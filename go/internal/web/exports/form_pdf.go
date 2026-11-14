package exports

// Brief 1605: GET /guests/{id}/form.pdf (exports.guest_form_pdf) and the
// signed registration form it serves (housebook.registration_form_pdf). The
// form is also an entry of the house-book PDF zip (1606) and of the workspace
// export (1607). The layout is pinned against reportlab by
// testdata/registration_form_golden.json (App/scripts/registration_form_golden.py).

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"image"
	_ "image/gif" // PIL reads these too; a signature is a PNG in practice
	_ "image/jpeg"
	"image/png"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pdf"
)

// housebookRetentionYears is housebook.RETENTION_YEARS.
const housebookRetentionYears = 6

// registrationFormSQL is the query of housebook.registration_form_pdf.
const registrationFormSQL = `SELECT g.*, r.date_from AS res_from, r.date_to AS res_to,
	a.internal_name, a.uby_idub, a.uby_name, a.uby_mark,
	a.addr_street, a.addr_house_no, a.addr_orient_no, a.addr_obec,
	a.addr_obec_cast, a.addr_zip, a.addr_okres
	FROM guest g JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id WHERE g.id = $1`

// errNoGuest is the ValueError registration_form_pdf raises for a missing guest.
var errNoGuest = errors.New("guest not found")

// signForRoles is reporting.SIGN_FOR_ROLES.
var signForRoles = map[string]string{
	"parent":            "parent or legal guardian",
	"responsible_adult": "adult responsible for the child during this stay",
}

// formStatus is the status_map of registration_form_pdf.
var formStatus = map[string]string{
	"sent":         "Reported to the Foreign Police",
	"not_required": "No reporting duty (Czech national)",
	"pending":      "NOT YET REPORTED",
	"error":        "REJECTED BY UBYPORT",
	"blocked":      "REJECTED BY UBYPORT (not correctable)",
}

// sigRecord is reporting.signature_record: kind and text.
type sigRecord struct {
	Kind string
	Text string
}

// pyStr is f"{value}" for a column value: None prints "None".
func pyStr(v any) string {
	switch x := v.(type) {
	case nil:
		return "None"
	case string:
		return x
	case int64:
		return strconv.FormatInt(x, 10)
	default:
		return fmt.Sprint(x)
	}
}

// signatureRecord is reporting.signature_record(guest, {date_from: res_from,
// date_to: res_to}) for a hydrated row of registrationFormSQL.
func signatureRecord(ctx context.Context, d deps, g row) (sigRecord, error) {
	kind, err := signatureKind(ctx, d, g)
	if err != nil {
		return sigRecord{}, err
	}
	switch kind {
	case "imported":
		return sigRecord{kind, "Signature on paper (host)"}, nil
	case "exempt":
		return sigRecord{kind, "Under 15, no signature required (§ 103(b))"}, nil
	case "signed_for":
		adults, _, err := queryRows(ctx, d.pool, `SELECT * FROM guest WHERE id = $1 AND reservation_id = $2
			AND archived_at IS NULL`, g.int("signed_for_guest_id"), g.int("reservation_id"))
		if err != nil {
			return sigRecord{}, err
		}
		if len(adults) == 0 {
			return sigRecord{}, errors.New("signer vanished between two reads")
		}
		adult := adults[0]
		if err := hydrate(d.getenv, adult); err != nil {
			return sigRecord{}, err
		}
		role := pyStr(g["signed_for_role"])
		if label, ok := signForRoles[role]; ok {
			role = label
		}
		return sigRecord{kind, fmt.Sprintf("Signed by %s %s for %s %s, as %s, %s, wording %s",
			pyStr(adult["first_name"]), pyStr(adult["surname"]), pyStr(g["first_name"]), pyStr(g["surname"]),
			role, pyStr(g["signed_for_at"]), pyStr(g["signed_for_wording"]))}, nil
	}
	return sigRecord{Kind: kind}, nil
}

// registrationFormPDF is housebook.registration_form_pdf(guest_id): errNoGuest
// when the guest does not exist, any other error as Python raises it.
func registrationFormPDF(ctx context.Context, d deps, guestID int64, at time.Time) ([]byte, error) {
	rows, _, err := queryRows(ctx, d.pool, registrationFormSQL, guestID)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, errNoGuest
	}
	g := rows[0]
	if err := hydrate(d.getenv, g); err != nil {
		return nil, err
	}
	rec, err := signatureRecord(ctx, d, g)
	if err != nil {
		return nil, err
	}
	return drawRegistrationForm(g, rec, at).Bytes()
}

// gray is reportlab's setFillGray / setStrokeGray.
func gray(v float64) pdf.Color { return pdf.Color{v, v, v} }

// drawField is housebook._draw_field.
func drawField(doc *pdf.Doc, x, y float64, label, value string, width float64) {
	doc.Text(x, y+12, label, pdf.Reg, 7, gray(0.35))
	text := value
	if text == "" {
		text = "-"
	}
	for doc.Width(pdf.Reg, text, 10) > width-4 && len([]rune(text)) > 4 {
		r := []rune(text)
		text = string(r[:len(r)-2])
	}
	doc.Text(x, y, text, pdf.Reg, 10, gray(0))
	doc.Line(x, y-3, x+width, y-3, gray(0.75), 1)
}

// houseLabel is housebook._house_label.
func houseLabel(g row) string {
	house := strings.TrimSpace(g.str("addr_house_no"))
	orient := strings.TrimSpace(g.str("addr_orient_no"))
	if house != "" && orient != "" {
		return house + "/" + orient
	}
	return orStr(house, orient)
}

// joinNonEmpty is sep.join(p for p in parts if p).
func joinNonEmpty(sep string, parts ...string) string {
	var out []string
	for _, p := range parts {
		if p != "" {
			out = append(out, p)
		}
	}
	return strings.Join(out, sep)
}

// signatureImage is ImageReader(base64.b64decode(value.split(",", 1)[-1])):
// the PNG to embed and its pixel size; ok is false where Python's try fails.
func signatureImage(value string) ([]byte, int, int, bool) {
	raw := value
	if i := strings.Index(raw, ","); i >= 0 {
		raw = raw[i+1:]
	}
	data, ok := b64decode(raw)
	if !ok {
		return nil, 0, 0, false
	}
	img, _, err := image.Decode(bytes.NewReader(data))
	if err != nil {
		return nil, 0, 0, false
	}
	b := img.Bounds()
	if b.Dx() <= 0 || b.Dy() <= 0 {
		return nil, 0, 0, false
	}
	// Re-encoded so the PDF writer always gets a plain 8-bit PNG (alpha kept).
	var out bytes.Buffer
	if err := png.Encode(&out, img); err != nil {
		return nil, 0, 0, false
	}
	return out.Bytes(), b.Dx(), b.Dy(), true
}

// drawRegistrationForm records the page of housebook.registration_form_pdf
// for a hydrated guest row (registrationFormSQL) and its signature record.
// at is the "Generated" time (datetime.now(), server-local).
func drawRegistrationForm(g row, rec sigRecord, at time.Time) *pdf.Doc {
	doc := pdf.NewDoc()
	width, height := pdf.W, pdf.H
	mm := pdf.MM
	left := 20 * mm
	inner := width - 40*mm

	doc.Text(left, height-25*mm, "Přihlašovací tiskopis cizince", pdf.Bold, 14, gray(0))
	doc.Text(left, height-31*mm, "Foreigner's registration form / house book entry", pdf.Reg, 10, gray(0.35))

	facility := joinNonEmpty(", ",
		joinNonEmpty(" ", g.str("addr_street"), houseLabel(g)),
		g.str("addr_obec_cast"),
		joinNonEmpty(" ", g.str("addr_zip"), g.str("addr_obec")))

	y := height - 45*mm
	doc.Text(left, y, "Ubytovatel / Accommodation provider", pdf.Bold, 10, gray(0))
	y -= 8 * mm
	drawField(doc, left, y, "NÁZEV ZAŘÍZENÍ / FACILITY", orStr(g.str("uby_name"), g.str("internal_name")), inner*0.6)
	drawField(doc, left+inner*0.65, y, "IDUB", g.str("uby_idub"), inner*0.35)
	y -= 14 * mm
	drawField(doc, left, y, "ADRESA / ADDRESS", facility, inner)

	y -= 18 * mm
	doc.Text(left, y, "Ubytovaný cizinec / Accommodated foreigner", pdf.Bold, 10, gray(0))
	y -= 8 * mm

	half := inner * 0.48
	rightX := left + inner*0.52
	nat := g.str("nationality")
	drawField(doc, left, y, "PŘÍJMENÍ / SURNAME", g.str("surname"), half)
	drawField(doc, rightX, y, "JMÉNO / GIVEN NAME(S)", g.str("first_name"), half)
	y -= 14 * mm
	drawField(doc, left, y, "DATUM NAROZENÍ / DATE OF BIRTH", formatBirthDate(g.str("birth_date")), half)
	drawField(doc, rightX, y, "STÁTNÍ OBČANSTVÍ / NATIONALITY", strings.TrimSpace(nat+" "+countryNameEN(nat)), half)
	y -= 14 * mm
	drawField(doc, left, y, "ČÍSLO CESTOVNÍHO DOKLADU / TRAVEL DOCUMENT NO.", g.str("doc_number"), half)
	drawField(doc, rightX, y, "ČÍSLO VÍZA / VISA NO.", g.str("visa_number"), half)
	y -= 14 * mm
	drawField(doc, left, y, "BYDLIŠTĚ V ZAHRANIČÍ / PERMANENT RESIDENCE ABROAD",
		composeResidence(g.str("res_street"), g.str("res_city"), strings.ToUpper(g.str("res_country"))), inner)
	y -= 14 * mm
	drawField(doc, left, y, "ÚČEL POBYTU / PURPOSE OF STAY", purposeLabel(g.str("purpose")), half)
	drawField(doc, rightX, y, "POZNÁMKA / NOTE", g.str("note"), half)
	y -= 14 * mm
	drawField(doc, left, y, "OD / FROM", orStr(g.str("stay_from"), g.str("res_from")), half)
	drawField(doc, rightX, y, "DO / TO", orStr(g.str("stay_to"), g.str("res_to")), half)

	// Signature block
	y -= 30 * mm
	doc.Text(left, y+24*mm, "Podpis cizince / Signature of the foreigner", pdf.Bold, 10, gray(0))
	vouched := rec.Kind == "signed_for" || rec.Kind == "exempt"
	if vouched {
		lines := doc.SimpleSplit(rec.Text, pdf.Reg, 9, width-2*left)
		for i := range lines {
			doc.Text(left, y+8+11*float64(i), lines[len(lines)-1-i], pdf.Reg, 9, gray(0))
		}
	} else if sig := g.str("signature_png"); sig != "" {
		if img, iw, ih, ok := signatureImage(sig); ok {
			// drawImage(..., width=70mm, height=22mm, preserveAspectRatio=True,
			// anchor="sw"): boxstuff.aspectRatioFix.
			boxW, boxH := 70*mm, 22*mm
			scale := min(boxW/float64(iw), boxH/float64(ih))
			doc.Image("signature", img, left, y, scale*float64(iw)-1e-8, scale*float64(ih)-1e-8)
		} else {
			doc.Text(left, y+8, "(signature could not be rendered)", pdf.Reg, 9, gray(0))
		}
	}
	doc.Line(left, y-2*mm, left+80*mm, y-2*mm, gray(0.6), 1)
	signed := orStr(g.str("signed_at"), g.str("filled_at"))
	if vouched {
		// The reporting status is right-aligned on this baseline, so only a
		// sentence as short as the rule above repeats here.
		if doc.Width(pdf.Reg, rec.Text, 8) <= 80*mm {
			doc.Text(left, y-7*mm, rec.Text, pdf.Reg, 8, gray(0.4))
		}
	} else {
		doc.Text(left, y-7*mm, "Signed electronically: "+signed, pdf.Reg, 8, gray(0.4))
	}

	// Reporting status, as required by rule 10.5(3).
	state := g.str("submit_state")
	byHand := state == "sent" && g.str("manual_filed_at") != ""
	status, known := formStatus[state]
	if !known {
		status = state
	}
	if byHand {
		status = "Reported to the Foreign Police (filed by hand in UbyPort)"
	}
	doc.TextRight(width-20*mm, y-7*mm, status, pdf.Reg, 9, gray(0))
	filed := g.str("submitted_at")
	if byHand {
		filed = g.str("manual_filed_at")
	}
	if filed != "" {
		line := "at " + filed
		if byHand && g.str("manual_reference") != "" {
			line += ", ref. " + g.str("manual_reference")
		}
		doc.TextRight(width-20*mm, y-12*mm, line, pdf.Reg, 9, gray(0.4))
	}

	if g.str("notice_version") != "" {
		doc.Text(left, 19*mm, fmt.Sprintf("Privacy notice v%s acknowledged %s (%s)",
			g.str("notice_version"), g.str("notice_ack_at"), g.str("notice_lang")), pdf.Reg, 7, gray(0.45))
	}
	doc.Text(left, 15*mm, fmt.Sprintf("Generated %s - retain for %d years from the end of the stay (§ 101 Act 326/1999 Coll.)",
		at.Local().Format("2006-01-02 15:04"), housebookRetentionYears), pdf.Reg, 7, gray(0.45))
	return doc
}

// countryNameEN is validation.country_name(code, "en").
func countryNameEN(code string) string { return countries.Name(code, "en") }

// GuestFormPDFHandler is exports.guest_form_pdf.
func GuestFormPDFHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		ctx := r.Context()
		// access.guest selects g.*, so a broken token is a 500 here already.
		guests, _, err := queryRows(ctx, pool, ownedGuestSQL, id, ownerID(h))
		if err == nil && len(guests) > 0 {
			err = hydrate(getenv, guests[0])
		}
		if err != nil {
			serverError(w, err)
			return
		}
		if len(guests) == 0 {
			backErr(w, r, "/reservations", "flash.error.no_such_guest", nil)
			return
		}
		if !identityVisible(h, &id) {
			backErr(w, r, fmt.Sprintf("/guests/%d", id), "flash.error.identity_hidden_guest", nil)
			return
		}
		body, err := registrationFormPDF(ctx, d, id, at)
		if errors.Is(err, errNoGuest) {
			backErr(w, r, "/reservations", "flash.error.no_such_guest", nil)
			return
		}
		if err != nil {
			serverError(w, err)
			return
		}
		if err := audit(ctx, pool, h, at, "export_registration_pdf", fmt.Sprintf("guest_id=%d", id)); err != nil {
			serverError(w, err)
			return
		}
		attachment(w, "application/pdf", fmt.Sprintf("registration-form-%d.pdf", id), body)
	}
}
