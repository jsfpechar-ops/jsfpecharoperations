package ai

// havel_engine.go: everything between the form and the model, the port of
// App/app/havel.py lines 124-569 (guide and pages blocks, redaction, signed
// history, host context, messages, local replies, validation, ask). Pure
// code: the database is reached only through the sink ask is given.

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

// --- system blocks ----------------------------------------------------------

// havelLabel is havel.label: guide strings come from the guide table, the rest
// from the host catalog.
func havelLabel(lang, key string) string {
	if strings.HasPrefix(key, "guide.") {
		if t, ok := havelGuideStrings(havelGuideLang(lang))[key]; ok && t != "" {
			return t
		}
		if t, ok := havelGuideStrings("en")[key]; ok {
			return t
		}
		return key
	}
	return havelCatalog.T(lang, key, nil)
}

// havelGuideBlock is havel.guide_block.
func havelGuideBlock(lang string) string {
	strs := havelGuideStrings(havelGuideLang(lang))
	keys := make([]string, 0, len(strs))
	for k := range strs {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var b strings.Builder
	b.WriteString(`<guide lang="` + havelGuideLang(lang) + "\">\n")
	for _, k := range keys {
		b.WriteString(k + ": " + strings.Join(havelFields(strs[k]), " ") + "\n")
	}
	b.WriteString("</guide>")
	return b.String()
}

// havelPagesBlock is havel.pages_block.
func havelPagesBlock(lang string) string {
	var b strings.Builder
	b.WriteString("<pages>\nid | label | what it is for")
	for _, p := range havelPages {
		b.WriteString("\n" + p.ID + " | " + havelLabel(lang, p.LabelKey) + " | " + p.Purpose)
	}
	b.WriteString("\n</pages>")
	return b.String()
}

// HavelSystemBlocks is havel.system_blocks: constant per language, cached.
func HavelSystemBlocks(lang string) []string {
	return []string{havelSystemPrompt, havelGuideBlock(lang), havelPagesBlock(lang)}
}

// HavelPageURL is havel.page_url: "" for an unknown id. A property page without
// an owned property falls back to the Properties list.
func HavelPageURL(page string, propertyID *int64, owned []int64) string {
	p, ok := havelPageByID[page]
	if !ok {
		return ""
	}
	if strings.Contains(p.URL, "{id}") {
		if propertyID != nil {
			for _, id := range owned {
				if id == *propertyID {
					return strings.ReplaceAll(p.URL, "{id}", strconv.FormatInt(id, 10))
				}
			}
		}
		return havelPageByID["properties"].URL
	}
	return p.URL
}

// --- redaction ----------------------------------------------------------------

var (
	havelDateRE   = regexp.MustCompile(`\d{4}-\d{2}-\d{2}|\b\d{1,2}\.\s?\d{1,2}\.(?:\s?\d{4})?|\b\d{1,2}:\d{2}\b`)
	havelEmailRE  = regexp.MustCompile(`[\w.+-]+@[\w-]+(?:\.[\w-]+)+`)
	havelPhoneRE  = regexp.MustCompile(`^\+?\d(?:[\s-]?\d){6,}`) // anchored; the look-behind is havelPhones
	havelNumberRE = regexp.MustCompile(`\b(?:\d{6,}|[A-Za-z]{1,4}\d{6,})\b`)
	havelDigitsRE = regexp.MustCompile(`\d+`)
)

// havelPhones is _PHONE.finditer: (?<![A-Za-z\d])\+?\d(?:[\s-]?\d){6,}.
func havelPhones(s string) [][2]int {
	folded, _ := havelFold(s)
	var out [][2]int
	for i := 0; i < len(folded); {
		if i > 0 {
			c := folded[i-1]
			if (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') {
				i++
				continue
			}
		}
		if m := havelPhoneRE.FindStringIndex(folded[i:]); m != nil {
			out = append(out, [2]int{i, i + m[1]})
			i += m[1]
			continue
		}
		i++
	}
	return out
}

// havelSubSpans replaces the given rune spans.
func havelSubSpans(s string, spans [][2]int, repl func(string) string) string {
	if len(spans) == 0 {
		return s
	}
	runes := []rune(s)
	var b strings.Builder
	last := 0
	for _, sp := range spans {
		b.WriteString(string(runes[last:sp[0]]))
		b.WriteString(repl(string(runes[sp[0]:sp[1]])))
		last = sp[1]
	}
	b.WriteString(string(runes[last:]))
	return b.String()
}

// HavelMapping is the placeholder -> real value map of one request, in the
// order the placeholders were made (a Python dict).
type HavelMapping struct {
	Names []string
	Real  map[string]string
}

// NewHavelMapping returns an empty mapping.
func NewHavelMapping() *HavelMapping { return &HavelMapping{Real: map[string]string{}} }

func (m *HavelMapping) placeholder(kind, value string) string {
	prefix := "[" + kind + " "
	count := 0
	for _, name := range m.Names {
		if strings.HasPrefix(name, prefix) {
			if m.Real[name] == value {
				return name
			}
			count++
		}
	}
	name := prefix + strconv.Itoa(count+1) + "]"
	m.Names = append(m.Names, name)
	m.Real[name] = value
	return name
}

// HavelRedact is havel.redact: e-mails, phone numbers and ID-like tokens become
// [email 1], [phone 1], [number 1]; dates and times stay. The mapping is reused
// across the turns of one request.
func HavelRedact(text string, m *HavelMapping) string {
	var keep []string
	out := havelSub(havelDateRE, text, func(match string) string {
		keep = append(keep, match)
		return "\x00" + strconv.Itoa(len(keep)-1) + "\x00"
	})
	out = havelSub(havelEmailRE, out, func(v string) string { return m.placeholder("email", v) })
	out = havelSubSpans(out, havelPhones(out), func(v string) string { return m.placeholder("phone", v) })
	out = havelSub(havelNumberRE, out, func(v string) string { return m.placeholder("number", v) })
	return havelParkRE.ReplaceAllStringFunc(out, func(s string) string {
		n, _ := strconv.Atoi(strings.Trim(s, "\x00"))
		return keep[n]
	})
}

var havelParkRE = regexp.MustCompile("\x00[0-9]+\x00")

// HavelRestore is havel.restore (an empty text stays empty).
func HavelRestore(text string, m *HavelMapping) string {
	if text == "" {
		return text
	}
	for _, name := range m.Names {
		text = strings.ReplaceAll(text, name, m.Real[name])
	}
	return text
}

// --- signed history ---------------------------------------------------------------

// HavelExchange is one question and answer of the conversation.
type HavelExchange struct{ Host, Havel string }

func havelSig(secret string, userID int64, payload string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(strconv.FormatInt(userID, 10) + "\n" + payload))
	return hex.EncodeToString(mac.Sum(nil))
}

func havelTrim(items []HavelExchange) []HavelExchange {
	if len(items) > HavelMaxExchanges {
		items = items[len(items)-HavelMaxExchanges:]
	}
	out := make([]HavelExchange, len(items))
	for i, e := range items {
		out[i] = HavelExchange{havelClip(e.Host, HavelMaxMessageChars), havelClip(e.Havel, HavelMaxReplyChars)}
	}
	return out
}

// HavelSignHistory is havel.sign_history: the compact JSON and its signature.
func HavelSignHistory(secret string, userID int64, exchanges []HavelExchange) (payload, sig string) {
	var b strings.Builder
	b.WriteByte('[')
	for i, e := range havelTrim(exchanges) {
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteString(`{"host":` + havelPyString(e.Host) + `,"havel":` + havelPyString(e.Havel) + `}`)
	}
	b.WriteByte(']')
	payload = b.String()
	return payload, havelSig(secret, userID, payload)
}

// HavelReadHistory is havel.read_history: a bad or missing signature empties
// the history; it never fails the request.
func HavelReadHistory(secret string, userID int64, payload, sig string) []HavelExchange {
	if payload == "" || sig == "" || !hmac.Equal([]byte(havelSig(secret, userID, payload)), []byte(sig)) {
		return []HavelExchange{}
	}
	var items []any
	if err := json.Unmarshal([]byte(payload), &items); err != nil {
		return []HavelExchange{}
	}
	var clean []HavelExchange
	for _, it := range items {
		obj, ok := it.(map[string]any)
		if !ok {
			continue
		}
		clean = append(clean, HavelExchange{havelStrOr(obj["host"]), havelStrOr(obj["havel"])})
	}
	if clean == nil {
		return []HavelExchange{}
	}
	return havelTrim(clean)
}

// havelStrOr is str(e.get(key, "")) for a signed payload (the server wrote it).
func havelStrOr(v any) string {
	if v == nil {
		return "None"
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprint(v)
}

// --- the request ----------------------------------------------------------------------

// HavelProperty is one entry of Host.properties.
type HavelProperty struct {
	ID   int64
	Name string
	City string
}

// HavelHost is havel.Host.
type HavelHost struct {
	UserID     int64
	Lang       string
	Device     string
	Properties []HavelProperty
	Page       string
	Topic      string
	ReadKeys   []string
}

// PropertyIDs is Host.property_ids.
func (h HavelHost) PropertyIDs() []int64 {
	out := make([]int64, len(h.Properties))
	for i, p := range h.Properties {
		out[i] = p.ID
	}
	return out
}

// HavelHostContext is havel.host_context.
func HavelHostContext(h HavelHost, today time.Time) string {
	props := make([]string, 0, len(h.Properties))
	for _, p := range h.Properties {
		if p.City != "" {
			props = append(props, fmt.Sprintf("id %d: %s (%s)", p.ID, p.Name, p.City))
		} else {
			props = append(props, fmt.Sprintf("id %d: %s", p.ID, p.Name))
		}
	}
	list := strings.Join(props, "; ")
	if list == "" {
		list = "none"
	}
	page := h.Page
	if page == "" {
		page = "unknown"
	}
	lines := []string{
		"today: " + today.Format("2006-01-02") + " (" + today.Weekday().String() + ")",
		"lang: " + h.Lang,
		"device: " + h.Device,
		"properties: " + list,
		"page: " + page,
	}
	if h.Topic != "" {
		lines = append(lines, "topic: "+h.Topic)
	}
	if len(h.ReadKeys) > 0 {
		lines = append(lines, "read_keys: "+strings.Join(h.ReadKeys, ", "))
	}
	return "<host_context>\n" + strings.Join(lines, "\n") + "\n</host_context>"
}

// HavelModelHistory is havel.model_history: the last four exchanges within 4000 characters.
func HavelModelHistory(history []HavelExchange) []HavelExchange {
	trimmed := history
	if len(trimmed) > havelMaxHistory {
		trimmed = trimmed[len(trimmed)-havelMaxHistory:]
	}
	for len(trimmed) > 0 {
		total := 0
		for _, e := range trimmed {
			total += havelLen(e.Host) + havelLen(e.Havel)
		}
		if total <= havelMaxHistoryChars {
			break
		}
		trimmed = trimmed[1:]
	}
	return trimmed
}

// HavelBuildMessages is havel.build_messages: earlier exchanges (redacted),
// then the new user turn with the host context. These are the only texts that
// reach the model besides the constant system blocks.
func HavelBuildMessages(h HavelHost, history []HavelExchange, message string, today time.Time, m *HavelMapping) []anthropic.Message {
	var out []anthropic.Message
	for _, e := range HavelModelHistory(history) {
		out = append(out, anthropic.Message{Role: "user", Content: "<message>" + HavelRedact(e.Host, m) + "</message>"})
		out = append(out, anthropic.Message{Role: "assistant", Content: HavelRedact(e.Havel, m)})
	}
	text := HavelRedact(message, m)
	out = append(out, anthropic.Message{Role: "user", Content: HavelHostContext(h, today) + "\n<message>" + text + "</message>"})
	return out
}

// --- free local replies -----------------------------------------------------------------

const havelSpaceClass = `\s\v\x{1c}-\x{1f}\x{85}\p{Z}`

var (
	havelGreetingRE = regexp.MustCompile(`(?i)^(?:hi|hello|hey|good (?:morning|afternoon|evening)|ahoj|dobr[ýy] den|zdrav[ií]m|čau|xin ch[àa]o|ch[àa]o)[` + havelSpaceClass + `!.,]*$`)
	havelThanksRE   = regexp.MustCompile(`(?i)^(?:thanks?|thank you|thx|ok(?:ay)?|d[íi]ky|d[ěe]kuj[iu]|super|c[ảa]m [ơo]n)[` + havelSpaceClass + `!.,]*$`)
)

// HavelLocalReply is havel.local_reply: the copy key of a greeting or thanks, or "".
func HavelLocalReply(message string) string {
	text := havelStrip(message)
	if havelLen(text) > 40 {
		return ""
	}
	if havelGreetingRE.MatchString(text) {
		return "havel.greeting"
	}
	if havelThanksRE.MatchString(text) {
		return "havel.thanks"
	}
	return ""
}

// --- validation ----------------------------------------------------------------------------

// HavelLink is one link button: the label and the URL.
type HavelLink struct{ Label, URL string }

// HavelReply is havel.Reply. Action holds the validated action in field order
// (values as the model sent them, restored text).
type HavelReply struct {
	Kind           string
	Text           string
	Links          []HavelLink
	Action         map[string]any
	SupportSummary *string
	FailReason     string
	Sources        []string
	Next           []string
}

func havelFail(reason string) HavelReply { return HavelReply{Kind: "fail", FailReason: reason} }

var (
	havelScriptsRE = regexp.MustCompile(`[\x{0400}-\x{04FF}\x{0590}-\x{05FF}\x{0600}-\x{06FF}\x{0E00}-\x{0E7F}\x{3040}-\x{30FF}\x{4E00}-\x{9FFF}\x{AC00}-\x{D7AF}]`)
	havelAddressRE = regexp.MustCompile(`(?i)https?:|www\.|@|/[A-Za-z]|\+?\d(?:[\s-]?\d){6,}|\b[\w-]+\.(?:com|cz|net|org|io|eu|sk|de|app|info)\b`)
	havelMarkupRE  = regexp.MustCompile("(?m)[<>`]|\\*\\*|^#")
	havelDateishRE = regexp.MustCompile(`\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?|\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}`)
	havelISORE     = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}\n?$`)
	havelHHMMRE    = regexp.MustCompile(`^(?:[01]\d|2[0-3]):[0-5]\d\n?$`)
	havelStepRE    = regexp.MustCompile(`(?m)^\d{1,2}\.\s`)
	havelEmailFull = regexp.MustCompile(`^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$`)
)

// havelScripts is _FORBIDDEN_SCRIPTS.search on the original text.
func havelScripts(s string) bool { return havelScriptsRE.MatchString(s) }

// havelAddress is _ADDRESS.search(_DATEISH.sub("", s)).
func havelAddress(s string) bool {
	return havelSearch(havelAddressRE, havelSub(havelDateishRE, s, func(string) string { return "" }))
}

func havelMarkup(s string) bool { return havelSearch(havelMarkupRE, s) }

// havelNumbersOK is _numbers_ok: every digit run of the reply is a step number,
// part of a date or time, or present in the allowed text.
func havelNumbersOK(reply, allowed string) bool {
	cleaned := havelSub(havelDateishRE, havelSub(havelStepRE, reply, func(string) string { return "" }), func(string) string { return "" })
	for _, run := range havelFindAll(havelDigitsRE, cleaned) {
		if !strings.Contains(allowed, run) {
			return false
		}
	}
	return true
}

// havelStringList is a model value read as a list of items (a str would be
// iterated by character in Python; nothing else is iterable here).
func havelList(v any) []any {
	switch t := v.(type) {
	case []any:
		return t
	case string:
		var out []any
		for _, r := range t {
			out = append(out, string(r))
		}
		return out
	}
	return nil
}

func havelTruthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case string:
		return t != ""
	case bool:
		return t
	case []any:
		return len(t) > 0
	case map[string]any:
		return len(t) > 0
	case json.Number:
		f, _ := t.Float64()
		return f != 0
	}
	return true
}

// HavelValidate is havel.validate: the model's JSON becomes what the host may
// see, or a "fail" reply. The server, not the model, decides.
func HavelValidate(data any, h HavelHost, message string, history []HavelExchange, m *HavelMapping, today time.Time) HavelReply {
	obj, ok := data.(map[string]any)
	if !ok {
		return havelFail("schema")
	}
	kind, _ := obj["kind"].(string)
	validKind := false
	for _, k := range havelKinds {
		if k == kind {
			validKind = true
		}
	}
	rawReply, replyIsStr := obj["reply"].(string)
	if !validKind || !replyIsStr {
		return havelFail("schema")
	}
	reply := havelStrip(rawReply)
	if reply == "" || havelLen(reply) > HavelMaxReplyChars {
		return havelFail("length")
	}
	if havelScripts(reply) {
		return havelFail("script")
	}
	if havelAddress(reply) {
		return havelFail("address")
	}
	if havelMarkup(reply) {
		return havelFail("markup")
	}
	prompt := []rune(havelSystemPrompt)
	limit := len(prompt) - 40
	if limit < 1 {
		limit = 1
	}
	for start := 0; start < limit; start += 20 {
		end := start + 40
		if end > len(prompt) {
			end = len(prompt)
		}
		if strings.Contains(reply, string(prompt[start:end])) {
			return havelFail("prompt_leak")
		}
	}
	for _, name := range m.Names {
		if strings.Contains(reply, m.Real[name]) {
			return havelFail("secret")
		}
	}

	strs := havelGuideStrings(havelGuideLang(h.Lang))
	var sources []string
	if raw, ok := obj["sources"].([]any); ok {
		for _, s := range raw {
			if str, ok := s.(string); ok {
				if _, known := strs[str]; known {
					sources = append(sources, str)
				}
			}
		}
	}
	if len(sources) > 8 {
		sources = sources[:8]
	}
	context := HavelHostContext(h, today)
	var hostTexts []string
	for _, e := range history {
		hostTexts = append(hostTexts, e.Host)
	}
	if kind == "answer" {
		if len(sources) == 0 {
			return havelFail("sources")
		}
		var texts []string
		for _, s := range sources {
			texts = append(texts, strs[s])
		}
		allowed := strings.Join(texts, " ") + " " + message + " " + context + " " + strings.Join(hostTexts, " ") + " " + havelEmergency
		if !havelNumbersOK(reply, allowed) {
			return havelFail("number")
		}
	}

	var next []string
	if kind != "refuse" {
		known := message + " " + context + " " + strings.Join(hostTexts, " ") + " " + havelEmergency
		for _, item := range havelList(obj["next"]) {
			if len(next) == havelMaxNext {
				break
			}
			str, ok := item.(string)
			if !ok {
				continue
			}
			str = havelClip(havelStrip(str), havelMaxNextChars)
			if str == "" || havelScripts(str) || havelMarkup(str) || havelAddress(str) {
				continue
			}
			okRuns := true
			for _, run := range havelFindAll(havelDigitsRE, havelSub(havelDateishRE, str, func(string) string { return "" })) {
				if !strings.Contains(known, run) {
					okRuns = false
					break
				}
			}
			if !okRuns {
				continue
			}
			next = append(next, HavelRestore(str, m))
		}
	}

	var links []HavelLink
	if kind == "answer" || kind == "clarify" || kind == "escalate" {
		for _, item := range havelList(obj["links"]) {
			if len(links) == 3 {
				break
			}
			entry, ok := item.(map[string]any)
			if !ok {
				continue
			}
			page, ok := entry["page"].(string)
			if !ok {
				continue
			}
			if _, known := havelPageByID[page]; !known {
				continue
			}
			var pid *int64
			if n, ok := havelPyInt(entry["property_id"]); ok {
				pid = &n
			}
			if url := HavelPageURL(page, pid, h.PropertyIDs()); url != "" {
				links = append(links, HavelLink{havelLabel(h.Lang, havelPageByID[page].LabelKey), url})
			}
		}
	}

	var summary *string
	if kind == "escalate" {
		s, ok := obj["support_summary"].(string)
		if !ok || havelStrip(s) == "" {
			return havelFail("summary")
		}
		if havelLen(s) > HavelMaxSummaryChars {
			return havelFail("length")
		}
		restored := HavelRestore(havelStrip(s), m)
		summary = &restored
	}

	var action map[string]any
	if kind == "action" {
		var fail *HavelReply
		action, fail = havelValidateAction(obj["action"], h, m)
		if fail != nil {
			return *fail
		}
	}

	return HavelReply{Kind: kind, Text: HavelRestore(reply, m), Links: links, Action: action,
		SupportSummary: summary, Sources: sources, Next: next}
}

// havelValidateAction is the action branch of havel.validate (lines 454-496).
func havelValidateAction(raw any, h HavelHost, m *HavelMapping) (map[string]any, *HavelReply) {
	f := func(reason string) (map[string]any, *HavelReply) {
		r := havelFail(reason)
		return nil, &r
	}
	obj, ok := raw.(map[string]any)
	if !ok {
		return f("action")
	}
	typ, _ := obj["type"].(string)
	known := false
	for _, a := range HavelActions {
		if a == typ {
			known = true
		}
	}
	if !known {
		return f("action")
	}
	action := map[string]any{}
	for _, name := range havelActionFields {
		action[name] = obj[name]
	}
	// restore() on a value that is not text would raise in Python (a 500); here it is a plain fail.
	for _, name := range []string{"guest_email", "note"} {
		switch v := action[name].(type) {
		case nil:
		case string:
			action[name] = HavelRestore(v, m)
		default:
			return f("action_text")
		}
	}
	var pid *int64
	if n, ok := havelPyInt(action["property_id"]); ok {
		pid = &n
	}
	ids := h.PropertyIDs()
	inIDs := func(p *int64) bool {
		if p == nil {
			return false
		}
		for _, id := range ids {
			if id == *p {
				return true
			}
		}
		return false
	}
	if typ != "sync_calendars" {
		if len(h.Properties) == 1 && pid == nil {
			p := ids[0]
			pid = &p
		}
		if !inIDs(pid) {
			return f("action_property")
		}
	} else if !inIDs(pid) {
		pid = nil
	}
	if pid == nil {
		action["property_id"] = nil
	} else {
		action["property_id"] = json.Number(strconv.FormatInt(*pid, 10))
	}
	for _, name := range []string{"date_from", "date_to"} {
		if action[name] != nil && !havelISORE.MatchString(havelFoldStr(havelPyStr(action[name]))) {
			return f("action_dates")
		}
	}
	for _, name := range []string{"start_time", "end_time"} {
		if action[name] != nil && !havelHHMMRE.MatchString(havelFoldStr(havelPyStr(action[name]))) {
			return f("action_times")
		}
	}
	from, _ := action["date_from"].(string)
	to, _ := action["date_to"].(string)
	if typ == "create_stay" {
		if from == "" || to == "" || to <= from {
			return f("action_dates")
		}
		if g := action["guests"]; g != nil {
			n, ok := havelPyInt(g)
			if !ok || n < 1 || n > 60 {
				return f("action_guests")
			}
		}
	}
	if typ == "create_cleaning" && from == "" {
		return f("action_dates")
	}
	for _, name := range []string{"note", "guest_email"} {
		v, isStr := action[name].(string)
		if action[name] == nil {
			continue
		}
		if !isStr || havelScripts(v) || havelMarkup(v) {
			return f("action_text")
		}
		if name == "note" && havelAddress(v) {
			return f("action_text")
		}
	}
	if email, ok := action["guest_email"].(string); ok && !havelEmailFull.MatchString(havelFoldStr(email)) {
		return f("action_email")
	}
	return action, nil
}

// havelFoldStr is the folded text, for the anchored whole-string patterns.
func havelFoldStr(s string) string { f, _ := havelFold(s); return f }

// --- one call, end to end ------------------------------------------------------------------

// HavelModel is what ask needs of the model client; *anthropic.Service
// satisfies it (enabled switch, spend caps and usage ledger included).
type HavelModel interface {
	Call(ctx context.Context, feature string, system []string, messages []anthropic.Message, schema json.RawMessage, key *string, maxTokens int) (map[string]any, error)
}

// HavelStatSink is havel.record_stat.
type HavelStatSink func(ctx context.Context, kind string, day time.Time) error

// HavelAsk is havel.ask: build, call, validate. It returns an *anthropic.Error
// with Disabled or Budget set (the page shows its own text), a database error
// as it is, and every other failure (API, refusal, bad JSON, guardrail) as a
// reply of kind "fail". input_too_large drops the oldest exchange and retries
// once.
func HavelAsk(ctx context.Context, model HavelModel, stat HavelStatSink, h HavelHost, history []HavelExchange, message string, today time.Time) (HavelReply, error) {
	var data map[string]any
	var mapping *HavelMapping
	for attempt := 0; ; attempt++ {
		mapping = NewHavelMapping()
		messages := HavelBuildMessages(h, history, message, today, mapping)
		var err error
		data, err = model.Call(ctx, HavelFeature, HavelSystemBlocks(h.Lang), messages, HavelSchema(), nil, HavelMaxTokens)
		if err == nil {
			break
		}
		aerr := anthropic.AsError(err)
		if aerr == nil {
			return HavelReply{}, err
		}
		if aerr.Disabled || aerr.Budget {
			return HavelReply{}, aerr
		}
		if aerr.Reason == "input_too_large" && attempt == 0 && len(history) > 0 {
			history = history[1:]
			continue
		}
		if err := stat(ctx, "guardrail_fail", today); err != nil {
			return HavelReply{}, err
		}
		return havelFail(aerr.Reason), nil
	}
	reply := HavelValidate(data, h, message, history, mapping, today)
	kind := reply.Kind
	if kind == "fail" {
		kind = "guardrail_fail"
	}
	if err := stat(ctx, kind, today); err != nil {
		return HavelReply{}, err
	}
	return reply, nil
}
