"""0350: add Leon's 20 guest copy keys to i18n.py (en, cs, de, es, fr) and guest_uk_i18n.py (uk). Run from the repo root once."""
import json
from pathlib import Path

KEYS = {
    "en": {
        "leon_name": "Leon (AI)",
        "leon_hi": "Hello, I'm Leon, the host's AI assistant. How can I help you with your stay?",
        "leon_thanks": "You're welcome. I'm here if you need anything else.",
        "leon_asked_host": "I don't want to guess about this, so I've asked %(host)s, your host. I'll show the answer here as soon as it comes.",
        "leon_asked_host_plain": "I don't want to guess about this, so I've asked your host. I'll show the answer here as soon as it comes.",
        "leon_refuse": "I can only help with your stay and this property. Is there anything about them I can do for you?",
        "leon_paused": "I'll take a break from this conversation until tomorrow. If something is urgent, please contact your host directly.",
        "leon_too_long": "Please keep a message under %(n)s characters.",
        "leon_slow_down": "Let's take a short break. You can write again in a few minutes.",
        "leon_asked_host_sorry": "I'm sorry about this. I've passed it to %(host)s, your host, and I'll show the answer here as soon as it comes.",
        "leon_asked_host_sorry_plain": "I'm sorry about this. I've passed it to your host and I'll show the answer here as soon as it comes.",
        "leon_asked_host_part": "The rest I've passed to your host; the answer will appear here.",
        "leon_asked_already": "I've already passed this to your host. The answer will appear here as soon as it comes.",
        "leon_passed_to_host": "I've passed your message to %(host)s, your host. The answer will appear here.",
        "leon_passed_to_host_plain": "I've passed your message to your host. The answer will appear here.",
        "leon_emergency": "If anyone is in danger, call 112 now (in Czechia also 150 fire, 155 ambulance, 158 police). I've told your host it is urgent.",
        "leon_unclear": "I'm not sure what you need. Tell me in a few words and I'll help.",
        "leon_about": "I'm Leon, your host's AI assistant, not a person. I answer from the host's guide, and when it has no answer I ask your host for you.",
        "leon_busy": "One moment, I'm still answering the previous message.",
        "leon_see_above": "Your host has already answered this above.",
    },
    "cs": {
        "leon_name": "Leon (AI)",
        "leon_hi": "Dobrý den, jsem Leon, AI asistent vašeho hostitele. S čím vám můžu během pobytu pomoct?",
        "leon_thanks": "Rádo se stalo. Kdybyste ještě něco potřebovali, jsem tu.",
        "leon_asked_host": "Nechci v tomhle hádat, proto jsem se zeptal vašeho hostitele, %(host)s. Odpověď vám tady ukážu, jakmile přijde.",
        "leon_asked_host_plain": "Nechci v tomhle hádat, proto jsem se zeptal vašeho hostitele. Odpověď vám tady ukážu, jakmile přijde.",
        "leon_refuse": "Můžu pomoct jen s vaším pobytem a s tímto ubytováním. Můžu pro vás v tomhle něco udělat?",
        "leon_paused": "V této konverzaci si do zítřka dám pauzu. Pokud něco spěchá, obraťte se prosím přímo na hostitele.",
        "leon_too_long": "Napište prosím zprávu kratší než %(n)s znaků.",
        "leon_slow_down": "Dáme si krátkou pauzu. Za pár minut můžete psát dál.",
        "leon_asked_host_sorry": "Je mi to líto. Předal jsem to vašemu hostiteli, %(host)s, a odpověď vám tady ukážu, jakmile přijde.",
        "leon_asked_host_sorry_plain": "Je mi to líto. Předal jsem to vašemu hostiteli a odpověď vám tady ukážu, jakmile přijde.",
        "leon_asked_host_part": "Zbytek jsem předal hostiteli; odpověď se objeví tady.",
        "leon_asked_already": "Tohle už jsem hostiteli předal. Odpověď se tady objeví, jakmile přijde.",
        "leon_passed_to_host": "Vaši zprávu jsem předal vašemu hostiteli, %(host)s. Odpověď se objeví tady.",
        "leon_passed_to_host_plain": "Vaši zprávu jsem předal vašemu hostiteli. Odpověď se objeví tady.",
        "leon_emergency": "Pokud je někdo v nebezpečí, volejte hned 112 (v Česku také 150 hasiči, 155 záchranka, 158 policie). Hostiteli jsem dal vědět, že to spěchá.",
        "leon_unclear": "Nejsem si jistý, co potřebujete. Napište mi to pár slovy a pomůžu.",
        "leon_about": "Jsem Leon, AI asistent vašeho hostitele, ne člověk. Odpovídám podle průvodce od hostitele, a když v něm odpověď není, zeptám se hostitele za vás.",
        "leon_busy": "Moment, ještě odpovídám na předchozí zprávu.",
        "leon_see_above": "Na tohle už vám hostitel odpověděl výše.",
    },
    "de": {
        "leon_name": "Leon (KI)",
        "leon_hi": "Hallo, ich bin Leon, der KI-Assistent Ihres Gastgebers. Wie kann ich Ihnen bei Ihrem Aufenthalt helfen?",
        "leon_thanks": "Gern geschehen. Ich bin da, wenn Sie noch etwas brauchen.",
        "leon_asked_host": "Ich möchte hier nicht raten, deshalb habe ich %(host)s, Ihren Gastgeber, gefragt. Die Antwort zeige ich Ihnen hier, sobald sie kommt.",
        "leon_asked_host_plain": "Ich möchte hier nicht raten, deshalb habe ich Ihren Gastgeber gefragt. Die Antwort zeige ich Ihnen hier, sobald sie kommt.",
        "leon_refuse": "Ich kann nur bei Ihrem Aufenthalt und dieser Unterkunft helfen. Kann ich dazu etwas für Sie tun?",
        "leon_paused": "Ich mache in diesem Gespräch bis morgen eine Pause. Wenn etwas dringend ist, wenden Sie sich bitte direkt an Ihren Gastgeber.",
        "leon_too_long": "Bitte halten Sie eine Nachricht unter %(n)s Zeichen.",
        "leon_slow_down": "Machen wir eine kurze Pause. In ein paar Minuten können Sie weiterschreiben.",
        "leon_asked_host_sorry": "Das tut mir leid. Ich habe es an %(host)s, Ihren Gastgeber, weitergegeben und zeige Ihnen die Antwort hier, sobald sie kommt.",
        "leon_asked_host_sorry_plain": "Das tut mir leid. Ich habe es an Ihren Gastgeber weitergegeben und zeige Ihnen die Antwort hier, sobald sie kommt.",
        "leon_asked_host_part": "Den Rest habe ich an Ihren Gastgeber weitergegeben; die Antwort erscheint hier.",
        "leon_asked_already": "Das habe ich Ihrem Gastgeber schon weitergegeben. Die Antwort erscheint hier, sobald sie kommt.",
        "leon_passed_to_host": "Ich habe Ihre Nachricht an %(host)s, Ihren Gastgeber, weitergegeben. Die Antwort erscheint hier.",
        "leon_passed_to_host_plain": "Ich habe Ihre Nachricht an Ihren Gastgeber weitergegeben. Die Antwort erscheint hier.",
        "leon_emergency": "Wenn jemand in Gefahr ist, rufen Sie sofort 112 an (in Tschechien auch 150 Feuerwehr, 155 Rettung, 158 Polizei). Ich habe Ihrem Gastgeber gesagt, dass es dringend ist.",
        "leon_unclear": "Ich bin nicht sicher, was Sie brauchen. Schreiben Sie es mir in ein paar Worten, dann helfe ich.",
        "leon_about": "Ich bin Leon, der KI-Assistent Ihres Gastgebers, kein Mensch. Ich antworte aus dem Gästeführer des Gastgebers, und wenn er keine Antwort hat, frage ich Ihren Gastgeber für Sie.",
        "leon_busy": "Einen Moment, ich beantworte noch die vorige Nachricht.",
        "leon_see_above": "Darauf hat Ihr Gastgeber oben schon geantwortet.",
    },
    "es": {
        "leon_name": "Leon (IA)",
        "leon_hi": "Hola, soy Leon, el asistente de IA de su anfitrión. ¿En qué puedo ayudarle con su estancia?",
        "leon_thanks": "De nada. Aquí estoy si necesita algo más.",
        "leon_asked_host": "No quiero adivinar en esto, así que se lo he preguntado a %(host)s, su anfitrión. Le mostraré la respuesta aquí en cuanto llegue.",
        "leon_asked_host_plain": "No quiero adivinar en esto, así que se lo he preguntado a su anfitrión. Le mostraré la respuesta aquí en cuanto llegue.",
        "leon_refuse": "Solo puedo ayudar con su estancia y con este alojamiento. ¿Puedo hacer algo por usted en ese sentido?",
        "leon_paused": "Haré una pausa en esta conversación hasta mañana. Si algo es urgente, contacte directamente con su anfitrión.",
        "leon_too_long": "Por favor, escriba un mensaje de menos de %(n)s caracteres.",
        "leon_slow_down": "Hagamos una breve pausa. Podrá escribir de nuevo en unos minutos.",
        "leon_asked_host_sorry": "Lo siento. Se lo he pasado a %(host)s, su anfitrión, y le mostraré la respuesta aquí en cuanto llegue.",
        "leon_asked_host_sorry_plain": "Lo siento. Se lo he pasado a su anfitrión y le mostraré la respuesta aquí en cuanto llegue.",
        "leon_asked_host_part": "El resto se lo he pasado a su anfitrión; la respuesta aparecerá aquí.",
        "leon_asked_already": "Esto ya se lo he pasado a su anfitrión. La respuesta aparecerá aquí en cuanto llegue.",
        "leon_passed_to_host": "He pasado su mensaje a %(host)s, su anfitrión. La respuesta aparecerá aquí.",
        "leon_passed_to_host_plain": "He pasado su mensaje a su anfitrión. La respuesta aparecerá aquí.",
        "leon_emergency": "Si alguien está en peligro, llame ahora al 112 (en Chequia también 150 bomberos, 155 ambulancia, 158 policía). He avisado a su anfitrión de que es urgente.",
        "leon_unclear": "No estoy seguro de qué necesita. Dígamelo en pocas palabras y le ayudo.",
        "leon_about": "Soy Leon, el asistente de IA de su anfitrión, no una persona. Respondo con la guía del anfitrión y, cuando no tiene la respuesta, se lo pregunto a su anfitrión por usted.",
        "leon_busy": "Un momento, todavía estoy respondiendo al mensaje anterior.",
        "leon_see_above": "Su anfitrión ya ha respondido a esto más arriba.",
    },
    "fr": {
        "leon_name": "Leon (IA)",
        "leon_hi": "Bonjour, je suis Leon, l'assistant IA de votre hôte. Comment puis-je vous aider pendant votre séjour ?",
        "leon_thanks": "Je vous en prie. Je suis là si vous avez besoin d'autre chose.",
        "leon_asked_host": "Je ne veux pas deviner, alors j'ai demandé à %(host)s, votre hôte. Je vous montrerai la réponse ici dès qu'elle arrivera.",
        "leon_asked_host_plain": "Je ne veux pas deviner, alors j'ai demandé à votre hôte. Je vous montrerai la réponse ici dès qu'elle arrivera.",
        "leon_refuse": "Je ne peux aider qu'au sujet de votre séjour et de ce logement. Puis-je faire quelque chose pour vous à ce sujet ?",
        "leon_paused": "Je fais une pause dans cette conversation jusqu'à demain. Si c'est urgent, contactez directement votre hôte.",
        "leon_too_long": "Merci d'écrire un message de moins de %(n)s caractères.",
        "leon_slow_down": "Faisons une courte pause. Vous pourrez écrire à nouveau dans quelques minutes.",
        "leon_asked_host_sorry": "Je suis désolé. J'ai transmis cela à %(host)s, votre hôte, et je vous montrerai la réponse ici dès qu'elle arrivera.",
        "leon_asked_host_sorry_plain": "Je suis désolé. J'ai transmis cela à votre hôte et je vous montrerai la réponse ici dès qu'elle arrivera.",
        "leon_asked_host_part": "J'ai transmis le reste à votre hôte ; la réponse apparaîtra ici.",
        "leon_asked_already": "Je l'ai déjà transmis à votre hôte. La réponse apparaîtra ici dès qu'elle arrivera.",
        "leon_passed_to_host": "J'ai transmis votre message à %(host)s, votre hôte. La réponse apparaîtra ici.",
        "leon_passed_to_host_plain": "J'ai transmis votre message à votre hôte. La réponse apparaîtra ici.",
        "leon_emergency": "Si quelqu'un est en danger, appelez tout de suite le 112 (en Tchéquie aussi 150 pompiers, 155 ambulance, 158 police). J'ai prévenu votre hôte que c'est urgent.",
        "leon_unclear": "Je ne suis pas sûr de ce dont vous avez besoin. Dites-le-moi en quelques mots et je vous aide.",
        "leon_about": "Je suis Leon, l'assistant IA de votre hôte, pas une personne. Je réponds à partir du guide de l'hôte et, quand il n'a pas la réponse, je pose la question à votre hôte pour vous.",
        "leon_busy": "Un instant, je réponds encore au message précédent.",
        "leon_see_above": "Votre hôte a déjà répondu à cela plus haut.",
    },
    "uk": {
        "leon_name": "Leon (ШІ)",
        "leon_hi": "Вітаю, я Leon, ШІ-помічник вашого господаря. Чим можу допомогти під час вашого проживання?",
        "leon_thanks": "Будь ласка. Я поруч, якщо потрібно ще щось.",
        "leon_asked_host": "Я не хочу вгадувати, тому запитав %(host)s, вашого господаря. Покажу відповідь тут, щойно вона надійде.",
        "leon_asked_host_plain": "Я не хочу вгадувати, тому запитав вашого господаря. Покажу відповідь тут, щойно вона надійде.",
        "leon_refuse": "Я можу допомогти лише з вашим проживанням і цим помешканням. Чи можу я щось для вас зробити в цьому?",
        "leon_paused": "Я зроблю перерву в цій розмові до завтра. Якщо щось термінове, зверніться безпосередньо до господаря.",
        "leon_too_long": "Будь ласка, напишіть повідомлення коротше за %(n)s символів.",
        "leon_slow_down": "Зробімо коротку перерву. За кілька хвилин ви зможете писати далі.",
        "leon_asked_host_sorry": "Мені шкода. Я передав це %(host)s, вашому господарю, і покажу відповідь тут, щойно вона надійде.",
        "leon_asked_host_sorry_plain": "Мені шкода. Я передав це вашому господарю і покажу відповідь тут, щойно вона надійде.",
        "leon_asked_host_part": "Решту я передав вашому господарю; відповідь з'явиться тут.",
        "leon_asked_already": "Це я вже передав вашому господарю. Відповідь з'явиться тут, щойно надійде.",
        "leon_passed_to_host": "Я передав ваше повідомлення %(host)s, вашому господарю. Відповідь з'явиться тут.",
        "leon_passed_to_host_plain": "Я передав ваше повідомлення вашому господарю. Відповідь з'явиться тут.",
        "leon_emergency": "Якщо хтось у небезпеці, негайно телефонуйте 112 (у Чехії також 150 пожежна, 155 швидка, 158 поліція). Я повідомив господаря, що це терміново.",
        "leon_unclear": "Я не впевнений, що вам потрібно. Напишіть кількома словами, і я допоможу.",
        "leon_about": "Я Leon, ШІ-помічник вашого господаря, а не людина. Я відповідаю за путівником господаря, а коли відповіді там немає, запитую господаря за вас.",
        "leon_busy": "Хвилинку, я ще відповідаю на попереднє повідомлення.",
        "leon_see_above": "Ваш господар уже відповів на це вище.",
    },
}
def block(lang: str, indent: str) -> str:
    return "".join(f"{indent}{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in KEYS[lang].items())


def main() -> None:
    main_path = Path("App/app/i18n.py")
    lines = main_path.read_text(encoding="utf-8").splitlines(keepends=True)
    assert '"leon_hi"' not in "".join(lines), "already added"
    # The five anchors appear in language order en, cs, de, es, fr.
    order = iter(("en", "cs", "de", "es", "fr"))
    out = []
    for line in lines:
        out.append(line)
        if line.strip().startswith('"guide_photo_alt":'):
            out.append(block(next(order), "        "))
    text = "".join(out)
    assert text.count('"leon_hi"') == 5, text.count('"leon_hi"')
    main_path.write_text(text, encoding="utf-8")
    uk_path = Path("App/app/guest_uk_i18n.py")
    uk = uk_path.read_text(encoding="utf-8")
    anchor = '    "guide_photo_alt": "Фото %(n)s",\n'
    assert uk.count(anchor) == 1 and '"leon_hi"' not in uk
    uk_path.write_text(uk.replace(anchor, anchor + block("uk", "    ")), encoding="utf-8")
    print("added", len(KEYS["en"]), "keys x 6 languages")


if __name__ == "__main__":
    main()
