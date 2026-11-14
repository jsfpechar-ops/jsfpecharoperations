// Package stayfeepdf draws the stay-fee hlášení PDF ("Invoice companion"
// design), a port of App/app/stay_fee_remittance_pdf.py. It implements
// stayfee.PDFRenderer. The document is Czech only, A4, and has no QR code
// (the Python renderer draws none). Layout returns one pdf.Doc per page so the
// tests can compare the draw operations with the Python golden.
package stayfeepdf

import (
	"bytes"
	"encoding/base64"
	"errors"
	"fmt"
	"image"
	_ "image/jpeg" // signature images may be JPEG
	_ "image/png"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pdf"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// Renderer is the stayfee.PDFRenderer of the hlášení. Sample labels a mockup
// made with fictional data ("NÁHLED · UKÁZKOVÁ DATA"); the checks still apply.
type Renderer struct{ Sample bool }

var _ stayfee.PDFRenderer = Renderer{}

// Render is stay_fee_remittance_pdf.render.
func (r Renderer) Render(h stayfee.Hlaseni) ([]byte, error) {
	pages, err := Layout(h, r.Sample)
	if err != nil {
		return nil, err
	}
	return pdf.PagesBytes(pages...)
}

const (
	mm = pdf.MM
	pw = pdf.W
	ph = pdf.H
	mg = 18 * mm
	rt = pw - mg
)

var (
	ink       = pdf.Ink
	secondary = pdf.Ink2
	muted     = pdf.Muted
	lineCol   = pdf.LineCol
	canvasCol = pdf.Canvas
	coral     = pdf.Coral
	white     = pdf.Color{1, 1, 1}
)

var months = [12]string{"leden", "únor", "březen", "duben", "květen", "červen",
	"červenec", "srpen", "září", "říjen", "listopad", "prosinec"}

func shift(first time.Time, n int) time.Time {
	idx := first.Year()*12 + int(first.Month()) - 1 + n
	return time.Date(idx/12, time.Month(idx%12+1), 1, 0, 0, 0, 0, time.UTC)
}

func parseDate(s string) (time.Time, error) { return time.Parse("2006-01-02", s) }

func required(v, label string) error {
	if strings.TrimSpace(v) == "" {
		return fmt.Errorf("Missing %s", label)
	}
	return nil
}

// Validate refuses a blank or internally inconsistent document (validate).
func Validate(h stayfee.Hlaseni) error {
	for _, f := range [][2]string{{h.PayerName, "payer_name"}, {h.RecipientName, "recipient_name"}, {h.VS, "vs"},
		{h.PeriodStart, "period_start"}, {h.PeriodEnd, "period_end"}, {h.IssuedOn, "issued_on"}} {
		if err := required(f[0], f[1]); err != nil {
			return err
		}
	}
	start, err := parseDate(h.PeriodStart)
	if err != nil {
		return err
	}
	end, err := parseDate(h.PeriodEnd)
	if err != nil {
		return err
	}
	if _, err := parseDate(h.IssuedOn); err != nil {
		return err
	}
	quarterly := h.Cadence == "quarterly"
	n := 1
	if quarterly {
		n = 3
	}
	if start.Day() != 1 || (quarterly && (int(start.Month())-1)%3 != 0) ||
		!end.Equal(shift(start, n).AddDate(0, 0, -1)) {
		return errors.New("Report period must be one complete calendar month or quarter")
	}
	totalNights, totalCZK := 0, 0
	for _, row := range h.Rows {
		if err := required(row.PropertyName, "property_name"); err != nil {
			return err
		}
		if row.RateCZK < 0 {
			return errors.New("rate_czk must be a non-negative integer")
		}
		if row.LiableNights*row.RateCZK != row.AmountCZK {
			return errors.New("Facility amount does not match nights × rate")
		}
		totalNights += row.LiableNights
		totalCZK += row.AmountCZK
	}
	if totalNights < 0 || totalCZK < 0 {
		return errors.New("Report total must be a non-negative integer")
	}
	if h.LiableNights != totalNights || h.TotalCZK != totalCZK {
		return errors.New("Report totals do not match facility rows")
	}
	exempt := 0
	for _, it := range h.NotCharged {
		if err := required(it.Reason, "not_charged reason"); err != nil {
			return err
		}
		if it.Count < 0 || it.Nights < 0 {
			return errors.New("not_charged count must be a non-negative integer")
		}
		exempt += it.Nights
	}
	if h.ExemptNights != exempt {
		return errors.New("Exempt nights do not match the non-chargeable reasons")
	}
	return nil
}

// --- formatting -----------------------------------------------------------------

func czDate(s string) string {
	t, _ := parseDate(s)
	return fmt.Sprintf("%d. %d. %d", t.Day(), int(t.Month()), t.Year())
}

// PeriodPhrase is period_phrase: "srpen 2026" or "3. čtvrtletí 2026".
func PeriodPhrase(h stayfee.Hlaseni) string {
	t, _ := parseDate(h.PeriodStart)
	if h.Cadence == "quarterly" {
		return fmt.Sprintf("%d. čtvrtletí %d", (int(t.Month())-1)/3+1, t.Year())
	}
	return fmt.Sprintf("%s %d", months[t.Month()-1], t.Year())
}

func nights(n int) string {
	word := "lůžkodnů"
	switch {
	case n == 1:
		word = "lůžkoden"
	case n >= 2 && n <= 4:
		word = "lůžkodny"
	}
	return fmt.Sprintf("%d %s", n, word)
}

func amount(v int) string {
	s := strconv.Itoa(v)
	neg := strings.HasPrefix(s, "-")
	s = strings.TrimPrefix(s, "-")
	var b []byte
	for i := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			b = append(b, ' ')
		}
		b = append(b, s[i])
	}
	out := string(b) + " Kč"
	if neg {
		out = "-" + out
	}
	return out
}

// --- drawing primitives -------------------------------------------------------------

type page struct{ *pdf.Doc }

func (p page) text(x, y float64, v string, size float64, bold bool, c pdf.Color, right bool) {
	font := pdf.Reg
	if bold {
		font = pdf.Bold
	}
	if right {
		p.TextRight(x, y, v, font, size, c)
	} else {
		p.Text(x, y, v, font, size, c)
	}
}

func (p page) label(x, y float64, v string, right bool, c pdf.Color) {
	p.text(x, y, strings.ToUpper(v), 6.8, true, c, right)
}

func (p page) rule(y float64, strong bool) {
	if strong {
		p.Line(mg, y, rt, y, ink, 0.8)
	} else {
		p.Line(mg, y, rt, y, lineCol, 0.55)
	}
}

func (p page) card(x, y, w, h float64, tinted bool) {
	if tinted {
		p.Rect(x, y, w, h, 3*mm, &canvasCol, nil, 0)
		return
	}
	p.Rect(x, y, w, h, 3*mm, &white, &lineCol, 1)
}

func splitLines(s string) []string {
	s = strings.ReplaceAll(strings.ReplaceAll(s, "\r\n", "\n"), "\r", "\n")
	if s == "" {
		return nil
	}
	parts := strings.Split(s, "\n")
	if parts[len(parts)-1] == "" {
		parts = parts[:len(parts)-1]
	}
	return parts
}

func (p page) split(v string, width, size float64, bold bool) []string {
	font := pdf.Reg
	if bold {
		font = pdf.Bold
	}
	var out []string
	for _, block := range splitLines(v) {
		parts := p.SimpleSplit(block, font, size, width)
		if len(parts) == 0 {
			parts = []string{""}
		}
		out = append(out, parts...)
	}
	return out
}

func (p page) wrap(x, y float64, v string, width, size float64, bold bool, c pdf.Color, leading float64) float64 {
	for _, part := range p.split(v, width, size, bold) {
		p.text(x, y, part, size, bold, c, false)
		y -= leading
	}
	return y
}

// --- page parts ---------------------------------------------------------------------

func footer(p page, n int) {
	p.rule(20*mm, false)
	p.Image("mark", pdf.Mark(), mg, 12.7*mm, 4.5*mm, 4.5*mm)
	p.text(mg+6.5*mm, 14*mm, "UbyHost", 8.5, true, ink, false)
	p.text(mg+32*mm, 14*mm, "Vytvořeno v UbyHost", 7, false, muted, false)
	p.text(rt, 14*mm, fmt.Sprintf("Strana %d", n), 7, false, muted, true)
}

func pageTop(p page, h stayfee.Hlaseni, continuation, sample bool) float64 {
	p.Rect(0, ph-1.6*mm, pw, 1.6*mm, 0, &coral, nil, 0)
	if sample {
		p.label(mg, ph-9*mm, "NÁHLED · UKÁZKOVÁ DATA", false, coral)
	}
	if continuation {
		p.label(mg, ph-18*mm, "HLÁŠENÍ K MÍSTNÍMU POPLATKU Z POBYTU · POKRAČOVÁNÍ", false, coral)
		p.text(rt, ph-18*mm, PeriodPhrase(h), 8, false, ink, true)
		return ph - 31*mm
	}
	top := ph - 26*mm
	p.label(mg, top, "PLÁTCE POPLATKU", false, muted)
	payer := p.SimpleSplit(h.PayerName, pdf.Bold, 13, 95*mm)
	size := 13.0
	if len(payer) > 2 {
		size = 10
		payer = p.SimpleSplit(h.PayerName, pdf.Bold, 10, 95*mm)
	}
	y := top - 8*mm
	for i, part := range payer {
		if i == 3 {
			break
		}
		p.text(mg, y, part, size, true, ink, false)
		y -= 5.7 * mm
	}
	var idBits []string
	if h.PayerICO != "" {
		idBits = append(idBits, "IČO "+h.PayerICO)
	}
	idBits = append(idBits, "VS "+h.VS)
	p.text(mg, min(y+1*mm, top-14*mm), strings.Join(idBits, " · "), 8, false, secondary, false)

	kind := "HLÁŠENÍ K MÍSTNÍMU"
	if h.Cadence == "quarterly" {
		kind = "ČTVRTLETNÍ HLÁŠENÍ K MÍSTNÍMU"
	}
	p.label(rt, top, kind, true, coral)
	p.text(rt, top-8*mm, "poplatku z pobytu", 15, true, ink, true)
	p.text(rt, top-15*mm, "za "+PeriodPhrase(h), 9, false, secondary, true)

	leftW := 104 * mm
	rightX := mg + leftW + 6*mm
	innerW := leftW - 10*mm
	nameLines := p.split(h.RecipientName, innerW, 9, true)
	var dparts []string
	for _, s := range []string{h.RecipientAddress, h.RecipientContact} {
		if s != "" {
			dparts = append(dparts, s)
		}
	}
	detail := strings.Join(dparts, "\n")
	var detailLines []string
	if detail != "" {
		detailLines = p.split(detail, innerW, 7.3, false)
	}
	extra := 0.0
	if len(detailLines) > 0 {
		extra = 2
	}
	cardH := max(23*mm, 17*mm+float64(len(nameLines)-1)*11+float64(len(detailLines))*9.5+extra)
	cardY := ph - 52*mm - cardH
	p.card(mg, cardY, leftW, cardH, true)
	p.label(mg+5*mm, cardY+cardH-7*mm, "PŘÍJEMCE · SPRÁVCE POPLATKU", false, muted)
	yy := p.wrap(mg+5*mm, cardY+cardH-14*mm, h.RecipientName, innerW, 9, true, ink, 11)
	if len(detailLines) > 0 {
		p.wrap(mg+5*mm, yy-1, detail, innerW, 7.3, false, secondary, 9.5)
	}
	p.card(rightX, cardY+cardH-23*mm, rt-rightX, 23*mm, false)
	p.label(rightX+5*mm, cardY+cardH-7*mm, "OBDOBÍ / VYHOTOVENO", false, muted)
	p.text(rightX+5*mm, cardY+cardH-14*mm, czDate(h.PeriodStart)+" – "+czDate(h.PeriodEnd), 7.5, true, ink, false)
	p.text(rightX+5*mm, cardY+cardH-19*mm, czDate(h.IssuedOn), 7.5, false, muted, false)

	y = cardY - 9*mm
	for _, line := range []string{h.PayerSeat, h.PayerContact} {
		if line != "" {
			p.text(mg, y, line, 7.5, false, secondary, false)
			y -= 5 * mm
		}
	}
	return y - 10*mm
}

func tableHeader(p page, y float64) float64 {
	p.label(mg, y, "VÝPOČET ZA ZAŘÍZENÍ", false, muted)
	p.rule(y-5*mm, true)
	p.label(mg, y-12*mm, "ZAŘÍZENÍ", false, muted)
	p.label(rt-62*mm, y-12*mm, "LŮŽKODNY K POPLATKU", true, muted)
	p.label(rt-39*mm, y-12*mm, "SAZBA", true, muted)
	p.label(rt, y-12*mm, "POPLATEK", true, muted)
	p.rule(y-16*mm, false)
	return y - 25*mm
}

func rowHeight(p page, row stayfee.HlaseniRow) float64 {
	name := p.SimpleSplit(row.PropertyName, pdf.Bold, 9, 79*mm)
	addr := p.SimpleSplit(row.PropertyAddress, pdf.Reg, 7.7, 79*mm)
	return max(14*mm, (float64(len(name))*4.5+float64(len(addr))*4+5)*mm)
}

func tableRow(p page, y float64, row stayfee.HlaseniRow) float64 {
	bottom := y - rowHeight(p, row)
	afterName := p.wrap(mg, y, row.PropertyName, 79*mm, 9, true, ink, 4.5*mm)
	if row.PropertyAddress != "" {
		p.wrap(mg, afterName-0.3*mm, row.PropertyAddress, 79*mm, 7.7, false, muted, 4*mm)
	}
	p.text(rt-62*mm, y-1*mm, strconv.Itoa(row.LiableNights), 9, false, ink, true)
	p.text(rt-39*mm, y-1*mm, amount(row.RateCZK), 9, false, ink, true)
	p.text(rt, y-1*mm, amount(row.AmountCZK), 9, true, ink, true)
	p.rule(bottom+2*mm, false)
	return bottom - 3*mm
}

func summary(p page, y float64, h stayfee.Hlaseni) float64 {
	sh := 27 * mm
	bw := 78 * mm
	bx := rt - bw
	p.card(bx, y-sh, bw, sh, true)
	if payee := strings.TrimSpace(h.Payee); payee != "" {
		p.label(bx+5*mm, y-8*mm, "CELKEM K ODVODU NA ÚČET "+payee, false, muted)
	} else {
		p.label(bx+5*mm, y-8*mm, "CELKEM K ODVODU OBCI", false, muted)
	}
	p.text(rt-5*mm, y-20*mm, amount(h.TotalCZK), 19, true, ink, true)
	p.label(mg, y-8*mm, "SOUHRN", false, muted)
	p.text(mg, y-15*mm, nights(h.LiableNights)+" podléhá poplatku", 8.5, false, secondary, false)
	p.text(mg, y-21*mm, nights(h.ExemptNights)+" osvobozeno", 8.5, false, secondary, false)
	p.text(mg, y-26.5*mm, "Lůžkoden = osoba × počet nocí", 7, false, muted, false)
	y -= sh + 10*mm
	if len(h.NotCharged) > 0 {
		p.label(mg, y, "OSVOBOZENÉ OSOBY", false, muted)
		p.rule(y-3.5*mm, false)
		y -= 10 * mm
		for _, it := range h.NotCharged {
			p.text(mg, y, it.Reason, 8.5, false, ink, false)
			p.text(rt, y, fmt.Sprintf("%d os. · %s", it.Count, nights(it.Nights)), 8.5, false, ink, true)
			p.rule(y-3.5*mm, false)
			y -= 9 * mm
		}
	}
	return y - 8*mm
}

func signature(p page, y float64, h stayfee.Hlaseni) (float64, error) {
	p.label(mg, y, "ZA PLÁTCE", false, muted)
	p.text(mg, y-8*mm, "Datum: "+czDate(h.IssuedOn), 7.8, false, secondary, false)
	p.text(mg, y-13*mm, "Podpis, razítko / elektronické podání", 7.8, false, muted, false)
	lineY := y - 11*mm
	if h.SignaturePNG != "" {
		raw := h.SignaturePNG
		if i := strings.Index(raw, ","); i >= 0 {
			raw = raw[i+1:]
		}
		raw = strings.Map(func(r rune) rune {
			if r == '\n' || r == '\r' || r == ' ' || r == '\t' {
				return -1
			}
			return r
		}, raw)
		data, err := base64.StdEncoding.DecodeString(raw)
		if err != nil {
			data, err = base64.RawStdEncoding.DecodeString(strings.TrimRight(raw, "="))
		}
		if err != nil {
			return 0, fmt.Errorf("signature image: %w", err)
		}
		cfg, _, err := image.DecodeConfig(bytes.NewReader(data))
		if err != nil || cfg.Width == 0 || cfg.Height == 0 {
			return 0, fmt.Errorf("signature image unreadable: %v", err)
		}
		iw, ih := float64(cfg.Width), float64(cfg.Height)
		scale := min(45*mm/iw, 13*mm/ih)
		p.Image("signature", data, rt-iw*scale, lineY+1.5*mm, iw*scale, ih*scale)
	} else if h.SignatureName != "" {
		p.text(rt, lineY+2*mm, h.SignatureName, 9, true, ink, true)
	}
	// reportlab keeps the last line width of the page (0.55 after any rule);
	// a page without a rule is still at the default 1.
	lw := 1.0
	for _, o := range p.Ops() {
		if o.Kind == "line" {
			lw = o.LW
		}
	}
	p.Line(mg+80*mm, lineY, rt, lineY, lineCol, lw)
	y -= 21 * mm
	if h.Instruction != "" {
		y = p.wrap(mg, y, h.Instruction, rt-mg, 7, false, muted, 9.5)
	}
	return y, nil
}

func signatureHeight(p page, h stayfee.Hlaseni) float64 {
	lines := 0
	if h.Instruction != "" {
		lines = len(p.split(h.Instruction, rt-mg, 7, false))
	}
	return 22*mm + float64(lines)*9.5
}

// Layout draws the hlášení and returns one Doc per page (render).
func Layout(h stayfee.Hlaseni, sample bool) ([]*pdf.Doc, error) {
	if err := Validate(h); err != nil {
		return nil, err
	}
	var docs []*pdf.Doc
	newPage := func() page {
		d := pdf.NewDoc()
		docs = append(docs, d)
		return page{d}
	}
	p := newPage()
	p.Meta("Hlášení k místnímu poplatku z pobytu – "+PeriodPhrase(h), h.PayerName, "UbyHost")
	n := 1
	y := tableHeader(p, pageTop(p, h, false, sample))
	if len(h.Rows) == 0 || (h.TotalCZK == 0 && h.ExemptNights == 0) {
		p.text(mg, y, "V tomto období nevznikla povinnost odvést poplatek.", 9, false, secondary, false)
		y -= 12 * mm
	}
	for _, row := range h.Rows {
		if y-rowHeight(p, row) < 55*mm {
			footer(p, n)
			p = newPage()
			n++
			y = tableHeader(p, pageTop(p, h, true, sample))
		}
		y = tableRow(p, y, row)
	}
	extraNC := 0.0
	if len(h.NotCharged) > 0 {
		extraNC = 10
	}
	need := (27+10+extraNC+float64(len(h.NotCharged))*9+8)*mm + signatureHeight(p, h)
	if y-need < 24*mm {
		footer(p, n)
		p = newPage()
		n++
		y = pageTop(p, h, true, sample)
	}
	y = summary(p, y, h)
	if _, err := signature(p, y, h); err != nil {
		return nil, err
	}
	footer(p, n)
	return docs, nil
}
