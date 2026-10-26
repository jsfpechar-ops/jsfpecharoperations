"""Brief 0419 step 4: insert keys.py into App/app/host_i18n.py after the 0417 overdue keys. Run from the repo root."""
import json
import pathlib
import runpy

keys = runpy.run_path(str(pathlib.Path(__file__).parent / "keys.py"))
target = pathlib.Path("App/app/host_i18n.py")
text = target.read_text(encoding="utf-8")
for lang, anchor in (
    ("EN", '        "mail.billing_overdue.action": "Open your plan",\n'),
    ("CS", '        "mail.billing_overdue.action": "Otevřít předplatné",\n'),
):
    assert text.count(anchor) == 1, f"anchor not found once: {anchor!r}"
    lines = "".join(
        f"        {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},\n"
        for k, v in keys[lang].items()
    )
    text = text.replace(anchor, anchor + lines)
target.write_text(text, encoding="utf-8")
print("inserted", len(keys["EN"]), "EN and", len(keys["CS"]), "CS keys")
