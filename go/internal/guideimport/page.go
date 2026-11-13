package guideimport

import (
	"context"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

// prefillFromImport is property_page.prefill_from_import: copy listing text
// into the empty columns of the apartment's page row (created empty when it
// is missing), never overwriting what the host wrote. The page row is the
// only consumer; photos are not handled (see runOne).
func prefillFromImport(ctx context.Context, pool *pgxpool.Pool, apartmentID int64, data Trimmed, now string) error {
	if _, err := pool.Exec(ctx,
		"INSERT INTO property_page (apartment_id, created_at, updated_at) VALUES ($1, $2, $2) ON CONFLICT (apartment_id) DO NOTHING",
		apartmentID, now); err != nil {
		return err
	}
	var description, checkin, checkout, amenities, rules *string
	err := pool.QueryRow(ctx,
		"SELECT description, checkin_text, checkout_text, amenities_json, house_rules FROM property_page WHERE apartment_id = $1",
		apartmentID).Scan(&description, &checkin, &checkout, &amenities, &rules)
	if err != nil {
		return err
	}
	empty := func(s *string) bool { return s == nil || *s == "" }
	var sets []string
	var args []any
	add := func(col string, val any) {
		args = append(args, val)
		sets = append(sets, fmt.Sprintf("%s = $%d", col, len(args)))
	}
	str := func(key string) string { s, _ := data.Get(key).(string); return s }
	if empty(description) {
		text := str("description")
		if text == "" {
			text = str("subDescription")
		}
		if text != "" {
			add("description", text)
		}
	}
	if empty(checkin) && str("checkIn") != "" {
		add("checkin_text", str("checkIn"))
	}
	if empty(checkout) && str("checkOut") != "" {
		add("checkout_text", str("checkOut"))
	}
	if list, ok := data.Get("amenities").([]string); ok && empty(amenities) {
		parts := make([]string, len(list))
		for i, s := range list {
			parts[i] = anthropic.PyJSONString(s)
		}
		add("amenities_json", "["+strings.Join(parts, ", ")+"]")
	}
	if list, ok := data.Get("houseRules").([]string); ok && empty(rules) {
		var lines []string
		for _, s := range list {
			if t := pyStrip(s); t != "" {
				lines = append(lines, t)
			}
		}
		if len(lines) > 0 {
			add("house_rules", strings.Join(lines, "\n"))
		}
	}
	if len(sets) == 0 {
		return nil
	}
	args = append(args, now, apartmentID)
	q := fmt.Sprintf("UPDATE property_page SET %s, updated_at = $%d WHERE apartment_id = $%d",
		strings.Join(sets, ", "), len(args)-1, len(args))
	_, err = pool.Exec(ctx, q, args...)
	return err
}
