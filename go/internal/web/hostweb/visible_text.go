package hostweb

import (
	"html"
	"regexp"
	"sort"
	"strings"
)

var (
	dashDrop = []*regexp.Regexp{
		regexp.MustCompile(`(?s)<!--.*?-->`),
		regexp.MustCompile(`(?is)<script\b.*?</script>`),
		regexp.MustCompile(`(?is)<style\b.*?</style>`),
		regexp.MustCompile(`(?is)<svg\b.*?</svg>`),
	}
	dashToken = regexp.MustCompile(`<[^>]*>|[^<]+`)
	dashTag   = regexp.MustCompile(`^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)`)
	dashAttr  = regexp.MustCompile(`(?i)([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?`)
	dashSpace = regexp.MustCompile(`[ \t\n\r\f\v]+`)
	dashKept  = map[string]bool{
		"id": true, "href": true, "action": true, "method": true, "name": true, "value": true,
		"type": true, "aria-current": true, "class": true, "aria-label": true,
	}
)

// DashboardVisibleLines is visible_lines in App/scripts/go_dashboard_golden.py.
func DashboardVisibleLines(page string) []string {
	start := strings.Index(page, `<div class="ui-page"`)
	if start < 0 {
		start = strings.Index(page, `<main id="content"`)
	}
	if start < 0 {
		return nil
	}
	page = page[start:]
	if end := strings.Index(page, `<div class="page-skeleton"`); end >= 0 {
		page = page[:end]
	}
	for _, re := range dashDrop {
		page = re.ReplaceAllString(page, "")
	}
	var out []string
	for _, tok := range dashToken.FindAllString(page, -1) {
		if !strings.HasPrefix(tok, "<") {
			text := strings.Trim(dashSpace.ReplaceAllString(html.UnescapeString(tok), " "), " ")
			if text != "" {
				out = append(out, text)
			}
			continue
		}
		m := dashTag.FindStringSubmatch(tok)
		if m == nil || m[1] == "/" {
			continue
		}
		name := strings.ToLower(m[2])
		attrs := map[string]struct {
			has bool
			val string
		}{}
		for _, a := range dashAttr.FindAllStringSubmatch(tok, -1) {
			key := strings.ToLower(a[1])
			has := strings.Contains(a[0], "=")
			val := html.UnescapeString(a[2] + a[3] + a[4])
			if key == "class" {
				val = strings.Join(strings.Fields(val), " ")
			}
			attrs[key] = struct {
				has bool
				val string
			}{has, val}
		}
		if attrs["name"].val == "_csrf" {
			attrs["value"] = struct {
				has bool
				val string
			}{true, "*"}
		}
		var keys []string
		for k := range attrs {
			if dashKept[k] {
				keys = append(keys, k)
			}
		}
		sort.Strings(keys)
		var parts []string
		for _, k := range keys {
			a := attrs[k]
			if a.has {
				parts = append(parts, k+"="+a.val)
			} else {
				parts = append(parts, k)
			}
		}
		if len(parts) > 0 {
			out = append(out, "<"+name+" "+strings.Join(parts, " ")+">")
		}
	}
	return out
}
