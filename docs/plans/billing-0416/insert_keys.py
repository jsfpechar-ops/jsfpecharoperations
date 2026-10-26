"""Brief 0416 step 5: insert keys.py into App/app/host_i18n.py after the 0414 banner keys. Run from the repo root."""
import json
import pathlib
import runpy

keys = runpy.run_path(str(pathlib.Path(__file__).parent / "keys.py"))
target = pathlib.Path("App/app/host_i18n.py")
text = target.read_text(encoding="utf-8")
for lang, anchor in (
    ("EN", '        "billing.banner.action_canceling": "Keep my plan",\n'),
    ("CS", '        "billing.banner.action_canceling": "Ponechat předplatné",\n'),
):
    assert text.count(anchor) == 1, f"anchor not found once: {anchor!r}"
    lines = "".join(
        f"        {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},\n"
        for k, v in keys[lang].items()
    )
    text = text.replace(anchor, anchor + lines)
target.write_text(text, encoding="utf-8")
print("inserted", len(keys["EN"]), "EN and", len(keys["CS"]), "CS keys")
