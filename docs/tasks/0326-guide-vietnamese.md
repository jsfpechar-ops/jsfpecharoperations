# 0326: Guide: Vietnamese for every new guide key, and Havel reads the vi guide

Status: todo
Depends on: 0328 (and so 0316 to 0318) | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0326-guide-vietnamese
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 55k tokens (most of it is the Vietnamese text you write)

## 1. Objective

The Help & guide page in Vietnamese is complete again after 0316 to 0328 added about 190 English and Czech keys, and Havel answers a Vietnamese host from the Vietnamese guide instead of the English one. Plan section 16a.4; owner item 8 (a Vietnamese speaker reviews this text after merge).

## 2. Context

Today (checked 2026-10-24 with `grep -nF`):

- `App/app/host_vi_i18n.py` is one flat dict `STRINGS` with 154 `guide.*` keys. It imports nothing from the app, so another module can import it without a cycle. Line 2435 starts `    "guide.demo.body": "Nhấn Khám phá với dữ liệu mẫu` and is the last guide key in the file.
- `App/app/guide_i18n.py` holds `GUIDE_STRINGS = {"en": {...}, "cs": {...}}` only, so Havel (`havel.guide_lang`, brief 0311) uses English for `vi`. The file ends with the two lines `    },` and `}`.
- `App/app/host_i18n.py` lines 4790 to 4792:

```python
from .guide_i18n import GUIDE_STRINGS
for _lang, _strings in GUIDE_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

  `STRINGS` has no `"vi"` key at that point; line 7640 `STRINGS["vi"] = dict(_VI_STRINGS)` builds it later from `host_vi_i18n`. So adding `"vi"` to `GUIDE_STRINGS` without step 2 raises `KeyError: 'vi'` at import.
- `App/tests/test_host_i18n.py` line 147 `test_every_vietnamese_key_exists_in_english_with_the_same_placeholders`: every vi key must exist in English and keep the same `%(name)s` placeholders.
- From brief 0316 (grep before editing): `App/tests/test_guide_browser.py` has `@pytest.mark.parametrize("lang", ["en", "cs"])` and `            if width == 390 and lang == "en":`.
- `guide.door_codes.terms1` to `terms9` are legal terms; they stay English in vi. Do not translate them.

Vietnamese words to use (from `host_vi_i18n.py`; any other UI label: find its en key with `grep -nF '"<English label>"' app/host_i18n.py | head -3`, then use that key's vi text): Help = Trợ giúp, Dashboard = Tổng quan, Stays = Lưu trú, Properties = Chỗ ở, Cleaning = Dọn dẹp, More = Thêm, Stay fees = Phí lưu trú, Invoices = Hóa đơn, Settings = Cài đặt, Guest links = Liên kết cho khách, Data requests = Yêu cầu về dữ liệu, Guest register = Sổ khách lưu trú, Police reporting = Khai báo cảnh sát, sign out = Đăng xuất. Keep UbyPort, UbyHost, iCal, PIN, IDUB, Airbnb, Booking.com, TTLock and passkey as they are.

Style: the second person "bạn", short sentences, one action per step, "Nhấn" for tap or click (the existing vi guide does this), no em or en dashes (`test_no_em_dashes.py`), every `%(name)s` placeholder copied exactly.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/host_vi_i18n.py | edit | new vi guide keys after `guide.demo.body` |
| App/app/guide_i18n.py | edit | `GUIDE_STRINGS["vi"]` at the bottom, docstring line |
| App/app/host_i18n.py | edit | one line in the guide loop |
| App/tests/test_guide_browser.py | edit | add `vi`, vi screenshots |
| docs/tasks/screenshots-guide/*-vi.png | new | |

## 4. Steps

1. List the keys to translate. From `App/`:

```bash
.venv/bin/python - <<'EOF' | tail -3
from app import guide_i18n, host_vi_i18n
en, vi = guide_i18n.GUIDE_STRINGS["en"], host_vi_i18n.STRINGS
missing = [k for k in en if k not in vi and not k.startswith("guide.door_codes.terms")]
with open("/tmp/0326-missing.txt", "w") as out:
    for k in missing:
        out.write(f"{k}\t{en[k]}\n")
print(len(missing), "missing")
EOF
```

   Expected: about 190 missing (write the number in the report). Read `/tmp/0326-missing.txt` in parts of 60 lines (`sed -n 1,60p`, then 61,120 and so on); never print it whole.

2. In `App/app/host_i18n.py` replace `    STRINGS[_lang].update(_strings)` in the guide loop (the line right after `for _lang, _strings in GUIDE_STRINGS.items():`) with:

```python
    STRINGS.setdefault(_lang, {}).update(_strings)
```

   Only that one occurrence: the same text appears in the `HOST_DESIGN_STRINGS` loop two lines above; leave that one. Check: `grep -n 'setdefault(_lang' app/host_i18n.py | tail -3` prints one line.

3. At the bottom of `App/app/guide_i18n.py`, after the closing `}`, add:

```python


# Vietnamese lives in host_vi_i18n.py with the rest of the vi host copy (brief 0196).
# Havel reads GUIDE_STRINGS, so vi is built here: every English key, in Vietnamese
# where host_vi_i18n has it, English otherwise (the door-code terms stay English).
from .host_vi_i18n import STRINGS as _VI  # noqa: E402

GUIDE_STRINGS["vi"] = {key: _VI.get(key, text) for key, text in GUIDE_STRINGS["en"].items()}
```

   In the module docstring change `English and Czech.` to `English and Czech; Vietnamese in host_vi_i18n.py.`
   Check: `.venv/bin/python -c "from app import host_i18n, guide_i18n; print(len(guide_i18n.GUIDE_STRINGS['vi']) == len(guide_i18n.GUIDE_STRINGS['en']))"` prints `True`.

4. Translate. In `App/app/host_vi_i18n.py`, directly after the line that starts `    "guide.demo.body": "Nhấn Khám phá`, add one line per missing key, in the order of `/tmp/0326-missing.txt`, in the form `    "guide.x.y": "…",`. Translate the meaning, not word by word. Do it in three or four Edit calls of about 50 keys each. A sentence that names a button or menu uses that label's vi text (section 2). Steps that say "On a phone, tap X. On a computer, click X in the menu on the left." keep both places.
   Check after the last edit: rerun the script of step 1. Expected `0 missing`.

5. Placeholders and dashes. From `App/`:

```bash
.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -15
```

   Expected: all pass. A placeholder failure names the key; copy the `%(name)s` from the English line.

6. Browser test. In `App/tests/test_guide_browser.py` change `@pytest.mark.parametrize("lang", ["en", "cs"])` to `@pytest.mark.parametrize("lang", ["en", "cs", "vi"])`, and change the screenshot block

```python
            if width == 390 and lang == "en":
                for section in SECTIONS:
                    if page.locator(f"#{section}").count():
                        page.locator(f"#{section}").screenshot(path=str(SHOTS / f"guide-{section}-390.png"))
```

   to

```python
            if width == 390 and lang in ("en", "vi"):
                suffix = "" if lang == "en" else "-vi"
                for section in SECTIONS:
                    if page.locator(f"#{section}").count():
                        page.locator(f"#{section}").screenshot(path=str(SHOTS / f"guide-{section}-390{suffix}.png"))
```

   Command in section 6. Expected: 6 passed, 0 skipped; `ls ../docs/tasks/screenshots-guide/*-vi.png | wc -l` prints the number of `SECTIONS` that exist on the page.

7. Run the copy row (section 6, second command) and the lint. Expected: pass, `context_lint: OK`.

## 5. Do not touch

`guide.html`, `guide_i18n.py` en and cs text, `havel.py` (it picks up `GUIDE_STRINGS["vi"]` through `guide_lang` with no change), the door-code terms, any non-guide vi key.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

- `.venv/bin/python -m pytest tests/test_guide_browser.py -q --tb=short -x -rs 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_guide.py tests/test_havel_engine.py -q --tb=short -x 2>&1 | tail -15`
- From the repo root: `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] Step 1 script prints `0 missing`; `GUIDE_STRINGS["vi"]` has as many keys as en.
- [ ] `/guide?lang=vi` shows Vietnamese in every section (the door-code terms excepted).
- [ ] Browser test 6 passed, 0 skipped; vi screenshots at 390 px saved.
- [ ] Copy row and `test_havel_engine.py` pass; lint OK.

## 8. Stop and ask

- The import in step 3 raises a circular-import error: stop, report the traceback's last 10 lines.
- An English key reads as wrong or as describing behaviour the page does not have: translate it as it is and list it in the report.

## 9. Report

Write `docs/tasks/0326-report.md` (500 tokens at most) and set `Status: review`: the missing count from step 1, files changed, each command's last 5 lines, section 7 ticked, keys you were unsure of, and the vi screenshot paths.

## Risk list (for the reviewer)

- Machine-quality Vietnamese: the owner decided on 2026-10-24 that it ships without a native review.
- `GUIDE_STRINGS["vi"]` falls back to English per key, so a future en key without vi silently shows English; 0327's coverage test catches it.

## Owner steps

1. After merge, send the Vietnamese reviewer the link `/guide?lang=vi` on staging and the screenshot folder `docs/tasks/screenshots-guide/` (files ending `-vi.png`).
2. Collect corrections as a list of "key: new text" and hand it to the orchestrator for a follow-up brief.
