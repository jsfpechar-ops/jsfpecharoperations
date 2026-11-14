package ai

// havel_pages.go: what the Havel pages show, the port of the helpers of
// App/app/routes/havel.py (lines 37-134): the thread items, _page_context and
// the small text helpers. The handlers are in havel_handlers.go.

import (
	"context"
	"path"
	"regexp"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

// Joined is the steps of a list as one line (the host bubble shows steps that way).
func (b havelBlock) Joined() string { return strings.Join(b.Items, " ") }

// havelBlock is one paragraph ("p") or one numbered list ("ol") of a bubble.
type havelBlock struct {
	Kind  string
	Text  string
	Items []string
}

// havelItem is routes/havel.py _item: one bubble of the thread.
type havelItem struct {
	Role           string
	Text           string
	Blocks         []havelBlock
	Links          []HavelLink
	Support        bool
	SupportSummary string
	Next           []string
	Card           *HavelCard
	NotHelped      bool
}

var havelStepRE2 = regexp.MustCompile(`^\d{1,2}\.\s+`)

// havelSplitLines is str.splitlines().
func havelSplitLines(s string) []string {
	var out []string
	var cur []rune
	runes := []rune(s)
	for i := 0; i < len(runes); i++ {
		r := runes[i]
		switch r {
		case '\n', '\r', '\v', '\f', 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029:
			if r == '\r' && i+1 < len(runes) && runes[i+1] == '\n' {
				i++
			}
			out = append(out, string(cur))
			cur = nil
		default:
			cur = append(cur, r)
		}
	}
	if len(cur) > 0 {
		out = append(out, string(cur))
	}
	return out
}

// havelBlocks is routes/havel.py blocks(): paragraphs and numbered steps as
// blocks, so steps render as a real list.
func havelBlocks(text string) []havelBlock {
	out := []havelBlock{}
	for _, line := range havelSplitLines(text) {
		line = havelStrip(line)
		if line == "" {
			continue
		}
		folded, runes := havelFold(line)
		if m := havelStepRE2.FindStringIndex(folded); m != nil {
			if len(out) == 0 || out[len(out)-1].Kind != "ol" {
				out = append(out, havelBlock{Kind: "ol", Items: []string{}})
			}
			last := &out[len(out)-1]
			last.Items = append(last.Items, string(runes[m[1]:]))
		} else {
			out = append(out, havelBlock{Kind: "p", Text: line})
		}
	}
	return out
}

// havelNewItem is _item.
func havelNewItem(role, text string) havelItem {
	return havelItem{Role: role, Text: text, Blocks: havelBlocks(text)}
}

// havelCleanID is _clean_id: letters a-z and underscore, 30 at most.
func havelCleanID(value string) string {
	var b strings.Builder
	for _, r := range value {
		if (r >= 'a' && r <= 'z') || r == '_' {
			b.WriteRune(r)
		}
	}
	return havelClip(b.String(), 30)
}

// havelThread is _thread: the greeting, the earlier exchanges, the newest items.
func havelThread(intro string, exchanges []HavelExchange, last []havelItem, hasLast bool) []havelItem {
	items := []havelItem{havelNewItem("havel", intro)}
	shown := exchanges
	if hasLast && len(shown) > 0 {
		shown = shown[:len(shown)-1]
	}
	for _, e := range shown {
		items = append(items, havelNewItem("host", e.Host), havelNewItem("havel", e.Havel))
	}
	if hasLast {
		items = append(items, last...)
	}
	return items
}

// HavelView is the context of the Havel templates (the havel_* names of _page_context).
type HavelView struct {
	Items          []havelItem
	State          string // "off", a limit suffix, or "" when the host may send
	Error          string
	History        string
	HistorySig     string
	Topic          string
	Q              string
	Page           string
	ReturnTo       string
	Max            int
	Fresh          bool
	Ask            bool
	Locked         bool
	Topics         []havelTopic
	TopicData      *havelTopic
	Answer         *HavelAnswer
	ShowTopics     bool
	SupportTo      string
	SupportBlocked bool
	OperatorEmail  string
	Fragment       bool
	IntroText      string
	PropertyIDs    []int64
	FirstProperty  *int64
	Lang           string
	OwnerID        int64
}

// PageURL is page_url(page_id) of the context: the first property as the default.
func (v HavelView) PageURL(page string) string {
	return HavelPageURL(page, v.FirstProperty, v.PropertyIDs)
}

// PageLabel is the button label of a topic answer's page.
func (v HavelView) PageLabel(page string) string {
	if strings.HasPrefix(page, "guide_") {
		return havelCatalog.T(v.Lang, "havel.topic.guide", nil)
	}
	return havelCatalog.T(v.Lang, havelPageByID[page].LabelKey, nil)
}

// ThreadItems is the items the thread template shows: the greeting is left out
// when the topics layer shows it already.
func (v HavelView) ThreadItems() []havelItem {
	if v.ShowTopics && len(v.Items) > 0 && v.Items[0].Text == v.IntroText {
		return v.Items[1:]
	}
	return v.Items
}

// IsGreeting reports whether the item at index i of ThreadItems is the greeting.
func (v HavelView) IsGreeting(i int, it havelItem) bool { return i == 0 && it.Text == v.IntroText }

// IsLast reports whether index i is the last of ThreadItems.
func (v HavelView) IsLast(i int) bool { return i == len(v.ThreadItems())-1 }

// havelOptions are the inputs of one rendering of the context.
type havelOptions struct {
	Topic, Q, Page, ReturnTo, Error string
	Ask                             bool
}

// havelPageContext is _page_context.
func (c *havelCall) pageContext(ctx context.Context, items []havelItem, exchanges []HavelExchange, o havelOptions) (HavelView, error) {
	state, err := c.state(ctx)
	if err != nil {
		return HavelView{}, err
	}
	payload, sig := HavelSignHistory(c.secret, c.h.Account.ID, exchanges)
	props, err := c.properties(ctx)
	if err != nil {
		return HavelView{}, err
	}
	blocked, err := c.store.SupportBlocked(ctx, c.h.Account.ID, c.at)
	if err != nil {
		return HavelView{}, err
	}
	email, err := c.accountEmail(ctx)
	if err != nil {
		return HavelView{}, err
	}
	v := HavelView{
		Items: items, State: state, Error: o.Error, History: payload, HistorySig: sig, Topic: o.Topic, Q: o.Q, Page: o.Page,
		ReturnTo: o.ReturnTo, Max: HavelMaxMessageChars, Fresh: len(exchanges) == 0, Ask: o.Ask,
		Locked: len(exchanges) == 0 && !o.Ask, ShowTopics: len(exchanges) == 0 && len(items) == 0,
		SupportTo: mail.MaskEmail(email), SupportBlocked: blocked, OperatorEmail: havelOperatorEmail(c.env),
		IntroText: c.t("havel.intro", nil), Lang: c.lang, OwnerID: c.h.Account.ID,
	}
	nav := ""
	for _, k := range havelNavOrder {
		if havelNavToPage[k] == o.Page {
			nav = k
			break
		}
	}
	v.Topics = HavelOrderedTopics(nav)
	if o.Topic != "" {
		v.TopicData = HavelFindTopic(o.Topic)
		if o.Q != "" {
			v.Answer = HavelTopicAnswer(c.lang, o.Topic, o.Q)
		}
	}
	for _, p := range props {
		v.PropertyIDs = append(v.PropertyIDs, p.ID)
	}
	if len(v.PropertyIDs) > 0 {
		first := v.PropertyIDs[0]
		v.FirstProperty = &first
	}
	return v, nil
}

// havelNavOrder is the key order of NAV_TO_PAGE in routes/havel.py.
var havelNavOrder = []string{"dashboard", "reservations", "submissions", "housebook", "apartments", "cleaning", "stay_fees", "invoices",
	"settings", "guide", "entities", "smart_locks"}

// --- safe_local_path (security.py 42-60), as go/internal/web/properties/localpath.go ---

func havelUnquote(s string) string {
	if !strings.Contains(s, "%") {
		return s
	}
	var b []byte
	for i := 0; i < len(s); i++ {
		if s[i] == '%' && i+2 < len(s) && havelIsHex(s[i+1]) && havelIsHex(s[i+2]) {
			b = append(b, havelHexVal(s[i+1])<<4|havelHexVal(s[i+2]))
			i += 2
			continue
		}
		b = append(b, s[i])
	}
	return strings.ToValidUTF8(string(b), "�")
}

func havelIsHex(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}

func havelHexVal(c byte) byte {
	switch {
	case c >= 'a':
		return c - 'a' + 10
	case c >= 'A':
		return c - 'A' + 10
	}
	return c - '0'
}

func havelHasControl(s string) bool {
	for _, r := range s {
		if r < 0x20 {
			return true
		}
	}
	return false
}

// HavelSafeLocalPath is security.safe_local_path: a normalised same-site path
// with its query, or def for unsafe input.
func HavelSafeLocalPath(value, def string) string {
	raw := havelStrip(value)
	if raw == "" || havelHasControl(raw) || strings.Contains(raw, "\\") || !strings.HasPrefix(raw, "/") {
		return def
	}
	if strings.HasPrefix(raw, "//") {
		raw = raw[2:]
		if !strings.HasPrefix(raw, "/") {
			return def
		}
	}
	p, query := raw, ""
	if i := strings.IndexByte(p, '#'); i >= 0 {
		p = p[:i]
	}
	if i := strings.IndexByte(p, '?'); i >= 0 {
		p, query = p[:i], p[i+1:]
	}
	decoded := havelUnquote(p)
	if strings.HasPrefix(decoded, "//") || strings.Contains(decoded, "\\") || havelHasControl(decoded) {
		return def
	}
	clean := path.Clean(p)
	if !strings.HasPrefix(clean, "/") || strings.HasPrefix(clean, "//") {
		return def
	}
	if query != "" {
		return clean + "?" + query
	}
	return clean
}
