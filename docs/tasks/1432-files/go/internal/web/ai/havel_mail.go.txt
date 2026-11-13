package ai

// havel_mail.go: the support mail Havel sends to UbyHost, the port of
// mail_notify.build_havel_support and mail_notify.havel_support (lines
// 2972-3014). The markup is the shell of go/internal/mail/submission_problem.go
// (mail_notify._shell), copied here because that package keeps it private.
//
// The mail carries what the host typed into the support form and the host's
// last four messages, so the operator can answer. It is queued in email_outbox
// and sent by the mail job; nothing is sent from the request.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	havelColInk          = "#20201e"
	havelColInkSecondary = "#50504c"
	havelColInkMuted     = "#73736e"
	havelColCanvas       = "#f7f7f5"
	havelColSurface      = "#ffffff"
	havelColLine         = "#e4e4e1"
	havelFontStack       = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
	havelLogoPath        = "/static/ubyhost-logo.jpg"
	havelLogoWidth       = 180
)

var havelPreheaderSpacer = strings.Repeat("\u2007\ufeff\u034f", 40)

var havelEscaper = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&quot;", "'", "&#x27;")

// havelEsc is Python's html.escape(quote=True).
func havelEsc(s string) string { return havelEscaper.Replace(s) }

func havelBlockHeading(text string) string {
	return `<tr><td style="padding:20px 24px 0 24px;"><h1 style="margin:0;font:600 22px/1.3 ` +
		havelFontStack + `;color:` + havelColInk + `;">` + havelEsc(text) + `</h1></td></tr>`
}

func havelBlockParagraph(text string) string {
	return `<tr><td style="padding:12px 24px 0 24px;"><p style="margin:0;font:400 16px/1.6 ` +
		havelFontStack + `;color:` + havelColInkSecondary + `;">` + havelEsc(text) + `</p></td></tr>`
}

func havelBlockFact(label, value string) string {
	return `<tr><td style="padding:20px 24px 0 24px;"><div style="font:600 14px/1.4 ` + havelFontStack +
		`;color:` + havelColInk + `;padding:0 0 6px 0;">` + havelEsc(label) + `</div>` +
		`<div style="font:400 15px/1.5 ` + havelFontStack + `;color:` + havelColInk + `;">` + havelEsc(value) + `</div>` +
		`</td></tr>`
}

// havelMailShell is mail_notify._shell for plain footer lines.
func havelMailShell(publicBaseURL, pageTitle, preheader string, blocks, footerLines []string) string {
	var footerHTML strings.Builder
	for i, line := range footerLines {
		if i > 0 {
			footerHTML.WriteString(`<div style="padding:4px 0 0 0;">` + havelEsc(line) + `</div>`)
		} else {
			footerHTML.WriteString(`<div>` + havelEsc(line) + `</div>`)
		}
	}
	preheaderHTML := ""
	if preheader != "" {
		preheaderHTML = `<div style="display:none;font-size:1px;line-height:1px;max-height:0;` +
			`max-width:0;opacity:0;overflow:hidden;mso-hide:all;">` + havelEsc(preheader) + havelPreheaderSpacer + `</div>`
	}
	logoURL := publicBaseURL + havelLogoPath
	width := strconv.Itoa(havelLogoWidth)
	return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only">
<title>` + havelEsc(pageTitle) + `</title>
</head>
<body style="margin:0;padding:0;background:` + havelColCanvas + `;">
` + preheaderHTML + `
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:` + havelColCanvas + `;border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:` + havelColSurface + `;border:1px solid ` + havelColLine + `;border-radius:14px;border-collapse:separate;">
<tr><td style="padding:28px 24px 0 24px;">
<img src="` + havelEsc(logoURL) + `" width="` + width + `" alt="UbyHost" style="display:block;border:0;outline:none;text-decoration:none;width:` + width + `px;max-width:100%;height:auto;">
</td></tr>
` + strings.Join(blocks, "") + `
<tr><td style="padding:28px 24px 28px 24px;">
<div style="border-top:1px solid ` + havelColLine + `;padding:16px 0 0 0;font:400 13px/1.6 ` + havelFontStack + `;color:` + havelColInkMuted + `;">
` + footerHTML.String() + `
</div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
`
}

// HavelSupportInput is what havel_support is given.
type HavelSupportInput struct {
	UserID       int64
	AccountEmail string
	Workspace    string
	Lang         string
	Page         string
	Summary      string
	Note         string
	Turns        []string
}

// havelOperatorEmail is config.OPERATOR_EMAIL.
func havelOperatorEmail(env HavelEnv) string {
	if v := strings.TrimSpace(env.Get("UBYHOST_OPERATOR_EMAIL", "")); v != "" {
		return v
	}
	return "support@ubyhost.com"
}

func havelOneLine(s string) string { return strings.Join(havelFields(s), " ") }

// HavelBuildSupportMail is mail_notify.build_havel_support. The mail is in
// English (HOST_MAIL_LANGUAGE): the operator reads it.
func HavelBuildSupportMail(env HavelEnv, in HavelSupportInput) (subject, text, html string) {
	t := func(key string, params map[string]any) string { return havelCatalog.T("en", key, params) }
	name := in.Workspace
	if name == "" {
		name = in.AccountEmail
	}
	subject = t("mail.havel_support.subject", map[string]any{"workspace": havelClip(havelOneLine(name), 80)})
	heading := t("mail.havel_support.heading", nil)
	intro := t("mail.havel_support.intro", nil)
	dash := func(s string) string {
		if s == "" {
			return "-"
		}
		return s
	}
	type fact struct{ label, value string }
	facts := []fact{
		{t("mail.havel_support.account", nil), dash(in.AccountEmail)},
		{t("mail.havel_support.workspace", nil), dash(in.Workspace)},
		{t("mail.havel_support.language", nil), in.Lang},
		{t("mail.havel_support.page", nil), dash(in.Page)},
		{t("mail.havel_support.summary", nil), dash(in.Summary)},
		{t("mail.havel_support.note", nil), dash(in.Note)},
	}
	for i, turn := range in.Turns {
		facts = append(facts, fact{t("mail.havel_support.turn", map[string]any{"n": i + 1}), turn})
	}
	footer := []string{"UbyHost", t("mail.workspace_deletion.footer", map[string]any{"support": havelOperatorEmail(env)})}
	lines := []string{intro, ""}
	for _, f := range facts {
		lines = append(lines, f.label+": "+f.value)
	}
	lines = append(lines, "", "--")
	lines = append(lines, footer...)
	text = strings.Join(lines, "\n")
	blocks := []string{havelBlockHeading(heading), havelBlockParagraph(intro)}
	for _, f := range facts {
		blocks = append(blocks, havelBlockFact(f.label, f.value))
	}
	html = havelMailShell(hostweb.PublicBase(env.Getenv), heading, intro, blocks, footer)
	return subject, text, html
}

// havelMailOn is mail.mail_enabled: the backend is console or ses.
func havelMailOn(env HavelEnv) bool {
	switch strings.ToLower(strings.TrimSpace(env.Get("UBYHOST_MAIL_BACKEND", ""))) {
	case "console", "ses":
		return true
	}
	return false
}

// HavelSupportKey is the idempotency key of mail_notify.havel_support: the
// same text twice in one ISO week is one mail.
func HavelSupportKey(userID int64, summary, note string, at time.Time) string {
	sum := sha256.Sum256([]byte(summary + "\n" + note))
	year, week := at.ISOWeek()
	return fmt.Sprintf("havel-support-%d-%d-%02d-%s", userID, year, week, hex.EncodeToString(sum[:])[:16])
}

// EnqueueSupport is mail_notify.havel_support: the mail to the operator goes
// into email_outbox (kind havel_support). It reports whether a row exists; mail
// switched off or an address that does not normalise queue nothing.
func (s HavelStore) EnqueueSupport(ctx context.Context, in HavelSupportInput, at time.Time) (bool, error) {
	subject, text, html := HavelBuildSupportMail(s.Env, in)
	if !havelMailOn(s.Env) {
		return false, nil
	}
	to := ubyport.NormaliseEmail(havelOperatorEmail(s.Env))
	if to == "" {
		return false, nil
	}
	payload := `{"text": ` + ubyport.PyString(text) + `, "html": ` + ubyport.PyString(html) + `, "lang": "en"}`
	id, err := ubyport.EnqueueMail(ctx, s.Pool, ubyport.OutboxMail{
		Kind: "havel_support", Key: HavelSupportKey(in.UserID, in.Summary, in.Note, at), To: to, Subject: subject, Payload: payload,
	})
	return id != 0, err
}
