package mailnotify

import (
	"strings"
)

// ClaimInput is the localized content for a claim link sent to a guest.
type ClaimInput struct {
	Lang, PropertyName, Dates, Link string
	Resend, StayComplete            bool
	Host                            *Host
}

// BuildClaim is the Go port of mail_notify.build_claim_link.
func BuildClaim(publicBaseURL string, in ClaimInput) Content {
	lang := GuestLanguage(in.Lang)
	resendKey := ""
	if in.Resend {
		resendKey = "_resend"
	}
	subject := claimText(lang, "mail_claim"+resendKey+"_subject", Args{"property": in.PropertyName})
	intro := claimText(lang, "mail_claim_intro", Args{"property": in.PropertyName, "dates": in.Dates})
	action := claimText(lang, "mail_claim_action", nil)
	expiry := claimText(lang, "mail_claim_expiry"+resendKey, nil)
	nextLabel := claimText(lang, "mail_claim_next_label", nil)
	nextKey := "mail_claim_next_body"
	if in.StayComplete {
		nextKey = "mail_claim_next_done"
	}
	nextBody := claimText(lang, nextKey, nil)
	fallback := claimText(lang, "mail_link_fallback", nil)
	preheader := claimText(lang, "mail_claim"+resendKey+"_preheader", nil)
	heading := claimText(lang, "mail_claim"+resendKey+"_heading", nil)
	footer := GuestFooterLines(lang, in.PropertyName, in.Host)
	textLines := []string{intro, "", action + ": " + in.Link, "", expiry, "", nextLabel + ": " + nextBody, "", "--"}
	textLines = append(textLines, FooterText(footer)...)
	blocks := []string{BlockHeading(heading), BlockParagraph(intro, false), BlockButton(in.Link, action), BlockParagraphSized(expiry, true, 15), BlockLink(in.Link, fallback), BlockSection(nextLabel, nextBody)}
	return Content{Subject: subject, Text: strings.Join(textLines, "\n"), HTML: Shell(ShellParams{PublicBaseURL: strings.TrimRight(publicBaseURL, "/"), Lang: lang, Title: in.PropertyName, Preheader: preheader, Blocks: blocks, FooterLines: footer})}
}
