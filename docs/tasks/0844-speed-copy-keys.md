# 0844: Speed briefs: every new copy key in EN, CS and VI

Status: todo
Depends on: PR #707 merged into main (it edits the same two locale files) | Base commit: main after #707 | Branch: task/0844-speed-copy-keys
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add, in one place, the 19 copy keys that the speed briefs 0845-0853 use, so those briefs never edit the locale files and can run in parallel. Nothing renders these keys until the later briefs land.

## 2. Context

- Host copy lives in `App/app/host_i18n.py` (an English dict and a Czech dict, each line indented 8 spaces) and `App/app/host_vi_i18n.py` (one dict, 4 spaces). Tests: EN and CS carry the same keys; every VI key exists in EN with the same placeholders (`tests/test_host_i18n.py`).
- Rule 9 (one explanation in one place; no sentence the button already says) and no em dashes (`tests/test_no_em_dashes.py`). No fine print: these are labels, flashes and one confirm question only.
- Anchors (search by text, line numbers move):
  - EN, `App/app/host_i18n.py`: `        "flash.stay_fees.period_saved": "Period saved. You can download the PDF and CSV.",`
  - CS, `App/app/host_i18n.py`: `        "flash.stay_fees.period_saved": "Období uloženo. PDF a CSV jsou k dispozici.",`
  - VI, `App/app/host_vi_i18n.py`: `    "flash.stay_fees.period_saved": "Đã lưu kỳ. Bạn có thể tải PDF và CSV.",`

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/host_i18n.py` | edit | 19 EN lines + 19 CS lines |
| `App/app/host_vi_i18n.py` | edit | 19 VI lines |
| `docs/tasks/0844-report.md` | new | Report |

No other file may change.

## 4. Steps

1. Check: `grep -c '"stay_fees.bulk.confirm"\|"invoice.price_use"\|"housebook.preset.label"' app/host_i18n.py app/host_vi_i18n.py` (from `App/`) prints 0 for both. If not 0, STOP (someone added them already).
2. EN: directly below the EN anchor insert:
```python
        "stay_fees.bulk.label": "All properties",
        "stay_fees.bulk.confirm": "Confirm all ready (%(count)s)",
        "stay_fees.bulk.confirm_ask": "Save every ready period with the figures shown?",
        "stay_fees.bulk.pdfs": "Download all PDFs (%(count)s)",
        "flash.stay_fees.bulk_saved": "Periods saved: %(count)s. You can download the PDFs.",
        "flash.stay_fees.bulk_none": "No period was ready to save.",
        "stay_fees.copy.title": "Same setup as %(name)s?",
        "stay_fees.copy.use": "Use this setup",
        "stay_fees.copy.other": "Set up differently",
        "flash.stay_fees.copy_done": "Stay fee set up like %(name)s.",
        "flash.stay_fees.copy_failed": "This setup cannot be copied here. Set the fee in the property settings.",
        "invoice.picker.recent": "Recent stays without an invoice",
        "invoice.picker.other": "Another stay",
        "invoice.price_use": "Use last price: %(price)s Kč",
        "housebook.preset.label": "Quick range",
        "housebook.preset.this_month": "This month",
        "housebook.preset.last_month": "Last month",
        "housebook.preset.this_year": "This year",
        "stay_fees.copy.label": "Copy the stay fee setup",
```
   Commit `0844 step 2`.
3. CS: directly below the CS anchor insert:
```python
        "stay_fees.bulk.label": "Všechny nemovitosti",
        "stay_fees.bulk.confirm": "Potvrdit všechna připravená (%(count)s)",
        "stay_fees.bulk.confirm_ask": "Uložit všechna připravená období s uvedenými údaji?",
        "stay_fees.bulk.pdfs": "Stáhnout všechna PDF (%(count)s)",
        "flash.stay_fees.bulk_saved": "Uložená období: %(count)s. PDF jsou k dispozici.",
        "flash.stay_fees.bulk_none": "Žádné období nebylo připravené k uložení.",
        "stay_fees.copy.title": "Stejné nastavení jako %(name)s?",
        "stay_fees.copy.use": "Použít toto nastavení",
        "stay_fees.copy.other": "Nastavit jinak",
        "flash.stay_fees.copy_done": "Poplatek nastaven stejně jako u %(name)s.",
        "flash.stay_fees.copy_failed": "Toto nastavení sem nejde převzít. Nastavte poplatek v nastavení nemovitosti.",
        "invoice.picker.recent": "Nedávné pobyty bez faktury",
        "invoice.picker.other": "Jiný pobyt",
        "invoice.price_use": "Použít poslední cenu: %(price)s Kč",
        "housebook.preset.label": "Rychlý výběr",
        "housebook.preset.this_month": "Tento měsíc",
        "housebook.preset.last_month": "Minulý měsíc",
        "housebook.preset.this_year": "Letos",
        "stay_fees.copy.label": "Převzít nastavení poplatku",
```
   Commit `0844 step 3`.
4. VI: directly below the VI anchor insert (4-space indent):
```python
    "stay_fees.bulk.label": "Tất cả chỗ ở",
    "stay_fees.bulk.confirm": "Xác nhận tất cả kỳ sẵn sàng (%(count)s)",
    "stay_fees.bulk.confirm_ask": "Lưu mọi kỳ sẵn sàng với số liệu đã hiển thị?",
    "stay_fees.bulk.pdfs": "Tải tất cả PDF (%(count)s)",
    "flash.stay_fees.bulk_saved": "Đã lưu kỳ: %(count)s. Bạn có thể tải PDF.",
    "flash.stay_fees.bulk_none": "Không có kỳ nào sẵn sàng để lưu.",
    "stay_fees.copy.title": "Thiết lập giống %(name)s?",
    "stay_fees.copy.use": "Dùng thiết lập này",
    "stay_fees.copy.other": "Thiết lập khác",
    "flash.stay_fees.copy_done": "Đã thiết lập phí giống %(name)s.",
    "flash.stay_fees.copy_failed": "Không thể sao chép thiết lập này. Hãy thiết lập phí trong cài đặt chỗ ở.",
    "invoice.picker.recent": "Lượt lưu trú gần đây chưa có hóa đơn",
    "invoice.picker.other": "Lượt lưu trú khác",
    "invoice.price_use": "Dùng giá gần nhất: %(price)s Kč",
    "housebook.preset.label": "Chọn nhanh",
    "housebook.preset.this_month": "Tháng này",
    "housebook.preset.last_month": "Tháng trước",
    "housebook.preset.this_year": "Năm nay",
    "stay_fees.copy.label": "Sao chép thiết lập phí",
```
   Commit `0844 step 4`.
5. Run §6. Commit.

## 5. Do not touch

Any other key, any template, route or test. No key is deleted or reworded.

## 6. Commands

From `App/`:
1. `.venv/bin/python -c "import app.host_i18n, app.host_vi_i18n" 2>&1 | tail -5` (no output)
2. Copy row: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`

Expected: all pass.

## 7. Acceptance

- [ ] `grep -c '"stay_fees.bulk.confirm"' app/host_i18n.py` prints 2; in `app/host_vi_i18n.py` prints 1. Same for `"housebook.preset.this_year"`.
- [ ] Command 2 passes.

## 8. Stop and ask

Stop, and write the report, if an anchor is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0844-report.md` (300 tokens at most) and set `Status: review`: `git diff --stat`, command 2's last 5 lines, §7 ticked.

## Risk list (for the reviewer)

`App/app/host_i18n.py` (each block landed in the right language dict: the CS lines must sit below the Czech anchor).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green. It must merge before 0845, 0847, 0848, 0849, 0852 and 0853.
