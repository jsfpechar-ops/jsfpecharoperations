# 0022: A waiting guest sees a standard status and is told the code comes by e-mail

Status: replaced by 0024 (owner decision 2026-10-09)
Depends on: PR #325 merged to `main` | Base commit: `main` after PR #325 | Branch: task/0022-guest-door-code-waiting-messages
Executor: Cursor local agent (composer, Kimi or Claude Haiku) | Fits one session

> Replaced by brief 0024 (`claude/charming-feynman-k7oear`). Do not run this brief. 0024 is the only brief that changes the guest waiting copy: while the code is not there, the guest sees only "You will receive your door code by e-mail."

## 1. Objective

On the guest stay page, a guest whose door code is not ready yet must see a standard status, not a problem. The status "Your door code is being prepared." stays. Under it, the guest reads that the code will also be e-mailed to them. If the code is still not there after the normal wait, the card says "You will receive your passcode in your email." The lines "Reload this page in a minute" and "taking longer than expected" are removed everywhere, and nothing on the waiting card reads as a fault.

## 2. Context

Rules that apply (AGENTS.md): rule 9 (copy: one explanation lives in one place; write "no tracking cookies", never "no cookies"; this brief does not mention cookies), rule 7 (a template change needs the browser and geometry tests with 0 skipped; screenshots are taken by the reviewer, see Owner steps), rule 4 (no dependency).

Decisions already made (do not re-open):
- Owner decision 2026-10-09 (revised): the "being prepared" line stays. The e-mail line goes under it. The late-code line is "You will receive your passcode in your email." This replaces the earlier "taking longer than expected" text and the reload line. It also replaces the rule in brief 0024 that a waiting guest reads only the e-mail line.
- The guest gets **no** e-mail when a code could not be created. The e-mail promise shows only when the template variable `claim_email_masked` is non-empty (the same variable the "issued" state already uses). Guests always give an address, so the late state shows the passcode sentence without a condition.
- The e-mail line is not shown in the late state. The late sentence already says e-mail, and one explanation lives in one place (rule 9).
- The `failed` state is unchanged. Its text already says the host will send the code.
- Languages: English, Czech, German, Spanish, French (`App/app/i18n.py` has five blocks, in that order).

Anchor 1, `App/app/i18n.py`: five lines, each found verbatim exactly once, one per language block, in this order in the file. `door_code_by_email` must not exist yet (check it in step 1).

English:
```python
        "door_code_preparing": "Your door code is being prepared. Reload this page in a minute.",
```
Czech:
```python
        "door_code_preparing": "Váš kód ke dveřím se připravuje. Za minutu tuto stránku obnovte.",
```
German:
```python
        "door_code_preparing": "Ihr Türcode wird vorbereitet. Laden Sie diese Seite in einer Minute neu.",
```
Spanish:
```python
        "door_code_preparing": "Estamos preparando su código de la puerta. Vuelva a cargar esta página en un minuto.",
```
French:
```python
        "door_code_preparing": "Votre code de porte est en préparation. Rechargez cette page dans une minute.",
```

Anchor 2, `App/app/i18n.py`: five lines, same rules.

English:
```python
        "door_code_delayed": "Your door code is taking longer than expected. Your host has been told and will send it to you.",
```
Czech:
```python
        "door_code_delayed": "Váš kód ke dveřím trvá déle, než jsme čekali. Hostitel o tom ví a kód vám pošle.",
```
German:
```python
        "door_code_delayed": "Ihr Türcode braucht länger als erwartet. Ihr Gastgeber wurde informiert und schickt ihn Ihnen.",
```
Spanish:
```python
        "door_code_delayed": "Su código de la puerta tarda más de lo esperado. Su anfitrión ha sido avisado y se lo enviará.",
```
French:
```python
        "door_code_delayed": "Votre code de porte prend plus de temps que prévu. Votre hôte a été prévenu et vous l'enverra.",
```

Anchor 3, `App/app/templates/guest/stay.html` (must be found verbatim, exactly once):

```html
      {% elif door_code.state == 'delayed' %}
        <p class="g-intro">{{ t('door_code_delayed') }}</p>
      {% else %}
        <p class="g-intro">{{ t('door_code_preparing') }}</p>
      {% endif %}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/i18n.py` | edit | Replace the 10 anchor lines (preparing and delayed, 5 languages); add one `door_code_by_email` line per language |
| `App/app/templates/guest/stay.html` | edit | Waiting states: status, e-mail line under it when there is an address, late sentence |
| `App/tests/test_door_code_guest_messages.py` | create | The tests in step 4 |
| `docs/tasks/0022-report.md` | create | The report (§9) |

No other file may change.

## 4. Steps

1. Run `git status --short`; it must be empty. Run `grep -c door_code_by_email App/app/i18n.py`; it must print `0`.

2. In `App/app/i18n.py`, replace each preparing anchor (Anchor 1) with the two lines below it, and each delayed anchor (Anchor 2) with the one line below it. Same 8-space indentation, same language block. Copy the text exactly.

English:
```python
        "door_code_preparing": "Your door code is being prepared.",
        "door_code_by_email": "We will also e-mail it to %(email)s as soon as it is ready.",
```
```python
        "door_code_delayed": "You will receive your passcode in your email.",
```
Czech:
```python
        "door_code_preparing": "Váš kód ke dveřím se připravuje.",
        "door_code_by_email": "Pošleme ho také e-mailem na %(email)s, jakmile bude hotový.",
```
```python
        "door_code_delayed": "Kód ke dveřím vám přijde e-mailem.",
```
German:
```python
        "door_code_preparing": "Ihr Türcode wird vorbereitet.",
        "door_code_by_email": "Wir senden ihn Ihnen außerdem per E-Mail an %(email)s, sobald er fertig ist.",
```
```python
        "door_code_delayed": "Den Türcode erhalten Sie per E-Mail.",
```
Spanish:
```python
        "door_code_preparing": "Estamos preparando su código de la puerta.",
        "door_code_by_email": "También se lo enviaremos por correo a %(email)s en cuanto esté listo.",
```
```python
        "door_code_delayed": "Recibirá el código de la puerta en su correo electrónico.",
```
French:
```python
        "door_code_preparing": "Votre code de porte est en préparation.",
        "door_code_by_email": "Nous vous l'enverrons aussi par e-mail à %(email)s dès qu'il sera prêt.",
```
```python
        "door_code_delayed": "Vous recevrez le code de porte par e-mail.",
```

3. In `App/app/templates/guest/stay.html`, replace Anchor 3 with exactly:

```html
      {% elif door_code.state == 'delayed' %}
        <p class="g-intro">{{ t('door_code_delayed') }}</p>
      {% else %}
        <p class="g-intro">{{ t('door_code_preparing') }}</p>
        {% if claim_email_masked %}<p class="g-intro">{{ t('door_code_by_email', email=claim_email_masked) }}</p>{% endif %}
      {% endif %}
```

4. Create `App/tests/test_door_code_guest_messages.py` with exactly this content:

```python
"""Task 0022: a waiting guest sees a standard status and the e-mail promise, never a fault."""
from __future__ import annotations

from pathlib import Path

import pytest

from app import i18n

LANGUAGES = ("en", "cs", "de", "es", "fr")
TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "guest" / "stay.html"

EXPECTED = {
    "door_code_preparing": {
        "en": "Your door code is being prepared.",
        "cs": "Váš kód ke dveřím se připravuje.",
        "de": "Ihr Türcode wird vorbereitet.",
        "es": "Estamos preparando su código de la puerta.",
        "fr": "Votre code de porte est en préparation.",
    },
    "door_code_delayed": {
        "en": "You will receive your passcode in your email.",
        "cs": "Kód ke dveřím vám přijde e-mailem.",
        "de": "Den Türcode erhalten Sie per E-Mail.",
        "es": "Recibirá el código de la puerta en su correo electrónico.",
        "fr": "Vous recevrez le code de porte par e-mail.",
    },
}


def _text(lang: str, key: str) -> str:
    return i18n.STRINGS[lang][key]


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_waiting_copy_is_exact(lang, key):
    assert _text(lang, key) == EXPECTED[key][lang]


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_language_promises_the_code_by_email_to_the_masked_address(lang):
    assert "%(email)s" in _text(lang, "door_code_by_email")


def test_english_email_line_is_exact():
    assert _text("en", "door_code_by_email") == "We will also e-mail it to %(email)s as soon as it is ready."


def test_no_waiting_copy_says_reload_or_taking_longer():
    for lang in LANGUAGES:
        for key in EXPECTED:
            assert "taking longer" not in _text(lang, key).lower()
            assert "reload" not in _text(lang, key).lower()
            assert "Rechargez" not in _text(lang, key)


def test_the_waiting_states_show_the_e_mail_line_only_when_there_is_an_address():
    source = TEMPLATE.read_text(encoding="utf-8")
    late_line = "<p class=\"g-intro\">{{ t('door_code_delayed') }}</p>"
    email_line = "{% if claim_email_masked %}<p class=\"g-intro\">{{ t('door_code_by_email', email=claim_email_masked) }}</p>{% endif %}"
    assert source.count(email_line) == 1
    assert source.count(late_line) == 1
    failed = source.index("door_code.state == 'failed'")
    delayed = source.index("door_code.state == 'delayed'")
    else_branch = source.index("{% else %}", delayed)
    assert failed < delayed < source.index(late_line) < else_branch < source.index(email_line)
    assert "door_code_by_email" not in source[failed:delayed]
    assert "door_code_by_email" not in source[delayed:else_branch]
```

5. Run the commands in §6 and write the report (§9).

## 5. Do not touch

- Any other key in `i18n.py`, any other template, any CSS or JavaScript.
- `App/app/door_codes.py`, `App/app/mail_notify.py`, `App/app/host_i18n.py`.
- `docs/context/*` and `docs/privacy/*`.
- AGENTS.md rules that apply: 7 (guest page change), 9 (copy), 8 (never push to `main`; open one PR).

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_door_code_guest_messages.py -q
```
Expected: all tests in the file pass.

```
.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_wp28_geometry.py tests/test_download_skeleton_browser.py -q -rs
```
Expected: all pass and **no** `SKIPPED` line. If any test is skipped (for example "No module named playwright"), do not install anything: write the skipped list in the report and go to §8.

```
.venv/bin/python -m pytest tests -q
```
Expected: 0 failed, apart from at most these 4 which fail in a sandbox without outbound DNS and fail the same way on `main`: `test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses`, `test_feed_url_ssrf.py::test_redirects_are_revalidated_not_followed_blindly`, `test_feed_url_ssrf.py::test_a_redirect_that_drops_https_is_refused`, `test_feed_url_ssrf.py::test_allows_public_https_calendar`.

From the repo root:

```
python3 scripts/context_lint.py
```
Expected last line: `context lint: OK`.

## 7. Acceptance

- [ ] All tests in `test_door_code_guest_messages.py` pass.
- [ ] The browser and geometry command shows 0 skipped and 0 failed (or the report states why it could not run).
- [ ] `git diff --stat` lists only the four files in §3.
- [ ] `grep -c door_code_by_email App/app/i18n.py` prints `5`.
- [ ] `grep -c "Reload this page\|Rechargez\|taking longer" App/app/i18n.py` prints `0`.
- [ ] `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in §2 is not found exactly once;
- a test fails twice after you re-read your edit against §4;
- the browser or geometry tests are skipped or fail;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

`docs/tasks/0022-report.md` (1,500 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

Read the diff of `stay.html` (the late-state line must be the plain delayed line, and the e-mail line must sit inside the "being prepared" branch only, never in `failed` or the late state) and the `door_code_preparing`, `door_code_by_email` and `door_code_delayed` lines in `i18n.py` (right language in the right block, `%(email)s` intact). The Czech, German, Spanish and French lines are new translations and need a native-speaker read before merge.

## Open before execution (owner)

1. The English late line says "passcode" (owner's wording). The rest of the guest page says "door code". Confirm "passcode", or change it to "door code" in the English line and the test.

## Owner steps

1. The reviewer takes the screenshots (a claimed stay is needed to see the card): the door-code card in the "being prepared" state and the late state, at 360, 390 and 1280 px, with an e-mail address. The executor does not take them.
2. After merge and deploy, nothing else is needed: the text changes only the guest page.
