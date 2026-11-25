package mailnotify

var claimCatalogue = map[string]map[string]string{
	"en": {
		"mail_claim_subject":          "Confirm your stay at %(property)s (link valid 30 min)",
		"mail_claim_resend_subject":   "New link: confirm your stay at %(property)s",
		"mail_claim_preheader":        "Tap the button, then fill in each guest (about 2 minutes per person).",
		"mail_claim_resend_preheader": "Your previous link has stopped working. Here is a new one.",
		"mail_claim_heading":          "Confirm your stay",
		"mail_claim_resend_heading":   "Here is your new link",
		"mail_claim_intro":            "Confirm your stay at %(property)s (%(dates)s) by opening the link below.",
		"mail_claim_action":           "Confirm my stay",
		"mail_link_fallback":          "If the button does not work, copy this address into your browser:",
		"mail_claim_expiry":           "The button works for 30 minutes. After you confirm, this phone or computer remembers your stay. You won't need the link again on it.",
		"mail_claim_expiry_resend":    "This new link replaces the previous one and works for 30 minutes.",
		"mail_claim_next_label":       "What happens next",
		"mail_claim_next_body":        "You will enter the details of every guest of this stay and then sign. It takes about two minutes per guest and works on a phone. If you're asked for a PIN, use the one from your host's message.",
		"mail_claim_next_done":        "Everyone is already registered. The link just opens your stay page.",
	},
	"cs": {
		"mail_claim_subject":          "Potvrďte svůj pobyt – %(property)s (odkaz platí 30 minut)",
		"mail_claim_resend_subject":   "Nový odkaz: potvrďte svůj pobyt – %(property)s",
		"mail_claim_preheader":        "Klepněte na tlačítko a vyplňte údaje hostů – asi 2 minuty na osobu.",
		"mail_claim_resend_preheader": "Předchozí odkaz už nefunguje. Tady je nový.",
		"mail_claim_heading":          "Potvrďte svůj pobyt",
		"mail_claim_resend_heading":   "Tady je váš nový odkaz",
		"mail_claim_intro":            "Potvrďte svůj pobyt: %(property)s, %(dates)s. Stačí otevřít odkaz níže.",
		"mail_claim_action":           "Potvrdit můj pobyt",
		"mail_link_fallback":          "Pokud tlačítko nefunguje, zkopírujte tuto adresu do prohlížeče:",
		"mail_claim_expiry":           "Tlačítko funguje 30 minut. Po potvrzení si váš pobyt zapamatuje tento telefon nebo počítač – odkaz už na něm znovu potřebovat nebudete.",
		"mail_claim_expiry_resend":    "Tento nový odkaz nahrazuje předchozí a funguje 30 minut.",
		"mail_claim_next_label":       "Co bude následovat",
		"mail_claim_next_body":        "Vyplníte údaje ke každému hostovi tohoto pobytu a poté je podepíšete. Zabere to přibližně dvě minuty na hosta a funguje to i na telefonu. Pokud se stránka zeptá na PIN, použijte ten ze zprávy od hostitele.",
		"mail_claim_next_done":        "Všichni už jsou zaregistrovaní – odkaz jen otevře stránku vašeho pobytu.",
	},
	"de": {
		"mail_claim_subject":          "Bestätigen Sie Ihren Aufenthalt in %(property)s (Link 30 Min. gültig)",
		"mail_claim_resend_subject":   "Neuer Link: Bestätigen Sie Ihren Aufenthalt in %(property)s",
		"mail_claim_preheader":        "Tippen Sie auf die Schaltfläche und erfassen Sie dann jeden Gast (etwa 2 Minuten pro Person).",
		"mail_claim_resend_preheader": "Ihr vorheriger Link funktioniert nicht mehr. Hier ist ein neuer.",
		"mail_claim_heading":          "Aufenthalt bestätigen",
		"mail_claim_resend_heading":   "Hier ist Ihr neuer Link",
		"mail_claim_intro":            "Bestätigen Sie Ihren Aufenthalt in %(property)s (%(dates)s), indem Sie den Link unten öffnen.",
		"mail_claim_action":           "Aufenthalt bestätigen",
		"mail_link_fallback":          "Falls die Schaltfläche nicht funktioniert, kopieren Sie diese Adresse in Ihren Browser:",
		"mail_claim_expiry":           "Die Schaltfläche funktioniert 30 Minuten lang. Nach der Bestätigung merkt sich dieses Telefon oder dieser Computer Ihren Aufenthalt. Sie brauchen den Link dort nicht mehr.",
		"mail_claim_expiry_resend":    "Dieser neue Link ersetzt den vorherigen und funktioniert 30 Minuten lang.",
		"mail_claim_next_label":       "Wie es weitergeht",
		"mail_claim_next_body":        "Sie geben die Angaben aller Gäste dieses Aufenthalts ein und unterschreiben dann. Das dauert etwa zwei Minuten pro Gast und funktioniert auf dem Telefon. Wenn nach einer PIN gefragt wird, verwenden Sie die aus der Nachricht Ihres Gastgebers.",
		"mail_claim_next_done":        "Alle sind bereits registriert. Der Link öffnet nur Ihre Aufenthaltsseite.",
	},
	"es": {
		"mail_claim_subject":          "Confirme su estancia en %(property)s (enlace válido 30 min)",
		"mail_claim_resend_subject":   "Nuevo enlace: confirme su estancia en %(property)s",
		"mail_claim_preheader":        "Toque el botón y rellene los datos de cada huésped (unos 2 minutos por persona).",
		"mail_claim_resend_preheader": "Su enlace anterior ha dejado de funcionar. Aquí tiene uno nuevo.",
		"mail_claim_heading":          "Confirme su estancia",
		"mail_claim_resend_heading":   "Aquí tiene su nuevo enlace",
		"mail_claim_intro":            "Confirme su estancia en %(property)s (%(dates)s) abriendo el enlace de abajo.",
		"mail_claim_action":           "Confirmar mi estancia",
		"mail_link_fallback":          "Si el botón no funciona, copie esta dirección en su navegador:",
		"mail_claim_expiry":           "El botón funciona durante 30 minutos. Tras confirmar, este teléfono u ordenador recordará su estancia. No volverá a necesitar el enlace en él.",
		"mail_claim_expiry_resend":    "Este nuevo enlace sustituye al anterior y funciona durante 30 minutos.",
		"mail_claim_next_label":       "Qué ocurre a continuación",
		"mail_claim_next_body":        "Introducirá los datos de cada huésped de esta estancia y después firmará. Se tarda unos dos minutos por huésped y funciona en el teléfono. Si se le pide un PIN, use el del mensaje de su anfitrión.",
		"mail_claim_next_done":        "Todos ya están registrados. El enlace solo abre la página de su estancia.",
	},
	"fr": {
		"mail_claim_subject":          "Confirmez votre séjour à %(property)s (lien valable 30 min)",
		"mail_claim_resend_subject":   "Nouveau lien : confirmez votre séjour à %(property)s",
		"mail_claim_preheader":        "Touchez le bouton, puis remplissez chaque voyageur (environ 2 minutes par personne).",
		"mail_claim_resend_preheader": "Votre lien précédent ne fonctionne plus. En voici un nouveau.",
		"mail_claim_heading":          "Confirmez votre séjour",
		"mail_claim_resend_heading":   "Voici votre nouveau lien",
		"mail_claim_intro":            "Confirmez votre séjour à %(property)s (%(dates)s) en ouvrant le lien ci-dessous.",
		"mail_claim_action":           "Confirmer mon séjour",
		"mail_link_fallback":          "Si le bouton ne fonctionne pas, copiez cette adresse dans votre navigateur :",
		"mail_claim_expiry":           "Le bouton fonctionne pendant 30 minutes. Après confirmation, ce téléphone ou cet ordinateur mémorise votre séjour. Vous n'aurez plus besoin du lien sur cet appareil.",
		"mail_claim_expiry_resend":    "Ce nouveau lien remplace le précédent et fonctionne pendant 30 minutes.",
		"mail_claim_next_label":       "La suite",
		"mail_claim_next_body":        "Vous saisirez les informations de chaque voyageur de ce séjour, puis signerez. Cela prend environ deux minutes par voyageur et fonctionne sur téléphone. Si un PIN vous est demandé, utilisez celui du message de votre hôte.",
		"mail_claim_next_done":        "Tout le monde est déjà enregistré. Le lien ouvre simplement la page de votre séjour.",
	},
	"uk": {
		"mail_claim_subject":          "Підтвердьте проживання в %(property)s (посилання дійсне 30 хв)",
		"mail_claim_resend_subject":   "Нове посилання: підтвердьте проживання в %(property)s",
		"mail_claim_preheader":        "Натисніть кнопку, а потім заповніть дані кожного гостя (близько 2 хвилин на особу).",
		"mail_claim_resend_preheader": "Попереднє посилання більше не діє. Ось нове.",
		"mail_claim_heading":          "Підтвердьте проживання",
		"mail_claim_resend_heading":   "Ось ваше нове посилання",
		"mail_claim_intro":            "Підтвердьте проживання в %(property)s (%(dates)s), відкривши посилання нижче.",
		"mail_claim_action":           "Підтвердити проживання",
		"mail_link_fallback":          "Якщо кнопка не працює, скопіюйте цю адресу в браузер:",
		"mail_claim_expiry":           "Кнопка діє 30 хвилин. Після підтвердження цей телефон чи комп’ютер запам’ятає ваше проживання, і посилання на ньому більше не знадобиться.",
		"mail_claim_expiry_resend":    "Це нове посилання замінює попереднє і діє 30 хвилин.",
		"mail_claim_next_label":       "Що далі",
		"mail_claim_next_body":        "Ви введете дані кожного гостя цього проживання, а потім підпишетеся. Це займає близько двох хвилин на гостя, і все можна зробити з телефона. Якщо запитають PIN-код, використайте той, що в повідомленні від господаря.",
		"mail_claim_next_done":        "Усіх уже зареєстровано. Посилання просто відкриває сторінку вашого проживання.",
	},
}

func claimText(lang, key string, args Args) string {
	table := claimCatalogue[GuestLanguage(lang)]
	text, ok := table[key]
	if !ok {
		text = claimCatalogue["en"][key]
	}
	if len(args) == 0 {
		return text
	}
	if out, ok := pyFormat(text, args); ok {
		return out
	}
	return text
}
