package booking

// booking_setup.steps and can_publish (brief 0819).

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

var setupStepOrder = []string{"pay", "page", "price", "policy", "calendar", "publish"}

// SetupStep is one row on the host setup checklist.
type SetupStep struct {
	Key     string
	Done    bool
	Current bool
}

type hostPageRow struct {
	Description *string
	PhotosJSON  *string
	Published   int
}

func ensurePageRow(ctx context.Context, db DB, apartmentID int64, now time.Time) error {
	stamp := StampAt(now)
	_, err := db.Exec(ctx, `INSERT INTO property_page (apartment_id, created_at, updated_at) VALUES ($1, $2, $2)
		ON CONFLICT (apartment_id) DO NOTHING`, apartmentID, stamp)
	return err
}

func loadHostPage(ctx context.Context, db DB, apartmentID int64, now time.Time) (*hostPageRow, error) {
	if err := ensurePageRow(ctx, db, apartmentID, now); err != nil {
		return nil, err
	}
	var row hostPageRow
	err := db.QueryRow(ctx, `SELECT description, photos_json, published FROM property_page WHERE apartment_id = $1`,
		apartmentID).Scan(&row.Description, &row.PhotosJSON, &row.Published)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return &row, err
}

func hostPhotosLen(raw *string) int {
	if raw == nil || strings.TrimSpace(*raw) == "" {
		return 0
	}
	var photos []string
	if err := json.Unmarshal([]byte(*raw), &photos); err != nil {
		return 0
	}
	return len(photos)
}

func settingsStored(ctx context.Context, db DB, apartmentID int64) (bool, error) {
	var v *string
	err := db.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, settingKey(apartmentID)).Scan(&v)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return err == nil && v != nil, err
}

// SetupSteps is booking_setup.steps.
func SetupSteps(ctx context.Context, db DB, getenv func(string) string, apartmentID, ownerID int64, now time.Time) ([]SetupStep, error) {
	s, err := LoadSettings(ctx, db, apartmentID)
	if err != nil {
		return nil, err
	}
	page, err := loadHostPage(ctx, db, apartmentID, now)
	if err != nil {
		return nil, err
	}
	mode := StripeMode(getenv)
	stripeOK, err := StripeComplete(ctx, db, mode, ownerID)
	if err != nil {
		return nil, err
	}
	railsOK, err := RailsReady(ctx, db, apartmentID)
	if err != nil {
		return nil, err
	}
	payDone := stripeOK || railsOK
	desc := ""
	photos := 0
	pub := false
	if page != nil {
		if page.Description != nil {
			desc = strings.TrimSpace(*page.Description)
		}
		photos = hostPhotosLen(page.PhotosJSON)
		pub = page.Published != 0
	}
	policy, err := settingsStored(ctx, db, apartmentID)
	if err != nil {
		return nil, err
	}
	ical, err := icalDone(ctx, db, apartmentID)
	if err != nil {
		return nil, err
	}
	done := map[string]bool{
		"pay":      payDone,
		"page":     photos > 0 && desc != "",
		"price":    s.NightlyPriceCZK > 0,
		"policy":   policy,
		"calendar": ical,
		"publish":  pub,
	}
	current := ""
	for _, key := range setupStepOrder {
		if !done[key] {
			current = key
			break
		}
	}
	out := make([]SetupStep, len(setupStepOrder))
	for i, key := range setupStepOrder {
		out[i] = SetupStep{Key: key, Done: done[key], Current: key == current}
	}
	return out, nil
}

// CanPublish is booking_setup.can_publish.
func CanPublish(steps []SetupStep) bool {
	done := map[string]bool{}
	for _, row := range steps {
		done[row.Key] = row.Done
	}
	return done["pay"] && done["price"] && done["page"]
}

func stepsDoneCount(steps []SetupStep) int {
	n := 0
	for _, row := range steps {
		if row.Done {
			n++
		}
	}
	return n
}
