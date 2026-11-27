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
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// JourneyStep is one icon step in the chronological stay journey strip:
// Email (mail/mail-x) -> Link opened (mail-open) -> Form (users) ->
// [TTLock Code (key-round)] -> Police (police).
type JourneyStep struct {
	Key      string // "email" | "opened" | "form" | "code" | "police"
	Icon     string // "mail" | "mail-x" | "mail-open" | "users" | "key-round" | "police"
	Tone     string // "waiting" | "scheduled" | "progress" | "done" | "bad"
	Counter  string // e.g. "1/2" for form or partial police
	StateKey string // i18n suffix under stays.journey.state.<Key>.<StateKey>
	Extra    string // optional non-PII suffix such as scheduled Prague timestamp ("12.11. 15:04")
	LinkHref string // optional secondary action link shown in Stay Detail bar (e.g. "/housebook")
	LinkKey  string // i18n key for LinkHref label
}

// StayJourney is the ordered list of applicable journey steps for one stay.
type StayJourney struct {
	Steps []JourneyStep
}

// JourneySignal holds non-sensitive DB booleans and states used to compute a
// stay's chronological journey. Raw PINs, entry codes, emails, and IDs are never read.
type JourneySignal struct {
	ClaimState           string
	ClaimMailState       string
	CompletionNotifiedAt string
	DoorCodeState        string
	DoorCodeNotifiedAt   string
	HasTTLock            bool
	FilesUbyPort         bool
	AutomationMode       string
	CheckinHour          *int
}

const journeySignalsSQL = `
SELECT r.id,
  COALESCE(rc.state, 'unclaimed'),
  COALESCE(cm.claim_mail_state, ''),
  COALESCE(rc.completion_notified_at, ''),
  COALESCE(dc.state, ''),
  COALESCE(dc.notified_at, ''),
  (COALESCE(a.lock_provider, '') = 'ttlock' AND COALESCE(a.lock_id, '') <> '') AS has_ttlock,
  (COALESCE(TRIM(a.uby_idub), '') <> ''
   AND COALESCE(TRIM(a.uby_ws_user), '') <> ''
   AND COALESCE(TRIM(a.uby_ws_password_enc), '') <> '') AS files_ubyport,
  COALESCE(NULLIF(TRIM(a.automation_mode), ''), 'manual') AS automation_mode,
  a.checkin_hour
FROM reservation r
JOIN apartment a ON a.id = r.apartment_id
LEFT JOIN reservation_claim rc ON rc.reservation_id = r.id
LEFT JOIN LATERAL (
  SELECT COALESCE(o.state, '') AS claim_mail_state
  FROM email_outbox o
  WHERE o.reservation_id = r.id
    AND o.kind IN ('claim', 'claim_resend')
  ORDER BY o.id DESC
  LIMIT 1
) cm ON TRUE
LEFT JOIN door_code dc ON dc.reservation_id = r.id
WHERE r.id = ANY($1::bigint[])`

// LoadJourneySignals loads claim, claim-email SES outbox, TTLock door-code,
// UbyPort, and automation flags for a batch of reservations in one query.
func LoadJourneySignals(ctx context.Context, pool *pgxpool.Pool, reservationIDs []int64, _ time.Time) (map[int64]JourneySignal, error) {
	out := make(map[int64]JourneySignal, len(reservationIDs))
	if len(reservationIDs) == 0 || pool == nil {
		return out, nil
	}
	rows, err := pool.Query(ctx, journeySignalsSQL, reservationIDs)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var sig JourneySignal
		if err := rows.Scan(
			&id, &sig.ClaimState, &sig.ClaimMailState, &sig.CompletionNotifiedAt,
			&sig.DoorCodeState, &sig.DoorCodeNotifiedAt,
			&sig.HasTTLock, &sig.FilesUbyPort, &sig.AutomationMode, &sig.CheckinHour,
		); err != nil {
			return nil, err
		}
		out[id] = sig
	}
	return out, rows.Err()
}

func isClaimMailFailed(state string) bool {
	return state == "failed" || state == "bounced" || state == "complained"
}

func isClaimMailSending(state string) bool {
	return state == "queued" || state == "sending"
}

// BuildJourney computes the chronological 5-step (4 without TTLock) journey for
// a stay. Cancelled stays that already reported guests to UbyPort retain a
// single red warning step; other non-active stays return an empty StayJourney.
func BuildJourney(res Reservation, prog Progress, sig JourneySignal, today time.Time) StayJourney {
	demo := isDemo(res.InternalName, res.Source)
	if res.Status != "" && res.Status != "active" {
		if res.Status == "cancelled" && prog.ReportedCount > 0 && !demo {
			return StayJourney{Steps: []JourneyStep{{
				Key: "police", Icon: "police", Tone: "bad", StateKey: "cancelled_after_report",
			}}}
		}
		return StayJourney{}
	}

	todayDate := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC)
	checkInDate, hasCheckIn := validation.ParseISODate(res.DateFrom)
	isCheckInDayOrPast := hasCheckIn && !todayDate.Before(checkInDate)

	hasAnyGuest := prog.Filled > 0 || prog.Incomplete > 0
	formComplete := prog.Filled > 0 && prog.Incomplete == 0 && (prog.Expected == nil || prog.Filled >= *prog.Expected)
	claimUnclaimed := sig.ClaimState == "" || sig.ClaimState == "unclaimed"
	// Host manual override: host entered guests without a magic link, or finished
	// entering all guests manually after an invite was never opened / bounced.
	manualOverride := (claimUnclaimed && hasAnyGuest) || (sig.ClaimState == "provisional" && formComplete)

	steps := make([]JourneyStep, 0, 5)

	// 1. Email (AWS SES delivery tracking)
	emailIcon, emailTone, emailState := "mail", "waiting", "not_started"
	switch {
	case manualOverride:
		emailTone, emailState = "done", "manual"
	case sig.ClaimState == "claimed":
		emailTone, emailState = "done", "sent"
	case isClaimMailFailed(sig.ClaimMailState):
		emailIcon, emailTone, emailState = "mail-x", "bad", "failed"
	case isClaimMailSending(sig.ClaimMailState):
		emailTone, emailState = "progress", "sending"
	case sig.ClaimMailState == "sent" || sig.ClaimState == "provisional":
		emailTone, emailState = "done", "sent"
	case isCheckInDayOrPast:
		emailTone, emailState = "progress", "not_sent"
	}
	steps = append(steps, JourneyStep{
		Key: "email", Icon: emailIcon, Tone: emailTone, StateKey: emailState,
	})

	// 2. Link opened (guest clicked magic link and unlocked form)
	openTone, openState := "waiting", "not_opened"
	switch {
	case manualOverride:
		openTone, openState = "done", "manual"
	case sig.ClaimState == "claimed":
		openTone, openState = "done", "opened"
	case isClaimMailFailed(sig.ClaimMailState):
		// Step 1 already shows red; keep Step 2 neutral so only one icon screams red.
		openTone, openState = "waiting", "not_opened"
	case sig.ClaimState == "provisional" || sig.ClaimMailState == "sent" || isClaimMailSending(sig.ClaimMailState):
		openTone, openState = "progress", "unopened"
	}
	steps = append(steps, JourneyStep{
		Key: "opened", Icon: "mail-open", Tone: openTone, StateKey: openState,
	})

	// 3. Guest form (+ Domovní kniha when complete)
	counter := strconv.Itoa(prog.Filled)
	if prog.Expected != nil && *prog.Expected > 0 {
		counter = fmt.Sprintf("%d/%d", prog.Filled, *prog.Expected)
	}
	formStep := JourneyStep{Key: "form", Icon: "users", Counter: counter}
	switch {
	case formComplete:
		formStep.Tone, formStep.StateKey = "done", "complete"
		formStep.LinkHref, formStep.LinkKey = "/housebook", "stays.journey.housebook_link"
	case hasAnyGuest:
		formStep.Tone, formStep.StateKey = "progress", "partial"
	case isCheckInDayOrPast:
		formStep.Tone, formStep.StateKey = "progress", "missing_today"
	default:
		formStep.Tone, formStep.StateKey = "waiting", "empty"
	}
	steps = append(steps, formStep)

	// 4. Smart lock code (TTLock only; static saved entry codes are separate)
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

	// 5. Foreign Police / UbyPort (every non-demo stay)
	if !demo {
		polStep := JourneyStep{Key: "police", Icon: "police", Tone: "waiting", StateKey: "waiting"}
		mode := sig.AutomationMode
		if mode == "" {
			mode = res.AutomationMode
		}
		switch {
		case prog.Status == "not_required":
			// Czech-only stays never need UbyPort, even on unconnected properties.
			polStep.Tone, polStep.StateKey = "done", "not_required"
		case prog.Status == "reported" || prog.Cell.State == "filed_on_time" || prog.Cell.State == "filed_late":
			polStep.Tone = "done"
			if prog.Cell.ByHand {
				polStep.StateKey = "filed_manual"
			} else {
				polStep.StateKey = "filed"
			}
		case prog.Status == "failed" || prog.Cell.Level == "overdue":
			polStep.Tone = "bad"
			if prog.Cell.Level == "overdue" {
				polStep.StateKey = "overdue"
			} else {
				polStep.StateKey = "failed"
			}
		case !sig.FilesUbyPort:
			polStep.StateKey = "not_connected"
			if prog.ReportableCount > 0 || prog.Status == "ready" || prog.Status == "awaiting_verification" || prog.Filled > 0 {
				polStep.Tone = "bad"
			}
		case prog.Status == "awaiting_verification":
			polStep.Tone, polStep.StateKey = "progress", "verify_id"
		case prog.ReportedCount > 0 && (prog.Status == "incomplete" || (prog.ReportableCount > 0 && prog.ReportedCount < prog.ReportableCount)):
			denom := prog.ReportableCount
			if prog.Status == "incomplete" && prog.Expected != nil && *prog.Expected > denom {
				denom = *prog.Expected
			}
			if denom < prog.ReportedCount {
				denom = prog.ReportedCount
			}
			polStep.Tone, polStep.StateKey = "progress", "partial"
			polStep.Counter = fmt.Sprintf("%d/%d", prog.ReportedCount, denom)
		case prog.Status == "ready":
			if mode == "scheduled" || mode == "immediate" {
				polStep.Tone, polStep.StateKey, polStep.Extra = "scheduled", "scheduled", prog.ScheduledSendLabel
			} else {
				polStep.Tone, polStep.StateKey = "progress", "ready_manual"
			}
		}
		steps = append(steps, polStep)
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
	if s.Extra != "" {
		state = state + " · " + s.Extra
	}
	if s.Counter != "" {
		full = fmt.Sprintf("%s: %s (%s)", name, state, s.Counter)
	} else {
		full = fmt.Sprintf("%s: %s", name, state)
	}
	return name, state, full
}

func (j StayJourney) step(key string) (JourneyStep, bool) {
	for _, s := range j.Steps {
		if s.Key == key {
			return s, true
		}
	}
	return JourneyStep{}, false
}

// JourneySummary returns one concise plain-language status line and tone derived
// directly from StayJourney so list rows and Stay Detail never disagree with icons.
func JourneySummary(lang string, j StayJourney) (text, tone string) {
	if len(j.Steps) == 0 {
		return "", ""
	}
	email, _ := j.step("email")
	opened, _ := j.step("opened")
	form, _ := j.step("form")
	code, _ := j.step("code")
	pol, hasPol := j.step("police")

	switch {
	case hasPol && pol.StateKey == "cancelled_after_report":
		return catalog.T(lang, "stays.journey.summary.cancelled_after_report", nil), "bad"
	case hasPol && pol.Tone == "bad":
		switch pol.StateKey {
		case "overdue":
			return catalog.T(lang, "stays.journey.summary.police_overdue", nil), "bad"
		case "not_connected":
			return catalog.T(lang, "stays.journey.summary.police_not_connected", nil), "bad"
		default:
			return catalog.T(lang, "stays.journey.summary.police_failed", nil), "bad"
		}
	case email.Tone == "bad":
		return catalog.T(lang, "stays.journey.summary.email_failed", nil), "bad"
	case code.Tone == "bad":
		return catalog.T(lang, "stays.journey.summary.code_failed", nil), "bad"
	case hasPol && pol.StateKey == "verify_id":
		return catalog.T(lang, "stays.journey.summary.verify_id", nil), "progress"
	case hasPol && pol.StateKey == "ready_manual":
		return catalog.T(lang, "stays.journey.summary.ready_manual", nil), "progress"
	case hasPol && pol.StateKey == "partial":
		return catalog.T(lang, "stays.journey.summary.police_partial", map[string]any{"counter": pol.Counter}), "progress"
	case hasPol && pol.Tone == "scheduled":
		if pol.Extra != "" {
			return catalog.T(lang, "stays.journey.summary.scheduled", map[string]any{"when": pol.Extra}), "scheduled"
		}
		return catalog.T(lang, "stays.journey.summary.scheduled_soon", nil), "scheduled"
	case form.StateKey == "missing_today":
		return catalog.T(lang, "stays.journey.summary.missing_today", nil), "progress"
	case form.StateKey == "partial":
		return catalog.T(lang, "stays.journey.summary.form_partial", map[string]any{"counter": form.Counter}), "progress"
	case email.StateKey == "sending":
		return catalog.T(lang, "stays.journey.summary.email_sending", nil), "progress"
	case opened.StateKey == "unopened":
		return catalog.T(lang, "stays.journey.summary.link_unopened", nil), "progress"
	case hasPol && pol.Tone == "done":
		switch pol.StateKey {
		case "not_required":
			return catalog.T(lang, "stays.journey.summary.done_cz", nil), "done"
		case "filed_manual":
			return catalog.T(lang, "stays.journey.summary.done_manual", nil), "done"
		default:
			return catalog.T(lang, "stays.journey.summary.done_filed", nil), "done"
		}
	case !hasPol && form.Tone == "done":
		return catalog.T(lang, "stays.journey.summary.done_demo", nil), "done"
	default:
		return catalog.T(lang, "stays.journey.summary.waiting", nil), "waiting"
	}
}

// RenderJourneySummary renders the single concise status pill derived from StayJourney.
func RenderJourneySummary(lang string, j StayJourney) template.HTML {
	text, tone := JourneySummary(lang, j)
	if text == "" {
		return ""
	}
	return template.HTML(`<span class="stay-journey-summary" data-tone="` + html.EscapeString(tone) + `">` + html.EscapeString(text) + `</span>`)
}

// RenderJourneyStrip renders the compact chronological icon strip for list rows,
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

// RenderJourneyBar renders the labeled horizontal checklist shown at the top of
// Stay Detail, reusing the exact same icons, order, and tones.
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
		b.WriteString(`<span class="stay-journey-bar-icon" aria-hidden="true">`)
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
		if s.LinkHref != "" && s.LinkKey != "" {
			b.WriteString(`<a class="stay-journey-bar-link" href="`)
			b.WriteString(html.EscapeString(s.LinkHref))
			b.WriteString(`">`)
			b.WriteString(html.EscapeString(state))
			b.WriteString(`</a>`)
		} else {
			b.WriteString(html.EscapeString(state))
		}
		b.WriteString(`</small></span></li>`)
	}
	b.WriteString(`</ol>`)
	return template.HTML(b.String())
}

// RenderJourneyLegend renders a compact, zero-JS collapsible legend explaining
// every icon and color for hosts (especially on phones without hover tooltips).
func RenderJourneyLegend(lang string) template.HTML {
	icons := []struct{ icon, key string }{
		{"mail", "email"},
		{"mail-open", "opened"},
		{"users", "form"},
		{"key-round", "code"},
		{"police", "police"},
	}
	tones := []string{"waiting", "scheduled", "progress", "done", "bad"}

	var b strings.Builder
	b.WriteString(`<details class="journey-legend">`)
	b.WriteString(`<summary class="journey-legend-toggle">`)
	b.WriteString(string(layout.Icon("circle-help", 14)))
	b.WriteString(`<span>`)
	b.WriteString(html.EscapeString(catalog.T(lang, "stays.journey.legend.toggle", nil)))
	b.WriteString(`</span></summary>`)
	b.WriteString(`<div class="journey-legend-body">`)
	b.WriteString(`<div class="journey-legend-group"><strong>`)
	b.WriteString(html.EscapeString(catalog.T(lang, "stays.journey.legend.icons_title", nil)))
	b.WriteString(`</strong><ul>`)
	for _, it := range icons {
		b.WriteString(`<li><span class="stay-journey-step" data-tone="waiting" aria-hidden="true">`)
		b.WriteString(string(layout.Icon(it.icon, 13)))
		b.WriteString(`</span><span>`)
		b.WriteString(html.EscapeString(catalog.T(lang, "stays.journey.legend.icon."+it.key, nil)))
		b.WriteString(`</span></li>`)
	}
	b.WriteString(`</ul></div>`)
	b.WriteString(`<div class="journey-legend-group"><strong>`)
	b.WriteString(html.EscapeString(catalog.T(lang, "stays.journey.legend.colors_title", nil)))
	b.WriteString(`</strong><ul>`)
	for _, tone := range tones {
		b.WriteString(`<li><span class="journey-legend-swatch" data-tone="`)
		b.WriteString(html.EscapeString(tone))
		b.WriteString(`" aria-hidden="true"></span><span>`)
		b.WriteString(html.EscapeString(catalog.T(lang, "stays.journey.legend.color."+tone, nil)))
		b.WriteString(`</span></li>`)
	}
	b.WriteString(`</ul></div></div></details>`)
	return template.HTML(b.String())
}
