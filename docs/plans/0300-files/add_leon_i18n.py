"""0300: add Leon's guest copy to i18n.py (en, cs, de, es, fr) and guest_uk_i18n.py (uk). Run from the repo root once."""
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
        "leon_resting": "I'm resting right now and can't answer. Please try again later or contact your host directly.",
        "leon_about": "I'm Leon, your host's AI assistant, not a person. I answer from the host's guide, and when it has no answer I ask your host for you.",
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
        "leon_resting": "Teď odpočívám a nemůžu odpovědět. Zkuste to prosím později, nebo se obraťte přímo na hostitele.",
        "leon_about": "Jsem Leon, AI asistent vašeho hostitele, ne člověk. Odpovídám podle průvodce od hostitele, a když v něm odpověď není, zeptám se hostitele za vás.",
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
        "leon_resting": "Ich ruhe mich gerade aus und kann nicht antworten. Bitte versuchen Sie es später noch einmal oder wenden Sie sich direkt an Ihren Gastgeber.",
        "leon_about": "Ich bin Leon, der KI-Assistent Ihres Gastgebers, kein Mensch. Ich antworte aus dem Gästeführer des Gastgebers, und wenn er keine Antwort hat, frage ich Ihren Gastgeber für Sie.",
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
        "leon_resting": "Ahora mismo estoy descansando y no puedo responder. Inténtelo más tarde o contacte directamente con su anfitrión.",
        "leon_about": "Soy Leon, el asistente de IA de su anfitrión, no una persona. Respondo con la guía del anfitrión y, cuando no tiene la respuesta, se lo pregunto a su anfitrión por usted.",
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
        "leon_resting": "Je me repose en ce moment et ne peux pas répondre. Réessayez plus tard ou contactez directement votre hôte.",
        "leon_about": "Je suis Leon, l'assistant IA de votre hôte, pas une personne. Je réponds à partir du guide de l'hôte et, quand il n'a pas la réponse, je pose la question à votre hôte pour vous.",
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
        "leon_resting": "Зараз я відпочиваю і не можу відповісти. Спробуйте пізніше або зверніться безпосередньо до господаря.",
        "leon_about": "Я Leon, ШІ-помічник вашого господаря, а не людина. Я відповідаю за путівником господаря, а коли відповіді там немає, запитую господаря за вас.",
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
