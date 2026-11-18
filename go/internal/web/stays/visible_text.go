package stays

import (
	"html"
	"regexp"
	"sort"
	"strings"
)

var (
	visibleDrop = []*regexp.Regexp{
		regexp.MustCompile(`(?s)<!--.*?-->`),
		regexp.MustCompile(`(?is)<script\b.*?</script>`),
		regexp.MustCompile(`(?is)<style\b.*?</style>`),
		regexp.MustCompile(`(?is)<svg\b.*?</svg>`),
	}
	visibleToken = regexp.MustCompile(`<[^>]*>|[^<]+`)
	visibleTag   = regexp.MustCompile(`^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)`)
	visibleSpace = regexp.MustCompile(`[ \t\n\r\f\v]+`)
)

// staysVisibleLines extracts user-visible strings from the stays list body
// (head stays-head through stays-index-card). Keep in step with visible_lines()
// in App/scripts/go_stays_list_golden.py.
func staysVisibleLines(page string) []string {
	mark := `<div class="head stays-head"`
	start := strings.Index(page, mark)
	if start < 0 {
		return nil
	}
	if i := strings.Index(page[start:], `>`); i >= 0 {
		page = page[start+i+1:]
	} else {
		page = page[start:]
	}
	if end := strings.Index(page, `class="page-skeleton"`); end >= 0 {
		page = page[:end]
	} else if end := strings.LastIndex(page, `class="stays-index-card"`); end >= 0 {
		if close := strings.Index(page[end:], `</div>`); close >= 0 {
			page = page[:end+close+len(`</div>`)]
		}
	}
	for _, re := range visibleDrop {
		page = re.ReplaceAllString(page, "")
	}
	var out []string
	skip := false
	for _, tok := range visibleToken.FindAllString(page, -1) {
		if !strings.HasPrefix(tok, "<") {
			text := strings.Trim(visibleSpace.ReplaceAllString(html.UnescapeString(tok), " "), " ")
			if text != "" && !skip {
				out = append(out, text)
			}
			continue
		}
		m := visibleTag.FindStringSubmatch(tok)
		if m == nil {
			continue
		}
		name := strings.ToLower(m[2])
		if m[1] == "/" {
			if name == "a" {
				skip = false
			}
			continue
		}
		if strings.Contains(tok, `class="ui-ph-back"`) || strings.Contains(tok, `class="sr-only"`) {
			skip = true
		}
		if name == "a" && strings.Contains(tok, `ui-ph-back`) {
			skip = true
		}
	}
	return out
}

// rawI18nKeyInVisibleText finds untranslated catalog keys left in visible text.
// URLs and paths are ignored.
var rawI18nKeyRE = regexp.MustCompile(`(?:^|[\s"'>(])([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]+)+)`)

func rawI18nKeysInText(lines []string) []string {
	seen := map[string]bool{}
	var bad []string
	for _, line := range lines {
		for _, m := range rawI18nKeyRE.FindAllStringSubmatch(line, -1) {
			key := m[1]
			if strings.Contains(key, "://") || strings.HasPrefix(key, "www.") {
				continue
			}
			if strings.Contains(line, "http") && strings.Contains(line, key) {
				continue
			}
			// CSS classes and data attributes often contain dots; require two+ segments and a known prefix.
			if !strings.Contains(key, ".") {
				continue
			}
			prefix := key[:strings.Index(key, ".")]
			switch prefix {
			case "stays", "host", "flash", "status", "hint", "common", "send", "tabs", "csv", "demo", "how", "nav", "calendar", "setup", "onboarding", "confirm":
				if !seen[key] {
					seen[key] = true
					bad = append(bad, key)
				}
			}
		}
	}
	sort.Strings(bad)
	return bad
}
