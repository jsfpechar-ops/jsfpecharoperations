# 0022: A guest waiting for a door code is told it also arrives by e-mail

Status: todo
Depends on: PR #325 merged to `main` | Base commit: `main` after PR #325 | Branch: task/0022-guest-door-code-waiting-messages
Executor: Cursor local agent (composer, Kimi or Claude Haiku) | Fits one session

## 1. Objective

On the guest stay page, a guest who finished registering but has no door code yet should read that the code will also be e-mailed to them, and, once it is late, that they should contact their host if they still have no code. Today the page only says "being prepared, reload in a minute" or "taking longer than expected".

## 2. Context

Rules that apply (AGENTS.md): rule 9 (copy: one explanation lives in one place; write "no tracking cookies", never "no cookies"; this brief does not mention cookies), rule 7 (a template change needs the browser and geometry tests with 0 skipped; screenshots are taken by the reviewer, see Owner steps), rule 4 (no dependency).

Decisions already made (do not re-open):
- Owner decision 2026-10-09: the "being prepared" line stays, and the e-mail line goes under it. This replaces 0024's rule that a waiting guest reads only the e-mail line. Nothing the guest reads while waiting may look like a fault.
- The guest gets **no** e-mail when a code could not be created. The new sentence only promises the normal door-code e-mail that is sent when the code exists. That e-mail is sent only when the guest gave an address, so the sentence shows only when the template variable `claim_email_masked` is non-empty (the same variable the "issued" state already uses).
- The sentence is shown in the two waiting states (`preparing` and `delayed`). It is **not** shown in the `failed` state, whose text already says the host will send the code.
- The host's contact details are already on the same page in the "Your host" card right below the door-code card, so the delayed text says "below".
- Languages: English, Czech, German, Spanish, French (`App/app/i18n.py` has five blocks, in that order).

Anchor 1, `App/app/templates/guest/stay.html` (must be found verbatim, exactly once):

```html
      {% elif door_code.state == 'delayed' %}
        <p class="g-intro">{{ t('door_code_delayed') }}</p>
      {% else %}
        <p class="g-intro">{{ t('door_code_preparing') }}</p>
      {% endif %}
```

Anchor 2 to 6, `App/app/i18n.py`: five lines, each found verbatim exactly once, one per language block, in this order in the file.

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

Open before execution (owner to answer): the delayed copy in section 4 still says "taking longer than expected" and "contact your host". Under the decision above, that wording may need to change. Do not execute the delayed copy until the owner has confirmed it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/i18n.py` | edit | Replace five lines (longer delayed text) and add one new key per language |
| `App/app/templates/guest/stay.html` | edit | Show the new sentence in the two waiting states when there is an address |
| `App/tests/test_door_code_guest_messages.py` | create | 12 tests |
| `docs/tasks/0022-report.md` | create | The report (§9) |

No other file may change.

## 4. Steps

1. Run `git status --short`; it must be empty.

2. In `App/app/i18n.py`, replace each of the five anchor lines with the two lines below it (same 8-space indentation, in the same language block). Copy the text exactly.

English:
```python
        "door_code_delayed": "Your door code is taking longer than expected. Your host has been told and will send it to you. If you do not have it soon, contact your host below.",
        "door_code_by_email": "We will also e-mail it to %(email)s as soon as it is ready.",
```
Czech:
```python
        "door_code_delayed": "Váš kód ke dveřím trvá déle, než jsme čekali. Hostitel o tom ví a kód vám pošle. Pokud ho brzy nedostanete, kontaktujte hostitele níže.",
        "door_code_by_email": "Pošleme ho také e-mailem na %(email)s, jakmile bude hotový.",
```
German:
```python
        "door_code_delayed": "Ihr Türcode braucht länger als erwartet. Ihr Gastgeber wurde informiert und schickt ihn Ihnen. Wenn Sie ihn bald nicht haben, kontaktieren Sie Ihren Gastgeber unten.",
        "door_code_by_email": "Wir senden ihn Ihnen außerdem per E-Mail an %(email)s, sobald er fertig ist.",
```
Spanish:
```python
        "door_code_delayed": "Su código de la puerta tarda más de lo esperado. Su anfitrión ha sido avisado y se lo enviará. Si no lo tiene pronto, contacte con su anfitrión más abajo.",
        "door_code_by_email": "También se lo enviaremos por correo a %(email)s en cuanto esté listo.",
```
French:
```python
        "door_code_delayed": "Votre code de porte prend plus de temps que prévu. Votre hôte a été prévenu et vous l'enverra. Si vous ne l'avez pas bientôt, contactez votre hôte ci-dessous.",
        "door_code_by_email": "Nous vous l'enverrons aussi par e-mail à %(email)s dès qu'il sera prêt.",
```

3. In `App/app/templates/guest/stay.html`, replace Anchor 1 with exactly:

```html
      {% elif door_code.state == 'delayed' %}
        <p class="g-intro">{{ t('door_code_delayed') }}</p>
        {% if claim_email_masked %}<p class="g-intro">{{ t('door_code_by_email', email=claim_email_masked) }}</p>{% endif %}
      {% else %}
        <p class="g-intro">{{ t('door_code_preparing') }}</p>
        {% if claim_email_masked %}<p class="g-intro">{{ t('door_code_by_email', email=claim_email_masked) }}</p>{% endif %}
      {% endif %}
```

4. Create `App/tests/test_door_code_guest_messages.py` with exactly this content:

```python
"""Task 0022: a guest waiting for a door code is told the code will also come by e-mail."""
from __future__ import annotations

from pathlib import Path

import pytest

from app import i18n

LANGUAGES = ("en", "cs", "de", "es", "fr")
TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "guest" / "stay.html"


def _text(lang: str, key: str) -> str:
    return i18n.STRINGS[lang][key]


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_language_promises_the_code_by_email_to_the_masked_address(lang):
    assert "%(email)s" in _text(lang, "door_code_by_email")


@pytest.mark.parametrize("lang", LANGUAGES)
def test_the_delayed_text_is_translated_and_longer_than_the_old_one(lang):
    text = _text(lang, "door_code_delayed")
    if lang != "en":
        assert text != _text("en", "door_code_delayed")
    assert text.count(".") >= 2


def test_english_wording_is_exact():
    assert _text("en", "door_code_by_email") == "We will also e-mail it to %(email)s as soon as it is ready."
    assert _text("en", "door_code_delayed").endswith("If you do not have it soon, contact your host below.")


def test_the_page_shows_the_email_line_in_both_waiting_states_only_when_there_is_an_address():
    source = TEMPLATE.read_text(encoding="utf-8")
    line = "{% if claim_email_masked %}<p class=\"g-intro\">{{ t('door_code_by_email', email=claim_email_masked) }}</p>{% endif %}"
    assert source.count(line) == 2
    failed = source.index("door_code.state == 'failed'")
    delayed = source.index("door_code.state == 'delayed'")
    other = source.index("{% else %}", delayed)
    assert source.index(line) > delayed
    assert source.index(line, other) > other
    assert "door_code_by_email" not in source[failed:delayed]
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
Expected last line: `12 passed`.

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

- [ ] `12 passed` in `test_door_code_guest_messages.py`.
- [ ] The browser and geometry command shows 0 skipped and 0 failed (or the report states why it could not run).
- [ ] `git diff --stat` lists only the four files in §3.
- [ ] `grep -c door_code_by_email App/app/i18n.py` prints `5`.
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

Write `docs/tasks/0022-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `stay.html` (the two `{% if claim_email_masked %}` lines must be inside the waiting branches only, never in `failed`) and the five `door_code_delayed` and `door_code_by_email` lines in `i18n.py` (right language in the right block, `%(email)s` intact).

## Owner steps

1. The reviewer takes the screenshots (a claimed stay is needed to see the card): the door-code card in the "being prepared" and "taking longer" states at 360, 390 and 1280 px, once with an e-mail address and once without. The executor does not take them.
2. After merge and deploy, nothing else is needed: the text changes only the guest page.
