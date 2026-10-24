"""0352: add the Leon (AI) chat copy and the QR contact line to i18n.py (en, cs, de, es, fr) and guest_uk_i18n.py.
Run from the repo root once: python3 docs/plans/0352-files/add_chat_i18n.py"""
import json
from pathlib import Path

GUEST = {
    "en": {
        "leon_ask": "Ask Leon (AI)",
        "leon_intro": "Ask me about this place. I answer from your host's guide, and when it has no answer, I ask your host.",
        "leon_label": "Your question",
        "leon_placeholder": "For example: how does the heating work?",
        "leon_send": "Send",
        "leon_sending": "Sending",
        "leon_you": "You",
        "leon_needs_js": "To chat with Leon (AI), turn on JavaScript. The guide above works without it.",
        "leon_waiting": "Waiting for your host. The answer will appear here, and you can close this page in the meantime.",
        "leon_error": "That did not go through. Please try again.",
        "leon_error_reload": "This page has expired. Please reload it and try again.",
        "leon_queued": "Sending after Leon's reply",
        "guide_qr_contact": "To reach your host directly, write to them where you booked, for example in your Booking.com or Airbnb messages.",
    },
    "cs": {
        "leon_ask": "Zeptejte se Leona (AI)",
        "leon_intro": "Zeptejte se mě na cokoli k ubytování. Odpovídám podle průvodce od hostitele, a když v něm odpověď není, zeptám se hostitele.",
        "leon_label": "Váš dotaz",
        "leon_placeholder": "Například: jak funguje topení?",
        "leon_send": "Odeslat",
        "leon_sending": "Odesílám",
        "leon_you": "Vy",
        "leon_needs_js": "Pro chat s Leonem (AI) zapněte JavaScript. Průvodce výše funguje i bez něj.",
        "leon_waiting": "Čekáme na hostitele. Odpověď se objeví tady a stránku mezitím můžete zavřít.",
        "leon_error": "Nepodařilo se to odeslat. Zkuste to prosím znovu.",
        "leon_error_reload": "Platnost stránky vypršela. Načtěte ji prosím znovu a zkuste to ještě jednou.",
        "leon_queued": "Odešle se po Leonově odpovědi",
        "guide_qr_contact": "Hostiteli napíšete přímo tam, kde jste rezervovali, například ve zprávách na Booking.com nebo Airbnb.",
    },
    "de": {
        "leon_ask": "Leon (KI) fragen",
        "leon_intro": "Fragen Sie mich zu dieser Unterkunft. Ich antworte aus dem Guide Ihres Gastgebers, und wenn er keine Antwort hat, frage ich Ihren Gastgeber.",
        "leon_label": "Ihre Frage",
        "leon_placeholder": "Zum Beispiel: Wie funktioniert die Heizung?",
        "leon_send": "Senden",
        "leon_sending": "Wird gesendet",
        "leon_you": "Sie",
        "leon_needs_js": "Um mit Leon (KI) zu chatten, aktivieren Sie JavaScript. Der Guide oben funktioniert auch ohne.",
        "leon_waiting": "Wir warten auf Ihren Gastgeber. Die Antwort erscheint hier, und Sie können die Seite inzwischen schließen.",
        "leon_error": "Das hat nicht geklappt. Bitte versuchen Sie es noch einmal.",
        "leon_error_reload": "Diese Seite ist abgelaufen. Bitte laden Sie sie neu und versuchen Sie es noch einmal.",
        "leon_queued": "Wird nach Leons Antwort gesendet",
        "guide_qr_contact": "Ihren Gastgeber erreichen Sie direkt dort, wo Sie gebucht haben, zum Beispiel in Ihren Nachrichten bei Booking.com oder Airbnb.",
    },
    "es": {
        "leon_ask": "Preguntar a Leon (IA)",
        "leon_intro": "Pregúnteme sobre este alojamiento. Respondo con la guía de su anfitrión y, cuando no tiene la respuesta, se lo pregunto a su anfitrión.",
        "leon_label": "Su pregunta",
        "leon_placeholder": "Por ejemplo: ¿cómo funciona la calefacción?",
        "leon_send": "Enviar",
        "leon_sending": "Enviando",
        "leon_you": "Usted",
        "leon_needs_js": "Para chatear con Leon (IA), active JavaScript. La guía de arriba funciona sin él.",
        "leon_waiting": "Esperando a su anfitrión. La respuesta aparecerá aquí y mientras tanto puede cerrar esta página.",
        "leon_error": "No se ha podido enviar. Inténtelo de nuevo.",
        "leon_error_reload": "Esta página ha caducado. Vuelva a cargarla e inténtelo de nuevo.",
        "leon_queued": "Se enviará tras la respuesta de Leon",
        "guide_qr_contact": "Para contactar directamente con su anfitrión, escríbale donde hizo la reserva, por ejemplo en sus mensajes de Booking.com o Airbnb.",
    },
    "fr": {
        "leon_ask": "Demander à Leon (IA)",
        "leon_intro": "Posez-moi vos questions sur ce logement. Je réponds avec le guide de votre hôte et, s'il n'a pas la réponse, je demande à votre hôte.",
        "leon_label": "Votre question",
        "leon_placeholder": "Par exemple : comment marche le chauffage ?",
        "leon_send": "Envoyer",
        "leon_sending": "Envoi en cours",
        "leon_you": "Vous",
        "leon_needs_js": "Pour discuter avec Leon (IA), activez JavaScript. Le guide ci-dessus fonctionne sans.",
        "leon_waiting": "En attente de votre hôte. La réponse s'affichera ici, et vous pouvez fermer cette page en attendant.",
        "leon_error": "L'envoi n'a pas abouti. Veuillez réessayer.",
        "leon_error_reload": "Cette page a expiré. Rechargez-la et réessayez.",
        "leon_queued": "Envoi après la réponse de Leon",
        "guide_qr_contact": "Pour joindre directement votre hôte, écrivez-lui là où vous avez réservé, par exemple dans vos messages Booking.com ou Airbnb.",
    },
    "uk": {
        "leon_ask": "Запитати Leon (ШІ)",
        "leon_intro": "Запитайте мене про це помешкання. Я відповідаю за путівником господаря, а коли в ньому немає відповіді, запитую господаря.",
        "leon_label": "Ваше запитання",
        "leon_placeholder": "Наприклад: як працює опалення?",
        "leon_send": "Надіслати",
        "leon_sending": "Надсилаю",
        "leon_you": "Ви",
        "leon_needs_js": "Щоб поспілкуватися з Leon (ШІ), увімкніть JavaScript. Путівник вище працює і без нього.",
        "leon_waiting": "Чекаємо на господаря. Відповідь з'явиться тут, а сторінку тим часом можна закрити.",
        "leon_error": "Не вдалося надіслати. Спробуйте ще раз.",
        "leon_error_reload": "Термін дії сторінки минув. Оновіть її та спробуйте ще раз.",
        "leon_queued": "Надішлеться після відповіді Leon",
        "guide_qr_contact": "Щоб зв'язатися з господарем напряму, напишіть йому там, де ви бронювали, наприклад у повідомленнях Booking.com або Airbnb.",
    },
}


def block(lang: str, indent: str) -> str:
    return "".join(f"{indent}{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in GUEST[lang].items())


def main() -> None:
    main_path = Path("App/app/i18n.py")
    lines = main_path.read_text(encoding="utf-8").splitlines(keepends=True)
    assert '"leon_intro"' not in "".join(lines), "already added"
    order = iter(("en", "cs", "de", "es", "fr"))
    out = []
    for line in lines:
        out.append(line)
        if line.strip().startswith('"leon_host_answered_plain":'):
            out.append(block(next(order), "        "))
    text = "".join(out)
    assert text.count('"leon_intro"') == 5, text.count('"leon_intro"')
    main_path.write_text(text, encoding="utf-8")
    uk_path = Path("App/app/guest_uk_i18n.py")
    uk = uk_path.read_text(encoding="utf-8")
    anchors = [l for l in uk.splitlines(keepends=True) if l.strip().startswith('"leon_host_answered_plain":')]
    assert len(anchors) == 1 and '"leon_intro"' not in uk, "uk anchor"
    uk_path.write_text(uk.replace(anchors[0], anchors[0] + block("uk", "    ")), encoding="utf-8")
    print("added", len(GUEST["en"]), "guest keys x 6 languages")


if __name__ == "__main__":
    main()
