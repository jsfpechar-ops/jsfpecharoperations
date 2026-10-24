"""0301: add the host copy (en, cs) to host_i18n.py and the guest copy (6 languages) to i18n.py and guest_uk_i18n.py.
Run from the repo root once: python3 docs/plans/0301-files/add_handoff_i18n.py"""
import json
from pathlib import Path

HOST = {
    "en": {
        "guest_questions.title": "Guest questions",
        "guest_questions.link": "Guest questions (%(n)s)",
        "guest_questions.open": "%(n)s waiting for your answer",
        "guest_questions.none_open": "Nothing is waiting for you",
        "guest_questions.empty.title": "No questions yet",
        "guest_questions.empty.body": "When Leon (AI) cannot answer a guest from your guide, the question lands here. Your answer shows up on the guest's guide page.",
        "guest_questions.col.question": "Question",
        "guest_questions.col.state": "State",
        "guest_questions.door.qr": "QR page",
        "guest_questions.door.stay": "stay link",
        "guest_questions.state.open": "Waiting",
        "guest_questions.state.answered": "Answered",
        "guest_questions.state.dismissed": "Dismissed",
        "guest_questions.badge.urgent": "Urgent",
        "guest_questions.badge.unread": "Not read by Leon (AI)",
        "guest_question.title": "Guest question",
        "guest_question.asked": "The guest asked",
        "guest_question.urgent_banner": "Leon (AI) read this as an emergency and showed the guest the emergency number and your emergency card. Call or write to the guest now if you can.",
        "guest_question.summary": "In short:",
        "guest_question.your_answer": "Your answer",
        "guest_question.shown_to_guest": "The guest sees this on the guide page, word for word.",
        "guest_question.field.answer": "Answer",
        "guest_question.field.answer_help": "Plain text, up to %(max)s characters. Write it the way you would say it; no need to sign.",
        "guest_question.send": "Send to guest",
        "guest_question.dismiss": "Dismiss without answering",
        "guest_question.dismiss_help": "For a question that needs no answer. The guest is not told.",
        "guest_question.dismissed_banner": "You dismissed this question. You can still answer it.",
        "guest_question.card.title": "Add to guide",
        "guest_question.card.help": "Save this answer as a guide card, so Leon (AI) answers the next guest himself. You can edit the card afterwards.",
        "guest_question.card.button": "Add to guide",
        "guest_question.card.done": "This answer is in your guide.",
        "guest_question.card.open": "Open the card",
        "flash.guest_question.sent": "Answer sent. The guest sees it on the guide page.",
        "flash.guest_question.dismissed": "Question dismissed.",
        "flash.guest_question.card": "Added to your guide. Check the card and save.",
        "flash.error.guest_question_empty": "Write an answer first.",
        "flash.error.guest_question_too_long": "The answer is too long. Shorten it to 1000 characters.",
        "flash.error.guest_question_gone": "That question no longer exists.",
        "flash.error.guest_question_not_answered": "Answer the question first, then add it to the guide.",
        "notification.action.guest_questions": "Answer",
        "notification.guest_question.title": "%(count)s guest question(s) at %(property)s",
        "notification.guest_question.title.urgent": "Urgent: a guest at %(property)s may need help",
        "notification.guest_question.detail": "Leon (AI) could not answer from your guide. Your answer shows up on the guest's guide page.",
        "notification.mail_kind.guest_question": "guest question waiting",
        "mail.guest_question.subject": "A guest at %(property)s has a question for you",
        "mail.guest_question.heading": "A guest has a question",
        "mail.guest_question.intro": "A guest at %(property)s asked something your guest guide does not answer yet. Leon (AI) told the guest you will reply. Answer in UbyHost; the guest sees it on the guide page.",
        "mail.guest_question.action": "Answer the question",
        "mail.guest_question.footer": "You get this mail once per batch of open questions. Further questions wait for you in the app.",
    },
    "cs": {
        "guest_questions.title": "Dotazy hostů",
        "guest_questions.link": "Dotazy hostů (%(n)s)",
        "guest_questions.open": "%(n)s čeká na vaši odpověď",
        "guest_questions.none_open": "Nic na vás nečeká",
        "guest_questions.empty.title": "Zatím žádné dotazy",
        "guest_questions.empty.body": "Když Leon (AI) nedokáže hostovi odpovědět z vašeho průvodce, dotaz přistane tady. Vaše odpověď se hostovi zobrazí na stránce průvodce.",
        "guest_questions.col.question": "Dotaz",
        "guest_questions.col.state": "Stav",
        "guest_questions.door.qr": "QR stránka",
        "guest_questions.door.stay": "odkaz na pobyt",
        "guest_questions.state.open": "Čeká",
        "guest_questions.state.answered": "Zodpovězeno",
        "guest_questions.state.dismissed": "Odloženo",
        "guest_questions.badge.urgent": "Naléhavé",
        "guest_questions.badge.unread": "Leon (AI) nečetl",
        "guest_question.title": "Dotaz hosta",
        "guest_question.asked": "Host se ptá",
        "guest_question.urgent_banner": "Leon (AI) to vyhodnotil jako nouzi a ukázal hostovi tísňové číslo a vaši kartu Nouze. Pokud můžete, hostovi hned zavolejte nebo napište.",
        "guest_question.summary": "Stručně:",
        "guest_question.your_answer": "Vaše odpověď",
        "guest_question.shown_to_guest": "Host ji uvidí na stránce průvodce slovo od slova.",
        "guest_question.field.answer": "Odpověď",
        "guest_question.field.answer_help": "Prostý text, nejvýše %(max)s znaků. Napište ji tak, jak byste ji řekli; podpis není třeba.",
        "guest_question.send": "Odeslat hostovi",
        "guest_question.dismiss": "Odložit bez odpovědi",
        "guest_question.dismiss_help": "Pro dotaz, který odpověď nepotřebuje. Host se nic nedozví.",
        "guest_question.dismissed_banner": "Tento dotaz jste odložili. Pořád na něj můžete odpovědět.",
        "guest_question.card.title": "Přidat do průvodce",
        "guest_question.card.help": "Uložte odpověď jako kartu průvodce, aby příštímu hostovi odpověděl Leon (AI) sám. Kartu pak můžete upravit.",
        "guest_question.card.button": "Přidat do průvodce",
        "guest_question.card.done": "Tato odpověď je ve vašem průvodci.",
        "guest_question.card.open": "Otevřít kartu",
        "flash.guest_question.sent": "Odpověď odeslána. Host ji uvidí na stránce průvodce.",
        "flash.guest_question.dismissed": "Dotaz odložen.",
        "flash.guest_question.card": "Přidáno do průvodce. Zkontrolujte kartu a uložte.",
        "flash.error.guest_question_empty": "Nejdřív napište odpověď.",
        "flash.error.guest_question_too_long": "Odpověď je příliš dlouhá. Zkraťte ji na 1000 znaků.",
        "flash.error.guest_question_gone": "Tento dotaz už neexistuje.",
        "flash.error.guest_question_not_answered": "Nejdřív na dotaz odpovězte, pak ho přidejte do průvodce.",
        "notification.action.guest_questions": "Odpovědět",
        "notification.guest_question.title": "Dotazy hostů (%(count)s): %(property)s",
        "notification.guest_question.title.urgent": "Naléhavé: host v objektu %(property)s asi potřebuje pomoc",
        "notification.guest_question.detail": "Leon (AI) nedokázal odpovědět z vašeho průvodce. Vaše odpověď se hostovi zobrazí na stránce průvodce.",
        "notification.mail_kind.guest_question": "čekající dotaz hosta",
        "mail.guest_question.subject": "Host v objektu %(property)s má na vás dotaz",
        "mail.guest_question.heading": "Host má dotaz",
        "mail.guest_question.intro": "Host v objektu %(property)s se zeptal na něco, co váš průvodce zatím neumí zodpovědět. Leon (AI) mu řekl, že odpovíte. Odpovězte v UbyHostu; host odpověď uvidí na stránce průvodce.",
        "mail.guest_question.action": "Odpovědět na dotaz",
        "mail.guest_question.footer": "Tento e-mail dostáváte jednou za dávku otevřených dotazů. Další dotazy na vás čekají v aplikaci.",
    },
}

# Guest copy for 0352's chat: the label above a host answer. %(host)s is the host's first name (leon.host_first_name).
GUEST = {
    "en": {"leon_host_answered": "%(host)s, your host, answered:", "leon_host_answered_plain": "Your host answered:"},
    "cs": {"leon_host_answered": "%(host)s, váš hostitel, odpovídá:", "leon_host_answered_plain": "Váš hostitel odpovídá:"},
    "de": {"leon_host_answered": "%(host)s, Ihr Gastgeber, antwortet:", "leon_host_answered_plain": "Ihr Gastgeber antwortet:"},
    "es": {"leon_host_answered": "%(host)s, su anfitrión, responde:", "leon_host_answered_plain": "Su anfitrión responde:"},
    "fr": {"leon_host_answered": "%(host)s, votre hôte, répond :", "leon_host_answered_plain": "Votre hôte répond :"},
    "uk": {"leon_host_answered": "%(host)s, ваш господар, відповідає:", "leon_host_answered_plain": "Ваш господар відповідає:"},
}


def block(table: dict, lang: str, indent: str) -> str:
    return "".join(f"{indent}{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in table[lang].items())


def main() -> None:
    host_path = Path("App/app/host_i18n.py")
    text = host_path.read_text(encoding="utf-8")
    assert '"guest_questions.title"' not in text, "already added"
    for lang, anchor in (("en", '        "guest_guide.add.button": "Add a card",\n'),
                         ("cs", '        "guest_guide.add.button": "Přidat kartu",\n')):
        assert text.count(anchor) == 1, anchor
        text = text.replace(anchor, anchor + block(HOST, lang, "        "))
    host_path.write_text(text, encoding="utf-8")

    main_path = Path("App/app/i18n.py")
    lines = main_path.read_text(encoding="utf-8").splitlines(keepends=True)
    assert '"leon_host_answered"' not in "".join(lines), "already added"
    order = iter(("en", "cs", "de", "es", "fr"))
    out = []
    for line in lines:
        out.append(line)
        if line.strip().startswith('"leon_about":'):
            out.append(block(GUEST, next(order), "        "))
    text = "".join(out)
    assert text.count('"leon_host_answered"') == 5, text.count('"leon_host_answered"')
    main_path.write_text(text, encoding="utf-8")
    uk_path = Path("App/app/guest_uk_i18n.py")
    uk = uk_path.read_text(encoding="utf-8")
    anchors = [l for l in uk.splitlines(keepends=True) if l.strip().startswith('"leon_about":')]
    assert len(anchors) == 1 and '"leon_host_answered"' not in uk
    uk_path.write_text(uk.replace(anchors[0], anchors[0] + block(GUEST, "uk", "    ")), encoding="utf-8")
    print("added", len(HOST["en"]), "host keys x 2 languages and", len(GUEST["en"]), "guest keys x 6 languages")


if __name__ == "__main__":
    main()
