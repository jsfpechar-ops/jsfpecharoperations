// Package pdf draws one-page A4 documents with embedded DejaVu Sans (regular
// and bold, the same fonts reportlab uses in App/app/invoice_pdf.py).
//
// Generic layer (reusable by other documents, for example stay-fee
// remittance PDFs):
//
//	d := pdf.NewDoc()                            // A4, bottom-left origin in points, like reportlab
//	d.Meta(title, author, creator)
//	d.Text(x, y, s, pdf.Reg, 9, pdf.Ink)         // drawString; y is the baseline
//	d.TextRight(x, y, s, pdf.Bold, 9, pdf.Ink)   // drawRightString
//	y = d.Wrap(x, y, s, width, pdf.Reg, 9, pdf.Ink, 0) // simpleSplit wrap; returns the next baseline
//	d.Width(pdf.Bold, "text", 7)                 // reportlab stringWidth
//	d.SimpleSplit(s, pdf.Reg, 9, width)          // reportlab simpleSplit
//	d.Rect(x, y, w, h, r, fill, stroke, lw)      // r > 0: rounded; fill/stroke may be nil
//	d.Line(x1, y1, x2, y2, color, lw)
//	d.Image(name, pngBytes, x, y, w, h)          // PNG with alpha
//	d.Link(url, x1, y1, x2, y2)
//	d.Watermark(s, pdf.Bold, 34, color, alpha, angle, cx, cy)
//	d.Ops()                                      // the recorded draw operations (golden tests)
//	d.Bytes()                                    // the PDF, byte-identical for identical input
//
// Every call is recorded as an Op first; Bytes replays the ops into gopdf. The
// layout is therefore testable without a PDF parser: the golden files in
// testdata hold the ops that App/app/invoice_pdf.py draws on the reportlab
// canvas. Units are points (1 mm = MM points).
package pdf

import (
	"bytes"
	_ "embed"
	"math"
	"strings"
	"time"

	"github.com/signintech/gopdf"
)

//go:embed fonts/DejaVuSans.ttf
var fontReg []byte

//go:embed fonts/DejaVuSans-Bold.ttf
var fontBold []byte

// Font names, as in Python (REG, BOLD).
const (
	Reg  = "UHSans"
	Bold = "UHSans-Bold"
)

// Page size (A4) and unit.
const (
	W  = 595.2755905511812
	H  = 841.8897637795277
	MM = 72.0 / 25.4
)

// Color is an RGB triple in 0..1.
type Color [3]float64

// RGB builds a Color from 0..255 values (the Python tokens are n/255).
func RGB(r, g, b int) Color { return Color{float64(r) / 255, float64(g) / 255, float64(b) / 255} }

var (
	regM, boldM *metrics
	fixedDate   = time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
)

func init() {
	var err error
	if regM, err = parseMetrics(fontReg); err != nil {
		panic(err)
	}
	if boldM, err = parseMetrics(fontBold); err != nil {
		panic(err)
	}
}

// Op is one recorded draw operation. Map gives the JSON form the golden files use.
type Op struct {
	Kind                   string // text, rect, line, image, link, watermark, meta
	S, Font, Name, URL     string
	Title, Author, Creator string
	Size, X, Y, W, H, R    float64
	X2, Y2, LW, Alpha, Ang float64
	Fill, Stroke, Color    *Color
	Right                  bool
	PNG                    []byte
}

func col(c *Color) []float64 { return []float64{c[0], c[1], c[2]} }

// Map is the golden-file form of the op (no image bytes; the layout tests
// compare geometry and colours, not pixels).
func (o Op) Map() map[string]any {
	m := map[string]any{"op": o.Kind}
	switch o.Kind {
	case "text":
		m["s"], m["font"], m["size"], m["x"], m["y"] = o.S, o.Font, o.Size, o.X, o.Y
		m["color"] = col(o.Color)
		m["align"] = "left"
		if o.Right {
			m["align"] = "right"
		}
	case "rect":
		m["x"], m["y"], m["w"], m["h"], m["r"] = o.X, o.Y, o.W, o.H, o.R
		if o.Fill != nil {
			m["fill"] = col(o.Fill)
		}
		if o.Stroke != nil {
			m["stroke"], m["lw"] = col(o.Stroke), o.LW
		}
	case "line":
		m["x"], m["y"], m["x2"], m["y2"], m["lw"], m["color"] = o.X, o.Y, o.X2, o.Y2, o.LW, col(o.Color)
	case "image":
		m["name"], m["x"], m["y"], m["w"], m["h"] = o.Name, o.X, o.Y, o.W, o.H
		if o.S != "" {
			m["payload"] = o.S // the SPAYD text a QR image encodes
		}
	case "link":
		m["url"], m["x"], m["y"], m["x2"], m["y2"] = o.URL, o.X, o.Y, o.X2, o.Y2
	case "watermark":
		m["s"], m["font"], m["size"], m["color"] = o.S, o.Font, o.Size, col(o.Color)
		m["alpha"], m["angle"], m["x"], m["y"] = o.Alpha, o.Ang, o.X, o.Y
	case "meta":
		m["title"], m["author"], m["creator"] = o.Title, o.Author, o.Creator
	}
	return m
}

// Doc records the operations of one A4 page.
type Doc struct{ ops []Op }

// NewDoc starts an empty page.
func NewDoc() *Doc { return &Doc{} }

// Ops returns the recorded operations.
func (d *Doc) Ops() []Op { return d.ops }

func fontMetrics(font string) *metrics {
	if font == Bold {
		return boldM
	}
	return regM
}

// Width is reportlab's pdfmetrics.stringWidth.
func (d *Doc) Width(font, s string, size float64) float64 {
	return fontMetrics(font).width(s, size)
}

// SimpleSplit is reportlab's simpleSplit (greedy wrap on white space; a word
// wider than the line stays alone on its line).
func (d *Doc) SimpleSplit(text, font string, size, maxW float64) []string {
	sw := func(s string) float64 { return d.Width(font, s, size) }
	var out []string
	for _, line := range strings.Split(text, "\n") {
		ws := sw(" ")
		var cur []string
		w := -ws
		for _, t := range pyFields(line) {
			lt := sw(t)
			if w+ws+lt <= maxW || len(cur) == 0 {
				cur = append(cur, t)
				w = w + ws + lt
			} else {
				out = append(out, strings.Join(cur, " "))
				cur = []string{t}
				w = lt
			}
		}
		if len(cur) > 0 {
			out = append(out, strings.Join(cur, " "))
		}
	}
	return out
}

// Meta sets title, author and creator.
func (d *Doc) Meta(title, author, creator string) {
	d.ops = append(d.ops, Op{Kind: "meta", Title: title, Author: author, Creator: creator})
}

// Text is drawString: x is the left edge, y the baseline.
func (d *Doc) Text(x, y float64, s, font string, size float64, c Color) {
	d.ops = append(d.ops, Op{Kind: "text", X: x, Y: y, S: s, Font: font, Size: size, Color: &c})
}

// TextRight is drawRightString: x is the right edge.
func (d *Doc) TextRight(x, y float64, s, font string, size float64, c Color) {
	d.ops = append(d.ops, Op{Kind: "text", X: x, Y: y, S: s, Font: font, Size: size, Color: &c, Right: true})
}

// Wrap draws s wrapped to width, one line per leading (0 means 1.35 * size),
// and returns the baseline of the next line (_wrap in Python).
func (d *Doc) Wrap(x, y float64, s string, width float64, font string, size float64, c Color, leading float64) float64 {
	if leading == 0 {
		leading = size * 1.35
	}
	for _, line := range d.SimpleSplit(s, font, size, width) {
		d.Text(x, y, line, font, size, c)
		y -= leading
	}
	return y
}

// Rect draws a rectangle (r = 0) or a rounded rectangle; fill and stroke may be nil.
func (d *Doc) Rect(x, y, w, h, r float64, fill, stroke *Color, lw float64) {
	d.ops = append(d.ops, Op{Kind: "rect", X: x, Y: y, W: w, H: h, R: r, Fill: fill, Stroke: stroke, LW: lw})
}

// Line draws a line with the given colour and width.
func (d *Doc) Line(x1, y1, x2, y2 float64, c Color, lw float64) {
	d.ops = append(d.ops, Op{Kind: "line", X: x1, Y: y1, X2: x2, Y2: y2, Color: &c, LW: lw})
}

// Image draws a PNG (alpha kept) into the box; name labels it in the ops.
func (d *Doc) Image(name string, png []byte, x, y, w, h float64) {
	d.ops = append(d.ops, Op{Kind: "image", Name: name, PNG: png, X: x, Y: y, W: w, H: h})
}

// Link adds a clickable external link over the box.
func (d *Doc) Link(url string, x1, y1, x2, y2 float64) {
	d.ops = append(d.ops, Op{Kind: "link", URL: url, X: x1, Y: y1, X2: x2, Y2: y2})
}

// Watermark draws centred text rotated by angle degrees around (cx, cy), with
// fill transparency alpha.
func (d *Doc) Watermark(s, font string, size float64, c Color, alpha, angle, cx, cy float64) {
	d.ops = append(d.ops, Op{Kind: "watermark", S: s, Font: font, Size: size, Color: &c, Alpha: alpha, Ang: angle, X: cx, Y: cy})
}

func u8(v float64) uint8 { return uint8(math.Round(v * 255)) }

// Bytes replays the ops into a PDF. Creation date and ids are fixed, so the
// same ops always give the same bytes.
func (d *Doc) Bytes() ([]byte, error) {
	p := &gopdf.GoPdf{}
	p.Start(gopdf.Config{Unit: gopdf.UnitPT, PageSize: gopdf.Rect{W: W, H: H}})
	if err := p.AddTTFFontData(Reg, fontReg); err != nil {
		return nil, err
	}
	if err := p.AddTTFFontData(Bold, fontBold); err != nil {
		return nil, err
	}
	p.AddPage()
	info := gopdf.PdfInfo{Producer: "UbyHost", Creator: "UbyHost", CreationDate: fixedDate}
	for _, o := range d.ops {
		switch o.Kind {
		case "meta":
			info.Title, info.Author, info.Creator = o.Title, o.Author, o.Creator
		case "text":
			if err := p.SetFont(o.Font, "", o.Size); err != nil {
				return nil, err
			}
			p.SetTextColor(u8(o.Color[0]), u8(o.Color[1]), u8(o.Color[2]))
			x := o.X
			if o.Right {
				x -= fontMetrics(o.Font).width(o.S, o.Size)
			}
			p.SetXY(x, H-o.Y-baselineOffset(o.Size))
			if err := p.Text(o.S); err != nil {
				return nil, err
			}
		case "rect":
			style := ""
			if o.Fill != nil {
				p.SetFillColor(u8(o.Fill[0]), u8(o.Fill[1]), u8(o.Fill[2]))
				style += "F"
			}
			if o.Stroke != nil {
				p.SetStrokeColor(u8(o.Stroke[0]), u8(o.Stroke[1]), u8(o.Stroke[2]))
				p.SetLineWidth(o.LW)
				style += "D"
			}
			top := H - (o.Y + o.H)
			if o.R > 0 {
				if err := p.Rectangle(o.X, top, o.X+o.W, top+o.H, style, o.R, 20); err != nil {
					return nil, err
				}
			} else {
				p.SetLineWidth(0)
				if err := p.Rectangle(o.X, top, o.X+o.W, top+o.H, style, 0, 0); err != nil {
					return nil, err
				}
			}
		case "line":
			p.SetStrokeColor(u8(o.Color[0]), u8(o.Color[1]), u8(o.Color[2]))
			p.SetLineWidth(o.LW)
			p.Line(o.X, H-o.Y, o.X2, H-o.Y2)
		case "image":
			h, err := gopdf.ImageHolderByBytes(o.PNG)
			if err != nil {
				return nil, err
			}
			if err := p.ImageByHolderWithOptions(h, gopdf.ImageOptions{X: o.X, Y: H - o.Y - o.H, Rect: &gopdf.Rect{W: o.W, H: o.H}}); err != nil {
				return nil, err
			}
		case "link":
			p.AddExternalLink(o.URL, o.X, H-o.Y2, o.X2-o.X, o.Y2-o.Y)
		case "watermark":
			if err := p.SetFont(o.Font, "", o.Size); err != nil {
				return nil, err
			}
			p.SetTextColor(u8(o.Color[0]), u8(o.Color[1]), u8(o.Color[2]))
			p.Rotate(o.Ang, o.X, H-o.Y)
			p.SetXY(o.X-fontMetrics(o.Font).width(o.S, o.Size)/2, H-o.Y-wmOffset(o.Font, o.Size))
			opt := gopdf.CellOption{Transparency: &gopdf.Transparency{Alpha: o.Alpha, BlendModeType: gopdf.NormalBlendMode}}
			if err := p.CellWithOption(&gopdf.Rect{W: fontMetrics(o.Font).width(o.S, o.Size) + 1, H: o.Size}, o.S, opt); err != nil {
				return nil, err
			}
			p.RotateReset()
		}
	}
	p.SetInfo(info)
	var buf bytes.Buffer
	if _, err := p.WriteTo(&buf); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// baselineOffset is how far below the gopdf cursor y the text baseline falls.
// Calibrated by TestBaseline against the content stream.
func baselineOffset(size float64) float64 { return 0 }

// wmOffset is the distance from the top of a gopdf cell to the text baseline
// (calibrated against the content stream: the baseline lands on the requested y).
func wmOffset(font string, size float64) float64 { return size * 25.83 / 34 }
