# 0240: Stay fee step: one-line intro, signature help behind "?"

Status: todo
Depends on: 0239 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 20 tool calls

## 1. Objective

Owner (Josef, 2026-10-22, on the 390 px wizard shot): the stay fee intro is too much text and the signature's "Optional. The town wants..." paragraph is too long and ugly. Fix: the intro becomes one short sentence (plus the existing skip line); the signature heading says "(optional)" and its explanation moves behind a "?" tip. The fields' own "?" tips already say where to find the rate, symbol and account.

## 2. Context

- `host_i18n.py` defines `entity.signature.*` and `why.stay_fee` twice per language; the LATER definitions win (EN around line 6977 and 7033, CS around 6987 and 7049). Edit only those later lines and the VI ones in `host_vi_i18n.py` around lines 3178 and 3208.
- `help_tip(id, text)` from `_components.html` is already imported in `_entity_business_fields.html`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_entity_business_fields.html` | edit | step 1 |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | step 2 |
| `docs/tasks/0240-report.md` | create | report |

## 4. Steps

1. `App/app/templates/_entity_business_fields.html`, anchor (these two exact lines):

```jinja
    <legend>{{ t('entity.signature.heading') }}</legend>
    <p class="small">{{ t('entity.signature.scope') }}</p>
```

Replace with:

```jinja
    {#- 0240: the why sits behind "?", not in a paragraph. -#}
    <legend>{{ t('entity.signature.heading') }} {{ help_tip(prefix ~ 'signature-help', t('entity.signature.scope')) }}</legend>
```

Commit `0240 step 1`.

2. Replace the VALUE (keep the key and indentation) of these lines:

| File, key (the later definition) | New value |
|---|---|
| host_i18n.py EN `entity.signature.heading` ("Your signature on stay-fee reports") | `Signature (optional)` |
| host_i18n.py EN `entity.signature.scope` ("Optional. The town wants...") | `Printed on every stay-fee report, so you never sign it by hand. Without it, your typed name is printed.` |
| host_i18n.py CS `entity.signature.heading` ("Váš podpis na hlášení poplatku z pobytu") | `Podpis (nepovinné)` |
| host_i18n.py CS `entity.signature.scope` ("Nepovinné. Obec chce...") | `Vytiskne se na každé hlášení poplatku, takže ho nepodepisujete ručně. Bez něj se vytiskne vaše jméno.` |
| host_i18n.py EN `why.stay_fee` ("Most towns charge guests...") | `UbyHost works out the fee for each stay and prepares the report and the payment QR code.` |
| host_i18n.py CS `why.stay_fee` ("Většina obcí vybírá...") | `UbyHost spočítá poplatek u každého pobytu a připraví hlášení i QR kód k platbě.` |
| host_vi_i18n.py `entity.signature.heading` ("Chữ ký của bạn trên báo cáo phí lưu trú") | `Chữ ký (không bắt buộc)` |
| host_vi_i18n.py `entity.signature.scope` ("Không bắt buộc. Thành phố...") | `Được in trên mọi báo cáo phí lưu trú, bạn không cần ký tay. Nếu không có, tên bạn nhập sẽ được in.` |
| host_vi_i18n.py `why.stay_fee` ("Hầu hết các địa phương...") | `UbyHost tính phí cho từng lượt lưu trú và chuẩn bị báo cáo cùng mã QR thanh toán.` |

Keep each file's quote style. Commit `0240 step 2`.

3. Run from `App/` (timeout 600000 ms):

```
.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_stay_fee_signature.py tests/test_fee_setup_compatibility.py tests/test_onboarding_wizard_survival.py tests/test_entity*.py -q --tb=short -p no:cacheprovider 2>&1 | tail -12
```

If `tests/test_entity*.py` matches nothing, drop it. Expected: all passed. A failure that asserts the old wording: quote it in the report and stop (do not edit the test).

## 5. Do not touch

Everything outside section 3. No CSS. Do not run browser tests or screenshots (the orchestrator does).

## 6. Commands

As in section 4.

## 7. Acceptance

- [ ] Step 3 passes.

## 8. Stop and ask

A test fails twice, or an anchor is missing: stop and report the last 30 lines.

## 9. Report

Write `docs/tasks/0240-report.md` (250 tokens at most): commits, step 3 last lines. Set `Status: review`, commit both as `0240 report` (git add those two files only). Do not push.
