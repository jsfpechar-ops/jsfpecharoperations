package submissions

import (
	"html"
	"regexp"
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

// submissionsVisibleLines extracts user-visible strings from the submissions
// list body (head stays-head through the list or empty state). Keep in step
// with visible_lines() in App/scripts/go_go_submissions_reservations_read_golden.py.
func submissionsVisibleLines(page string) []string {
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
		if strings.Contains(tok, `class="sr-only"`) || strings.Contains(tok, `ui-ph-back`) {
			skip = true
		}
	}
	return out
}

// submissionDetailVisibleLines extracts visible text from the report detail
// body (e-page through the guest table). Same contract as the golden script.
func submissionDetailVisibleLines(page string) []string {
	mark := `<div class="e-page"`
	start := strings.Index(page, mark)
	if start < 0 {
		return nil
	}
	page = page[start:]
	if end := strings.Index(page, `class="page-skeleton"`); end >= 0 {
		page = page[:end]
	}
	if end := strings.Index(page, `<details class="panel technical"`); end >= 0 {
		page = page[:end]
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
		if strings.Contains(tok, `class="sr-only"`) {
			skip = true
		}
	}
	return out
}

// stayDetailHeadLines is the visible slice of GET /reservations/{id} used by
// the golden script (stay detail is already on main; this only pins extraction).
func stayDetailHeadLines(page string) []string {
	mark := `<div class="e-page"`
	start := strings.Index(page, mark)
	if start < 0 {
		return nil
	}
	page = page[start:]
	if end := strings.Index(page, `id="guests"`); end >= 0 {
		page = page[:end]
	}
	for _, re := range visibleDrop {
		page = re.ReplaceAllString(page, "")
	}
	var out []string
	for _, tok := range visibleToken.FindAllString(page, -1) {
		if strings.HasPrefix(tok, "<") {
			continue
		}
		text := strings.Trim(visibleSpace.ReplaceAllString(html.UnescapeString(tok), " "), " ")
		if text != "" {
			out = append(out, text)
		}
	}
	return out
}
