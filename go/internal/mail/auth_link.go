// Account mails of App/app/mail_notify.py, byte for byte (brief 1501):
// build_link_mail (login link, invitation, e-mail confirmation),
// build_email_changed, build_passkey_added and build_workspace_deletion, with
// _block_paragraph(size=15), _shell(lang=...) and _signup_footer as
// auth_signup.go has them. The strings are copied from host_i18n.STRINGS by
// App/scripts/auth_shared_golden.py's check; the golden test in this package
// compares every byte with Python. The queue side is auth_queue.go.
package mail

import (
	"errors"
	"strconv"
	"strings"
)

// Link mail kinds (mail_notify.LINK_MAIL) and the path each link opens.
const (
	KindLoginLink     = "login_link"
	KindAccountInvite = "account_invite"
	KindEmailConfirm  = "email_confirm"
)

var linkMail = map[string][2]string{
	KindLoginLink:     {"mail.login_link", "/login/link"},
	KindAccountInvite: {"mail.account_invite", "/login/link"},
	KindEmailConfirm:  {"mail.email_confirm", "/account/email/confirm"},
}

// Workspace deletion stages (mail_notify.WORKSPACE_DELETION_STAGES).
const (
	DeletionScheduled  = "scheduled"
	DeletionWeekBefore = "week_before"
)

// ErrUnknownMail is the ValueError of the builders: an unknown link kind,
// e-mail-changed side or deletion stage.
var ErrUnknownMail = errors.New("mail: unknown account mail variant")

// accountStrings holds the host_i18n keys these mails read, per language.
// mail.workspace_deletion.footer and mail_link_fallback are in authStrings.
var accountStrings = map[string]map[string]string{
	"en": {
		"mail.account_invite.action":                  "Log in for the first time",
		"mail.account_invite.heading":                 "Welcome to UbyHost",
		"mail.account_invite.intro":                   "A UbyHost account was created for this e-mail address. You log in with links sent here, so there is no password to remember.",
		"mail.account_invite.subject":                 "Your UbyHost account is ready",
		"mail.email_changed.heading":                  "Login e-mail changed",
		"mail.email_changed.help_new":                 "Log in from the UbyHost login page with this address. If you did not expect this, write to %(support)s.",
		"mail.email_changed.help_old":                 "If you did not ask for this, write to %(support)s straight away.",
		"mail.email_changed.intro_new":                "This address is now the login e-mail of a UbyHost account.",
		"mail.email_changed.intro_old":                "UbyHost support changed the login e-mail of your account to %(address)s. This address no longer logs in.",
		"mail.email_changed.intro_old_self":           "The login e-mail of your UbyHost account was changed to %(address)s. This address no longer logs in.",
		"mail.email_changed.subject":                  "Your UbyHost login e-mail changed",
		"mail.email_confirm.action":                   "Confirm this address",
		"mail.email_confirm.heading":                  "Confirm your new login e-mail",
		"mail.email_confirm.intro":                    "You asked to log in to UbyHost with this address from now on.",
		"mail.email_confirm.subject":                  "Confirm your new UbyHost login e-mail",
		"mail.link.expiry_hours":                      "The link works once, for %(hours)s hours.",
		"mail.link.expiry_minutes":                    "The link works once, for %(minutes)s minutes.",
		"mail.link.ignore":                            "If you did not ask for this, ignore this e-mail: nothing happens without the link. Questions: %(support)s.",
		"mail.login_link.action":                      "Log in",
		"mail.login_link.heading":                     "Log in to UbyHost",
		"mail.login_link.intro":                       "Someone asked to log in to UbyHost with this e-mail address.",
		"mail.login_link.subject":                     "Your UbyHost login link",
		"mail.passkey_added.heading":                  "New passkey",
		"mail.passkey_added.help":                     "If this was not you, log in with the e-mail link, remove it in Settings → Security, and write to %(support)s.",
		"mail.passkey_added.intro":                    "A passkey named “%(name)s” can now log in to your UbyHost account.",
		"mail.passkey_added.subject":                  "A passkey was added to your UbyHost account",
		"mail.workspace_deletion.heading":             "Account deletion on %(date)s",
		"mail.workspace_deletion.intro_scheduled":     "Deletion of your UbyHost account is scheduled for %(date)s. Until then you can still sign in and download everything as a ZIP from the banner at the top of the app. On %(date)s every property, stay, guest record, invoice and stay-fee filing in the account will be permanently deleted.",
		"mail.workspace_deletion.intro_week_before":   "This is a reminder: on %(date)s every property, stay, guest record, invoice and stay-fee filing in your UbyHost account will be permanently deleted.",
		"mail.workspace_deletion.keep":                "Czech law may require you to keep invoices, stay-fee filings and police receipts for several years. That duty stays with you after the account is gone. Download your export from the app before %(date)s, or write to %(support)s if you need help.",
		"mail.workspace_deletion.keep_label":          "Records you must keep",
		"mail.workspace_deletion.subject_scheduled":   "Your UbyHost account will be deleted on %(date)s",
		"mail.workspace_deletion.subject_week_before": "Your UbyHost account will be deleted in 7 days (%(date)s)",
	},
	"cs": {
		"mail.account_invite.action":                  "Poprvé se přihlásit",
		"mail.account_invite.heading":                 "Vítejte v UbyHostu",
		"mail.account_invite.intro":                   "Pro tuto e-mailovou adresu vznikl účet v UbyHostu. Přihlašujete se odkazy zaslanými sem, takže si nemusíte pamatovat heslo.",
		"mail.account_invite.subject":                 "Váš účet v UbyHostu je připravený",
		"mail.email_changed.heading":                  "Přihlašovací e-mail změněn",
		"mail.email_changed.help_new":                 "Přihlaste se touto adresou na přihlašovací stránce UbyHostu. Pokud jste to nečekali, napište na %(support)s.",
		"mail.email_changed.help_old":                 "Pokud jste o změnu nežádali, napište hned na %(support)s.",
		"mail.email_changed.intro_new":                "Tato adresa je nyní přihlašovacím e-mailem účtu v UbyHostu.",
		"mail.email_changed.intro_old":                "Podpora UbyHostu změnila přihlašovací e-mail vašeho účtu na %(address)s. Tato adresa už k přihlášení neslouží.",
		"mail.email_changed.intro_old_self":           "Přihlašovací e-mail vašeho účtu v UbyHostu se změnil na %(address)s. Tato adresa už k přihlášení neslouží.",
		"mail.email_changed.subject":                  "Přihlašovací e-mail k UbyHostu se změnil",
		"mail.email_confirm.action":                   "Potvrdit tuto adresu",
		"mail.email_confirm.heading":                  "Potvrďte nový přihlašovací e-mail",
		"mail.email_confirm.intro":                    "Požádali jste, abyste se do UbyHostu odteď přihlašovali touto adresou.",
		"mail.email_confirm.subject":                  "Potvrďte nový přihlašovací e-mail do UbyHostu",
		"mail.link.expiry_hours":                      "Odkaz platí jednou, %(hours)s hodin.",
		"mail.link.expiry_minutes":                    "Odkaz platí jednou, %(minutes)s minut.",
		"mail.link.ignore":                            "Pokud jste o nic nežádali, e-mail ignorujte: bez odkazu se nic nestane. Dotazy: %(support)s.",
		"mail.login_link.action":                      "Přihlásit se",
		"mail.login_link.heading":                     "Přihlášení do UbyHostu",
		"mail.login_link.intro":                       "Někdo požádal o přihlášení do UbyHostu touto e-mailovou adresou.",
		"mail.login_link.subject":                     "Váš přihlašovací odkaz do UbyHostu",
		"mail.passkey_added.heading":                  "Nový přístupový klíč",
		"mail.passkey_added.help":                     "Pokud jste to nebyli vy, přihlaste se odkazem z e-mailu, klíč odeberte v Nastavení → Zabezpečení a napište na %(support)s.",
		"mail.passkey_added.intro":                    "Klíčem „%(name)s“ se teď lze přihlásit k vašemu účtu UbyHost.",
		"mail.passkey_added.subject":                  "K vašemu účtu UbyHost byl přidán přístupový klíč",
		"mail.workspace_deletion.heading":             "Smazání účtu %(date)s",
		"mail.workspace_deletion.intro_scheduled":     "Smazání vašeho účtu UbyHost je naplánováno na %(date)s. Do té doby se můžete přihlásit a vše stáhnout jako ZIP z banneru v horní části aplikace. Dne %(date)s budou z účtu trvale smazány všechny nemovitosti, pobyty, údaje hostů, faktury i přiznání k poplatku z pobytu.",
		"mail.workspace_deletion.intro_week_before":   "Připomínáme, že dne %(date)s budou z vašeho účtu UbyHost trvale smazány všechny nemovitosti, pobyty, údaje hostů, faktury i přiznání k poplatku z pobytu.",
		"mail.workspace_deletion.keep":                "Faktury, přiznání k poplatku z pobytu a doručenky z policie můžete být podle zákona povinni uchovávat několik let. Tato povinnost zůstává na vás i po smazání účtu. Export si stáhněte v aplikaci do %(date)s, nebo napište na %(support)s, pokud potřebujete pomoc.",
		"mail.workspace_deletion.keep_label":          "Doklady, které musíte uchovat",
		"mail.workspace_deletion.subject_scheduled":   "Váš účet UbyHost bude %(date)s smazán",
		"mail.workspace_deletion.subject_week_before": "Váš účet UbyHost bude za 7 dní smazán (%(date)s)",
	},
	"vi": {
		"mail.account_invite.action":                  "Đăng nhập lần đầu",
		"mail.account_invite.heading":                 "Chào mừng đến với UbyHost",
		"mail.account_invite.intro":                   "Một tài khoản UbyHost đã được tạo cho địa chỉ e-mail này. Bạn đăng nhập bằng liên kết gửi đến đây, nên không cần nhớ mật khẩu.",
		"mail.account_invite.subject":                 "Tài khoản UbyHost của bạn đã sẵn sàng",
		"mail.email_changed.heading":                  "Đã đổi e-mail đăng nhập",
		"mail.email_changed.help_new":                 "Đăng nhập từ trang đăng nhập UbyHost bằng địa chỉ này. Nếu bạn không mong đợi việc này, hãy viết cho %(support)s.",
		"mail.email_changed.help_old":                 "Nếu bạn không yêu cầu việc này, hãy viết ngay cho %(support)s.",
		"mail.email_changed.intro_new":                "Địa chỉ này giờ là e-mail đăng nhập của một tài khoản UbyHost.",
		"mail.email_changed.intro_old":                "Bộ phận hỗ trợ UbyHost đã đổi e-mail đăng nhập của tài khoản bạn thành %(address)s. Địa chỉ này không còn dùng để đăng nhập.",
		"mail.email_changed.intro_old_self":           "E-mail đăng nhập của tài khoản UbyHost của bạn đã được đổi thành %(address)s. Địa chỉ này không còn dùng để đăng nhập.",
		"mail.email_changed.subject":                  "E-mail đăng nhập UbyHost của bạn đã thay đổi",
		"mail.email_confirm.action":                   "Xác nhận địa chỉ này",
		"mail.email_confirm.heading":                  "Xác nhận e-mail đăng nhập mới",
		"mail.email_confirm.intro":                    "Bạn đã yêu cầu từ nay đăng nhập UbyHost bằng địa chỉ này.",
		"mail.email_confirm.subject":                  "Xác nhận e-mail đăng nhập UbyHost mới",
		"mail.link.expiry_hours":                      "Liên kết dùng được một lần, trong %(hours)s giờ.",
		"mail.link.expiry_minutes":                    "Liên kết dùng được một lần, trong %(minutes)s phút.",
		"mail.link.ignore":                            "Nếu bạn không yêu cầu, hãy bỏ qua e-mail này: không có gì xảy ra nếu không mở liên kết. Câu hỏi: %(support)s.",
		"mail.login_link.action":                      "Đăng nhập",
		"mail.login_link.heading":                     "Đăng nhập UbyHost",
		"mail.login_link.intro":                       "Có người yêu cầu đăng nhập UbyHost bằng địa chỉ e-mail này.",
		"mail.login_link.subject":                     "Liên kết đăng nhập UbyHost của bạn",
		"mail.passkey_added.heading":                  "Passkey mới",
		"mail.passkey_added.help":                     "Nếu không phải bạn, hãy đăng nhập bằng liên kết e-mail, xóa passkey trong Cài đặt → Bảo mật, và viết cho %(support)s.",
		"mail.passkey_added.intro":                    "Passkey tên “%(name)s” giờ có thể đăng nhập vào tài khoản UbyHost của bạn.",
		"mail.passkey_added.subject":                  "Một passkey đã được thêm vào tài khoản UbyHost của bạn",
		"mail.workspace_deletion.heading":             "Xóa tài khoản vào ngày %(date)s",
		"mail.workspace_deletion.intro_scheduled":     "Tài khoản UbyHost của bạn đã được lên lịch xóa vào ngày %(date)s. Trước đó, bạn vẫn đăng nhập được và tải toàn bộ dữ liệu dưới dạng ZIP từ thanh thông báo ở đầu ứng dụng. Vào ngày %(date)s, mọi chỗ ở, lượt lưu trú, hồ sơ khách, hóa đơn và hồ sơ phí lưu trú trong tài khoản sẽ bị xóa vĩnh viễn.",
		"mail.workspace_deletion.intro_week_before":   "Xin nhắc lại: vào ngày %(date)s, mọi chỗ ở, lượt lưu trú, hồ sơ khách, hóa đơn và hồ sơ phí lưu trú trong tài khoản UbyHost của bạn sẽ bị xóa vĩnh viễn.",
		"mail.workspace_deletion.keep":                "Luật Séc có thể yêu cầu bạn lưu hóa đơn, hồ sơ phí lưu trú và biên nhận khai báo cảnh sát trong nhiều năm. Nghĩa vụ đó vẫn thuộc về bạn sau khi tài khoản bị xóa. Hãy tải bản xuất từ ứng dụng trước ngày %(date)s, hoặc viết cho %(support)s nếu cần hỗ trợ.",
		"mail.workspace_deletion.keep_label":          "Hồ sơ bạn phải lưu giữ",
		"mail.workspace_deletion.subject_scheduled":   "Tài khoản UbyHost của bạn sẽ bị xóa vào ngày %(date)s",
		"mail.workspace_deletion.subject_week_before": "Tài khoản UbyHost của bạn sẽ bị xóa sau 7 ngày (%(date)s)",
	},
}

// accountText is host_i18n.translate for an already normalised language:
// accountStrings first (a missing language falls back to English), then
// authStrings. pairs are the %(name)s values; %% becomes % only when values
// are given, as Python's "text % kwargs" does, and a value is never read as
// a placeholder again.
func accountText(lang, key string, pairs ...string) string {
	if _, ok := accountStrings["en"][key]; !ok {
		return authText(lang, key, pairs...)
	}
	text, ok := accountStrings[lang][key]
	if !ok {
		text = accountStrings["en"][key]
	}
	if len(pairs) == 0 {
		return text
	}
	return strings.NewReplacer(append(pairs, "%%", "%")...).Replace(text)
}

// BuildLinkMail is build_link_mail: the mail whose one job is a link that
// logs in (login_link, account_invite) or confirms an address
// (email_confirm). link is the full URL with the claim-secret marker
// standing in for the token; minutes is how long it works (120 or more is
// said in whole hours). lang "" means English (HOST_MAIL_LANGUAGE).
func BuildLinkMail(publicBaseURL, operatorEmail, kind, link string, minutes int, lang string) (Content, error) {
	spec, ok := linkMail[kind]
	if !ok {
		return Content{}, ErrUnknownMail
	}
	prefix := spec[0]
	lang = authLanguage(lang)
	subject := accountText(lang, prefix+".subject")
	heading := accountText(lang, prefix+".heading")
	intro := accountText(lang, prefix+".intro")
	action := accountText(lang, prefix+".action")
	var expiry string
	if minutes >= 120 {
		expiry = accountText(lang, "mail.link.expiry_hours", "%(hours)s", strconv.Itoa(floorDiv(minutes, 60)))
	} else {
		expiry = accountText(lang, "mail.link.expiry_minutes", "%(minutes)s", strconv.Itoa(minutes))
	}
	ignore := accountText(lang, "mail.link.ignore", "%(support)s", operatorEmail)
	fallback := authText(lang, "mail_link_fallback")
	footer := authFooter(lang, operatorEmail)
	text := strings.Join(append([]string{intro, "", action + ": " + link, "", expiry, "", ignore, "", "--"}, footer...), "\n")
	blocks := []string{
		blockHeading(heading),
		blockParagraph(intro, false),
		blockButton(link, action),
		authParagraph15(expiry),
		blockLink(link, fallback),
		blockParagraph(ignore, true),
	}
	return Content{Subject: subject, Text: text, HTML: authShell(publicBaseURL, lang, heading, intro, blocks, footer)}, nil
}

// floorDiv is Python's // for the minutes of a link (never negative in use).
func floorDiv(a, b int) int {
	q := a / b
	if (a%b != 0) && ((a < 0) != (b < 0)) {
		q--
	}
	return q
}

// BuildEmailChanged is build_email_changed: the notice that a login e-mail
// changed. side is "old" (the address that no longer logs in) or "new";
// newMasked is mask_email(new address); by "self" words the old side's
// notice as the host's own change, anything else as support's. No link.
func BuildEmailChanged(publicBaseURL, operatorEmail, side, newMasked, lang, by string) (Content, error) {
	if side != "old" && side != "new" {
		return Content{}, ErrUnknownMail
	}
	lang = authLanguage(lang)
	subject := accountText(lang, "mail.email_changed.subject")
	heading := accountText(lang, "mail.email_changed.heading")
	introKey := "mail.email_changed.intro_" + side
	if side == "old" && by == "self" {
		introKey = "mail.email_changed.intro_old_self"
	}
	intro := accountText(lang, introKey, "%(address)s", newMasked)
	help := accountText(lang, "mail.email_changed.help_"+side, "%(support)s", operatorEmail)
	return noticeMail(publicBaseURL, operatorEmail, lang, subject, heading, intro, help), nil
}

// BuildPasskeyAdded is build_passkey_added: the notice that a passkey named
// name can now log in. No link.
func BuildPasskeyAdded(publicBaseURL, operatorEmail, name, lang string) Content {
	lang = authLanguage(lang)
	subject := accountText(lang, "mail.passkey_added.subject")
	heading := accountText(lang, "mail.passkey_added.heading")
	intro := accountText(lang, "mail.passkey_added.intro", "%(name)s", name)
	help := accountText(lang, "mail.passkey_added.help", "%(support)s", operatorEmail)
	return noticeMail(publicBaseURL, operatorEmail, lang, subject, heading, intro, help)
}

// noticeMail is the shared body of build_email_changed and
// build_passkey_added: heading, intro, a 15 px help paragraph.
func noticeMail(publicBaseURL, operatorEmail, lang, subject, heading, intro, help string) Content {
	footer := authFooter(lang, operatorEmail)
	text := strings.Join(append([]string{intro, "", help, "", "--"}, footer...), "\n")
	blocks := []string{
		blockHeading(heading),
		blockParagraph(intro, false),
		authParagraph15(help),
	}
	return Content{Subject: subject, Text: text, HTML: authShell(publicBaseURL, lang, heading, intro, blocks, footer)}
}

// BuildWorkspaceDeletion is build_workspace_deletion: the notice that the
// account is deleted on date (already DD.MM.YYYY), at stage "scheduled" or
// "week_before".
func BuildWorkspaceDeletion(publicBaseURL, operatorEmail, stage, date, lang string) (Content, error) {
	if stage != DeletionScheduled && stage != DeletionWeekBefore {
		return Content{}, ErrUnknownMail
	}
	lang = authLanguage(lang)
	subject := accountText(lang, "mail.workspace_deletion.subject_"+stage, "%(date)s", date)
	heading := accountText(lang, "mail.workspace_deletion.heading", "%(date)s", date)
	intro := accountText(lang, "mail.workspace_deletion.intro_"+stage, "%(date)s", date)
	keepLabel := accountText(lang, "mail.workspace_deletion.keep_label")
	keep := accountText(lang, "mail.workspace_deletion.keep", "%(date)s", date, "%(support)s", operatorEmail)
	footer := authFooter(lang, operatorEmail)
	text := strings.Join(append([]string{intro, "", keepLabel + ": " + keep, "", "--"}, footer...), "\n")
	blocks := []string{
		blockHeading(heading),
		blockParagraph(intro, false),
		blockSection(keepLabel, keep),
	}
	return Content{Subject: subject, Text: text, HTML: authShell(publicBaseURL, lang, heading, intro, blocks, footer)}, nil
}
