"""0304: the guide card catalog (fewer, richer cards). Run once from the repo root.

Rewrites TOPICS / KINDS / DEFAULT_KINDS in App/app/guest_guide.py and every
guest_guide.topic.* / guest_guide.kind.* line (en, cs) in App/app/host_i18n.py,
plus the ghost text (placeholders) of every card and the two progress lines.
All copy lives in catalog_copy.py. Kind keys never change: rows already use them.
Refuses to run twice; writes nothing unless every check passes.
"""
import json
from pathlib import Path

from catalog_copy import CARDS, CUSTOM_PLACEHOLDERS, KEPT, PLACEHOLDERS, PROGRESS, TOPICS

FIELDS = ("location", "steps", "watch_out")


def py_block() -> str:
    topics = "".join(f'    "{key}",\n' for key, _, _ in TOPICS)
    kinds = "".join(f'    "{kind}": "{topic}",\n' for kind, topic, *_ in CARDS)
    defaults = "".join(f'    "{kind}",\n' for kind, _, default, *_ in CARDS if default)
    return (
        "# Guest order. A custom item names one of these.\n"
        f"TOPICS = (\n{topics})\n\n"
        "# Built-in cards: kind -> topic, in guest order (0304: few, rich cards; each\n"
        "# prompt is a checklist of what guests ask). Never rename a kind: rows use it.\n"
        f"KINDS: Dict[str, str] = {{\n{kinds}}}\n\n"
        "# Every property gets these cards. The other built-in kinds are narrower cards\n"
        "# kept for data that already uses them: they appear only where an import or\n"
        "# earlier data created them.\n"
        f"DEFAULT_KINDS = (\n{defaults})\n\n"
    )


def _line(key: str, value: str) -> str:
    return f"        {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},\n"


def i18n_lines(lang: str) -> list:
    col = 1 if lang == "en" else 2
    out = [_line(f"guest_guide.topic.{t[0]}", t[col]) for t in TOPICS]
    for card in CARDS:
        kind = card[0]
        title, prompt = (card[3], card[4]) if lang == "en" else (card[5], card[6])
        out.append(_line(f"guest_guide.kind.{kind}.title", title))
        out.append(_line(f"guest_guide.kind.{kind}.prompt", prompt))
        for field, text in zip(FIELDS, PLACEHOLDERS[kind][lang]):
            out.append(_line(f"guest_guide.kind.{kind}.ph.{field}", text))
    for field, text in zip(FIELDS, CUSTOM_PLACEHOLDERS[lang]):
        out.append(_line(f"guest_guide.custom.ph.{field}", text))
    return out


def main() -> None:
    kinds = [c[0] for c in CARDS]
    assert all(k in kinds for k in KEPT), "a kept kind is missing"
    assert sorted(PLACEHOLDERS) == sorted(kinds), "every card needs ghost text"
    gg = Path("App/app/guest_guide.py")
    text = gg.read_text(encoding="utf-8")
    assert '"something_wrong"' not in text, "already applied"
    start = text.index("# Guest order. A custom item names one of these.\n")
    end = text.index("# The guide goes live for guests once these five are done (or skipped).\n")
    assert text.count("# Guest order. A custom item names one of these.\n") == 1
    new_gg = text[:start] + py_block() + text[end:]

    hi = Path("App/app/host_i18n.py")
    lines = hi.read_text(encoding="utf-8").splitlines(keepends=True)
    first = lines.index("_GUEST_GUIDE_STRINGS = {\n")
    last = lines.index("for _lang, _strings in _GUEST_GUIDE_STRINGS.items():\n")
    out, lang, inserted, removed = [], None, set(), 0
    for i, line in enumerate(lines):
        inside = first < i < last
        if inside and line in ('    "en": {\n', '    "cs": {\n'):
            lang = line.strip()[1:3]
        if inside and line.startswith(('        "guest_guide.topic.', '        "guest_guide.kind.')):
            removed += 1
            if lang not in inserted:
                out.extend(i18n_lines(lang))
                inserted.add(lang)
            continue
        if inside and line.startswith('        "guest_guide.progress": '):
            plain, live = PROGRESS[lang]
            out.append(_line("guest_guide.progress", plain))
            out.append(_line("guest_guide.progress_live", live))
            continue
        out.append(line)
    assert inserted == {"en", "cs"} and removed == 102, (inserted, removed)
    gg.write_text(new_gg, encoding="utf-8")
    hi.write_text("".join(out), encoding="utf-8")
    print(f"catalog: {len(TOPICS)} topics, {len(CARDS)} cards, {sum(1 for c in CARDS if c[2])} default")


if __name__ == "__main__":
    main()
