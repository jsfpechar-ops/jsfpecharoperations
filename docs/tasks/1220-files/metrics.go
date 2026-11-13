package pdf

import (
	"encoding/binary"
	"errors"
	"strings"
	"unicode"
)

// metrics holds the advance widths of one TrueType font, parsed the way
// reportlab's TTFontFace does (hmtx advances scaled to 1000 units per em; a
// code point without a glyph gets the width of glyph 0; U+00A0 and U+0020
// share one width). That makes Width equal to reportlab's stringWidth.
type metrics struct {
	widths  map[rune]float64
	notdef  float64
	unitsEm float64
}

func parseMetrics(data []byte) (*metrics, error) {
	be := binary.BigEndian
	if len(data) < 12 {
		return nil, errors.New("pdf: font too short")
	}
	n := int(be.Uint16(data[4:]))
	tab := map[string][2]int{}
	for i := 0; i < n; i++ {
		o := 12 + 16*i
		if o+16 > len(data) {
			return nil, errors.New("pdf: bad font table directory")
		}
		tab[string(data[o:o+4])] = [2]int{int(be.Uint32(data[o+8:])), int(be.Uint32(data[o+12:]))}
	}
	for _, t := range []string{"head", "hhea", "maxp", "hmtx", "cmap"} {
		if _, ok := tab[t]; !ok {
			return nil, errors.New("pdf: font lacks table " + t)
		}
	}
	upm := float64(be.Uint16(data[tab["head"][0]+18:]))
	nh := int(be.Uint16(data[tab["hhea"][0]+34:]))
	ng := int(be.Uint16(data[tab["maxp"][0]+4:]))
	scale := 1000.0 / upm
	adv := make([]float64, ng)
	hm := tab["hmtx"][0]
	var last float64
	for g := 0; g < ng; g++ {
		if g < nh {
			last = float64(be.Uint16(data[hm+4*g:])) * scale
		}
		adv[g] = last
	}
	m := &metrics{widths: map[rune]float64{}, notdef: adv[0], unitsEm: upm}
	cm := tab["cmap"][0]
	ns := int(be.Uint16(data[cm+2:]))
	for i := 0; i < ns; i++ {
		off := cm + int(be.Uint32(data[cm+4+8*i+4:]))
		switch be.Uint16(data[off:]) {
		case 4:
			segX2 := int(be.Uint16(data[off+6:]))
			endO := off + 14
			startO := endO + segX2 + 2
			deltaO := startO + segX2
			rangeO := deltaO + segX2
			for s := 0; s < segX2/2; s++ {
				end := int(be.Uint16(data[endO+2*s:]))
				start := int(be.Uint16(data[startO+2*s:]))
				delta := int(be.Uint16(data[deltaO+2*s:]))
				ro := int(be.Uint16(data[rangeO+2*s:]))
				for c := start; c <= end && c != 0xFFFF; c++ {
					var g int
					if ro == 0 {
						g = (c + delta) & 0xFFFF
					} else {
						p := rangeO + 2*s + ro + 2*(c-start)
						g = int(be.Uint16(data[p:]))
						if g != 0 {
							g = (g + delta) & 0xFFFF
						}
					}
					if g != 0 && g < ng {
						m.widths[rune(c)] = adv[g]
					}
				}
			}
		case 12:
			groups := int(be.Uint32(data[off+12:]))
			for k := 0; k < groups; k++ {
				p := off + 16 + 12*k
				sc, ec, sg := be.Uint32(data[p:]), be.Uint32(data[p+4:]), be.Uint32(data[p+8:])
				for c := sc; c <= ec; c++ {
					g := int(sg + (c - sc))
					if g != 0 && g < ng {
						m.widths[rune(c)] = adv[g]
					}
				}
			}
		}
	}
	if w, ok := m.widths[0x20]; ok {
		m.widths[0xa0] = w
	} else if w, ok := m.widths[0xa0]; ok {
		m.widths[0x20] = w
	}
	return m, nil
}

// width is the text width in points at the given size.
func (m *metrics) width(s string, size float64) float64 {
	var sum float64
	for _, r := range s {
		w, ok := m.widths[r]
		if !ok {
			w = m.notdef
		}
		sum += w
	}
	return sum * size * 0.001
}

// pyFields is Python's str.split(): split on Unicode white space, which also
// includes the separators U+001C..U+001F that Go's unicode.IsSpace lacks.
func pyFields(s string) []string {
	return strings.FieldsFunc(s, func(r rune) bool {
		return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
	})
}
