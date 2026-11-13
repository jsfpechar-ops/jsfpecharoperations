// Sign-up mails, byte for byte as App/app/mail_notify.py renders them
// (brief 1281): build_signup_verify, build_signup_exists, build_signup_admin
// and _signup_footer, with _block_paragraph(size=15) and _shell(lang=...).
// The strings are copied from host_i18n.STRINGS (en, cs, vi) and the guest
// catalogue's mail_link_fallback; the golden test in go/internal/signup
// compares every byte with Python.
package mail

import "strings"

// authStrings holds the host_i18n keys these mails read, per language.
// signup_admin is always English (HOST_MAIL_LANGUAGE).
var authStrings = map[string]map[string]string{
	"en": {
		"mail.signup_verify.subject":     "Confirm your UbyHost account",
		"mail.signup_verify.heading":     "Confirm your e-mail address",
		"mail.signup_verify.intro":       "Thanks for signing up for UbyHost with the workspace “%(workspace)s”. Open the link below and press the button to activate the account.",
		"mail.signup_verify.action":      "Confirm e-mail",
		"mail.signup_verify.expiry":      "The link works for 24 hours. If you did not sign up, ignore this e-mail: the unconfirmed account is deleted after 7 days.",
		"mail.signup_exists.subject":     "Someone tried to create a UbyHost account with your e-mail",
		"mail.signup_exists.heading":     "You already have an account",
		"mail.signup_exists.intro":       "Someone, probably you, tried to create a new UbyHost account with this e-mail address. An account with this address already exists, so nothing was created.",
		"mail.signup_exists.action":      "Log in",
		"mail.signup_exists.help":        "Log in from the login page with this address: we e-mail you a link. If this was not you, you can ignore this e-mail.",
		"mail.workspace_deletion.footer": "Questions: %(support)s",
		"mail_link_fallback":             "If the button does not work, copy this address into your browser:",
		"mail.signup_admin.subject":      "New UbyHost sign-up: %(workspace)s",
		"mail.signup_admin.heading":      "New verified sign-up",
		"mail.signup_admin.intro":        "A new account was created and its e-mail address confirmed. The account is active now. If it should not be, disable it under Users.",
		"mail.signup_admin.action":       "Open Users",
		"mail.signup_admin.yes":          "yes",
		"mail.signup_admin.no":           "no",
		"mail.signup_admin.workspace":    "Workspace",
		"mail.signup_admin.email":        "E-mail",
		"mail.signup_admin.username":     "Username",
		"mail.signup_admin.source":       "Campaign",
		"mail.signup_admin.ads":          "Google Ads click",
		"mail.signup_admin.meta":         "Facebook/Instagram click (with consent)",
	},
	"cs": {
		"mail.signup_verify.subject":     "Potvrďte svůj účet UbyHost",
		"mail.signup_verify.heading":     "Potvrďte svou e-mailovou adresu",
		"mail.signup_verify.intro":       "Děkujeme za registraci do UbyHostu s pracovním prostorem „%(workspace)s“. Otevřete odkaz níže a stisknutím tlačítka účet aktivujte.",
		"mail.signup_verify.action":      "Potvrdit e-mail",
		"mail.signup_verify.expiry":      "Odkaz platí 24 hodin. Pokud jste se neregistrovali, e-mail ignorujte: nepotvrzený účet se po 7 dnech smaže.",
		"mail.signup_exists.subject":     "Někdo se pokusil založit účet UbyHost s vaším e-mailem",
		"mail.signup_exists.heading":     "Účet už máte",
		"mail.signup_exists.intro":       "Někdo, nejspíš vy, se pokusil založit nový účet UbyHost s touto e-mailovou adresou. Účet s touto adresou už existuje, takže se nic nového nezaložilo.",
		"mail.signup_exists.action":      "Přihlásit se",
		"mail.signup_exists.help":        "Přihlaste se touto adresou na přihlašovací stránce: pošleme vám odkaz. Pokud jste to nebyli vy, e-mail můžete ignorovat.",
		"mail.workspace_deletion.footer": "Dotazy: %(support)s",
		"mail_link_fallback":             "Pokud tlačítko nefunguje, zkopírujte tuto adresu do prohlížeče:",
	},
	"vi": {
		"mail.signup_verify.subject":     "Xác nhận tài khoản UbyHost của bạn",
		"mail.signup_verify.heading":     "Xác nhận địa chỉ e-mail",
		"mail.signup_verify.intro":       "Cảm ơn bạn đã đăng ký UbyHost với không gian làm việc “%(workspace)s”. Mở liên kết bên dưới và nhấn nút để kích hoạt tài khoản.",
		"mail.signup_verify.action":      "Xác nhận e-mail",
		"mail.signup_verify.expiry":      "Liên kết có hiệu lực trong 24 giờ. Nếu bạn không đăng ký, hãy bỏ qua e-mail này: tài khoản chưa xác nhận sẽ bị xóa sau 7 ngày.",
		"mail.signup_exists.subject":     "Có người đã thử tạo tài khoản UbyHost bằng e-mail của bạn",
		"mail.signup_exists.heading":     "Bạn đã có tài khoản",
		"mail.signup_exists.intro":       "Có người, có thể là bạn, đã thử tạo tài khoản UbyHost mới bằng địa chỉ e-mail này. Địa chỉ này đã có tài khoản nên không có gì được tạo.",
		"mail.signup_exists.action":      "Đăng nhập",
		"mail.signup_exists.help":        "Đăng nhập từ trang đăng nhập bằng địa chỉ này: chúng tôi sẽ gửi liên kết qua e-mail. Nếu không phải bạn, hãy bỏ qua e-mail này.",
		"mail.workspace_deletion.footer": "Thắc mắc: %(support)s",
		"mail_link_fallback":             "If the button does not work, copy this address into your browser:",
	},
}

// authLanguage is host_i18n.normalise_language: the first two letters,
// lower-cased, if the app speaks that language, else en.
func authLanguage(lang string) string {
	code := []rune(strings.ToLower(lang))
	if len(code) > 2 {
		code = code[:2]
	}
	if _, ok := authStrings[string(code)]; ok {
		return string(code)
	}
	return "en"
}

// authText is host_i18n.translate for an already normalised language. pairs
// are the %(name)s values; %% becomes % only when values are given, as
// Python's "text % kwargs" does.
func authText(lang, key string, pairs ...string) string {
	text, ok := authStrings[lang][key]
	if !ok {
		text = authStrings["en"][key]
	}
	if len(pairs) == 0 {
		return text
	}
	return strings.NewReplacer(append(pairs, "%%", "%")...).Replace(text)
}

// authParagraph15 is _block_paragraph(text, size=15).
func authParagraph15(text string) string {
	return `<tr><td style="padding:12px 24px 0 24px;"><p style="margin:0;font:400 15px/1.6 ` +
		fontStack + `;color:` + colInkSecondary + `;">` + esc(text) + `</p></td></tr>`
}

// authShell is _shell with the page language set (shell writes lang="en").
func authShell(publicBaseURL, lang, title, preheader string, blocks, footer []string) string {
	page := shell(publicBaseURL, title, preheader, blocks, footer)
	return strings.Replace(page, `<html lang="en">`, `<html lang="`+esc(lang)+`">`, 1)
}

// authFooter is _signup_footer.
func authFooter(lang, operatorEmail string) []string {
	return []string{"UbyHost", authText(lang, "mail.workspace_deletion.footer", "%(support)s", operatorEmail)}
}

// BuildSignupVerify is build_signup_verify. link is the verify URL with the
// claim-secret marker standing in for the token.
func BuildSignupVerify(publicBaseURL, operatorEmail, lang, workspace, username, link string) Content {
	lang = authLanguage(lang)
	subject := authText(lang, "mail.signup_verify.subject")
	heading := authText(lang, "mail.signup_verify.heading")
	intro := authText(lang, "mail.signup_verify.intro", "%(workspace)s", workspace)
	action := authText(lang, "mail.signup_verify.action")
	expiry := authText(lang, "mail.signup_verify.expiry")
	fallback := authText(lang, "mail_link_fallback")
	footer := authFooter(lang, operatorEmail)
	text := strings.Join(append([]string{intro, "", action + ": " + link, "", expiry, "", "--"}, footer...), "\n")
	blocks := []string{
		blockHeading(heading),
		blockParagraph(intro, false),
		blockButton(link, action),
		authParagraph15(expiry),
		blockLink(link, fallback),
	}
	return Content{Subject: subject, Text: text, HTML: authShell(publicBaseURL, lang, heading, intro, blocks, footer)}
}

// BuildSignupExists is build_signup_exists: the "you already have an
// account" notice, with a button to the login page.
func BuildSignupExists(publicBaseURL, appBaseURL, operatorEmail, lang string) Content {
	lang = authLanguage(lang)
	subject := authText(lang, "mail.signup_exists.subject")
	heading := authText(lang, "mail.signup_exists.heading")
	intro := authText(lang, "mail.signup_exists.intro")
	action := authText(lang, "mail.signup_exists.action")
	help := authText(lang, "mail.signup_exists.help", "%(support)s", operatorEmail)
	link := appBaseURL + "/login?lang=" + lang
	footer := authFooter(lang, operatorEmail)
	text := strings.Join(append([]string{intro, "", action + ": " + link, "", help, "", "--"}, footer...), "\n")
	blocks := []string{
		blockHeading(heading),
		blockParagraph(intro, false),
		blockButton(link, action),
		authParagraph15(help),
	}
	return Content{Subject: subject, Text: text, HTML: authShell(publicBaseURL, lang, heading, intro, blocks, footer)}
}

// BuildSignupAdmin is build_signup_admin: the operator's notice of a
// verified sign-up, always in English.
func BuildSignupAdmin(publicBaseURL, appBaseURL, operatorEmail, workspace, email, username, campaign string, adsClick, metaClick bool) Content {
	lang := "en"
	yesNo := func(v bool) string {
		if v {
			return authText(lang, "mail.signup_admin.yes")
		}
		return authText(lang, "mail.signup_admin.no")
	}
	subject := authText(lang, "mail.signup_admin.subject", "%(workspace)s", workspace)
	heading := authText(lang, "mail.signup_admin.heading")
	intro := authText(lang, "mail.signup_admin.intro")
	action := authText(lang, "mail.signup_admin.action")
	link := appBaseURL + "/admin/users"
	if campaign == "" {
		campaign = "-"
	}
	facts := [][2]string{
		{authText(lang, "mail.signup_admin.workspace"), workspace},
		{authText(lang, "mail.signup_admin.email"), email},
		{authText(lang, "mail.signup_admin.username"), username},
		{authText(lang, "mail.signup_admin.source"), campaign},
		{authText(lang, "mail.signup_admin.ads"), yesNo(adsClick)},
		{authText(lang, "mail.signup_admin.meta"), yesNo(metaClick)},
	}
	footer := authFooter(lang, operatorEmail)
	lines := []string{intro, ""}
	blocks := []string{blockHeading(heading), blockParagraph(intro, false)}
	for _, f := range facts {
		lines = append(lines, f[0]+": "+f[1])
		blocks = append(blocks, blockFact(f[0], f[1]))
	}
	lines = append(lines, "", action+": "+link, "", "--")
	blocks = append(blocks, blockButton(link, action))
	text := strings.Join(append(lines, footer...), "\n")
	return Content{Subject: subject, Text: text, HTML: authShell(publicBaseURL, lang, heading, intro, blocks, footer)}
}
