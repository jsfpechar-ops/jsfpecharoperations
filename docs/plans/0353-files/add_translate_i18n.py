"""0353: guest copy for translated guide cards (6 languages) and the host usage line (en, cs).
Run from the repo root once: python3 docs/plans/0353-files/add_translate_i18n.py"""
import json
from pathlib import Path

GUEST = {
    "en": {"guide_translated": "Translated by AI. Show the original",
           "guide_translating": "Your guide is being translated into English. Reload this page in a minute to read it."},
    "cs": {"guide_translated": "Přeložila AI. Zobrazit originál",
           "guide_translating": "Průvodce se právě překládá do češtiny. Za minutu stránku načtěte znovu."},
    "de": {"guide_translated": "Von KI übersetzt. Original anzeigen",
           "guide_translating": "Ihr Guide wird gerade ins Deutsche übersetzt. Laden Sie die Seite in einer Minute neu."},
    "es": {"guide_translated": "Traducido por IA. Ver el original",
           "guide_translating": "Su guía se está traduciendo al español. Vuelva a cargar la página dentro de un minuto."},
    "fr": {"guide_translated": "Traduit par l'IA. Voir l'original",
           "guide_translating": "Votre guide est en cours de traduction en français. Rechargez la page dans une minute."},
    "uk": {"guide_translated": "Перекладено ШІ. Показати оригінал",
           "guide_translating": "Путівник зараз перекладається українською. Оновіть сторінку за хвилину."},
}

HOST = {
    "en": {"guest_guide.usage.leon": "Guest questions Leon (AI) answered this month: %(n)s",
           "guest_guide.usage.languages": "Translated for guests into: %(langs)s"},
    "cs": {"guest_guide.usage.leon": "Dotazy hostů, na které tento měsíc odpověděl Leon (AI): %(n)s",
           "guest_guide.usage.languages": "Přeloženo pro hosty do: %(langs)s"},
}


def block(table: dict, lang: str, indent: str) -> str:
    return "".join(f"{indent}{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in table[lang].items())


def after_lines(path: Path, start: str, table: dict, order, indent: str, marker: str, expected: int) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    assert marker not in "".join(lines), f"already added to {path}"
    order = iter(order)
    out = []
    for line in lines:
        out.append(line)
        if line.strip().startswith(start):
            out.append(block(table, next(order), indent))
    text = "".join(out)
    assert text.count(marker) == expected, (path, text.count(marker))
    path.write_text(text, encoding="utf-8")


def main() -> None:
    after_lines(Path("App/app/i18n.py"), '"leon_error_reload":', GUEST, ("en", "cs", "de", "es", "fr"),
                "        ", '"guide_translated"', 5)
    after_lines(Path("App/app/guest_uk_i18n.py"), '"leon_error_reload":', GUEST, ("uk",), "    ",
                '"guide_translated"', 1)
    after_lines(Path("App/app/host_i18n.py"), '"guest_guide.check_waiting":', HOST, ("en", "cs"), "        ",
                '"guest_guide.usage.leon"', 2)
    print("added", len(GUEST["en"]), "guest keys x 6 languages and", len(HOST["en"]), "host keys x 2 languages")


if __name__ == "__main__":
    main()
