# 0208: Privacy policy and recipient list for urgent alerts

Status: todo
Depends on: 0207 | Base commit: HEAD of the branch | Branch: claude/project-thread-w35ftw
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

## 1. Objective

Tell hosts in the privacy policy (EN, CS) what urgent alerts store, who delivers them and how long they are kept, and list the push services on /subprocessors as recipients that are not subprocessors. The position is in `docs/UbyHost_workplan/04_legal_positions.md` section 7. Wording is fixed; copy it exactly.

## 2. Context

- `App/app/privacy_policy_i18n.py`: each anchor in step 1 occurs exactly once (checked). Bodies are %-formatted; the new text has no `%`.
- `App/app/routes/legal.py`, verbatim:

```python
RECIPIENT_IDS = ("google_ads", "meta_ads", "police", "municipality", "ttlock")


def recipient_ids() -> tuple:
    hidden = set()
    if not signup.enabled():
```

- `App/app/subprocessors_i18n.py`: `"subprocessors.recipient_ttlock": (` occurs once under `"en"` and once under `"cs"`; each entry ends with a line `        ),`.
- `config.WEB_PUSH` is the alerts on/off switch (`UBYHOST_WEB_PUSH`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/privacy_policy_i18n.py` | edit | step 1 |
| `App/app/subprocessors_i18n.py` | edit | step 2 |
| `App/app/routes/legal.py` | edit | step 3 |
| `App/tests/test_privacy_legal_positions.py` | edit | step 4 |
| `docs/tasks/0208-push-privacy-text.md`, `docs/tasks/0208-report.md` | edit/create | Status, report |

No other file may change. `PRIVACY_VERSION` stays as it is (decision in section 7).

## 4. Steps

**Step 1.** In `App/app/privacy_policy_i18n.py` make these eight replacements with one python script that asserts each `old` occurs exactly once (use the strings exactly as below, including the leading/trailing quote characters shown):

1. old `of data about themselves unless you voluntarily include such information in free-text fields."`
   new `of data about themselves unless you voluntarily include such information in free-text fields. If you turn on urgent alerts on a device, we also keep that device's push address and keys (encrypted), its language, its device family (such as \"iPhone\"), the time of its last visit, and the alerts queued for it."`
2. old `is opened only over HTTPS for a limited period."`
   new `is opened only over HTTPS for a limited period. If you install the app or turn on urgent alerts, the browser also stores a small service worker, a copy of the offline page and the push subscription; this happens only at your request and is needed for that feature."`
3. old `Material changes are published there and reflected in this Policy."`
   new `Material changes are published there and reflected in this Policy. Urgent alerts you turn on are delivered through the push service of your browser's maker (Apple for Safari on iPhone, Google for Chrome, Mozilla for Firefox, Microsoft for Edge). Your browser chooses that service, not us. It receives each alert end-to-end encrypted, with the device address, the time and our contact address, and cannot read the text. It is a recipient under the browser maker's own terms, may process data outside the EEA, and is not our subprocessor. Alerts name the property and a date, never a guest."`
4. old `"logs are kept for 3 years. Guest Data "`
   new `"logs are kept for 3 years. Urgent-alert devices are deleted when you turn alerts off, remove the device or log out on it, or after 180 days without a visit; queued alerts after 30 days. Guest Data "`
5. old `Zvláštní kategorie údajů o ubytovateli nevyžadujeme, pokud je sami nezadáte v textových polích."`
   new `Zvláštní kategorie údajů o ubytovateli nevyžadujeme, pokud je sami nezadáte v textových polích. Pokud na zařízení zapnete naléhavá upozornění, uchováváme také push adresu a klíče tohoto zařízení (šifrovaně), jeho jazyk, typ zařízení (např. „iPhone“), čas poslední návštěvy a upozornění pro něj připravená."`
6. old `Transport Security (HSTS), takže se tato doména po omezenou dobu otevírá jen přes HTTPS."`
   new `Transport Security (HSTS), takže se tato doména po omezenou dobu otevírá jen přes HTTPS. Pokud si aplikaci nainstalujete nebo zapnete naléhavá upozornění, prohlížeč uloží také malý service worker, kopii offline stránky a push odběr; děje se to jen na vaši žádost a je to pro tuto funkci nezbytné."`
7. old `jsou na /subprocessors. Podstatné změny zveřejníme tam a promítneme do těchto Zásad."`
   new `jsou na /subprocessors. Podstatné změny zveřejníme tam a promítneme do těchto Zásad. Naléhavá upozornění, která zapnete, doručuje push služba výrobce vašeho prohlížeče (Apple u Safari na iPhonu, Google u Chrome, Mozilla u Firefoxu, Microsoft u Edge). Tuto službu volí váš prohlížeč, ne my. Každé upozornění dostává koncově šifrované, s adresou zařízení, časem a naší kontaktní adresou, a jeho text přečíst nemůže. Je příjemcem podle podmínek výrobce prohlížeče, může údaje zpracovávat mimo EHP a není naším subzpracovatelem. Upozornění uvádí ubytování a datum, nikdy jméno hosta."`
8. old `"účtu. Auditní záznamy se uchovávají 3 roky. Údaje hostů řídí nastavení a povinnosti "`
   new `"účtu. Auditní záznamy se uchovávají 3 roky. Zařízení s naléhavými upozorněními mažeme při vypnutí upozornění, odebrání zařízení nebo odhlášení na něm, nebo po 180 dnech bez návštěvy; připravená upozornění po 30 dnech. Údaje hostů řídí nastavení a povinnosti "`

In replacement 1 the `\"` is a backslash-escaped quote inside the Python string literal in the file (write the two characters `\` and `"`). Then `cd App && .venv/bin/python -c "import app.privacy_policy_i18n"`. Commit `0208 step 1`.

**Step 2.** In `App/app/subprocessors_i18n.py`, directly before each `"subprocessors.recipient_ttlock": (` line, insert (EN block under `"en"`, CS under `"cs"`):

EN:
```python
        "subprocessors.recipient_push": (
            "The push service of the host's browser maker (Apple, Google, Mozilla or Microsoft): "
            "delivers urgent alerts the host turned on, end-to-end encrypted; chosen by the "
            "browser, not by UbyHost; no guest names"
        ),
```

CS:
```python
        "subprocessors.recipient_push": (
            "Push služba výrobce prohlížeče ubytovatele (Apple, Google, Mozilla nebo Microsoft): "
            "doručuje naléhavá upozornění, která ubytovatel zapnul, koncově šifrovaná; volí ji "
            "prohlížeč, ne UbyHost; žádná jména hostů"
        ),
```

Commit `0208 step 2`.

**Step 3.** In `App/app/routes/legal.py` replace the §2 block with:

```python
RECIPIENT_IDS = ("google_ads", "meta_ads", "police", "municipality", "ttlock", "push")


def recipient_ids() -> tuple:
    hidden = set()
    if not config.WEB_PUSH:
        hidden.add("push")
    if not signup.enabled():
```

and add one comment line directly above `RECIPIENT_IDS`: `# "push" (0208) is listed only while urgent alerts are on (UBYHOST_WEB_PUSH).` Commit `0208 step 3`.

**Step 4.** Append to `App/tests/test_privacy_legal_positions.py`:

```python


def test_urgent_alerts_are_explained_and_their_push_services_listed(monkeypatch):
    """04_legal_positions.md section 7: recipients, storage and retention."""
    for lang, word in (("en", "Urgent-alert devices"), ("cs", "naléhavými upozorněními")):
        html = _get(f"/privacy?lang={lang}")
        assert "Mozilla" in html and "180" in html and word in html, lang
        monkeypatch.setattr(config, "WEB_PUSH", True)
        html = _get(f"/subprocessors?lang={lang}")
        assert SUBPROCESSOR_STRINGS[lang]["subprocessors.recipient_push"][:20] in html, lang
        monkeypatch.setattr(config, "WEB_PUSH", False)
        html = _get(f"/subprocessors?lang={lang}")
        assert SUBPROCESSOR_STRINGS[lang]["subprocessors.recipient_push"][:20] not in html, lang
```

If an assertion fails only because the page HTML-escapes a character in the first 20 characters, STOP and report (do not change the wording). Commit `0208 step 4`.

## 5. Do not touch

Everything not in §3; `config.py` (`PRIVACY_VERSION`, effective date); templates.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_privacy_legal_positions.py tests/test_privacy_*.py tests/test_no_em_dashes.py tests/test_owner_decisions.py tests/test_operator_naming.py -q --tb=short 2>&1 | tail -30` → all pass.
2. From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v ^WARN | tail -3` → OK.

## 7. Acceptance

- [ ] Commands pass. `grep -c "Mozilla" App/app/privacy_policy_i18n.py` prints 2.

## 8. Stop and ask

An anchor not found exactly once, or any test failure: stop and report.

## 9. Report

`docs/tasks/0208-report.md` (under 1500 tokens): commits, §6 last lines, deviations. Set Status to `review` or `blocked`. Commit.
