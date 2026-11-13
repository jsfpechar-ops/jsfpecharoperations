package pdf

import (
	_ "embed"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
)

//go:embed assets/ubyhost-mark-192.png
var markPNG []byte

// ErrTooLong: the content would run into the footer (invoice_pdf.TooLong).
var ErrTooLong = errors.New("pdf: invoice content runs into the footer")

// Brand tokens (invoice_pdf.py).
var (
	Ink     = RGB(0x1B, 0x1F, 0x25)
	Ink2    = RGB(0x50, 0x50, 0x4C)
	Muted   = RGB(0x73, 0x73, 0x6E)
	Faint   = RGB(0x92, 0x92, 0x8C)
	LineCol = RGB(0xDE, 0xDE, 0xD9)
	Canvas  = RGB(0xF7, 0xF7, 0xF5)
	Coral   = RGB(0xD3, 0x54, 0x45)
	Green   = RGB(0x16, 0x70, 0x44)
	GreenBG = RGB(0xE6, 0xF5, 0xEC)
)

const footerURL = "https://ubyhost.com/?utm_source=invoice&utm_medium=pdf"

// Invoice is the dict invoice_pdf.render takes: the invoice-table snapshot
// columns plus the view fields. Empty string means absent/falsy.
type Invoice struct {
	Number            string `json:"number"`
	Kind              string `json:"kind"`
	VATStatus         string `json:"vat_status"`
	SellerName        string `json:"seller_name"`
	SellerSeat        string `json:"seller_seat"`
	SellerICO         string `json:"seller_ico"`
	SellerDIC         string `json:"seller_dic"`
	SellerRegistry    string `json:"seller_registry"`
	SellerEmail       string `json:"seller_email"`
	SellerPhone       string `json:"seller_phone"`
	SellerIBAN        string `json:"seller_iban"`
	SellerBankAccount string `json:"seller_bank_account"`
	SellerBIC         string `json:"seller_bic"`
	BuyerName         string `json:"buyer_name"`
	BuyerStreet       string `json:"buyer_street"`
	BuyerZip          string `json:"buyer_zip"`
	BuyerCity         string `json:"buyer_city"`
	BuyerCountryName  string `json:"buyer_country_name"`
	BuyerICO          string `json:"buyer_ico"`
	BuyerDIC          string `json:"buyer_dic"`
	IssueDate         string `json:"issue_date"`
	DUZP              string `json:"duzp"`
	DueDate           string `json:"due_date"`
	PaidOn            string `json:"paid_on"`
	VS                string `json:"vs"`
	PaidViaLabel      string `json:"paid_via_label"`
	StayLabel         string `json:"stay_label"`
	CorrectsNumber    string `json:"corrects_number"`
	CorrectionReason  string `json:"correction_reason"`
	CorrectionDate    string `json:"correction_date"`
	Note              string `json:"note"`
	PartialCorrection bool   `json:"partial_correction"`
	TotalHaler        int64  `json:"total_haler"`
}

// Item is an invoice_item row. VATRate nil means outside VAT.
type Item struct {
	Description string `json:"description"`
	Quantity    int    `json:"quantity"`
	Unit        string `json:"unit"`
	VATRate     *int   `json:"vat_rate"`
	BaseHaler   int64  `json:"base_haler"`
	VATHaler    int64  `json:"vat_haler"`
	GrossHaler  int64  `json:"gross_haler"`
}

// Money is invoice_pdf.money: 1 234,50 Kč, always Czech format.
func Money(haler int64) string {
	neg := haler < 0
	a := haler
	if neg {
		a = -a
	}
	whole := strconv.FormatInt(a/100, 10)
	var parts []string
	for len(whole) > 3 {
		parts = append([]string{whole[len(whole)-3:]}, parts...)
		whole = whole[:len(whole)-3]
	}
	parts = append([]string{whole}, parts...)
	s := strings.Join(parts, " ") + fmt.Sprintf(",%02d Kč", a%100)
	if neg {
		return "−" + s
	}
	return s
}

func czDate(iso string) (string, error) {
	p := strings.Split(iso, "-")
	if len(p) != 3 {
		return "", fmt.Errorf("pdf: bad date %q", iso)
	}
	d, e1 := strconv.Atoi(p[2])
	m, e2 := strconv.Atoi(p[1])
	if e1 != nil || e2 != nil {
		return "", fmt.Errorf("pdf: bad date %q", iso)
	}
	return fmt.Sprintf("%d. %d. %s", d, m, p[0]), nil
}

func floorDiv(a, b int64) int64 {
	q := a / b
	if (a%b != 0) && ((a < 0) != (b < 0)) {
		q--
	}
	return q
}

func formatIBAN(iban string) string {
	var parts []string
	for i := 0; i < len(iban); i += 4 {
		end := i + 4
		if end > len(iban) {
			end = len(iban)
		}
		parts = append(parts, iban[i:end])
	}
	return strings.Join(parts, " ")
}

func join(sep string, parts ...string) string {
	var keep []string
	for _, p := range parts {
		if p != "" {
			keep = append(keep, p)
		}
	}
	return strings.Join(keep, sep)
}

type inv struct {
	d   *Doc
	err error
}

func (v *inv) date(s string) string {
	out, err := czDate(s)
	if err != nil && v.err == nil {
		v.err = err
	}
	return out
}

func (v *inv) label(x, y float64, s string, right bool) {
	t := strings.ToUpper(s)
	if right {
		v.d.TextRight(x, y, t, Bold, 6.5, Muted)
	} else {
		v.d.Text(x, y, t, Bold, 6.5, Muted)
	}
}

func titleFor(l map[string]string, in Invoice, payer bool) (string, error) {
	var t string
	switch in.Kind {
	case "invoice":
		t = l["invoice"]
		if payer {
			t = l["tax_invoice"]
		}
	case "storno":
		t = l["storno"]
		if in.PartialCorrection {
			t = l["credit_note"]
		}
	case "corrective":
		t = l["corrective"]
	default:
		return "", fmt.Errorf("pdf: unknown invoice kind %q", in.Kind)
	}
	return t, nil
}

// Layout draws the invoice (invoice_pdf.render) and returns the Doc.
func Layout(in Invoice, items []Item, lang string, preview, strict bool) (*Doc, error) {
	L, ok := labels[lang]
	if !ok {
		return nil, fmt.Errorf("pdf: unknown language %q", lang)
	}
	payer := in.VATStatus == "payer"
	d := NewDoc()
	v := &inv{d: d}
	d.Meta(L["invoice"]+" "+in.Number, in.SellerName, "UbyHost")
	M := 18 * MM
	CW := W - 2*M

	d.Rect(0, H-1.6*MM, W, 1.6*MM, 0, &Coral, nil, 0)
	top := H - M - 2*MM
	v.label(M, top+6*MM, L["supplier"], false)
	d.Text(M, top, in.SellerName, Bold, 15, Ink)
	y := top - 5.5*MM
	y = d.Wrap(M, y, in.SellerSeat, 90*MM, Reg, 8.5, Ink2, 0)
	var ids []string
	if in.SellerICO != "" {
		ids = append(ids, L["ico"]+" "+in.SellerICO)
	}
	if payer && in.SellerDIC != "" {
		ids = append(ids, L["dic"]+" "+in.SellerDIC)
	}
	if len(ids) > 0 {
		d.Text(M, y, strings.Join(ids, "   ·   "), Reg, 8.5, Ink2)
	}

	title, err := titleFor(L, in, payer)
	if err != nil {
		return nil, err
	}
	d.TextRight(W-M, top+0.5*MM, strings.ToUpper(title), Bold, 8, Coral)
	if lang != "cs" {
		cs, _ := titleFor(labels["cs"], in, payer)
		d.TextRight(W-M, top+4.2*MM, cs, Reg, 7, Muted)
	}
	d.TextRight(W-M, top-8*MM, in.Number, Bold, 20, Ink)
	if in.CorrectsNumber != "" {
		d.TextRight(W-M, top-13.5*MM, L["to"]+" "+in.CorrectsNumber, Reg, 8.5, Ink2)
	}

	cardTop := top - 24*MM
	cardH := 36 * MM
	gap := 6 * MM
	leftW := CW * 0.56
	rightW := CW - leftW - gap
	d.Rect(M, cardTop-cardH, leftW, cardH, 3*MM, &Canvas, nil, 0)
	v.label(M+5*MM, cardTop-6.5*MM, L["customer"], false)
	var buyerIDs []string
	if in.BuyerICO != "" {
		buyerIDs = append(buyerIDs, L["ico"]+" "+in.BuyerICO)
	}
	if in.BuyerDIC != "" {
		buyerIDs = append(buyerIDs, L["dic"]+" "+in.BuyerDIC)
	}
	buyer := []string{in.BuyerName, in.BuyerStreet, join(" ", in.BuyerZip, in.BuyerCity),
		in.BuyerCountryName, strings.Join(buyerIDs, "   ·   ")}
	yy := cardTop - 12.5*MM
	j := 0
	for _, line := range buyer {
		if line == "" {
			continue
		}
		font, size, color := Reg, 8.5, Ink2
		if j == 0 {
			font, size, color = Bold, 10.5, Ink
		}
		yy = d.Wrap(M+5*MM, yy, line, leftW-10*MM, font, size, color, 4.5*MM)
		j++
	}

	type fact struct{ lab, val string }
	facts := []fact{{L["issued"], v.date(in.IssueDate)}}
	if payer && in.DUZP != "" {
		facts = append(facts, fact{L["duzp"], v.date(in.DUZP)})
	}
	if in.DueDate != "" && in.PaidOn == "" {
		facts = append(facts, fact{L["due"], v.date(in.DueDate)})
	}
	facts = append(facts, fact{L["vs"], in.VS})
	method := L["transfer"]
	if in.PaidOn != "" {
		method = in.PaidViaLabel
	}
	facts = append(facts, fact{L["method"], method})
	rx := M + leftW + gap
	d.Rect(rx, cardTop-cardH, rightW, cardH, 3*MM, nil, &LineCol, 0.6)
	rowH := (cardH - 6*MM) / float64(len(facts))
	for i, f := range facts {
		ly := cardTop - 6.5*MM - float64(i)*rowH
		d.Text(rx+5*MM, ly, f.lab, Reg, 8, Muted)
		val := f.val
		if val == "" {
			val = "—"
		}
		d.TextRight(rx+rightW-5*MM, ly, val, Bold, 8.5, Ink)
	}
	fy := cardTop - cardH

	sy := fy - 9*MM
	if in.StayLabel != "" {
		v.label(M, sy, L["stay"], false)
		d.Text(M+14*MM, sy, in.StayLabel, Reg, 8.5, Ink2)
		sy -= 8 * MM
	}
	d.Line(M, sy, W-M, sy, Ink, 0.8)
	hy := sy - 4.6*MM
	type col struct {
		lab   string
		x     float64
		right bool
	}
	var cols []col
	if payer {
		cols = []col{{L["desc"], M, false}, {L["net"], W - M - 72*MM, true}, {L["rate"], W - M - 52*MM, true},
			{L["vat"], W - M - 30*MM, true}, {L["gross"], W - M, true}}
	} else {
		cols = []col{{L["desc"], M, false}, {L["qty"], W - M - 38*MM, true}, {L["price"], W - M, true}}
	}
	for _, c := range cols {
		v.label(c.x, hy, c.lab, c.right)
	}
	ry := hy - 3*MM
	d.Line(M, ry, W-M, ry, LineCol, 0.5)
	descW := CW - 50*MM
	if payer {
		descW = CW - 100*MM
	}
	for _, it := range items {
		lines := d.SimpleSplit(it.Description, Reg, 9, descW)
		if len(lines) > 2 {
			lines = lines[:2]
		}
		rowTop := ry - 5.2*MM
		yy := rowTop
		for _, ln := range lines {
			d.Text(M, yy, ln, Reg, 9, Ink)
			yy -= 4.2 * MM
		}
		qty := it.Quantity
		if qty < 1 {
			qty = 1
		}
		if payer && it.VATRate != nil {
			unit := floorDiv(it.BaseHaler, int64(qty))
			detail := strings.TrimSpace(fmt.Sprintf("%d %s × %s", qty, it.Unit, Money(unit)))
			d.Text(M, yy, detail, Reg, 8, Muted)
			yy -= 4.2 * MM
		}
		if payer {
			if it.VATRate == nil {
				d.TextRight(W-M-72*MM, rowTop, Money(it.GrossHaler), Reg, 9, Ink)
				d.TextRight(W-M-52*MM, rowTop, L["outside_vat"], Reg, 8, Muted)
				d.TextRight(W-M-30*MM, rowTop, "—", Reg, 9, Muted)
			} else {
				d.TextRight(W-M-72*MM, rowTop, Money(it.BaseHaler), Reg, 9, Ink)
				d.TextRight(W-M-52*MM, rowTop, fmt.Sprintf("%d %%", *it.VATRate), Reg, 9, Ink)
				d.TextRight(W-M-30*MM, rowTop, Money(it.VATHaler), Reg, 9, Ink)
			}
		} else {
			d.TextRight(W-M-38*MM, rowTop, strconv.Itoa(it.Quantity), Reg, 9, Ink)
		}
		d.TextRight(W-M, rowTop, Money(it.GrossHaler), Bold, 9, Ink)
		ry = yy - 1.5*MM
		d.Line(M, ry, W-M, ry, LineCol, 0.5)
	}

	ty := ry - 9*MM
	if payer {
		v.label(M, ty, L["recap"], false)
		rates := map[int][3]int64{}
		for _, it := range items {
			if it.VATRate != nil {
				r := rates[*it.VATRate]
				r[0] += it.BaseHaler
				r[1] += it.VATHaler
				r[2] += it.GrossHaler
				rates[*it.VATRate] = r
			}
		}
		keys := make([]int, 0, len(rates))
		for k := range rates {
			keys = append(keys, k)
		}
		sort.Ints(keys)
		yy := ty - 5*MM
		for _, k := range keys {
			r := rates[k]
			d.Text(M, yy, fmt.Sprintf("%d %%", k), Reg, 8.5, Ink2)
			d.TextRight(M+50*MM, yy, L["base"]+" "+Money(r[0]), Reg, 8.5, Ink2)
			d.TextRight(M+84*MM, yy, L["vat"]+" "+Money(r[1]), Reg, 8.5, Ink2)
			yy -= 4.5 * MM
		}
	}
	paid := in.PaidOn != ""
	boxW, boxH := 78*MM, 22*MM
	bx, by := W-M-boxW, ty-boxH+4*MM
	d.Rect(bx, by, boxW, boxH, 3*MM, &Canvas, nil, 0)
	isInvoice := in.Kind == "invoice"
	lab := L["gross"]
	if isInvoice {
		lab = L["total"]
		if paid {
			lab = L["paid_total"]
		}
	}
	v.label(bx+5*MM, by+boxH-7*MM, lab, false)
	d.TextRight(bx+boxW-5*MM, by+5.5*MM, Money(in.TotalHaler), Bold, 17, Ink)
	if paid && isInvoice {
		pill := L["paid"] + " " + v.date(in.PaidOn)
		pw := d.Width(Bold, pill, 6.5) + 5*MM
		px := bx + boxW - 5*MM - pw
		d.Rect(px, by+boxH-8.6*MM, pw, 4.8*MM, 2.4*MM, &GreenBG, nil, 0)
		d.Text(px+2.5*MM, by+boxH-7*MM, pill, Bold, 6.5, Green)
	}

	py := by - 12*MM
	if !paid && in.TotalHaler > 0 && in.SellerIBAN != "" {
		v.label(M, py, L["pay_title"], false)
		type row struct{ lab, val string }
		var rows []row
		if strings.Contains(in.SellerBankAccount, "/") {
			rows = append(rows, row{L["account"], in.SellerBankAccount})
		}
		rows = append(rows, row{"IBAN", formatIBAN(in.SellerIBAN)})
		if in.SellerBIC != "" {
			rows = append(rows, row{"BIC / SWIFT", in.SellerBIC})
		}
		rows = append(rows, row{L["vs"], in.VS}, row{L["amount"], Money(in.TotalHaler)})
		yy := py - 6*MM
		for _, r := range rows {
			d.Text(M, yy, r.lab, Reg, 8.5, Muted)
			d.Text(M+42*MM, yy, r.val, Bold, 9, Ink)
			yy -= 5 * MM
		}
		payload := spayd(in.SellerIBAN, in.TotalHaler, in.VS, "FAKTURA "+in.Number, in.SellerBIC)
		png, err := qrPNG(payload)
		if err != nil {
			return nil, err
		}
		q := 30 * MM
		qx, qy := W-M-q, py-q-1*MM
		d.Image("qr", png, qx, qy, q, q)
		d.ops[len(d.ops)-1].S = payload
		capW := d.Width(Bold, L["qr"], 7)
		d.Text(qx+(q-capW)/2, qy-3.5*MM, L["qr"], Bold, 7, Muted)
		py = qy - 8*MM
		if yy < py {
			py = yy
		}
	} else {
		py = by - 6*MM
	}

	ny := py - 4*MM
	if (in.Kind == "storno" || in.Kind == "corrective") && in.CorrectionReason != "" {
		ny = d.Wrap(M, ny, L["reason"]+": "+in.CorrectionReason, CW, Reg, 8.5, Ink2, 0)
	}
	if in.Kind == "corrective" && in.CorrectionDate != "" {
		ny = d.Wrap(M, ny, L["correction_date"]+": "+v.date(in.CorrectionDate), CW, Reg, 8.5, Ink2, 0)
	}
	if in.Note != "" {
		ny = d.Wrap(M, ny, in.Note, CW, Reg, 8.5, Ink2, 0)
	}
	if !payer {
		ny = d.Wrap(M, ny, L["non_payer"], CW, Reg, 8.5, Ink2, 0)
	}
	if v.err != nil {
		return nil, v.err
	}

	fy2 := M + 10*MM
	if strict && ny+2*MM < fy2+7*MM {
		return nil, ErrTooLong
	}
	if in.SellerRegistry != "" {
		d.Text(M, fy2+4.5*MM, in.SellerRegistry, Reg, 7, Muted)
	}
	if contact := join("   ·   ", in.SellerEmail, in.SellerPhone); contact != "" {
		d.Text(M, fy2, contact, Reg, 7, Muted)
	}
	d.Line(M, M+5*MM, W-M, M+5*MM, LineCol, 0.5)
	mark := 3.6 * MM
	d.Image("mark", markPNG, M, M-0.4*MM, mark, mark)
	credit := L["footer"] + "  ·  ubyhost.com"
	d.Text(M+mark+1.8*MM, M+0.4*MM, credit, Reg, 7, Faint)
	cw := d.Width(Reg, credit, 7)
	d.Link(footerURL, M, M-1*MM, M+mark+1.8*MM+cw, M+3.5*MM)
	d.TextRight(W-M, M+0.4*MM, L["page"], Reg, 7, Faint)

	if preview {
		d.Watermark(L["preview"], Bold, 34, Coral, 0.12, 35, W/2, H/2)
	}
	return d, nil
}

// Render is invoice_pdf.render: the finished PDF.
func Render(in Invoice, items []Item, lang string, preview, strict bool) ([]byte, error) {
	d, err := Layout(in, items, lang, preview, strict)
	if err != nil {
		return nil, err
	}
	return d.Bytes()
}

// TooLong is invoice_pdf.too_long.
func TooLong(in Invoice, items []Item, lang string) (bool, error) {
	_, err := Layout(in, items, lang, false, true)
	if errors.Is(err, ErrTooLong) {
		return true, nil
	}
	return false, err
}
