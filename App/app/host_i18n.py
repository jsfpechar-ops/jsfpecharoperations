"""Host-facing UI strings in English and Czech."""
from __future__ import annotations

from typing import Dict

from fastapi import Request

LANG_COOKIE = "ubyhost_lang"
LANGUAGES = ("en", "cs")
DEFAULT_LANGUAGE = "en"

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "lang.en": "English",
        "lang.cs": "Czech",
        "lang.switch": "Language",
        "nav.operations": "Operations",
        "nav.records": "Records",
        "nav.setup": "Setup",
        "nav.overview": "Overview",
        "nav.stays": "Stays",
        "nav.reports": "Reports",
        "nav.housebook": "House book",
        "nav.properties": "Properties",
        "nav.entities": "Legal entities",
        "nav.settings": "Settings",
        "nav.users": "Users",
        "nav.logout": "Log out",
        "nav.administrator": "Administrator",
        "login.title": "Your guest reporting workspace.",
        "login.lede": "Log in to your UbyHost account",
        "login.username": "Username",
        "login.password": "Password",
        "login.username_ph": "Enter your username…",
        "login.password_ph": "Enter your password…",
        "login.remember": "Remember me for 30 days",
        "login.submit": "Continue",
        "login.footnote": (
            "No public sign-up. UbyHost is invite-only. Ask your administrator for an account, "
            "or use the first-admin credentials from your deployment."
        ),
        "login.hero_title": "Guest reporting, handled for you.",
        "login.hero_body": (
            "Calendars, guest forms, house book, and UbyPort submissions in one calm workspace — "
            "built for Czech short-term hosts."
        ),
        "demo.load": "Explore with demo data",
        "demo.load_detail": (
            "One sample property with stays and guests. Nothing is sent to the police unless you "
            "submit real data yourself."
        ),
        "demo.clear": "Clear demo data",
        "csv.export_stays": "Export stays",
        "csv.import_stays": "Import stays",
        "csv.sample_stays": "Sample CSV",
        "csv.download": "Download CSV",
        "csv.import": "Import CSV",
        "csv.sample_housebook": "Sample CSV",
    },
    "cs": {
        "lang.en": "Angličtina",
        "lang.cs": "Čeština",
        "lang.switch": "Jazyk",
        "nav.operations": "Provoz",
        "nav.records": "Evidence",
        "nav.setup": "Nastavení účtu",
        "nav.overview": "Přehled",
        "nav.stays": "Pobyty",
        "nav.reports": "Hlášení",
        "nav.housebook": "Domovní kniha",
        "nav.properties": "Ubytování",
        "nav.entities": "Právnické osoby",
        "nav.settings": "Nastavení",
        "nav.users": "Uživatelé",
        "nav.logout": "Odhlásit se",
        "nav.administrator": "Správce",
        "login.title": "Váš pracovní prostor pro hlášení hostů.",
        "login.lede": "Přihlaste se do UbyHost",
        "login.username": "Uživatelské jméno",
        "login.password": "Heslo",
        "login.username_ph": "Zadejte uživatelské jméno…",
        "login.password_ph": "Zadejte heslo…",
        "login.remember": "Zapamatovat na 30 dní",
        "login.submit": "Pokračovat",
        "login.footnote": (
            "Veřejná registrace není k dispozici. UbyHost je pouze na pozvání. Účet vám vytvoří "
            "správce, nebo použijte přihlašovací údaje z nasazení."
        ),
        "login.hero_title": "Hlášení hostů bez zbytečné práce.",
        "login.hero_body": (
            "Kalendáře, formuláře hostů, domovní kniha a odeslání do UbyPortu na jednom místě — "
            "pro krátkodobé pronájmy v Česku."
        ),
        "demo.load": "Prohlédnout s ukázkovými daty",
        "demo.load_detail": (
            "Ukázkové ubytování s pobytem a hosty. Na policii se nic neodešle, dokud sami "
            "neodešlete skutečná data."
        ),
        "demo.clear": "Smazat ukázková data",
        "csv.export_stays": "Export pobytů",
        "csv.import_stays": "Import pobytů",
        "csv.sample_stays": "Vzorové CSV",
        "csv.download": "Stáhnout CSV",
        "csv.import": "Importovat CSV",
        "csv.sample_housebook": "Vzorové CSV",
    },
}


def normalise_language(value: str | None) -> str:
    value = (value or "").lower()[:2]
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def lang_from_request(request: Request) -> str:
    return normalise_language(request.cookies.get(LANG_COOKIE))


def translate(lang: str, key: str, **kwargs) -> str:
    table = STRINGS.get(normalise_language(lang), STRINGS[DEFAULT_LANGUAGE])
    fallback = STRINGS[DEFAULT_LANGUAGE]
    text = table.get(key, fallback.get(key, key))
    return text % kwargs if kwargs else text
