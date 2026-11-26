package stays

import (
	"context"
	"fmt"
	"html"
	"html/template"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

// JourneyStep is one icon step in the 4-step stay journey strip:
// Link (mail) -> Form (users) -> Code (key-round) -> Police (police).
type JourneyStep struct {
	Key      string // "link" | "form" | "code" | "police"
	Icon     string // "mail" | "users" | "key-round" | "police"
	Tone     string // "waiting" | "progress" | "done" | "bad"
	Counter  string // e.g. "1/2" for form step
	StateKey string // i18n suffix: "unclaimed", "sent", "verified", "empty", "partial", "complete", "waiting", "issuing", "ready", "available", "failed", "pending", "filed", "action"
}

// StayJourney is the ordered list of applicable journey steps for one stay.
type StayJourney struct {
	Steps []JourneyStep
}

// JourneySignal holds non-sensitive DB booleans and states used to compute a
// stay's 4-step journey. Raw PINs, entry codes, emails, and IDs are never read.
type JourneySignal struct {
	ClaimState           string
	CompletionNotifiedAt string
	DoorCodeState        string
	DoorCodeNotifiedAt   string
	HasTTLock            bool
	HasEntryCode         bool
	FilesUbyPort         bool
}

const journeySignalsSQL = `
SELECT r.id,
  COALESCE(rc.state, 'unclaimed'),
  COALESCE(rc.completion_notified_at, ''),
  COALESCE(dc.state, ''),
  COALESCE(dc.notified_at, ''),
  (COALESCE(a.lock_provider, '') = 'ttlock' AND COALESCE(a.lock_id, '') <> '') AS has_ttlock,
  (EXISTS (
     SELECT 1 FROM apartment_entry_code c
     WHERE c.apartment_id = a.id
       AND (c.valid_until IS NULL OR c.valid_until = '' OR c.valid_until >= $2)
   ) OR (
     COALESCE(a.entry_code_enc, '') <> ''
     AND (a.entry_code_until IS NULL OR a.entry_code_until = '' OR a.entry_code_until >= $2)
   )) AS has_entry_code,
  (COALESCE(TRIM(a.uby_idub), '') <> ''
   AND COALESCE(TRIM(a.uby_ws_user), '') <> ''
   AND COALESCE(TRIM(a.uby_ws_password_enc), '') <> '') AS files_ubyport
FROM reservation r
JOIN apartment a ON a.id = r.apartment_id
LEFT JOIN reservation_claim rc ON rc.reservation_id = r.id
LEFT JOIN door_code dc ON dc.reservation_id = r.id
WHERE r.id = ANY($1::bigint[])`

// LoadJourneySignals loads claim, door-code, entry-code, and UbyPort flags for
// a batch of reservations in a single query.
func LoadJourneySignals(ctx context.Context, pool *pgxpool.Pool, reservationIDs []int64, today time.Time) (map[int64]JourneySignal, error) {
	out := make(map[int64]JourneySignal, len(reservationIDs))
	if len(reservationIDs) == 0 || pool == nil {
		return out, nil
	}
	todayISO := today.Format("2006-01-02")
	rows, err := pool.Query(ctx, journeySignalsSQL, reservationIDs, todayISO)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var sig JourneySignal
		if err := rows.Scan(
			&id, &sig.ClaimState, &sig.CompletionNotifiedAt,
			&sig.DoorCodeState, &sig.DoorCodeNotifiedAt,
			&sig.HasTTLock, &sig.HasEntryCode, &sig.FilesUbyPort,
		); err != nil {
			return nil, err
		}
		out[id] = sig
	}
	return out, rows.Err()
}

// BuildJourney computes the chronological 4-step journey for an active stay.
// Non-active (cancelled/ignored) stays return an empty StayJourney.
func BuildJourney(res Reservation, prog Progress, sig JourneySignal, today time.Time) StayJourney {
	if res.Status != "" && res.Status != "active" {
		return StayJourney{}
	}
	steps := make([]JourneyStep, 0, 4)

	// 1. Link
	linkTone, linkState := "waiting", "unclaimed"
	switch sig.ClaimState {
	case "claimed":
		linkTone, linkState = "done", "verified"
	case "provisional":
		linkTone, linkState = "progress", "sent"
	}
	steps = append(steps, JourneyStep{
		Key: "link", Icon: "mail", Tone: linkTone, StateKey: linkState,
	})

	// 2. Form
	counter := strconv.Itoa(prog.Filled)
	if prog.Expected != nil && *prog.Expected > 0 {
		counter = fmt.Sprintf("%d/%d", prog.Filled, *prog.Expected)
	}
	formTone, formState := "done", "complete"
	if prog.Filled == 0 && prog.Incomplete == 0 {
		formTone, formState = "waiting", "empty"
	} else if prog.Incomplete > 0 || (prog.Expected != nil && prog.Filled < *prog.Expected) {
		formTone, formState = "progress", "partial"
	}
	steps = append(steps, JourneyStep{
		Key: "form", Icon: "users", Tone: formTone, Counter: counter, StateKey: formState,
	})

	// 3. Code (only when the property uses the smart lock feature)
	if sig.HasTTLock {
		codeTone, codeState := "waiting", "waiting"
		switch sig.DoorCodeState {
		case "failed":
			codeTone, codeState = "bad", "failed"
		case "delayed", "retrying", "issuing":
			codeTone, codeState = "progress", "issuing"
		case "issued":
			if strings.TrimSpace(sig.DoorCodeNotifiedAt) != "" || strings.TrimSpace(sig.CompletionNotifiedAt) != "" {
				codeTone, codeState = "done", "sent"
			} else {
				codeTone, codeState = "progress", "ready"
			}
		}
		steps = append(steps, JourneyStep{
			Key: "code", Icon: "key-round", Tone: codeTone, StateKey: codeState,
		})
	}

	// 4. Police (only when property has UbyPort credentials and stay is not demo)
	if sig.FilesUbyPort && !isDemo(res.InternalName, res.Source) {
		polTone, polState := "waiting", "waiting"
		switch {
		case prog.Status == "failed" || prog.Cell.Level == "overdue":
			polTone, polState = "bad", "action"
		case prog.Status == "reported" || prog.Status == "not_required" || prog.Cell.State == "filed_on_time":
			polTone, polState = "done", "filed"
		case prog.Status == "ready" || prog.Status == "awaiting_verification" || prog.Cell.State == "filed_late":
			polTone, polState = "progress", "pending"
		}
		steps = append(steps, JourneyStep{
			Key: "police", Icon: "police", Tone: polTone, StateKey: polState,
		})
	}

	return StayJourney{Steps: steps}
}

// BuildJourneyFromCounts constructs a StayJourney when only aggregate guest
// counts and a status string are available (for Dashboard summary rows).
func BuildJourneyFromCounts(status, source, internalName, dateFrom, dateTo string, filled int, expected *int, incomplete int, reportStatus, cellState, cellLevel string, sig JourneySignal, today time.Time) StayJourney {
	res := Reservation{
		Status:       status,
		Source:       source,
		InternalName: internalName,
		DateFrom:     dateFrom,
		DateTo:       dateTo,
	}
	prog := Progress{
		Filled:     filled,
		Expected:   expected,
		Incomplete: incomplete,
		Status:     reportStatus,
		Cell:       layout.DeadlineCell{State: cellState, Level: cellLevel},
	}
	return BuildJourney(res, prog, sig, today)
}

func stepLabel(lang string, s JourneyStep) (name, state, full string) {
	name = catalog.T(lang, "stays.journey.step."+s.Key, nil)
	state = catalog.T(lang, "stays.journey.state."+s.Key+"."+s.StateKey, nil)
	if s.Counter != "" {
		full = fmt.Sprintf("%s: %s (%s)", name, state, s.Counter)
	} else {
		full = fmt.Sprintf("%s: %s", name, state)
	}
	return name, state, full
}

// RenderJourneyStrip renders the compact 4-step icon strip for list rows,
// phone cards, and dashboard rails. Never leaks raw PINs, codes, or emails.
func RenderJourneyStrip(lang string, j StayJourney) template.HTML {
	if len(j.Steps) == 0 {
		return ""
	}
	parts := make([]string, 0, len(j.Steps))
	var items strings.Builder
	for _, s := range j.Steps {
		_, _, full := stepLabel(lang, s)
		parts = append(parts, full)
		items.WriteString(`<span class="stay-journey-step" data-step="`)
		items.WriteString(html.EscapeString(s.Key))
		items.WriteString(`" data-tone="`)
		items.WriteString(html.EscapeString(s.Tone))
		items.WriteString(`" title="`)
		items.WriteString(html.EscapeString(full))
		items.WriteString(`">`)
		items.WriteString(string(layout.Icon(s.Icon, 14)))
		if s.Counter != "" {
			items.WriteString(`<span class="stay-journey-count">`)
			items.WriteString(html.EscapeString(s.Counter))
			items.WriteString(`</span>`)
		}
		items.WriteString(`</span>`)
	}
	aria := strings.Join(parts, ", ")
	return template.HTML(`<span class="stay-journey" role="group" aria-label="` + html.EscapeString(aria) + `">` + items.String() + `</span>`)
}

// RenderJourneyBar renders the labeled horizontal 4-step checklist shown at
// the top of Stay Detail, reusing the exact same icons, order, and tones.
func RenderJourneyBar(lang string, j StayJourney) template.HTML {
	if len(j.Steps) == 0 {
		return ""
	}
	var b strings.Builder
	barLabel := catalog.T(lang, "stays.journey.bar_aria", nil)
	b.WriteString(`<ol class="stay-journey-bar" aria-label="`)
	b.WriteString(html.EscapeString(barLabel))
	b.WriteString(`">`)
	for _, s := range j.Steps {
		name, state, _ := stepLabel(lang, s)
		b.WriteString(`<li class="stay-journey-bar-step" data-step="`)
		b.WriteString(html.EscapeString(s.Key))
		b.WriteString(`" data-tone="`)
		b.WriteString(html.EscapeString(s.Tone))
		b.WriteString(`">`)
		b.WriteString(`<span class="stay-journey-bar-icon">`)
		b.WriteString(string(layout.Icon(s.Icon, 16)))
		b.WriteString(`</span>`)
		b.WriteString(`<span class="stay-journey-bar-copy"><strong>`)
		b.WriteString(html.EscapeString(name))
		if s.Counter != "" {
			b.WriteString(` <span class="stay-journey-bar-count">`)
			b.WriteString(html.EscapeString(s.Counter))
			b.WriteString(`</span>`)
		}
		b.WriteString(`</strong><small>`)
		b.WriteString(html.EscapeString(state))
		b.WriteString(`</small></span></li>`)
	}
	b.WriteString(`</ol>`)
	return template.HTML(b.String())
}
