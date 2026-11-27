package cleaning

import (
	"fmt"
	"html/template"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// cleaningPickerCard is one Airbnb-minimal row in the phone Cleaning Property Picker.
type cleaningPickerCard struct {
	ID      int64
	Name    string
	Href    string
	MiniSVG template.HTML
}

type cleaningPickerView struct {
	ShowPicker     bool
	SingleProperty bool
	ShowBackToAll  bool
	PropertyID     int64
	PropertyName   string
	IndexCards     []cleaningPickerCard
}

func buildCleaningPicker(p *payload, rawCalProp string, today time.Time) cleaningPickerView {
	var out cleaningPickerView
	if p == nil || len(p.Properties) == 0 {
		return out
	}

	var selected *propOut
	if id, err := strconv.ParseInt(strings.TrimSpace(rawCalProp), 10, 64); err == nil && id > 0 {
		for i := range p.Properties {
			if p.Properties[i].ID == id {
				selected = &p.Properties[i]
				break
			}
		}
	}

	if selected != nil {
		out.SingleProperty = true
		out.ShowBackToAll = len(p.Properties) >= 2
		out.PropertyID = selected.ID
		out.PropertyName = selected.Name
		return out
	}
	if len(p.Properties) == 1 {
		out.SingleProperty = true
		out.PropertyID = p.Properties[0].ID
		out.PropertyName = p.Properties[0].Name
		return out
	}

	out.ShowPicker = true
	bookingsByProp := make(map[int64][]*booking, len(p.Properties))
	for _, ev := range p.Events {
		if b, ok := ev.(*booking); ok && b != nil {
			bookingsByProp[b.PropertyID] = append(bookingsByProp[b.PropertyID], b)
		}
	}
	cleaningsByProp := make(map[int64][]*cleaningItem, len(p.Properties))
	for _, c := range p.Cleanings {
		if c != nil {
			cleaningsByProp[c.PropertyID] = append(cleaningsByProp[c.PropertyID], c)
		}
	}
	out.IndexCards = make([]cleaningPickerCard, 0, len(p.Properties))
	for _, prop := range p.Properties {
		out.IndexCards = append(out.IndexCards, cleaningPickerCard{
			ID:      prop.ID,
			Name:    prop.Name,
			Href:    fmt.Sprintf("/cleaning?cal_property=%d", prop.ID),
			MiniSVG: renderCleaningMiniMonthSVG(bookingsByProp[prop.ID], cleaningsByProp[prop.ID], today),
		})
	}
	return out
}

// renderCleaningMiniMonthSVG renders a quiet 5-week Monday-first mini-calendar
// SVG (112x66) showing bookings as calm bars and scheduled cleanings in amber.
func renderCleaningMiniMonthSVG(bookings []*booking, cleanings []*cleaningItem, today time.Time) template.HTML {
	t := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC)
	wd := (int(t.Weekday()) + 6) % 7 // Mon=0..Sun=6
	start := t.AddDate(0, 0, -wd)
	const (
		days = 35
		colW = 16
		rowH = 13
	)
	end := start.AddDate(0, 0, days-1)

	var b strings.Builder
	b.WriteString(`<svg class="mini-cal-svg" width="112" height="66" viewBox="0 0 112 66" aria-hidden="true" focusable="false">`)

	for i := 0; i < days; i++ {
		cx := (i%7)*colW + 8
		cy := (i/7)*rowH + 7
		fmt.Fprintf(&b, `<circle class="mini-cal-dot" cx="%d" cy="%d" r="2"/>`, cx, cy)
	}

	for _, bk := range bookings {
		from, ok1 := validation.ParseISODate(bk.Start)
		to, ok2 := validation.ParseISODate(bk.End)
		if !ok1 || !ok2 {
			continue
		}
		lastNight := to.AddDate(0, 0, -1)
		if lastNight.Before(from) {
			lastNight = from
		}
		if lastNight.Before(start) || from.After(end) {
			continue
		}
		sIdx := int(from.Sub(start).Hours() / 24)
		if sIdx < 0 {
			sIdx = 0
		}
		eIdx := int(lastNight.Sub(start).Hours() / 24)
		if eIdx >= days {
			eIdx = days - 1
		}
		for cur := sIdx; cur <= eIdx; {
			wk := cur / 7
			wkEnd := wk*7 + 6
			segEnd := eIdx
			if segEnd > wkEnd {
				segEnd = wkEnd
			}
			c1 := cur % 7
			c2 := segEnd % 7
			x := c1*colW + 3
			w := (c2-c1+1)*colW - 6
			y := wk*rowH + 4
			fmt.Fprintf(&b, `<rect class="mini-cal-bar mini-cal-bar-calm" x="%d" y="%d" width="%d" height="6" rx="3"/>`, x, y, w)
			cur = segEnd + 1
		}
	}

	seenCleanDay := make(map[int]bool, len(cleanings))
	for _, cl := range cleanings {
		d, ok := validation.ParseISODate(cl.Date)
		if !ok || d.Before(start) || d.After(end) {
			continue
		}
		idx := int(d.Sub(start).Hours() / 24)
		if idx < 0 || idx >= days || seenCleanDay[idx] {
			continue
		}
		seenCleanDay[idx] = true
		wk := idx / 7
		col := idx % 7
		x := col*colW + 3
		y := wk*rowH + 4
		fmt.Fprintf(&b, `<rect class="mini-cal-bar mini-cal-bar-warn" x="%d" y="%d" width="10" height="6" rx="3"/>`, x, y)
	}

	tx := wd*colW + 8
	ty := 7
	fmt.Fprintf(&b, `<circle class="mini-cal-today" cx="%d" cy="%d" r="4.8" fill="none" stroke-width="1.5"/>`, tx, ty)
	b.WriteString(`</svg>`)
	return template.HTML(b.String())
}
