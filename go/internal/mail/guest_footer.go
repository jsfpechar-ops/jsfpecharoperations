package mail

import "strings"

// HostDetails is host_details as a guest sees it in the footer (mail_notify.py).
type HostDetails struct {
	Name  string
	Seat  string
	Email string
	Phone string
}

// GuestFooterLink is one tappable channel in a guest footer line.
type GuestFooterLink struct {
	Label string
	Href  string
}

// guestFooterLines is _guest_footer_lines.
func guestFooterLines(lang, propertyName string, host HostDetails) []any {
	lines := []any{
		GuestText(lang, "mail_guest_footer_about", nil),
		GuestText(lang, "mail_guest_footer_why", Args{"property": propertyName}),
	}
	if host.Name != "" {
		lines = append(lines, GuestText(lang, "mail_guest_footer_host_label", nil)+": "+host.Name)
	}
	var contact []GuestFooterLink
	if host.Email != "" {
		contact = append(contact, GuestFooterLink{Label: host.Email, Href: "mailto:" + host.Email})
	}
	if host.Phone != "" {
		contact = append(contact, GuestFooterLink{
			Label: host.Phone,
			Href:  "tel:" + strings.ReplaceAll(host.Phone, " ", ""),
		})
	}
	if len(contact) > 0 {
		lines = append(lines, contact)
	}
	if host.Email != "" {
		lines = append(lines, GuestText(lang, "mail_guest_footer_help", nil))
	}
	return lines
}

// guestFooterText is _footer_text for a guest footer.
func guestFooterText(lines []any) []string {
	const sep = " \u00b7 "
	out := make([]string, 0, len(lines))
	for _, line := range lines {
		switch v := line.(type) {
		case []GuestFooterLink:
			labels := make([]string, 0, len(v))
			for _, l := range v {
				labels = append(labels, l.Label)
			}
			out = append(out, strings.Join(labels, sep))
		case string:
			out = append(out, v)
		}
	}
	return out
}

func guestFooterLineHTML(line any) string {
	const sep = " \u00b7 "
	switch v := line.(type) {
	case []GuestFooterLink:
		anchors := make([]string, 0, len(v))
		for _, l := range v {
			anchors = append(anchors, `<a href="`+esc(l.Href)+`" style="color:`+colInkSecondary+
				`;text-decoration:underline;">`+esc(l.Label)+`</a>`)
		}
		return strings.Join(anchors, sep)
	case string:
		return esc(v)
	}
	return ""
}
