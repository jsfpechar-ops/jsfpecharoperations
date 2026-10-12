# 0068: TTLock is the host's own provider (copy)

Status: todo
Depends on: none (may run before or after 0067; no shared lines) | Base commit: f55e156 | Branch: task/0068-ttlock-host-provider-copy
Executor: Cursor local agent (composer; copy and one tuple move) | Fits one session

## 1. Objective

TTLock told us it stores EU data in Germany and does not think it meets GDPR standards, so no SCCs exist. The owner approved the position that TTLock is the host's own lock provider, not a UbyHost subprocessor ([DOOR_CODES_LEGAL](../privacy/DOOR_CODES_LEGAL.md) §1, §3); the door-code terms, the public register and the guest privacy notice still say "subprocessor" and "SCCs" and must say what is true.

## 2. Context

- Legal source: [DOOR_CODES_LEGAL](../privacy/DOOR_CODES_LEGAL.md) §1 (roles), §3 (instruction, duty to warn), §5 (guest notice). This brief owns the copy of `guide.door_codes.terms4`, `guide.door_codes.terms5`, `subprocessors.recipient_ttlock` and `privacy_door_code_body`.
- Rule 2: no new outbound request, no new personal-data field. Rule 7: `guide.html` changes, so the browser and geometry tests run with 0 skipped, plus screenshots. Rule 9.
- DPA §11 never named TTLock: `dpa_i18n.py` does not change.
- The only connected host is the owner, so bumping the terms version needs no re-accept flow.

Anchor A, `App/app/ttlock.py`. Found verbatim once:

```python
DOOR_CODE_TERMS_VERSION = "2026-10-08"
```

Anchor B, `App/app/templates/guide.html`. Found verbatim once:

```html
      <p class="small muted">{{ t('guide.door_codes.terms_version', version='2026-10-08') }}</p>
```

Anchor C, `App/app/routes/legal.py`. Found verbatim once each:

```python
    "google",
    "ttlock",
)
```

```python
RECIPIENT_IDS = ("google_ads", "meta_ads", "police", "municipality")
```

Anchor D, `App/app/guide_i18n.py`: the `en` and `cs` lines starting `        "guide.door_codes.terms4":` and `        "guide.door_codes.terms5":` (one of each per language, 4 lines). Each line is quoted in full in Step 4.

Anchor E, `App/app/subprocessors_i18n.py`, `en` block: the five lines starting `        "subprocessors.ttlock_` (provider, purpose, data, location, safeguard), and in the `cs` block the same five keys. Then in each block this entry, found verbatim once per language:

```python
        "subprocessors.recipient_municipality": (
            "The municipality (stay-fee reports, if the host uses that feature)"
        ),
```

```python
        "subprocessors.recipient_municipality": (
            "Obec (hlášení k poplatku z pobytu, pokud ubytovatel tuto funkci používá)"
        ),
```

Anchor F, `App/app/i18n.py`, key `privacy_door_code_body`, once each in `en`, `cs`, `de`, `es`, `fr`. Step 6 quotes the exact sentence to replace in each.

If any anchor is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/ttlock.py` | edit | Step 1 |
| `App/app/templates/guide.html` | edit | Step 2 |
| `App/app/routes/legal.py` | edit | Step 3 |
| `App/app/guide_i18n.py` | edit | Step 4 |
| `App/app/subprocessors_i18n.py` | edit | Step 5 |
| `App/app/i18n.py` | edit | Step 6 |
| `App/tests/test_ttlock_host_provider.py` | create | Step 7 |

No other file may change.

## 4. Steps

1. `ttlock.py`: replace anchor A with `DOOR_CODE_TERMS_VERSION = "2026-10-12"`.

2. `guide.html`: in anchor B change `version='2026-10-08'` to `version='2026-10-12'`. Nothing else on the line.

3. `legal.py`: in `SUBPROCESSOR_IDS` delete the line `    "ttlock",` (the tuple then ends with `    "google",` and `)`). Replace the `RECIPIENT_IDS` line with:

```python
RECIPIENT_IDS = ("google_ads", "meta_ads", "police", "municipality", "ttlock")
```

4. `guide_i18n.py`: replace these four lines exactly.

`en` terms4, old:

```python
        "guide.door_codes.terms4": "TTLock is a service of Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China). By setting up smart locks you authorise UbyHost to use it as a subprocessor for door codes (DPA, section 11). UbyHost sends it the lock ID, the code's validity times and a reference number, never guest names or contact details, and uses the EU Standard Contractual Clauses for any transfer outside the EEA.",
```

new:

```python
        "guide.door_codes.terms4": "TTLock is your own lock provider, a service of Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China); it is not a UbyHost subprocessor. By setting up smart locks you instruct UbyHost to send it, on your behalf, the lock ID, each code's validity times and a reference number, never guest names or contact details. TTLock stores EU data in Germany, but has told us it does not consider itself to meet GDPR standards. Your relationship with TTLock, including any transfer outside the EEA, is yours.",
```

`en` terms5: in that line replace `UbyHost uses its own TTLock account for you and never sees your TTLock password.` with `UbyHost works on your locks as an authorized admin you appoint, through a TTLock account it makes for you, and never sees your TTLock password.` The rest of the line stays.

`cs` terms4, old:

```python
        "guide.door_codes.terms4": 'TTLock je služba společnosti Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Čína). Nastavením chytrých zámků UbyHost pověřujete, aby ji pro kódy ke dveřím využíval jako dalšího zpracovatele (smlouva o zpracování, článek 11). UbyHost jí posílá ID zámku, dobu platnosti kódu a referenční číslo, nikdy jména ani kontakty hostů, a pro předání mimo EHP používá standardní smluvní doložky EU.',
```

new:

```python
        "guide.door_codes.terms4": 'TTLock je váš vlastní poskytovatel zámků, služba společnosti Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Čína); není dalším zpracovatelem UbyHost. Nastavením chytrých zámků dáváte UbyHost pokyn, aby mu vaším jménem posílal ID zámku, dobu platnosti každého kódu a referenční číslo, nikdy jména ani kontakty hostů. TTLock ukládá údaje z EU v Německu, ale sdělil nám, že podle svého názoru standardům GDPR nevyhovuje. Váš vztah s TTLock, včetně případného předání mimo EHP, je vaší věcí.',
```

`cs` terms5: in that line replace `UbyHost pro vás používá vlastní účet TTLock a vaše heslo TTLock nikdy nevidí.` with `UbyHost pracuje na vašich zámcích jako pověřený správce, kterého jmenujete, přes účet TTLock, který pro vás vytvoří, a vaše heslo TTLock nikdy nevidí.` The rest of the line stays.

5. `subprocessors_i18n.py`: in both `en` and `cs`, delete the five `"subprocessors.ttlock_..."` lines. Then directly after the `recipient_municipality` entry (anchor E) insert, in `en`:

```python
        "subprocessors.recipient_ttlock": (
            "TTLock (Hangzhou Sciener Intelligent Control Technology Co., Ltd., China; data stored "
            "in Germany): the host's own lock provider, only for properties with door codes on. On "
            "the host's instruction UbyHost sends it the lock ID, the code's validity times and a "
            "reference number, no guest names or contact details"
        ),
```

and in `cs`:

```python
        "subprocessors.recipient_ttlock": (
            "TTLock (Hangzhou Sciener Intelligent Control Technology Co., Ltd., Čína; údaje uložené "
            "v Německu): vlastní poskytovatel zámků ubytovatele, jen u ubytování se zapnutými kódy "
            "ke dveřím. Na pokyn ubytovatele mu UbyHost posílá ID zámku, dobu platnosti kódu a "
            "referenční číslo, žádná jména ani kontakty hostů"
        ),
```

Then run `grep -rn 'subprocessors.ttlock_' App/` and expect no output.

6. `i18n.py`, `privacy_door_code_body`: in each language replace only the sentence shown; the rest of the string stays.

- `en`, old: `The code is created through TTLock, a service of Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), which receives the lock, the code, its validity times and a reference number, but not your name or contact details.`
  new: `The code is created in TTLock, the host's lock system, a service of Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China). TTLock receives the lock, the code, its validity times and a reference number, but not your name or contact details. It stores this data on servers in Germany; the company is based in China, for which the EU has no adequacy decision.`
- `cs`, old: `Kód vzniká přes TTLock, službu společnosti Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Čína), která dostane zámek, kód, dobu jeho platnosti a referenční číslo, nikoli vaše jméno ani kontakty.`
  new: `Kód vzniká v TTLock, zámkovém systému hostitele, službě společnosti Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Čína). TTLock dostane zámek, kód, dobu jeho platnosti a referenční číslo, nikoli vaše jméno ani kontakty. Tyto údaje ukládá na serverech v Německu; společnost sídlí v Číně, pro kterou EU nevydala rozhodnutí o odpovídající ochraně.`
- `de`, old: `Der Code wird über TTLock erstellt, einen Dienst der Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), die das Schloss, den Code, seine Gültigkeitszeiten und eine Referenznummer erhält, aber nicht Ihren Namen oder Ihre Kontaktdaten.`
  new: `Der Code wird in TTLock erstellt, dem Schließsystem des Gastgebers, einem Dienst der Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China). TTLock erhält das Schloss, den Code, seine Gültigkeitszeiten und eine Referenznummer, aber nicht Ihren Namen oder Ihre Kontaktdaten. Es speichert diese Daten auf Servern in Deutschland; das Unternehmen hat seinen Sitz in China, für das kein Angemessenheitsbeschluss der EU besteht.`
- `es`, old: `El código se crea a través de TTLock, un servicio de Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), que recibe la cerradura, el código, sus horas de validez y un número de referencia, pero no su nombre ni sus datos de contacto.`
  new: `El código se crea en TTLock, el sistema de cerraduras del anfitrión, un servicio de Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China). TTLock recibe la cerradura, el código, sus horas de validez y un número de referencia, pero no su nombre ni sus datos de contacto. Guarda estos datos en servidores en Alemania; la empresa tiene su sede en China, para la que no existe una decisión de adecuación de la UE.`
- `fr`, old: `Le code est créé via TTLock, un service de Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Chine), qui reçoit la serrure, le code, ses horaires de validité et un numéro de référence, mais ni votre nom ni vos coordonnées.`
  new: `Le code est créé dans TTLock, le système de serrures de l'hôte, un service de Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Chine). TTLock reçoit la serrure, le code, ses horaires de validité et un numéro de référence, mais ni votre nom ni vos coordonnées. Il conserve ces données sur des serveurs en Allemagne ; l'entreprise est établie en Chine, pour laquelle l'UE n'a pas adopté de décision d'adéquation.`

7. Create `App/tests/test_ttlock_host_provider.py`:

```python
"""0068: TTLock is the host's own lock provider, not a UbyHost subprocessor."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import db, i18n, ttlock
from app.guide_i18n import GUIDE_STRINGS
from app.main import app
from app.routes import legal
from app.subprocessors_i18n import SUBPROCESSOR_STRINGS


def _get(path: str) -> str:
    db.init_db()
    response = TestClient(app).get(path)
    assert response.status_code == 200, path
    return response.text


def test_ttlock_is_a_recipient_not_a_subprocessor():
    assert "ttlock" not in legal.SUBPROCESSOR_IDS
    assert "ttlock" in legal.recipient_ids()
    for lang in ("en", "cs"):
        strings = SUBPROCESSOR_STRINGS[lang]
        assert not [k for k in strings if k.startswith("subprocessors.ttlock_")], lang
        html = _get(f"/subprocessors?lang={lang}")
        assert strings["subprocessors.recipient_ttlock"].replace("'", "&#39;") in html, lang


def test_terms_name_the_host_as_ttlocks_customer_and_carry_no_scc_promise():
    assert ttlock.DOOR_CODE_TERMS_VERSION == "2026-10-12"
    for lang in ("en", "cs"):
        terms4 = GUIDE_STRINGS[lang]["guide.door_codes.terms4"]
        assert "GDPR" in terms4, lang
        assert "Standard Contractual" not in terms4 and "smluvní doložky" not in terms4, lang


def test_guest_notice_states_storage_and_no_adequacy():
    for lang, word in (("en", "Germany"), ("cs", "Německu"), ("de", "Deutschland"),
                       ("es", "Alemania"), ("fr", "Allemagne")):
        assert word in i18n.STRINGS[lang]["privacy_door_code_body"], lang
```

## 5. Do not touch

`App/app/dpa_i18n.py`, `App/app/privacy_policy_i18n.py`, `App/app/door_codes.py`, every i18n key not named in §2, `App/tests/test_privacy_legal_positions.py`. Hard rules 2, 3, 7, 8, 9 apply.

## 6. Commands

From `App/`:

```
grep -rn 'subprocessors.ttlock_\|Standard Contractual Clauses for any transfer' app/   # expect no output
.venv/bin/python -m pytest tests/test_ttlock_host_provider.py tests/test_privacy_legal_positions.py -q   # expect all pass
.venv/bin/python -m pytest tests -q   # expect all pass, browser and geometry tests 0 skipped
```

From the repo root: `python3 scripts/context_lint.py` (expect OK).

## 7. Acceptance

- [ ] The grep gives no output.
- [ ] Both test runs pass; browser and geometry tests ran with 0 skipped.
- [ ] Screenshots at 360, 390 and 1280 px of: `/guide` door-code terms section (en), `/subprocessors?lang=en` recipients panel, a guest privacy page of a property with door codes on (cs).
- [ ] `git diff --stat` lists only the files in §3.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0068-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/routes/legal.py`: the tuple move only.
- `App/app/guide_i18n.py`, `App/app/i18n.py`: only the named sentences; quotes and escapes intact.
- `App/app/subprocessors_i18n.py`: no `ttlock_` keys left; nothing else removed.

## Owner steps

1. Open the PR the executor pushed and check that CI is green.
2. Merge it with `scripts/merge-pr-on-green.sh <PR number>`.
3. On the Smart locks page, accept the 2026-10-12 terms again if UbyHost asks.
