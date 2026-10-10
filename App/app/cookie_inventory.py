"""One inventory of the cookies and local storage the app sets (FE-4).

The public privacy pages render this, and ``tests/test_cookie_inventory.py``
checks that no cookie or storage key is set anywhere in the app without a row
here. ``party`` is ``first`` or ``Cloudflare``; ``kind`` is ``cookie`` or
``localStorage``. Purpose and lifetime carry both languages in one place.
"""
from __future__ import annotations

from typing import Dict, Tuple

COOKIE_INVENTORY: Tuple[Dict[str, object], ...] = (
    {
        "name": "ubyhost_session",
        "set_by": "auth.py:attach_session",
        "party": "first",
        "kind": "cookie",
        "surface": "host",
        "purpose": {"en": "Keeps you signed in", "cs": "Udržuje přihlášení"},
        "lifetime": {
            "en": "Up to 400 days after you sign in, until you log out",
            "cs": "A\u017e 400 dn\u00ed po p\u0159ihl\u00e1\u0161en\u00ed, dokud se neodhl\u00e1s\u00edte",
        },
    },
    {
        "name": "ubyhost_csrf",
        "set_by": "security.py:attach_csrf_cookie",
        "party": "first",
        "kind": "cookie",
        "surface": "host",
        "purpose": {
            "en": "Protects forms against cross-site requests",
            "cs": "Chr\u00e1n\u00ed formul\u00e1\u0159e p\u0159ed po\u017eadavky z jin\u00fdch str\u00e1nek",
        },
        "lifetime": {
            "en": "Matches the session, up to 400 days",
            "cs": "Shodn\u00e9 s relac\u00ed, a\u017e 400 dn\u00ed",
        },
    },
    {
        "name": "ubyhost_lang",
        "set_by": "host_i18n.py:remember_language",
        "party": "first",
        "kind": "cookie",
        "surface": "public",
        "purpose": {"en": "Remembers your language", "cs": "Pamatuje si v\u00e1\u0161 jazyk"},
        "lifetime": {"en": "180 days", "cs": "180 dn\u00ed"},
    },
    {
        "name": "ubyhost_pin",
        "set_by": "auth.py:attach_pin_session",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Keeps your guest stay access on this device",
            "cs": "Udr\u017euje p\u0159\u00edstup k pobytu na tomto za\u0159\u00edzen\u00ed",
        },
        "lifetime": {"en": "7 days", "cs": "7 dn\u00ed"},
    },
    {
        "name": "ubyhost_owned",
        "set_by": "routes/guest.py:remember_owned",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Remembers which forms this device submitted",
            "cs": "Pamatuje si, kter\u00e9 formul\u00e1\u0159e toto za\u0159\u00edzen\u00ed odeslalo",
        },
        "lifetime": {"en": "60 days", "cs": "60 dn\u00ed"},
    },
    {
        "name": "ubyhost_claim",
        "set_by": "routes/guest.py:remember_claim",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Keeps a claimed reservation on this device",
            "cs": "Udr\u017euje p\u0159evzatou rezervaci na tomto za\u0159\u00edzen\u00ed",
        },
        "lifetime": {"en": "60 days", "cs": "60 dn\u00ed"},
    },
    {
        "name": "ubyhost_guest_lang",
        "set_by": "routes/guest.py:remember_guest_language",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Remembers the guest's language",
            "cs": "Pamatuje si jazyk hosta",
        },
        "lifetime": {"en": "60 days", "cs": "60 dn\u00ed"},
    },
    {
        "name": "ubyhost-sidebar-collapsed",
        "set_by": "static/app.js",
        "party": "first",
        "kind": "localStorage",
        "surface": "host",
        "purpose": {"en": "Remembers the sidebar state", "cs": "Pamatuje si stav postrann\u00edho panelu"},
        "lifetime": {"en": "Until you clear it", "cs": "Dokud jej nevyma\u017eete"},
    },
    {
        "name": "ubyhost-command-recents",
        "set_by": "static/app.js",
        "party": "first",
        "kind": "localStorage",
        "surface": "host",
        "purpose": {
            "en": "Recent command-palette items",
            "cs": "Ned\u00e1vn\u00e9 polo\u017eky palety p\u0159\u00edkaz\u016f",
        },
        "lifetime": {"en": "Until you clear it", "cs": "Dokud jej nevyma\u017eete"},
    },
    {
        "name": "ubyhost-saved-stay-views",
        "set_by": "static/app.js",
        "party": "first",
        "kind": "localStorage",
        "surface": "host",
        "purpose": {
            "en": "Saved stay-list views",
            "cs": "Ulo\u017een\u00e9 pohledy na seznam pobyt\u016f",
        },
        "lifetime": {"en": "Until you clear it", "cs": "Dokud jej nevyma\u017eete"},
    },
    {
        # WP09: written only when a visitor clicks the opt-out on /privacy
        # (static/analytics-optout.js). The PostHog tracker reads it and then counts
        # nothing in this browser; the opt-back-in link removes it.
        "name": "ubyhost.analytics.disabled",
        "set_by": "static/analytics-optout.js",
        "party": "first",
        "kind": "localStorage",
        "surface": "public",
        "purpose": {
            "en": (
                "Cookieless analytics (PostHog): no cookies are set. This optional key is stored "
                "only after you turn measurement off on the Privacy Policy page"
            ),
            "cs": (
                "Měření návštěvnosti bez cookies (PostHog): žádné cookies se nenastavují. Tento "
                "nepovinný klíč se uloží jen poté, co měření vypnete na stránce Zásad ochrany "
                "osobních údajů"
            ),
        },
        "lifetime": {
            "en": "Until you turn measurement back on or clear it",
            "cs": "Dokud měření znovu nezapnete nebo klíč nevymažete",
        },
    },
    {
        "name": "__cf_bm",
        "set_by": "Cloudflare edge",
        "party": "Cloudflare",
        "kind": "cookie",
        "surface": "any",
        "purpose": {
            "en": "Cloudflare bot management, set only when the edge challenges the request",
            "cs": "Spr\u00e1va bot\u016f Cloudflare, nastav\u00ed se jen p\u0159i v\u00fdzv\u011b na hran\u011b",
        },
        "lifetime": {"en": "About 30 minutes", "cs": "P\u0159ibli\u017en\u011b 30 minut"},
    },
    {
        "name": "cf_clearance",
        "set_by": "Cloudflare edge",
        "party": "Cloudflare",
        "kind": "cookie",
        "surface": "any",
        "purpose": {
            "en": "Cloudflare challenge clearance, set only after a challenge is passed",
            "cs": "Potvrzen\u00ed v\u00fdzvy Cloudflare, nastav\u00ed se po jej\u00edm projit\u00ed",
        },
        "lifetime": {"en": "Up to 1 year", "cs": "A\u017e 1 rok"},
    },
)


# Third-party services on the public pages that set no cookie, listed so the
# privacy page can say so (WP09, 04_legal_positions.md section 1). PostHog itself
# writes nothing; the only storage key involved is the visitor's own opt-out,
# "ubyhost.analytics.disabled", which is a COOKIE_INVENTORY row above because our
# analytics-optout.js writes it.
COOKIELESS_SERVICES: Tuple[Dict[str, object], ...] = (
    {
        "name": "PostHog Cloud EU",
        "surface": "public",
        "party": "PostHog, Inc.",
        "note": {
            "en": (
                "Cookieless analytics, no cookies set; optional localStorage key "
                "ubyhost.analytics.disabled only after opt-out. Public marketing and legal pages "
                "only, data stored in the EU. Never loaded in the app, on sign-in or on guest pages."
            ),
            "cs": (
                "Měření návštěvnosti bez cookies, žádné cookies se nenastavují; nepovinný klíč "
                "ubyhost.analytics.disabled v localStorage jen po vypnutí měření. Jen veřejné "
                "marketingové a právní stránky, data uložená v EU. V aplikaci, při přihlášení ani "
                "na stránkách pro hosty se nikdy nenačítá."
            ),
        },
    },
)


# WP26: purpose and lifetime for the guest pages' other languages. The guest
# privacy page renders this whole table, so every row carries them; the host
# and public pages stay EN/CS and never read these keys.
_GUEST_LANGUAGE_TEXT: Dict[str, Dict[str, Dict[str, str]]] = {
    "ubyhost_session": {
        "purpose": {
            "de": "Hält Sie angemeldet",
            "es": "Mantiene su sesión iniciada",
            "fr": "Maintient votre connexion",
        },
        "lifetime": {
            "de": "12 Stunden oder 30 Tage mit „Angemeldet bleiben“",
            "es": "12 horas, o 30 días con «recordarme»",
            "fr": "12 heures, ou 30 jours avec « se souvenir de moi »",
        },
    },
    "ubyhost_csrf": {
        "purpose": {
            "de": "Schützt Formulare vor Cross-Site-Anfragen",
            "es": "Protege los formularios contra solicitudes entre sitios",
            "fr": "Protège les formulaires contre les requêtes intersites",
        },
        "lifetime": {
            "de": "Wie die Sitzung, bis zu 30 Tage",
            "es": "Igual que la sesión, hasta 30 días",
            "fr": "Liée à la session, jusqu'à 30 jours",
        },
    },
    "ubyhost_lang": {
        "purpose": {
            "de": "Speichert Ihre Sprache",
            "es": "Recuerda su idioma",
            "fr": "Mémorise votre langue",
        },
        "lifetime": {
            "de": "180 Tage",
            "es": "180 días",
            "fr": "180 jours",
        },
    },
    "ubyhost_pin": {
        "purpose": {
            "de": "Speichert Ihren Gastzugang zum Aufenthalt auf diesem Gerät",
            "es": "Mantiene su acceso a la estancia en este dispositivo",
            "fr": "Conserve votre accès voyageur au séjour sur cet appareil",
        },
        "lifetime": {
            "de": "7 Tage",
            "es": "7 días",
            "fr": "7 jours",
        },
    },
    "ubyhost_owned": {
        "purpose": {
            "de": "Speichert, welche Formulare dieses Gerät gesendet hat",
            "es": "Recuerda qué formularios envió este dispositivo",
            "fr": "Mémorise les formulaires envoyés depuis cet appareil",
        },
        "lifetime": {
            "de": "60 Tage",
            "es": "60 días",
            "fr": "60 jours",
        },
    },
    "ubyhost_claim": {
        "purpose": {
            "de": "Speichert eine beanspruchte Reservierung auf diesem Gerät",
            "es": "Mantiene una reserva reclamada en este dispositivo",
            "fr": "Conserve une réservation revendiquée sur cet appareil",
        },
        "lifetime": {
            "de": "60 Tage",
            "es": "60 días",
            "fr": "60 jours",
        },
    },
    "ubyhost_guest_lang": {
        "purpose": {
            "de": "Speichert die Sprache des Gastes",
            "es": "Recuerda el idioma del huésped",
            "fr": "Mémorise la langue du voyageur",
        },
        "lifetime": {
            "de": "60 Tage",
            "es": "60 días",
            "fr": "60 jours",
        },
    },
    "ubyhost-sidebar-collapsed": {
        "purpose": {
            "de": "Speichert den Zustand der Seitenleiste",
            "es": "Recuerda el estado de la barra lateral",
            "fr": "Mémorise l'état de la barre latérale",
        },
        "lifetime": {
            "de": "Bis Sie es löschen",
            "es": "Hasta que la borre",
            "fr": "Jusqu'à ce que vous l'effaciez",
        },
    },
    "ubyhost-command-recents": {
        "purpose": {
            "de": "Zuletzt verwendete Einträge der Befehlspalette",
            "es": "Elementos recientes de la paleta de comandos",
            "fr": "Éléments récents de la palette de commandes",
        },
        "lifetime": {
            "de": "Bis Sie es löschen",
            "es": "Hasta que la borre",
            "fr": "Jusqu'à ce que vous l'effaciez",
        },
    },
    "ubyhost-saved-stay-views": {
        "purpose": {
            "de": "Gespeicherte Ansichten der Aufenthaltsliste",
            "es": "Vistas guardadas de la lista de estancias",
            "fr": "Vues enregistrées de la liste des séjours",
        },
        "lifetime": {
            "de": "Bis Sie es löschen",
            "es": "Hasta que la borre",
            "fr": "Jusqu'à ce que vous l'effaciez",
        },
    },
    "ubyhost.analytics.disabled": {
        "purpose": {
            "de": "Cookielose Analyse (PostHog): Es werden keine Cookies gesetzt. Dieser optionale Schlüssel wird nur gespeichert, nachdem Sie die Messung auf der Seite zur Datenschutzerklärung deaktiviert haben",
            "es": "Analítica sin cookies (PostHog): no se establecen cookies. Esta clave opcional solo se guarda después de que desactive la medición en la página de la Política de privacidad",
            "fr": "Mesure d'audience sans cookies (PostHog) : aucun cookie n'est défini. Cette clé facultative n'est enregistrée qu'après la désactivation de la mesure sur la page Politique de confidentialité",
        },
        "lifetime": {
            "de": "Bis Sie die Messung wieder aktivieren oder ihn löschen",
            "es": "Hasta que vuelva a activar la medición o la borre",
            "fr": "Jusqu'à la réactivation de la mesure ou son effacement",
        },
    },
    "__cf_bm": {
        "purpose": {
            "de": "Cloudflare-Bot-Management, nur gesetzt, wenn der Edge-Server die Anfrage prüft",
            "es": "Gestión de bots de Cloudflare; solo se establece cuando el servidor perimetral pone a prueba la solicitud",
            "fr": "Gestion des bots Cloudflare, définie uniquement lorsque le réseau périphérique soumet la requête à un contrôle",
        },
        "lifetime": {
            "de": "Etwa 30 Minuten",
            "es": "Unos 30 minutos",
            "fr": "Environ 30 minutes",
        },
    },
    "cf_clearance": {
        "purpose": {
            "de": "Cloudflare-Freigabe nach bestandener Prüfung, nur danach gesetzt",
            "es": "Autorización tras el desafío de Cloudflare; solo se establece después de superarlo",
            "fr": "Autorisation après contrôle Cloudflare, définie uniquement après la réussite d'un contrôle",
        },
        "lifetime": {
            "de": "Bis zu 1 Jahr",
            "es": "Hasta 1 año",
            "fr": "Jusqu'à 1 an",
        },
    },
}

for _row in COOKIE_INVENTORY:
    for _field, _texts in _GUEST_LANGUAGE_TEXT.get(str(_row["name"]), {}).items():
        _row[_field].update(_texts)  # type: ignore[union-attr]


def names() -> Tuple[str, ...]:
    return tuple(str(row["name"]) for row in COOKIE_INVENTORY)


# WP27 (privacy first): the only cookies the app itself ever sets. Every one is
# strictly necessary: sign-in, CSRF protection, the guest PIN and claim, the
# guest's own submitted forms, and the language the visitor chose. There is no
# analytics, advertising or other tracking cookie. ``tests/test_privacy_first.py``
# crawls host, guest and public pages and fails if the set of Set-Cookie names
# differs from this one. The Cloudflare rows are set by the edge, not the app.
STRICTLY_NECESSARY_COOKIES = frozenset(
    str(row["name"])
    for row in COOKIE_INVENTORY
    if row["kind"] == "cookie" and row["party"] == "first"
)
