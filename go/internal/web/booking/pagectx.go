package booking

// The data of a published property page: property_page.py widget_ready and
// the route module's _page_context, _noindex and _og (lines 169-247), plus
// booking_site.site_allowed.

import (
	"context"
	"encoding/json"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// Card is one guide card shown on the page.
type Card struct{ Title, Body string }

// OG is the Open Graph block of the head.
type OG struct{ URL, Image, Title, Description string }

// FormValues are the typed name and e-mail kept after a field error.
type FormValues struct{ Name, Email string }

// Page is everything a property page template reads.
type Page struct {
	Name, District, Description string
	HouseRules, Amenities       []string
	Photos                      []string
	MapURL                      string
	CheckinText, CheckoutText   string
	Cards                       []Card

	Noindex    bool
	OG         OG
	Bookable   bool
	BookError  string
	FormValues FormValues
	Booking    *BookingView
	PayModes   []string
}

// DescHead is page.description[:400]; DescTail is page.description[400:].
func (p *Page) DescHead() string { return runeSlice(p.Description, 0, 400) }
func (p *Page) DescTail() string { return runeSlice(p.Description, 400, -1) }
func (p *Page) DescLong() bool   { return len([]rune(p.Description)) > 400 }

// TopPhotos is page.photos[:5].
func (p *Page) TopPhotos() []string {
	if len(p.Photos) > 5 {
		return p.Photos[:5]
	}
	return p.Photos
}

// Modes is page.pay_modes or ['stripe'].
func (p *Page) Modes() []string {
	if len(p.PayModes) == 0 {
		return []string{"stripe"}
	}
	return p.PayModes
}

// runeSlice is Python s[from:to] on characters; to < 0 means the end.
func runeSlice(s string, from, to int) string {
	r := []rune(s)
	if from > len(r) {
		return ""
	}
	if to < 0 || to > len(r) {
		to = len(r)
	}
	return string(r[from:to])
}

func billingOn(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// SiteAllowed is booking_site.site_allowed: the Max plan only, billing off
// allows everyone. A host without a billing row, or still in a trial, has the
// standard plan.
func SiteAllowed(ctx context.Context, db DB, getenv func(string) string, ownerUserID int64) (bool, error) {
	if !billingOn(getenv) {
		return true, nil
	}
	var status string
	var plan *string
	err := db.QueryRow(ctx, `SELECT status, plan FROM billing_account WHERE owner_user_id = $1`, ownerUserID).Scan(&status, &plan)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	p := "standard"
	if plan != nil && *plan != "" {
		p = *plan
	}
	if status == "trial_pending" || status == "trialing" {
		p = "standard"
	}
	return p == "max", nil
}

// OwnerOf is _owner_of: the apartment's owner. ok is false for no apartment.
func OwnerOf(ctx context.Context, db DB, apartmentID int64) (owner int64, ok bool, err error) {
	err = db.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, apartmentID).Scan(&owner)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, false, nil
	}
	return owner, err == nil, err
}

// WidgetReady is property_page.widget_ready: published and priced, the plan
// allows a booking site, and a card account or a direct rail is ready.
func WidgetReady(ctx context.Context, db DB, getenv func(string) string, apartmentID int64) (bool, error) {
	owner, ok, err := OwnerOf(ctx, db, apartmentID)
	if err != nil || !ok {
		return false, err
	}
	var price *int64
	err = db.QueryRow(ctx, `SELECT nightly_price_czk FROM property_page WHERE apartment_id = $1`, apartmentID).Scan(&price)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if price == nil || *price == 0 {
		return false, nil
	}
	allowed, err := SiteAllowed(ctx, db, getenv, owner)
	if err != nil || !allowed {
		return false, err
	}
	complete, err := StripeComplete(ctx, db, StripeMode(getenv), owner)
	if err != nil || complete {
		return complete, err
	}
	return RailsReady(ctx, db, apartmentID)
}

// BookableApartment is _bookable_apartment: the apartment of a live slug whose
// widget is ready, else ok false (the route answers 404).
func BookableApartment(ctx context.Context, db DB, getenv func(string) string, slug string) (int64, bool, error) {
	res, err := Resolve(ctx, db, slug)
	if err != nil || res.Kind != "live" {
		return 0, false, err
	}
	ready, err := WidgetReady(ctx, db, getenv, res.ApartmentID)
	if err != nil || !ready {
		return 0, false, err
	}
	return res.ApartmentID, true, nil
}

func jsonList(raw *string) []string {
	if raw == nil || *raw == "" {
		return nil
	}
	var out []string
	if err := json.Unmarshal([]byte(*raw), &out); err != nil {
		return nil
	}
	return out
}

// splitLines is Python str.splitlines().
func splitLines(s string) []string {
	var out []string
	start := 0
	rs := []rune(s)
	for i := 0; i < len(rs); i++ {
		switch rs[i] {
		case '\n', '\v', '\f', 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029:
		case '\r':
			out = append(out, string(rs[start:i]))
			if i+1 < len(rs) && rs[i+1] == '\n' {
				i++
			}
			start = i + 1
			continue
		default:
			continue
		}
		out = append(out, string(rs[start:i]))
		start = i + 1
	}
	if start < len(rs) {
		out = append(out, string(rs[start:]))
	}
	return out
}

// LoadPage is _page_context plus _noindex and _og. nil means no apartment.
// A photos or amenities value that is not a JSON list of strings reads as an
// empty list (Python would answer 500).
func LoadPage(ctx context.Context, db DB, getenv func(string) string, apartmentID int64) (*Page, error) {
	var name string
	var obec, cast *string
	err := db.QueryRow(ctx, `SELECT internal_name, addr_obec, addr_obec_cast FROM apartment WHERE id = $1`, apartmentID).Scan(&name, &obec, &cast)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var desc, rules, in, out, photos, amen *string
	var hide *int64
	err = db.QueryRow(ctx, `SELECT description, house_rules, checkin_text, checkout_text, photos_json, amenities_json, hide_from_search
		FROM property_page WHERE apartment_id = $1`, apartmentID).Scan(&desc, &rules, &in, &out, &photos, &amen, &hide)
	found := err == nil
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return nil, err
	}
	str := func(p *string) string {
		if p == nil {
			return ""
		}
		return *p
	}
	var parts []string
	for _, p := range []*string{obec, cast} {
		if s := str(p); s != "" {
			parts = append(parts, s)
		}
	}
	where := strings.Join(parts, " ")
	pg := &Page{
		Name: name, District: strings.Join(parts, " · "), Description: str(desc),
		CheckinText: str(in), CheckoutText: str(out),
		Photos: jsonList(photos), Amenities: jsonList(amen),
	}
	// Town and district only; the street and number never leave the host side.
	if where != "" {
		pg.MapURL = "https://mapy.cz/zakladni?q=" + hostweb.QuotePath(where)
	}
	for _, ln := range splitLines(str(rules)) {
		if ln = strings.TrimSpace(ln); ln != "" {
			pg.HouseRules = append(pg.HouseRules, ln)
		}
	}
	rows, err := db.Query(ctx, `SELECT title, steps, watch_out, location FROM guide_item
		WHERE apartment_id = $1 AND visibility = 'everyone' AND state = 'done'
		ORDER BY topic, sort_order LIMIT 20`, apartmentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var title, steps, watch, loc string
		if err := rows.Scan(&title, &steps, &watch, &loc); err != nil {
			return nil, err
		}
		if title == "" && steps == "" && watch == "" {
			continue
		}
		var body []string
		for _, p := range []string{steps, watch, loc} {
			if p = strings.TrimSpace(p); p != "" {
				body = append(body, p)
			}
		}
		pg.Cards = append(pg.Cards, Card{Title: strings.TrimSpace(title), Body: strings.Join(body, "\n")})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	pg.Noindex = found && hide != nil && *hide != 0
	var slug string
	err = db.QueryRow(ctx, `SELECT slug FROM property_slug WHERE apartment_id = $1`, apartmentID).Scan(&slug)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return nil, err
	}
	base := hostweb.PublicBase(getenv)
	pg.OG = OG{URL: base + "/p/" + slug, Title: pg.Name, Description: runeSlice(pg.Description, 0, 200)}
	if len(pg.Photos) > 0 {
		pg.OG.Image = base + pg.Photos[0]
	}
	return pg, nil
}
