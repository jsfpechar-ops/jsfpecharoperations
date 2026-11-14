package ai

// leon_try.go: the host's test message to Leon at the end of the setup wizard,
// the port of leon.try_left, leon.try_reply and leon.plan_multiplier
// (App/app/leon.py 171-181, 667-724) with guide_facts.for_guest
// (guide_facts.py 136-153) and guide_facts.answers. Nothing is stored but the
// usage ledger of the model service and the rate-limit rows; the allowance is 5
// a day per property.

import (
	"context"
	"errors"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

// answers is guide_facts.answers.
func (s LeonStore) answers(ctx context.Context, apartmentID int64) (map[string]string, error) {
	rows, err := s.Pool.Query(ctx, `SELECT fact, value FROM guide_fact WHERE apartment_id = $1`, apartmentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]string{}
	for rows.Next() {
		var f, v string
		if err := rows.Scan(&f, &v); err != nil {
			return nil, err
		}
		out[f] = v
	}
	return out, rows.Err()
}

// GuestCards is guide_facts.for_guest(apartment_id, "booked", "en"): what a
// booked guest may read, empty until the guide is live. A built-in card the host
// has not written yet reaches guests with its quick-answer lines only (a draft
// is never shown).
func (s LeonStore) GuestCards(ctx context.Context, apartmentID int64) ([]LeonCard, error) {
	items, err := s.Items(ctx, apartmentID)
	if err != nil || !LeonProgressOf(items).Live {
		return nil, err
	}
	answers, err := s.answers(ctx, apartmentID)
	if err != nil {
		return nil, err
	}
	lines := LeonFactLines(answers)
	var out []LeonCard
	for _, it := range items {
		if it.Visibility != "everyone" && it.Visibility != "booked" {
			continue
		}
		var mine []string
		if it.Kind != "custom" {
			mine = lines[it.Kind]
		}
		card := LeonCard{ID: it.ID, Kind: it.Kind, Title: it.Title, Photos: it.Photos, Facts: mine}
		switch {
		case it.State == "done":
			card.Location, card.Steps, card.WatchOut, card.VideoURL = it.Location, it.Steps, it.WatchOut, it.VideoURL
		case len(mine) > 0 && (it.State == "missing" || it.State == "check"):
		default:
			continue
		}
		out = append(out, card)
	}
	return out, nil
}

// PlanMultiplier is leon.plan_multiplier: 0 paused, 1 Standard or trial, 5 Max.
func (s LeonStore) PlanMultiplier(ctx context.Context, apartmentID int64) (int, error) {
	var owner *int64
	err := s.Pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, apartmentID).Scan(&owner)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && owner == nil) {
		return 1, nil
	}
	if err != nil {
		return 0, err
	}
	return s.Multiplier(ctx, *owner)
}

// LeonTryResult is the dict try_reply returns.
type LeonTryResult struct {
	Kind     string
	Text     string
	WouldAsk bool
	Left     int64
}

// TryReply is leon.try_reply: one test message in, one reply out, never stored.
// The model is asked only for a message that passes every local check; what it
// sees is the character, the guide cards a booked guest may read and the
// redacted message (LeonSystemBlocks, LeonUserTurn).
func (s LeonStore) TryReply(ctx context.Context, model HavelModel, a LeonApartment, text, lang, hostName string, at time.Time) (LeonTryResult, error) {
	key := strconv.FormatInt(a.ID, 10)
	text = havelStrip(text)
	out := func(kind, body string, wouldAsk bool) (LeonTryResult, error) {
		left, err := s.TryLeft(ctx, a.ID, at)
		return LeonTryResult{Kind: kind, Text: body, WouldAsk: wouldAsk, Left: left}, err
	}
	mult, err := s.PlanMultiplier(ctx, a.ID)
	if err != nil {
		return LeonTryResult{}, err
	}
	if mult <= 0 {
		return out("passed", leonNamed(lang, "leon_passed_to_host", hostName), true)
	}
	if text == "" || havelLen(text) > LeonMaxMessageChars {
		return out("too_long", leonFixed(lang, "leon_too_long", map[string]any{"n": LeonMaxMessageChars}), false)
	}
	if small := LeonSmalltalkKind(text); small != "" {
		k := "leon_thanks"
		if small == "hi" {
			k = "leon_hi"
		}
		return out("smalltalk", leonFixed(lang, k, nil), false)
	}
	if LeonIsNoise(text) {
		return out("unclear", leonFixed(lang, "leon_unclear", nil), false)
	}
	blocked, err := s.Blocked(ctx, "leon_try", key, leonTryMax, leonTryWindow, at)
	if err != nil {
		return LeonTryResult{}, err
	}
	if blocked {
		return out("cap", "", false)
	}
	redacted := LeonRedact(text)
	cards, err := s.GuestCards(ctx, a.ID)
	if err != nil {
		return LeonTryResult{}, err
	}
	if len(cards) == 0 {
		return out("no_guide", "", false)
	}
	if err := s.Record(ctx, "leon_try", key, at); err != nil {
		return LeonTryResult{}, err
	}
	data, err := model.Call(ctx, LeonFeature, LeonSystemBlocks(cards, a.Name),
		[]anthropic.Message{{Role: "user", Content: LeonUserTurn(redacted, lang)}}, LeonSchema(), &key, LeonMaxTokens)
	if err != nil {
		if anthropic.AsError(err) == nil {
			return LeonTryResult{}, err
		}
		return out("passed", leonNamed(lang, "leon_passed_to_host", hostName), true)
	}
	v := LeonValidate(data, cards, redacted)
	switch v.Kind {
	case "answer":
		body := v.Text
		if v.Summary != "" {
			body += "\n" + leonFixed(lang, "leon_asked_host_part", nil)
		}
		return out("answer", body, v.Summary != "")
	case "emergency":
		return out("emergency", LeonEmergencyText(lang, cards), true)
	case "refuse":
		return out("refuse", leonFixed(lang, "leon_refuse", nil), false)
	case "about_me":
		return out("about_me", leonFixed(lang, "leon_about", nil), false)
	case "unclear":
		return out("unclear", leonFixed(lang, "leon_unclear", nil), false)
	}
	k := "leon_asked_host"
	if v.Upset {
		k = "leon_asked_host_sorry"
	}
	return out("ask_host", leonNamed(lang, k, hostName), true)
}
