# 0388: Leon is "your 24/7 concierge", not "the host's AI assistant"

Status: todo
Depends on: 0387 (same branch, not merged) | Base commit: HEAD of claude/0387-leon-chat-look | Branch: claude/0387-leon-chat-look (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Owner (Josef, 2026-10-25): "Not ai assistant, 24/7 concierge, and make him sound like that." Leon's guest-facing copy changes from "the host's AI assistant" to "your 24/7 concierge" in all six guest languages (en, cs, de, es, fr, uk). AI disclosure stays (EU AI Act Art. 50): the name in bubbles becomes plain "Leon", and the card header shows a small "AI" tag next to the name, with "24/7 concierge" under it. When a guest asks whether Leon is a person, `leon_about` still says plainly that he is an AI. The first line of his prompt changes to match. Nothing else in the prompt changes.

## 2. Context

- `App/app/i18n.py`: per-language dicts `"en"` (~104), `"cs"` (~752), `"de"` (~1387), `"es"` (~1802), `"fr"` (~2217). Keys `leon_name`, `leon_hi`, `leon_about`, `leon_ask`, `leon_intro`, `leon_needs_js`. `App/app/guest_uk_i18n.py` has the same keys for uk (~442-510).
- `App/app/templates/guest/_leon.html` (after 0387): `<div class="g-leon-head-text"><h2 id="leon-title">{{ t('leon_name') }}</h2><p class="g-intro">{{ t('leon_intro') }}</p></div>`.
- `App/app/leon.py` ~66: `CHARACTER = """You are Leon (AI), the guest assistant of one holiday rental. You are an AI, not a person, and say so when asked: the host's AI assistant, through whom the host can always be reached.`
- Tests that assert old copy: grep `App/tests/` for `Leon (AI)`, `AI assistant`, `AI asistent`, `KI-Assistent`, `asistente de IA`, `assistant IA`, `ШІ-помічник`, `Leon (KI)`, `Leon (IA)`, `Leon (ШІ)`. Known: `test_guest_leon_chat.py:78` asserts `"Leon (AI)" in body`. Host-side strings such as "Not read by Leon (AI)" (host pages) are NOT part of this brief. Leave them and their tests alone.
- Copy rule: no em dashes.

## 3. Files

| Path | Action |
|---|---|
| App/app/i18n.py | values below, 1 new key per language |
| App/app/guest_uk_i18n.py | values below, 1 new key |
| App/app/templates/guest/_leon.html | header markup |
| App/app/static/guest.css | append 2 rules |
| App/app/templates/guest/base.html | bump guest.css `?v=` to `20261025-0388` |
| App/tests/static_versions.json | `--write` |
| App/app/leon.py | first line of CHARACTER only |
| App/tests/* | only assertions of the changed guest copy |

## 4. Steps

1. **Copy.** Set these values. Add the new keys `leon_tag` and `leon_role` right after `leon_name` in each language.

**en**
- leon_name: `Leon`
- leon_tag: `AI`
- leon_role: `Your 24/7 concierge`
- leon_hi: `Hello, I'm Leon, your 24/7 concierge for this stay. What can I do for you?`
- leon_about: `I'm Leon, your 24/7 concierge. I'm an AI, not a person: I answer from your host's guide, and when it has no answer I ask your host for you.`
- leon_ask: `Ask Leon, your 24/7 concierge`
- leon_intro: `Ask me anything about your stay, day or night. I answer from your host's guide, and if it doesn't say, I check with your host for you.`
- leon_needs_js: `To chat with Leon, turn on JavaScript. The guide above works without it.`

**cs**
- leon_name: `Leon`
- leon_tag: `AI`
- leon_role: `Váš concierge nonstop`
- leon_hi: `Dobrý den, jsem Leon, váš concierge nonstop po celý pobyt. Co pro vás můžu udělat?`
- leon_about: `Jsem Leon, váš concierge nonstop. Jsem AI, ne člověk: odpovídám podle průvodce od hostitele, a když v něm odpověď není, zeptám se hostitele za vás.`
- leon_ask: `Zeptejte se Leona, vašeho concierge`
- leon_intro: `Ptejte se na cokoli k pobytu, ve dne i v noci. Odpovídám podle průvodce od hostitele, a když v něm odpověď není, ověřím to u hostitele.`
- leon_needs_js: `Pro chat s Leonem zapněte JavaScript. Průvodce výše funguje i bez něj.`

**de**
- leon_name: `Leon`
- leon_tag: `KI`
- leon_role: `Ihr Concierge rund um die Uhr`
- leon_hi: `Hallo, ich bin Leon, Ihr Concierge rund um die Uhr für diesen Aufenthalt. Was kann ich für Sie tun?`
- leon_about: `Ich bin Leon, Ihr Concierge rund um die Uhr. Ich bin eine KI, kein Mensch: Ich antworte aus dem Gästeführer Ihres Gastgebers, und wenn er keine Antwort hat, frage ich Ihren Gastgeber für Sie.`
- leon_ask: `Leon fragen, Ihren Concierge`
- leon_intro: `Fragen Sie mich alles zu Ihrem Aufenthalt, Tag und Nacht. Ich antworte aus dem Guide Ihres Gastgebers, und wenn er nichts dazu sagt, frage ich Ihren Gastgeber.`
- leon_needs_js: `Um mit Leon zu chatten, aktivieren Sie JavaScript. Der Guide oben funktioniert auch ohne.`

**es**
- leon_name: `Leon`
- leon_tag: `IA`
- leon_role: `Su conserje 24/7`
- leon_hi: `Hola, soy Leon, su conserje 24/7 durante esta estancia. ¿Qué puedo hacer por usted?`
- leon_about: `Soy Leon, su conserje 24/7. Soy una IA, no una persona: respondo con la guía de su anfitrión y, cuando no tiene la respuesta, se lo pregunto a su anfitrión por usted.`
- leon_ask: `Preguntar a Leon, su conserje`
- leon_intro: `Pregúnteme lo que quiera sobre su estancia, de día o de noche. Respondo con la guía de su anfitrión y, si no lo dice, lo consulto con su anfitrión.`
- leon_needs_js: `Para chatear con Leon, active JavaScript. La guía de arriba funciona sin él.`

**fr**
- leon_name: `Leon`
- leon_tag: `IA`
- leon_role: `Votre concierge 24h/24`
- leon_hi: `Bonjour, je suis Leon, votre concierge 24h/24 pendant ce séjour. Que puis-je faire pour vous ?`
- leon_about: `Je suis Leon, votre concierge 24h/24. Je suis une IA, pas une personne : je réponds à partir du guide de votre hôte et, quand il n'a pas la réponse, je pose la question à votre hôte pour vous.`
- leon_ask: `Demander à Leon, votre concierge`
- leon_intro: `Posez-moi toutes vos questions sur votre séjour, de jour comme de nuit. Je réponds avec le guide de votre hôte et, s'il ne dit rien, je vérifie auprès de votre hôte.`
- leon_needs_js: `Pour discuter avec Leon, activez JavaScript. Le guide ci-dessus fonctionne sans.`

**uk** (guest_uk_i18n.py)
- leon_name: `Leon`
- leon_tag: `ШІ`
- leon_role: `Ваш консьєрж 24/7`
- leon_hi: `Вітаю, я Leon, ваш консьєрж 24/7 на час проживання. Чим можу допомогти?`
- leon_about: `Я Leon, ваш консьєрж 24/7. Я ШІ, а не людина: відповідаю за путівником господаря, а коли відповіді там немає, запитую господаря за вас.`
- leon_ask: `Запитати Leon, вашого консьєржа`
- leon_intro: `Питайте про будь-що щодо проживання, вдень і вночі. Я відповідаю за путівником господаря, а якщо там цього немає, уточню в господаря.`
- leon_needs_js: `Щоб поспілкуватися з Leon, увімкніть JavaScript. Путівник вище працює і без нього.`

   If the i18n module has a test that every language has the same keys (grep `tests/` for a key-parity test), the new keys in all six satisfy it. If another language dict exists that is not listed above (grep `"leon_hi"` across `App/app/*.py`), STOP and report it.

2. **Header** (`_leon.html`): change the header text block to:
```html
    <div class="g-leon-head-text"><h2 id="leon-title">{{ t('leon_name') }} <span class="g-leon-tag">{{ t('leon_tag') }}</span></h2><p class="g-leon-role">{{ t('leon_role') }}</p></div>
```
   Then move the intro out of the header. Put `<p class="g-intro">{{ t('leon_intro') }}</p>` directly after the closing `</div>` of `g-leon-head`.

3. **CSS**: append to guest.css (after the 0387 block):
```css
/* 0388: the AI tag and the concierge line under Leon's name. */
.g-leon-tag { display: inline-block; margin-left: 6px; padding: 2px 6px; border-radius: 6px; background: var(--g-accent-soft); color: var(--g-accent); font-size: 11px; font-weight: 700; letter-spacing: .04em; vertical-align: middle; }
.g-leon-role { margin: 2px 0 0; font-size: 14px; color: var(--g-muted); }
```
   Bump guest.css's `?v=` in `templates/guest/base.html` to `20261025-0388` and run `tests/test_static_versions.py --write` from `App/`.

4. **Prompt** (`leon.py`): replace ONLY the first line of `CHARACTER` with:
`You are Leon, the 24/7 concierge of one holiday rental, always there for the guest, day or night. You are an AI, not a person, and say so when asked; the host can always be reached through you.`
   Leave every other line of CHARACTER untouched. If a test pins the prompt text or a hash of it (grep `tests/` for `guest assistant of one holiday rental` or `CHARACTER`), update the pinned value, and say so in the report.

5. **Tests**: update only the assertions that check the changed guest copy (§2 grep list), e.g. `test_guest_leon_chat.py:78` → `assert "24/7 concierge" in body or "Your 24/7 concierge" in body` (match the page language of that test). Add one assertion to that test file's English render: the header contains `class="g-leon-tag"` with text `AI`. Then regenerate the Leon screenshots by running `tests/test_guest_leon_browser.py` (it writes `docs/tasks/screenshots-0387/`).

## 5. Do not touch

Host-side copy and its tests (e.g. "Not read by Leon (AI)"), Havel, routes, caps, the rest of the prompt, and the `about_me` or `smalltalk` logic.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_guest_leon_browser.py tests/test_guest_leon_chat.py tests/test_leon.py tests/test_guest_handoff.py tests/test_0376_ai_gates.py tests/test_guest_guide_browser.py tests/test_static_versions.py $(ls tests | grep -E 'i18n|translation|copy' | sed 's#^#tests/#') -q --tb=short -rs 2>&1 | tail -30
cd .. && git checkout -- $(git ls-files -m docs/tasks | grep -v -e 0387 -e 0388) 2>/dev/null; true
```
If a test fails, put its first assertion line in the report. Fix only if the cause is in a file from §3; otherwise stop.

## 7. Acceptance

- [ ] All §6 commands pass with 0 skipped, or the failure is in the report.
- [ ] `docs/tasks/screenshots-0387/leon-chat-390.png` shows "Leon", the AI tag, "Your 24/7 concierge", and the new greeting. You looked at it once.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0388-report.md` (200 tokens), `Status: review`. ONE commit `0388: Leon speaks as a 24/7 concierge`, including this brief and the regenerated screenshots, ending with:
```
Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Lvzax2VbKkYR4rb7JYLc3K
```
Do not push.
