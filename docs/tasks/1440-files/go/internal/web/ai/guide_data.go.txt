package ai

// The data rules of the guest guide: App/app/guest_guide.py (items, cards,
// progress), App/app/guide_token.py (the QR token), the photo rows of
// App/app/guide_photos.py and the reading half of App/app/guide_facts.py.
// SQL is the Python SQL with $n placeholders.

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
)

// guideTopics is guest_guide.TOPICS (guest order).
var guideTopics = []string{"arrival", "wifi", "heating", "kitchen", "rooms", "bathroom", "rules", "trash", "checkout", "area", "emergency"}

// guideKindTopic is one built-in card kind and its topic.
type guideKindTopic struct{ Kind, Topic string }

// guideKinds is guest_guide.KINDS in guest order (never rename a kind).
var guideKinds = []guideKindTopic{
	{"checkin", "arrival"}, {"keys", "arrival"}, {"getting_here", "arrival"}, {"parking", "arrival"},
	{"garage", "arrival"}, {"wifi", "wifi"}, {"tv", "wifi"}, {"heating", "heating"},
	{"hot_water", "heating"}, {"air_conditioning", "heating"}, {"kitchen_appliances", "kitchen"},
	{"dishwasher", "kitchen"}, {"coffee_machine", "kitchen"}, {"bedrooms", "rooms"},
	{"sofa_bed", "rooms"}, {"balcony", "rooms"}, {"bathroom", "bathroom"},
	{"washing_machine", "bathroom"}, {"house_rules", "rules"}, {"trash", "trash"},
	{"checkout", "checkout"}, {"area_tips", "area"}, {"emergency", "emergency"},
	{"something_wrong", "emergency"},
}

// guideDefaultKinds is guest_guide.DEFAULT_KINDS.
var guideDefaultKinds = []string{
	"checkin", "keys", "getting_here", "parking", "wifi", "heating", "hot_water", "kitchen_appliances",
	"bedrooms", "bathroom", "washing_machine", "house_rules", "trash", "checkout", "area_tips",
	"emergency", "something_wrong",
}

// guideMustHave is guest_guide.MUST_HAVE.
var guideMustHave = []string{"checkin", "wifi", "heating", "checkout", "emergency"}

// guideVisibility is guest_guide.VISIBILITY.
var guideVisibility = []string{"everyone", "booked", "host"}

// guideLimitOrder is the order of guest_guide.LIMITS; guideLimits holds the sizes.
var guideLimitOrder = []string{"title", "location", "steps", "watch_out", "video_url"}
var guideLimits = map[string]int{"title": 120, "location": 500, "steps": 4000, "watch_out": 1000, "video_url": 500}

// guideError is GuideError: Key is the flash message key.
type guideError struct{ Key string }

func (e *guideError) Error() string { return e.Key }

func guideErr(key string) error { return &guideError{Key: key} }

// guideErrKey returns the key of a guideError, or "" for any other error.
func guideErrKey(err error) string {
	var ge *guideError
	if errors.As(err, &ge) {
		return ge.Key
	}
	return ""
}

func guideIn(list []string, v string) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

func guideTopicIndex(topic string) int {
	for i, t := range guideTopics {
		if t == topic {
			return i
		}
	}
	return len(guideTopics)
}

// guideKindTopicOf is KINDS[kind]; ok is false for a custom kind.
func guideKindTopicOf(kind string) (string, bool) {
	for _, k := range guideKinds {
		if k.Kind == kind {
			return k.Topic, true
		}
	}
	return "", false
}

// guideOrder is _order: the position of a kind in KINDS, len(KINDS) for any other.
func guideOrder(kind string) int64 {
	for i, k := range guideKinds {
		if k.Kind == kind {
			return int64(i)
		}
	}
	return int64(len(guideKinds))
}

// guidePyStrip is Python's str.strip(): it also trims the separators
// \x1c-\x1f, which unicode.IsSpace does not know.
func guidePyStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) })
}

// guideTruncate is text[:n] on code points.
func guideTruncate(s string, n int) string {
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n])
}

// guideItem is one guide_item row, with its photo count.
type guideItem struct {
	ID, ApartmentID                                         int64
	Topic, Kind, Title, Location, Steps, WatchOut, VideoURL string
	Visibility, State, Source                               string
	SortOrder                                               int64
	CreatedAt, UpdatedAt                                    string
	Photos                                                  int64
}

const guideItemColumns = `id, apartment_id, topic, kind, title, location, steps, watch_out, video_url, visibility, state, source, sort_order, created_at, updated_at`

func guideScanItem(row pgx.Row, withPhotos bool) (guideItem, error) {
	var it guideItem
	dst := []any{&it.ID, &it.ApartmentID, &it.Topic, &it.Kind, &it.Title, &it.Location, &it.Steps, &it.WatchOut,
		&it.VideoURL, &it.Visibility, &it.State, &it.Source, &it.SortOrder, &it.CreatedAt, &it.UpdatedAt}
	if withPhotos {
		dst = append(dst, &it.Photos)
	}
	err := row.Scan(dst...)
	return it, err
}

// items is items(): every item of the property in guest order, each with
// its photo count. A built-in card sits where the catalog puts it.
func (s *guideServer) items(ctx context.Context, apt int64) ([]guideItem, error) {
	rows, err := s.pool.Query(ctx, `SELECT i.id, i.apartment_id, i.topic, i.kind, i.title, i.location, i.steps, i.watch_out, i.video_url,
       i.visibility, i.state, i.source, i.sort_order, i.created_at, i.updated_at,
       (SELECT COUNT(*) FROM guide_photo p WHERE p.item_id = i.id) AS photos
  FROM guide_item i WHERE i.apartment_id = $1 ORDER BY i.sort_order, i.id`, apt)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []guideItem
	for rows.Next() {
		it, err := guideScanItem(rows, true)
		if err != nil {
			return nil, err
		}
		if topic, ok := guideKindTopicOf(it.Kind); ok {
			it.Topic, it.SortOrder = topic, guideOrder(it.Kind)
		}
		out = append(out, it)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i], out[j]
		if ta, tb := guideTopicIndex(a.Topic), guideTopicIndex(b.Topic); ta != tb {
			return ta < tb
		}
		if a.SortOrder != b.SortOrder {
			return a.SortOrder < b.SortOrder
		}
		return a.ID < b.ID
	})
	return out, nil
}

// getItem is get(): one item, only when it belongs to this property; nil when not.
func (s *guideServer) getItem(ctx context.Context, apt, id int64) (*guideItem, error) {
	it, err := guideScanItem(s.pool.QueryRow(ctx, `SELECT `+guideItemColumns+` FROM guide_item WHERE id = $1 AND apartment_id = $2`, id, apt), false)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &it, nil
}

// addKind is add_kind: the built-in card kind when the property lacks it; true when created.
func (s *guideServer) addKind(ctx context.Context, apt int64, kind, source, now string) (bool, error) {
	topic, ok := guideKindTopicOf(kind)
	if !ok {
		return false, guideErr("flash.error.guide_unknown_card")
	}
	tag, err := s.pool.Exec(ctx, `INSERT INTO guide_item (apartment_id, topic, kind, source, sort_order, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`, apt, topic, kind, source, guideOrder(kind), now, now)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// ensureDefaults is ensure_defaults: the default cards, once; the old
// checkin_info / checkout_info text becomes a draft ('check').
func (s *guideServer) ensureDefaults(ctx context.Context, a *guideApartment, now string) error {
	rows, err := s.pool.Query(ctx, `SELECT kind FROM guide_item WHERE apartment_id = $1`, a.ID)
	if err != nil {
		return err
	}
	have := map[string]bool{}
	for rows.Next() {
		var kind string
		if err := rows.Scan(&kind); err != nil {
			rows.Close()
			return err
		}
		have[kind] = true
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, kind := range guideDefaultKinds {
		if !have[kind] {
			if _, err := s.addKind(ctx, a.ID, kind, "host", now); err != nil {
				return err
			}
		}
	}
	for _, legacy := range []struct{ kind, text string }{{"checkin", a.CheckinInfo}, {"checkout", a.CheckoutInfo}} {
		text := guidePyStrip(legacy.text)
		if text == "" {
			continue
		}
		if _, err := s.pool.Exec(ctx, `UPDATE guide_item SET steps = $1, state = 'check', source = 'legacy', updated_at = $2
WHERE apartment_id = $3 AND kind = $4 AND state = 'missing' AND steps = ''`,
			guideTruncate(text, guideLimits["steps"]), now, a.ID, legacy.kind); err != nil {
			return err
		}
	}
	return nil
}

// guideClean is _clean: the cleaned, limit-checked text fields and visibility.
// fields holds only the names the form sent.
func guideClean(fields map[string]string) (map[string]string, error) {
	out := map[string]string{}
	for _, name := range guideLimitOrder {
		raw, ok := fields[name]
		if !ok {
			continue
		}
		value := guidePyStrip(strings.ReplaceAll(raw, "\r\n", "\n"))
		if utf8.RuneCountInString(value) > guideLimits[name] {
			return nil, guideErr("flash.error.guide_too_long")
		}
		out[name] = value
	}
	if url := out["video_url"]; url != "" && !strings.HasPrefix(url, "https://") {
		return nil, guideErr("flash.error.guide_video_url")
	}
	if v, ok := fields["visibility"]; ok {
		if !guideIn(guideVisibility, v) {
			return nil, guideErr("flash.error.guide_visibility")
		}
		out["visibility"] = v
	}
	return out, nil
}

// updateItem is db.update("guide_item", id, values) for a fixed set of columns.
func (s *guideServer) updateItem(ctx context.Context, id int64, values map[string]string) error {
	allowed := []string{"title", "location", "steps", "watch_out", "video_url", "visibility", "state", "source", "updated_at"}
	var sets []string
	var args []any
	for _, col := range allowed {
		if v, ok := values[col]; ok {
			args = append(args, v)
			sets = append(sets, col+" = $"+strconv.Itoa(len(args)))
		}
	}
	if len(sets) == 0 {
		return nil
	}
	args = append(args, id)
	_, err := s.pool.Exec(ctx, `UPDATE guide_item SET `+strings.Join(sets, ", ")+` WHERE id = $`+strconv.Itoa(len(args)), args...)
	return err
}

// save is save(): the host's edit; the item is done when it says where or how,
// else missing. It returns the saved item.
func (s *guideServer) save(ctx context.Context, apt, id int64, fields map[string]string, now string) (*guideItem, error) {
	item, err := s.getItem(ctx, apt, id)
	if err != nil {
		return nil, err
	}
	if item == nil {
		return nil, guideErr("flash.error.guide_no_such_item")
	}
	values, err := guideClean(fields)
	if err != nil {
		return nil, err
	}
	if t, ok := values["title"]; item.Kind == "custom" && ok && t == "" {
		return nil, guideErr("flash.error.guide_title_required")
	}
	steps, location := item.Steps, item.Location
	if v, ok := values["steps"]; ok {
		steps = v
	}
	if v, ok := values["location"]; ok {
		location = v
	}
	values["state"] = "missing"
	if steps != "" || location != "" {
		values["state"] = "done"
	}
	if item.Source != "host" {
		values["source"] = "host"
	}
	values["updated_at"] = now
	if err := s.updateItem(ctx, id, values); err != nil {
		return nil, err
	}
	return s.getItem(ctx, apt, id)
}

// skip is skip(): mark a card as not applying (or bring it back).
func (s *guideServer) skip(ctx context.Context, apt, id int64, skipped bool, now string) error {
	item, err := s.getItem(ctx, apt, id)
	if err != nil {
		return err
	}
	if item == nil {
		return guideErr("flash.error.guide_no_such_item")
	}
	hasText := item.Steps != "" || item.Location != ""
	state := "missing"
	switch {
	case skipped:
		state = "skipped"
	case hasText && item.Source == "host":
		state = "done"
	case hasText:
		// Imported or legacy text the host never saved goes back to "Check this".
		state = "check"
	}
	return s.updateItem(ctx, id, map[string]string{"state": state, "updated_at": now})
}

// discardDraft is discard_draft: text the host did not write goes away and the
// card is "Missing" again. Only for drafts; true when something was discarded.
func (s *guideServer) discardDraft(ctx context.Context, apt, id int64, now string) (bool, error) {
	item, err := s.getItem(ctx, apt, id)
	if err != nil || item == nil || item.State != "check" {
		return false, err
	}
	err = s.updateItem(ctx, id, map[string]string{"location": "", "steps": "", "watch_out": "", "video_url": "",
		"state": "missing", "source": "host", "updated_at": now})
	return err == nil, err
}

// addCustom is add_custom: a card the host names, under one of the topics.
func (s *guideServer) addCustom(ctx context.Context, apt int64, topic, title, now string) (int64, error) {
	if !guideIn(guideTopics, topic) {
		return 0, guideErr("flash.error.guide_unknown_card")
	}
	title = guidePyStrip(title)
	if title == "" {
		return 0, guideErr("flash.error.guide_title_required")
	}
	if utf8.RuneCountInString(title) > guideLimits["title"] {
		return 0, guideErr("flash.error.guide_too_long")
	}
	var id int64
	err := s.pool.QueryRow(ctx, `INSERT INTO guide_item (apartment_id, topic, kind, title, sort_order, created_at, updated_at)
VALUES ($1, $2, 'custom', $3, $4, $5, $5) RETURNING id`, apt, topic, title, int64(len(guideKinds)+1), now).Scan(&id)
	return id, err
}

// deleteCustom is delete_custom: true when a custom card was deleted.
func (s *guideServer) deleteCustom(ctx context.Context, apt, id int64) (bool, error) {
	tag, err := s.pool.Exec(ctx, `DELETE FROM guide_item WHERE id = $1 AND apartment_id = $2 AND kind = 'custom'`, id, apt)
	return err == nil && tag.RowsAffected() == 1, err
}

// guideProgress is progress(): the counts for the progress ring and whether guests can see the guide.
type guideProgress struct {
	Done, Total, Answered, Cards, Check, MustHaveDone, MustHaveTotal int
	Live                                                             bool
}

func guideProgressOf(rows []guideItem) guideProgress {
	var p guideProgress
	must := map[string]string{}
	for _, r := range rows {
		if r.State != "skipped" {
			p.Total++
			if r.State == "done" {
				p.Done++
			}
			if r.State == "check" {
				p.Check++
			}
		}
		if r.State == "done" || r.State == "skipped" {
			p.Answered++
		}
		if guideIn(guideMustHave, r.Kind) {
			must[r.Kind] = r.State
		}
	}
	for _, kind := range guideMustHave {
		if must[kind] == "done" || must[kind] == "skipped" {
			p.MustHaveDone++
		}
	}
	p.Cards, p.MustHaveTotal = len(rows), len(guideMustHave)
	p.Live = p.MustHaveDone == len(guideMustHave)
	return p
}

// progress reads the items and counts them.
func (s *guideServer) progress(ctx context.Context, apt int64) (guideProgress, error) {
	rows, err := s.items(ctx, apt)
	return guideProgressOf(rows), err
}

// guideNextOpen is _next_open: the next card in guest order that still needs
// the host, wrapping around; 0 when none.
func guideNextOpen(rows []guideItem, after int64) int64 {
	start := 0
	for i, r := range rows {
		if r.ID == after {
			start = i + 1
			break
		}
	}
	ordered := append(append([]guideItem{}, rows[start:]...), rows[:start]...)
	for _, r := range ordered {
		if r.ID != after && (r.State == "missing" || r.State == "check") {
			return r.ID
		}
	}
	return 0
}

// nextOpen reads the items and returns guideNextOpen.
func (s *guideServer) nextOpen(ctx context.Context, apt, after int64) (int64, error) {
	rows, err := s.items(ctx, apt)
	return guideNextOpen(rows, after), err
}

// guideNewToken is guide_token.new_token: secrets.token_urlsafe(24), 32 URL-safe characters.
func guideNewToken() (string, error) {
	b := make([]byte, 24)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

// currentToken is guide_token.current: nil-or-empty is "".
func (s *guideServer) currentToken(ctx context.Context, apt int64) (string, error) {
	var token string
	err := s.pool.QueryRow(ctx, `SELECT COALESCE(guide_token, '') FROM apartment WHERE id = $1`, apt).Scan(&token)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	return token, err
}

// ensureToken is guide_token.ensure: the token, created on first use, never replaced.
func (s *guideServer) ensureToken(ctx context.Context, apt int64) (string, error) {
	token, err := s.currentToken(ctx, apt)
	if err != nil || token != "" {
		return token, err
	}
	fresh, err := guideNewToken()
	if err != nil {
		return "", err
	}
	if _, err := s.pool.Exec(ctx, `UPDATE apartment SET guide_token = $1 WHERE id = $2 AND guide_token IS NULL`, fresh, apt); err != nil {
		return "", err
	}
	if token, err = s.currentToken(ctx, apt); err != nil || token != "" {
		return token, err
	}
	return fresh, nil
}

// rotateToken is guide_token.rotate: a fresh token; the old QR code stops working at once.
func (s *guideServer) rotateToken(ctx context.Context, apt int64) error {
	fresh, err := guideNewToken()
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(ctx, `UPDATE apartment SET guide_token = $1 WHERE id = $2`, fresh, apt)
	return err
}

// guidePhoto is one guide_photo row.
type guidePhoto struct {
	ID, ItemID int64
	FileName   string
	SortOrder  int64
}

// photos is guide_photos.photos: the card's photos in upload order; empty for a card of another property.
func (s *guideServer) photos(ctx context.Context, apt, item int64) ([]guidePhoto, error) {
	rows, err := s.pool.Query(ctx, `SELECT p.id, p.item_id, p.file_name, p.sort_order FROM guide_photo p JOIN guide_item i ON i.id = p.item_id
WHERE p.item_id = $1 AND i.apartment_id = $2 ORDER BY p.sort_order, p.id`, item, apt)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []guidePhoto
	for rows.Next() {
		var p guidePhoto
		if err := rows.Scan(&p.ID, &p.ItemID, &p.FileName, &p.SortOrder); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// photo is guide_photos.get; nil when the photo is not on this card of this property.
func (s *guideServer) photo(ctx context.Context, apt, item, id int64) (*guidePhoto, error) {
	var p guidePhoto
	err := s.pool.QueryRow(ctx, `SELECT p.id, p.item_id, p.file_name, p.sort_order FROM guide_photo p JOIN guide_item i ON i.id = p.item_id
WHERE p.id = $1 AND p.item_id = $2 AND i.apartment_id = $3`, id, item, apt).Scan(&p.ID, &p.ItemID, &p.FileName, &p.SortOrder)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &p, nil
}

// guidePhotosDir is guide_photos.PHOTOS_DIR: $UBYHOST_DATA_DIR/guide_photos.
func (s *guideServer) photosDir() string {
	dir := s.getenv("UBYHOST_DATA_DIR")
	if dir == "" {
		dir = "data"
	}
	return filepath.Join(dir, "guide_photos")
}

// deletePhoto is guide_photos.delete: the row goes, then the file. The Go
// container mounts the data volume read-only, so a file it cannot remove is
// left for guide_photos.purge_orphans (the scheduler's sweep of files no row
// names, once they are an hour old). It reports false when the photo is not on
// this card of this property.
func (s *guideServer) deletePhoto(ctx context.Context, apt, item, id int64) (bool, error) {
	p, err := s.photo(ctx, apt, item, id)
	if err != nil || p == nil {
		return false, err
	}
	if _, err := s.pool.Exec(ctx, `DELETE FROM guide_photo WHERE id = $1`, id); err != nil {
		return false, err
	}
	_ = os.Remove(filepath.Join(s.photosDir(), filepath.Base(p.FileName)))
	return true, nil
}

// guideSteps is guide_facts.STEPS.
var guideSteps = []string{"times", "rules", "access", "kitchen", "comfort"}

// guideSeen is guide_facts._SEEN: a row "step.<step>" = "seen" remembers a saved or skipped step.
const guideSeen = "step."

// answers is guide_facts.answers.
func (s *guideServer) answers(ctx context.Context, apt int64) (map[string]string, error) {
	rows, err := s.pool.Query(ctx, `SELECT fact, value FROM guide_fact WHERE apartment_id = $1`, apt)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]string{}
	for rows.Next() {
		var k, v string
		if err := rows.Scan(&k, &v); err != nil {
			return nil, err
		}
		out[k] = v
	}
	return out, rows.Err()
}

// nextStep is guide_facts.next_step: the first step neither saved nor skipped; "" when all are done.
func (s *guideServer) nextStep(ctx context.Context, apt int64) (string, error) {
	seen, err := s.answers(ctx, apt)
	if err != nil {
		return "", err
	}
	for _, step := range guideSteps {
		if _, ok := seen[guideSeen+step]; !ok {
			return step, nil
		}
	}
	return "", nil
}
