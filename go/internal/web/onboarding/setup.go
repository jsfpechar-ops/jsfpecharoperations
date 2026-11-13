// Package onboarding ports the parts of the onboarding area that render no
// HTML: App/app/property_setup.py (all but guest_city) and the settings-only
// POST routes of App/app/routes/onboarding.py. The Python files are the
// reference; each function names its source. Brief 1290.
package onboarding

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"sort"
	"strconv"
	"strings"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Steps is property_setup.STEPS: the wizard steps in story order.
var Steps = []string{"property", "calendar", "police", "guest_link"}

// RetiredSteps is property_setup.RETIRED_STEPS: former steps whose marks stay readable.
var RetiredSteps = []string{"automation", "stay_fee", "door_lock", "try_it"}

// KnownSteps is property_setup.KNOWN_STEPS (STEPS + RETIRED_STEPS).
var KnownSteps = append(append([]string{}, Steps...), RetiredSteps...)

// TotalSteps is property_setup.TOTAL_STEPS.
var TotalSteps = len(Steps)

// Optional is property_setup.OPTIONAL.
var Optional = map[string]bool{"stay_fee": true, "door_lock": true}

// Skippable is property_setup.SKIPPABLE.
var Skippable = map[string]bool{"calendar": true, "try_it": true, "stay_fee": true, "door_lock": true}

// Teaching is property_setup.TEACHING.
var Teaching = map[string]bool{"guest_link": true, "try_it": true}

// Marks is property_setup.MARKS: the values a step may be marked with.
var Marks = []string{"done", "skipped", "waiting", "not_needed"}

// StepFields is property_setup.STEP_FIELDS: the columns each wizard save may write.
var StepFields = map[string][]string{
	"property": {
		"internal_name",
		"city_en",
		"legal_entity_id",
		"data_controller_entity_id",
		"default_purpose",
		"checkin_hour",
		"checkout_hour",
		"addr_okres",
		"addr_obec",
		"addr_obec_cast",
		"addr_street",
		"addr_house_no",
		"addr_orient_no",
		"addr_zip",
	},
	"police": {"uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user"},
	"stay_fee": {
		"stay_fee_rate_czk",
		"stay_fee_cadence",
		"stay_fee_vs",
		"stay_fee_authority_name",
		"stay_fee_authority_address",
		"stay_fee_authority_contact",
		"stay_fee_authority_databox",
		"stay_fee_payee",
		"stay_fee_instruction",
		"stay_fee_council_account",
	},
	"door_lock":  {"lock_provider", "lock_id"},
	"automation": {"automation_mode", "submit_after_hours"},
}

// legacyStepAliases is property_setup._LEGACY_STEP_ALIASES: older stored step ids.
var legacyStepAliases = map[string]string{
	"guest_links": "guest_link",
	"pin":         "guest_link",
	"try":         "try_it",
	"reporting":   "police",
	"fee":         "stay_fee",
	"lock":        "door_lock",
}

// SectionMinutes is property_setup.SECTION_MINUTES (1099 short editor).
var SectionMinutes = map[string]int{"basics": 2, "police": 3, "calendars": 1, "messages": 2, "fee": 3, "lock": 5}

// SetupOrder is property_setup.SETUP_ORDER.
var SetupOrder = []string{"basics", "police"}

// State is the JSON in settings key property_setup:<id> (property_setup.py
// module docstring and load). A nil *State is Python's None.
type State struct {
	Steps      map[string]string `json:"steps"`
	Finished   bool              `json:"finished"`
	Hidden     bool              `json:"hidden"`
	Legacy     bool              `json:"legacy"`
	Celebrated bool              `json:"celebrated"`
	Tested     bool              `json:"tested"`
}

// Apartment holds the apartment columns property_setup reads. A NULL column
// is "" or 0, which Python's truthiness treats the same way.
type Apartment struct {
	ID             int64  `json:"id"`
	InternalName   string `json:"internal_name"`
	LegalEntityID  int64  `json:"legal_entity_id"`
	AddrObec       string `json:"addr_obec"`
	AddrHouseNo    string `json:"addr_house_no"`
	AddrZip        string `json:"addr_zip"`
	StayFeeRateCZK int64  `json:"stay_fee_rate_czk"`
	LockProvider   string `json:"lock_provider"`
}

// Facts is the facts dict the Python functions take. Current ignores DoorCode.
type Facts struct {
	Feeds            int    `json:"feeds"`
	Stays            int    `json:"stays"`
	GuestsRegistered bool   `json:"guests_registered"`
	ReportComplete   bool   `json:"report_complete"`
	DoorCode         string `json:"door_code"`
}

// Progress is one {"key", "state"} entry of current()["progress"].
type Progress struct {
	Key   string `json:"key"`
	State string `json:"state"`
}

// Guide is the dict property_setup.current returns.
type Guide struct {
	Key              string     `json:"key"`
	Number           int        `json:"number"`
	Total            int        `json:"total"`
	Optional         bool       `json:"optional"`
	Skippable        bool       `json:"skippable"`
	URL              string     `json:"url"`
	Progress         []Progress `json:"progress"`
	ReportingWaiting bool       `json:"reporting_waiting"`
	PoliceURL        string     `json:"police_url"`
	Legacy           bool       `json:"legacy"`
	DoneCount        int        `json:"done_count"`
}

// ChecklistRow is one {"key", "status"} row of property_setup.checklist.
type ChecklistRow struct {
	Key    string `json:"key"`
	Status string `json:"status"`
}

// Settings is the settings table as db.get_setting and db.set_setting use it.
type Settings interface {
	// Get is db.get_setting: "" for a missing row or a NULL value.
	Get(ctx context.Context, key string) (string, error)
	// Set is db.set_setting: insert, or overwrite the value of an existing key.
	Set(ctx context.Context, key, value string) error
}

// PoolSettings is Settings on PostgreSQL.
func PoolSettings(pool *pgxpool.Pool) Settings { return poolSettings{pool: pool} }

type poolSettings struct{ pool *pgxpool.Pool }

// Get is db.get_setting (db.py 2110-2112).
func (p poolSettings) Get(ctx context.Context, key string) (string, error) {
	var value *string
	err := p.pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, key).Scan(&value)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil || value == nil {
		return "", err
	}
	return *value, nil
}

// Set is db.set_setting (db.py 2124-2129).
func (p poolSettings) Set(ctx context.Context, key, value string) error {
	_, err := p.pool.Exec(ctx,
		`INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = excluded.value`,
		key, value)
	return err
}

// key is property_setup._key.
func key(apartmentID int64) string {
	return fmt.Sprintf("property_setup:%d", apartmentID)
}

// normaliseStep is property_setup._normalise_step.
func normaliseStep(step string) string {
	if alias, ok := legacyStepAliases[step]; ok {
		return alias
	}
	return step
}

func indexOf(list []string, s string) int {
	for i, v := range list {
		if v == s {
			return i
		}
	}
	return -1
}

func in(list []string, s string) bool { return indexOf(list, s) >= 0 }

// Load is property_setup.load: the stored state, or nil when the row is
// missing, empty, not JSON or not a JSON object.
func Load(ctx context.Context, s Settings, apartmentID int64) (*State, error) {
	raw, err := s.Get(ctx, key(apartmentID))
	if err != nil {
		return nil, err
	}
	return parseState(raw), nil
}

// parseState is the body of property_setup.load after db.get_setting.
func parseState(raw string) *State {
	if raw == "" {
		return nil
	}
	top, ok := decodeAll(raw)
	if !ok {
		return nil
	}
	obj, ok := top.(map[string]any)
	if !ok {
		return nil
	}
	state := &State{
		Steps:      map[string]string{},
		Finished:   truthy(obj["finished"]),
		Hidden:     truthy(obj["hidden"]),
		Legacy:     truthy(obj["legacy"]),
		Celebrated: truthy(obj["celebrated"]),
		Tested:     truthy(obj["tested"]),
	}
	// Python walks steps.items() in document order, a repeated key keeping
	// its first place and its last value; a later alias overwrites an earlier one.
	_, topValues, _ := orderedObject([]byte(raw))
	keys, values, ok := orderedObject(topValues["steps"])
	if !ok {
		return state
	}
	for _, k := range keys {
		var value any
		if err := json.Unmarshal(values[k], &value); err != nil {
			continue
		}
		mark, isString := value.(string)
		step := normaliseStep(k)
		if !isString || !in(KnownSteps, step) || !in(Marks, mark) {
			continue
		}
		if mark == "waiting" && step != "police" {
			continue
		}
		state.Steps[step] = mark
	}
	return state
}

// decodeAll is json.loads: exactly one JSON value, numbers kept as text so
// 1e400 parses as Python's float does. Python's NaN and Infinity literals
// are not JSON and fail here (brief 1290 section 2).
func decodeAll(raw string) (any, bool) {
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, false
	}
	if _, err := dec.Token(); err != io.EOF {
		return nil, false
	}
	return v, true
}

// orderedObject reads a JSON object's keys in first-seen order and the last
// value of each key, as Python's dict does. ok is false for anything else.
func orderedObject(raw []byte) ([]string, map[string]json.RawMessage, bool) {
	if len(raw) == 0 {
		return nil, nil, false
	}
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	tok, err := dec.Token()
	if err != nil || tok != json.Delim('{') {
		return nil, nil, false
	}
	var keys []string
	values := map[string]json.RawMessage{}
	for dec.More() {
		tok, err := dec.Token()
		if err != nil {
			return nil, nil, false
		}
		k, _ := tok.(string)
		var value json.RawMessage
		if err := dec.Decode(&value); err != nil {
			return nil, nil, false
		}
		if _, seen := values[k]; !seen {
			keys = append(keys, k)
		}
		values[k] = value
	}
	return keys, values, true
}

// truthy is Python's bool() of a json.loads value.
func truthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case bool:
		return t
	case string:
		return t != ""
	case json.Number:
		f, _ := strconv.ParseFloat(string(t), 64)
		return f != 0
	case []any:
		return len(t) > 0
	case map[string]any:
		return len(t) > 0
	}
	return true
}

// LegacyState is property_setup.legacy_state.
func LegacyState() *State {
	return &State{Steps: map[string]string{}, Legacy: true}
}

// saveJSON is the json.dumps(..., sort_keys=True) text property_setup._save
// writes: separators ", " and ": ", ASCII only.
func saveJSON(s *State) string {
	keys := make([]string, 0, len(s.Steps))
	for k := range s.Steps {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var b strings.Builder
	b.WriteString(`{"celebrated": ` + pyBool(s.Celebrated))
	b.WriteString(`, "finished": ` + pyBool(s.Finished))
	b.WriteString(`, "hidden": ` + pyBool(s.Hidden))
	b.WriteString(`, "legacy": ` + pyBool(s.Legacy))
	b.WriteString(`, "steps": {`)
	for i, k := range keys {
		if i > 0 {
			b.WriteString(", ")
		}
		b.WriteString(pyJSONString(k) + ": " + pyJSONString(s.Steps[k]))
	}
	b.WriteString(`}, "tested": ` + pyBool(s.Tested) + "}")
	return b.String()
}

func pyBool(v bool) string {
	if v {
		return "true"
	}
	return "false"
}

// pyJSONString is json.dumps of a str with ensure_ascii=True.
func pyJSONString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '"':
			b.WriteString(`\"`)
		case r == '\\':
			b.WriteString(`\\`)
		case r == '\n':
			b.WriteString(`\n`)
		case r == '\r':
			b.WriteString(`\r`)
		case r == '\t':
			b.WriteString(`\t`)
		case r == '\b':
			b.WriteString(`\b`)
		case r == '\f':
			b.WriteString(`\f`)
		case r >= 0x20 && r <= 0x7e:
			b.WriteRune(r)
		case r > 0xffff:
			r -= 0x10000
			fmt.Fprintf(&b, `\u%04x\u%04x`, 0xd800+(r>>10), 0xdc00+(r&0x3ff))
		default:
			fmt.Fprintf(&b, `\u%04x`, r)
		}
	}
	b.WriteByte('"')
	return b.String()
}

// save is property_setup._save.
func save(ctx context.Context, s Settings, apartmentID int64, state *State) error {
	return s.Set(ctx, key(apartmentID), saveJSON(state))
}

// loadOrLegacy is "load(apartment_id) or legacy_state()".
func loadOrLegacy(ctx context.Context, s Settings, apartmentID int64) (*State, error) {
	state, err := Load(ctx, s, apartmentID)
	if err != nil || state != nil {
		return state, err
	}
	return LegacyState(), nil
}

// Start is property_setup.start.
func Start(ctx context.Context, s Settings, apartmentID int64) error {
	return save(ctx, s, apartmentID, &State{Steps: map[string]string{}})
}

// Mark is property_setup.mark.
func Mark(ctx context.Context, s Settings, apartmentID int64, step, value string) error {
	step = normaliseStep(step)
	state, err := loadOrLegacy(ctx, s, apartmentID)
	if err != nil {
		return err
	}
	if state.Finished || !in(KnownSteps, step) || !in(Marks, value) {
		return nil
	}
	if value == "waiting" && step != "police" {
		return nil
	}
	state.Steps[step] = value
	return save(ctx, s, apartmentID, state)
}

// SetHidden is property_setup.set_hidden.
func SetHidden(ctx context.Context, s Settings, apartmentID int64, hidden bool) error {
	state, err := loadOrLegacy(ctx, s, apartmentID)
	if err != nil || state.Finished {
		return err
	}
	state.Hidden = hidden
	return save(ctx, s, apartmentID, state)
}

// Finish is property_setup.finish.
func Finish(ctx context.Context, s Settings, apartmentID int64) error {
	state, err := Load(ctx, s, apartmentID)
	if err != nil || state == nil || state.Finished {
		return err
	}
	state.Finished = true
	return save(ctx, s, apartmentID, state)
}

// CelebrateOnce is property_setup.celebrate_once: true the first time the
// finished wizard's finish page is shown.
func CelebrateOnce(ctx context.Context, s Settings, apartmentID int64) (bool, error) {
	state, err := Load(ctx, s, apartmentID)
	if err != nil || state == nil || !state.Finished || state.Celebrated {
		return false, err
	}
	state.Celebrated = true
	if err := save(ctx, s, apartmentID, state); err != nil {
		return false, err
	}
	return true, nil
}

// MarkTested is property_setup.mark_tested.
func MarkTested(ctx context.Context, s Settings, apartmentID int64) error {
	state, err := loadOrLegacy(ctx, s, apartmentID)
	if err != nil || state.Finished {
		return err
	}
	state.Tested = true
	return save(ctx, s, apartmentID, state)
}

// MarkTestedInWizard is property_setup.mark_tested_in_wizard.
func MarkTestedInWizard(ctx context.Context, s Settings, apartmentID int64) error {
	state, err := Load(ctx, s, apartmentID)
	if err != nil || state == nil {
		return err
	}
	state.Tested = true
	return save(ctx, s, apartmentID, state)
}

// IsFirstSetup is property_setup.is_first_setup.
func IsFirstSetup(state *State) bool {
	return state != nil && !state.Finished && !state.Hidden
}

// SectionDone is property_setup.section_done.
func SectionDone(section string, apt Apartment, facts Facts, state *State) bool {
	switch section {
	case "basics":
		return PropertyDetailsComplete(apt)
	case "police":
		if !facts.ReportComplete {
			return false
		}
		if IsFirstSetup(state) {
			return state.Tested
		}
		return true
	case "calendars":
		return facts.Feeds > 0 || facts.Stays > 0
	case "fee":
		return apt.StayFeeRateCZK > 0
	case "lock":
		return facts.DoorCode == "on"
	}
	return false
}

// OpenSection is property_setup.open_section: "" when every section is done.
func OpenSection(apt Apartment, facts Facts, state *State) string {
	for _, section := range SetupOrder {
		if !SectionDone(section, apt, facts, state) {
			return section
		}
	}
	return ""
}

// SetupComplete is property_setup.setup_complete.
func SetupComplete(apt Apartment, facts Facts, state *State) bool {
	for _, section := range SetupOrder {
		if !SectionDone(section, apt, facts, state) {
			return false
		}
	}
	return true
}

// WizardURL is property_setup.wizard_url.
func WizardURL(apartmentID int64, step string) string {
	return fmt.Sprintf("/apartments/%d/setup/%s", apartmentID, step)
}

// NextStep is property_setup.next_step: "" is Python's None.
func NextStep(step string) string {
	i := indexOf(Steps, normaliseStep(step))
	if i < 0 {
		return ""
	}
	if i+1 >= len(Steps) {
		return "done"
	}
	return Steps[i+1]
}

// PrevStep is property_setup.prev_step: "" is Python's None.
func PrevStep(step string) string {
	i := indexOf(Steps, normaliseStep(step))
	if i <= 0 {
		return ""
	}
	return Steps[i-1]
}

// StepApplicable is property_setup.step_applicable.
func StepApplicable(step string, apt Apartment, lockAvailable bool) bool {
	step = normaliseStep(step)
	if step == "property" && PropertyDetailsComplete(apt) {
		return false
	}
	if step == "door_lock" && !lockAvailable {
		return false
	}
	return in(Steps, step)
}

// NextApplicableStep is property_setup.next_applicable_step: the next step
// that exists for this property, "done" after the last, "" for None.
func NextApplicableStep(step string, apt Apartment, lockAvailable bool) string {
	i := indexOf(Steps, normaliseStep(step))
	if i < 0 {
		return ""
	}
	for _, next := range Steps[i+1:] {
		if StepApplicable(next, apt, lockAvailable) {
			return next
		}
	}
	return "done"
}

// PrevApplicableStep is property_setup.prev_applicable_step: "" for None.
func PrevApplicableStep(step string, apt Apartment, lockAvailable bool) string {
	i := indexOf(Steps, normaliseStep(step))
	if i < 0 {
		return ""
	}
	for j := i - 1; j >= 0; j-- {
		if StepApplicable(Steps[j], apt, lockAvailable) {
			return Steps[j]
		}
	}
	return ""
}

// MayViewStep is property_setup.may_view_step: whether GET /setup/{step}
// may render. guide is the Current result, nil for None.
func MayViewStep(step string, guide *Guide, state *State, apt Apartment, facts Facts, lockAvailable bool) bool {
	step = normaliseStep(step)
	if !in(Steps, step) {
		return false
	}
	if !StepApplicable(step, apt, lockAvailable) {
		return false
	}
	if guide == nil {
		return true
	}
	currentIdx := indexOf(Steps, guide.Key)
	stepIdx := indexOf(Steps, step)
	if stepIdx < currentIdx {
		return true
	}
	if stepIdx > currentIdx {
		return false
	}
	switch StepStatus(step, state, apt, facts) {
	case "done", "skipped", "waiting", "not_needed":
		return true
	}
	return step == guide.Key
}

// PropertyDetailsComplete is property_setup.property_details_complete.
func PropertyDetailsComplete(apt Apartment) bool {
	return pyStrip(apt.InternalName) != "" &&
		apt.LegalEntityID != 0 &&
		pyStrip(apt.AddrObec) != "" &&
		pyStrip(apt.AddrHouseNo) != "" &&
		pyStrip(apt.AddrZip) != ""
}

// resolved is property_setup._resolved.
func resolved(step string, state *State, apt Apartment, facts Facts) bool {
	_, marked := state.Steps[step]
	switch {
	case step == "property":
		return PropertyDetailsComplete(apt) || marked
	case step == "calendar":
		return facts.Feeds > 0 || facts.Stays > 0 || marked
	case Teaching[step]:
		if facts.GuestsRegistered {
			return true
		}
		return marked
	case step == "police":
		return facts.ReportComplete
	case step == "stay_fee":
		return marked || apt.StayFeeRateCZK > 0
	case step == "door_lock":
		return marked || apt.LockProvider == "ttlock"
	case step == "automation":
		return marked || state.Legacy
	}
	return marked
}

// StepStatus is property_setup.step_status: done, skipped, not_needed,
// waiting or todo.
func StepStatus(step string, state *State, apt Apartment, facts Facts) string {
	mark := state.Steps[step]
	if step == "police" && state.Steps["police"] == "waiting" && !facts.ReportComplete {
		return "waiting"
	}
	if mark == "skipped" {
		return "skipped"
	}
	// 0234: "No smart lock" is an answer, not a skip.
	if mark == "not_needed" {
		return "not_needed"
	}
	if resolved(step, state, apt, facts) {
		return "done"
	}
	return "todo"
}

// DoneCount is property_setup.done_count (Python's lock_available defaults to true).
func DoneCount(state *State, apt Apartment, facts Facts, lockAvailable bool) int {
	total := 0
	for _, step := range Steps {
		if step == "door_lock" && !lockAvailable {
			total++
			continue
		}
		switch StepStatus(step, state, apt, facts) {
		case "done", "skipped", "not_needed":
			total++
		}
	}
	return total
}

// WizardUnresolved is property_setup.wizard_unresolved: true while a setup
// step still needs an answer; police may be deferred.
func WizardUnresolved(apt Apartment, state *State, facts Facts, lockAvailable bool) bool {
	for _, step := range Steps {
		if !StepApplicable(step, apt, lockAvailable) {
			continue
		}
		switch StepStatus(step, state, apt, facts) {
		case "todo", "current":
			return true
		}
	}
	return false
}

// Current is property_setup.current: the wizard step the host should see, or
// nil when setup is complete. It reads Feeds, Stays, GuestsRegistered and
// ReportComplete from facts, as the Python keyword arguments.
func Current(apt Apartment, state *State, f Facts, lockAvailable bool) *Guide {
	if state == nil || state.Finished || state.Hidden {
		return nil
	}
	facts := Facts{Feeds: f.Feeds, Stays: f.Stays, GuestsRegistered: f.GuestsRegistered, ReportComplete: f.ReportComplete}
	waiting := state.Steps["police"] == "waiting" && !facts.ReportComplete
	progress := []Progress{}
	chosen := -1
	for index, step := range Steps {
		if step == "door_lock" && !lockAvailable {
			value := "skipped"
			if resolved(step, state, apt, facts) {
				value = "done"
			}
			progress = append(progress, Progress{Key: step, State: value})
			continue
		}
		status := StepStatus(step, state, apt, facts)
		switch {
		case status == "done" || status == "skipped" || status == "not_needed":
			value := "done"
			if status == "skipped" {
				value = "skipped"
			}
			progress = append(progress, Progress{Key: step, State: value})
		case step == "police" && waiting:
			progress = append(progress, Progress{Key: step, State: "waiting"})
		case chosen < 0:
			chosen = index
			progress = append(progress, Progress{Key: step, State: "current"})
		default:
			progress = append(progress, Progress{Key: step, State: "todo"})
		}
	}
	if chosen < 0 {
		return nil
	}
	step := Steps[chosen]
	return &Guide{
		Key:              step,
		Number:           chosen + 1,
		Total:            TotalSteps,
		Optional:         Optional[step],
		Skippable:        Skippable[step],
		URL:              WizardURL(apt.ID, step),
		Progress:         progress,
		ReportingWaiting: waiting,
		PoliceURL:        WizardURL(apt.ID, "police"),
		Legacy:           state.Legacy,
		DoneCount:        DoneCount(state, apt, facts, lockAvailable),
	}
}

// Checklist is property_setup.checklist.
func Checklist(state *State, apt Apartment, facts Facts, lockAvailable bool) []ChecklistRow {
	rows := []ChecklistRow{}
	for _, step := range Steps {
		if step == "door_lock" && !lockAvailable {
			rows = append(rows, ChecklistRow{Key: step, Status: "not_needed"})
			continue
		}
		rows = append(rows, ChecklistRow{Key: step, Status: StepStatus(step, state, apt, facts)})
	}
	return rows
}

// pyStrip is Python's str.strip(): str.isspace() is unicode.IsSpace plus the
// separators U+001C to U+001F.
func pyStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool {
		return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
	})
}
