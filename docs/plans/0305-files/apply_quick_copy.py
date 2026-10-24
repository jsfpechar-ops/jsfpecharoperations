"""0305: write the Quick answers copy. Run once from the repo root.

host_i18n.py gets a _GUIDE_QUICK_STRINGS block (en, cs) after the 0295 QR block;
i18n.py (en, cs, de, es, fr) and guest_uk_i18n.py (uk) get the guest lines after
"leon_about" (0300). All copy lives in quick_copy.py. Refuses to run twice and
writes nothing unless every check passes.
"""
import json
from pathlib import Path

from quick_copy import HOST, LANGS, guest

HOST_ANCHOR = "for _lang, _strings in _GUIDE_QR_STRINGS.items():\n    STRINGS[_lang].update(_strings)\n"


def _lines(pairs: dict, indent: str) -> str:
    return "".join(f"{indent}{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in pairs.items())


def main() -> None:
    host = Path("App/app/host_i18n.py")
    main_i18n = Path("App/app/i18n.py")
    uk = Path("App/app/guest_uk_i18n.py")
    host_text, main_text, uk_text = (p.read_text(encoding="utf-8") for p in (host, main_i18n, uk))
    assert "_GUIDE_QUICK_STRINGS" not in host_text and '"guide_fact_pets_yes"' not in main_text, "already applied"
    assert host_text.count(HOST_ANCHOR) == 1, "0295 QR block not found"
    block = (
        "\n# 0305: Quick answers, the host wizard.\n_GUIDE_QUICK_STRINGS = {\n"
        + "".join(f'    "{lang}": {{\n{_lines(HOST[lang], "        ")}    }},\n' for lang in ("en", "cs"))
        + "}\n\nfor _lang, _strings in _GUIDE_QUICK_STRINGS.items():\n    STRINGS[_lang].update(_strings)\n"
    )
    host_text = host_text.replace(HOST_ANCHOR, HOST_ANCHOR + block)

    order = iter(("en", "cs", "de", "es", "fr"))
    out = []
    for line in main_text.splitlines(keepends=True):
        out.append(line)
        if line.startswith('        "leon_about":'):
            out.append(_lines(guest(next(order)), "        "))
    main_text = "".join(out)
    assert main_text.count('"guide_fact_pets_yes"') == 5, "expected five leon_about lines in i18n.py"
    uk_lines = uk_text.splitlines(keepends=True)
    hits = [i for i, line in enumerate(uk_lines) if line.startswith('    "leon_about":')]
    assert len(hits) == 1, "expected one leon_about line in guest_uk_i18n.py"
    uk_lines.insert(hits[0] + 1, _lines(guest("uk"), "    "))

    host.write_text(host_text, encoding="utf-8")
    main_i18n.write_text(main_text, encoding="utf-8")
    uk.write_text("".join(uk_lines), encoding="utf-8")
    print(f"quick answers: {len(HOST['en'])} host keys x 2, {len(guest('en'))} guest keys x {len(LANGS)}")


if __name__ == "__main__":
    main()
