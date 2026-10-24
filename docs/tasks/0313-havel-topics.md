# 0313: Havel (AI): quick-help topics on /havel

Status: todo
Depends on: 0312 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0313-havel-topics
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The empty `/havel` page is not a blank box: it shows Josef's five topics, each with two to four questions whose answers come straight from the guide strings (no model call, no cost, no count), a link to the real page and "Still need help? Ask Havel", which hands the topic and the keys the host just read to the engine. Everything is plain links and a form, so it works without JavaScript; the panel (0324) reuses the same templates through an `X-Havel: 1` fragment.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` section 17c (topics table), 17e (copy). Rules: AGENTS.md 7 (one 390 px screenshot of the changed page), 9 (copy keys only); MASTER 7.1 (buttons), 10 (never do). Tokens only in `host2.css`.

Excerpts (verbatim; if one is not found, stop, section 8):

- `App/app/templates/_ui.html` line 82: macro `ui_menu_item(label, href='', danger=false, icon_name='', attrs='')` renders `<a class="ui-menu-item" role="menuitem" href=...>{{ icon(icon_name, 16) }}{{ label }}</a>`.
- Icons present in `App/app/templates/_icons.html`: `calendar-days`, `external-link`, `send`, `refresh-cw`, `triangle-alert`, `x`, `chevron-right`, `book-open`; `message-circle-question` was added by 0312.
- From 0312 (`grep -n` each before editing): `App/app/routes/havel.py` has `NAV_TO_PAGE`, `_page_context(...)`, `havel_page` (GET), `havel_send` (POST; `fragment = request.headers.get("x-havel") == "1"` renders `_havel_thread.html`). Templates `havel.html`, `_havel_thread.html`, `_havel_form.html` (hidden `_csrf, history, history_sig, page, device, topic, return_to`; textarea `id="havel-message"`; `data-havel-send`). `App/app/havel.py`: `Host(..., page="", topic="", read_keys=[])`, `MAX_MESSAGE_CHARS`, `PAGES`, `page_url(page, property_id, owned_ids)`. Keys `havel.*` exist in en/cs/vi (`havel.launcher`, `havel.open_page`, `havel.close`, `havel.topics_title`, `havel.topic.*`, `havel.q.*`, `havel.writing`, `havel.error`, `havel.retry`, `havel.support.mailto`). Fixtures: `tests.test_submission_retry_cap.host`, `tests.ai_fake.FakeClient`/`reply`, `ai.set_client_for_tests`.
- Guide strings: `App/app/guide_i18n.py` `GUIDE_STRINGS["en"|"cs"]` are merged into `host_i18n.STRINGS` (host_i18n.py line 4790), so `host_i18n.translate(lang, "guide.stays.body")` works. All 23 keys in the topic table below exist in en and cs (checked 2026-10-24).
- `App/app/templates/base.html` line 26 after 0312: `  <link rel="stylesheet" href="/static/host2.css?v=20261024-0312">`. `App/tests/test_cleaning_browser.py` lines 1–60 (uvicorn thread on a free port, `chromium_launch_kwargs()`, cookie `auth.SESSION_COOKIE`); `UBYHOST_REQUIRE_BROWSER=1` turns a skip into a failure. Static keys: `App/tests/test_static_versions.py --write`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/havel_topics.py | new | the five topics, their questions, guide keys, page-aware order |
| App/app/routes/havel.py | edit | topics in the context, `q` parameter, `read_keys`, nav keys, fragment template |
| App/app/templates/_havel_topics.html | new | topics list, questions, deterministic answer, hand-off button |
| App/app/templates/_havel_fragment.html | new | thread items + form (for 0324) |
| App/app/templates/_havel_form.html | edit | hidden `q` field |
| App/app/templates/havel.html | edit | topics on the page, `nav = 'havel'` |
| App/app/static/host2.css | edit | append topic rules; new `?v=` key in base.html |
| App/app/templates/base.html | edit | the CSS key only |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | one new key `havel.topic.support_body` (en, cs, vi) |
| App/tests/test_havel_topics.py | new | topics and route tests |
| docs/design/catalog.json | edit | classes and enforced templates |
| docs/design/pages/havel.md | edit | topics note |
| docs/tasks/screenshots-0313/havel-topic-390.png | new | |

No other file may change.

## 4. Steps

1. **Branch.** `git fetch origin && git checkout -b task/0313-havel-topics origin/task/0312-havel-page` if that branch exists; otherwise `origin/main` after 0312 is merged. Then `grep -n "def _page_context\|x-havel\|_havel_thread.html" App/app/routes/havel.py` must print three or more lines, else stop.

2. **Topics module.** Create `App/app/havel_topics.py`:

```python
"""Havel's quick-help layer (plan 17c): five topics, each with two to four questions.

An answer is the guide strings named by its keys, in order, shown as paragraphs.
No model call, no cost, no count. When the host presses "Still need help? Ask
Havel", the topic and the keys they have just read travel with the message as
``topic`` and ``read_keys`` in the host context, so Havel does not repeat them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import host_i18n

TOPICS: List[Dict[str, Any]] = [
    {"id": "stays", "icon": "calendar-days", "label": "havel.topic.stays", "questions": [
        {"id": "add", "label": "havel.q.stays.add", "keys": ["guide.stays.body"], "page": "add_stay"},
        {"id": "change", "label": "havel.q.stays.change", "keys": ["guide.stays.detail"], "page": "stays"},
        {"id": "cancelled", "label": "havel.q.stays.cancelled",
         "keys": ["guide.stays.cancelled", "guide.stays.dates_changed"], "page": "stays"},
    ]},
    {"id": "guest_link", "icon": "external-link", "label": "havel.topic.guest_link", "questions": [
        {"id": "how", "label": "havel.q.guest_link.how",
         "keys": ["guide.guests.body", "guide.guests.step_pin", "guide.guests.step_pick", "guide.guests.step_claim",
                  "guide.guests.step_form"], "page": "property_guests"},
        {"id": "where", "label": "havel.q.guest_link.where", "keys": ["guide.setup.step3"], "page": "property_guests"},
        {"id": "broken", "label": "havel.q.guest_link.broken", "keys": ["guide.faq.link_a"], "page": "property_guests"},
    ]},
    {"id": "reporting", "icon": "send", "label": "havel.topic.reporting", "questions": [
        {"id": "when", "label": "havel.q.reporting.when",
         "keys": ["guide.reporting.body", "guide.reporting.immediate", "guide.reporting.scheduled",
                  "guide.reporting.manual"], "page": "reports"},
        {"id": "colours", "label": "havel.q.reporting.colours",
         "keys": ["guide.statuses.lede", "guide.statuses.ready", "guide.statuses.waiting", "guide.statuses.reported",
                  "guide.statuses.failed"], "page": "guide_statuses"},
        {"id": "czech", "label": "havel.q.reporting.czech", "keys": ["guide.faq.czech_a"], "page": "reports"},
    ]},
    {"id": "calendars", "icon": "refresh-cw", "label": "havel.topic.calendars", "questions": [
        {"id": "connect", "label": "havel.q.calendars.connect", "keys": ["guide.setup.step2"], "page": "property_calendars"},
        {"id": "stale", "label": "havel.q.calendars.stale", "keys": ["guide.stays.body"], "page": "property_calendars"},
    ]},
    {"id": "wrong", "icon": "triangle-alert", "label": "havel.topic.wrong", "questions": [
        {"id": "report", "label": "havel.q.wrong.report", "keys": ["guide.reporting.failure"], "page": "reports"},
        {"id": "error", "label": "havel.q.wrong.error", "keys": ["havel.topic.support_body"], "page": None,
         "support": True},
    ]},
]
TOPIC_IDS = [t["id"] for t in TOPICS]

# The hosting page's nav key -> the topic shown first (plan 17c).
FIRST_FOR_NAV = {"cleaning": "stays", "reservations": "stays", "submissions": "reporting", "housebook": "reporting",
                 "apartments": "guest_link", "dashboard": "reporting"}


def ordered(nav: str = "") -> List[Dict[str, Any]]:
    first = FIRST_FOR_NAV.get(nav or "")
    return sorted(TOPICS, key=lambda t: 0 if t["id"] == first else 1)


def topic(topic_id: str) -> Optional[Dict[str, Any]]:
    return next((t for t in TOPICS if t["id"] == topic_id), None)


def question(topic_id: str, q_id: str) -> Optional[Dict[str, Any]]:
    t = topic(topic_id)
    if not t:
        return None
    return next((q for q in t["questions"] if q["id"] == q_id), None)


def read_keys(topic_id: str, q_id: str) -> List[str]:
    q = question(topic_id, q_id)
    return [k for k in (q["keys"] if q else []) if k.startswith("guide.")]


def answer(lang: str, topic_id: str, q_id: str) -> Optional[Dict[str, Any]]:
    """Paragraphs for one question, in the interface language, or None."""
    q = question(topic_id, q_id)
    if not q:
        return None
    texts = [host_i18n.translate(lang, k) for k in q["keys"]]
    return {"topic": topic_id, "question": q, "paragraphs": [t for t in texts if t and t != "?"],
            "page": q.get("page"), "support": bool(q.get("support"))}
```

   Command: `cd App && .venv/bin/python -c "from app import havel_topics as h; print(len(h.TOPICS), [t['id'] for t in h.ordered('apartments')][0], len(h.answer('cs','reporting','when')['paragraphs']))"`. Expected: `5 guest_link 4`.

   If `host_i18n.translate` returns the key itself or raises `KeyError` for a missing key, note the real behaviour in your report and adjust the filter in `answer` so that a missing key gives an empty paragraph list; the test in step 10 checks that every key resolves.

3. **One new copy key.** In `App/app/host_i18n.py` the en block has the line `        "havel.topic.guide": "Read more in the guide",` and the cs block has `        "havel.topic.guide": "Více v nápovědě",` (0312). Directly after each add, respectively:

```python
        "havel.topic.support_body": "Write to support with what you see and on which page. A person replies by e-mail.",
```

```python
        "havel.topic.support_body": "Napište podpoře, co vidíte a na které stránce. Odpoví vám člověk e-mailem.",
```

   In `App/app/host_vi_i18n.py`, after the line `    "havel.topic.guide": "Đọc thêm trong hướng dẫn",` add:

```python
    "havel.topic.support_body": "Hãy viết cho bộ phận hỗ trợ: bạn thấy gì và ở trang nào. Một người sẽ trả lời qua e-mail.",
```

   Command: `cd App && .venv/bin/python -c "from app import host_i18n as h, host_vi_i18n as v; print(h.translate('cs','havel.topic.support_body')[:8], 'havel.topic.support_body' in v.STRINGS)"`. Expected: `Napište True`.

4. **Route.** In `App/app/routes/havel.py`:

   a. Change the import line `from .. import access, ai, auth, havel, host_i18n, security` to `from .. import access, ai, auth, havel, havel_topics, host_i18n, security`.

   b. Replace the whole `_page_context` function (from `def _page_context(` to the line `    }` that closes its return dict) with:

```python
def _page_context(request: Request, uid: int, items: List[Dict[str, Any]], exchanges: List[Dict[str, str]],
                  *, topic: str = "", q: str = "", page: str = "", return_to: str = "/havel",
                  error: Optional[str] = None) -> Dict[str, Any]:
    state, remaining = _state(request, uid)
    payload, sig = havel.sign_history(uid, exchanges)
    nav = next((k for k, v in NAV_TO_PAGE.items() if v == page), "")
    return {
        "havel_items": items, "havel_state": state, "havel_remaining": remaining, "havel_error": error,
        "havel_history": payload, "havel_history_sig": sig, "havel_topic": topic, "havel_q": q, "havel_page": page,
        "havel_return_to": return_to, "havel_max": havel.MAX_MESSAGE_CHARS,
        "havel_fresh": len(exchanges) == 0,
        "havel_topics": havel_topics.ordered(nav), "havel_topic_data": havel_topics.topic(topic) if topic else None,
        "havel_answer": havel_topics.answer(request.state.lang, topic, q) if topic and q else None,
        "havel_show_topics": len(exchanges) == 0 and not items,
    }


def _clean_id(value: str) -> str:
    return re.sub(r"[^a-z_]", "", value)[:30]
```

   c. Replace the body of `havel_page` (keep the decorator and `def havel_page(request: Request):`) with:

```python
    guard = auth.require_login(request)
    if guard:
        return guard
    uid = int(auth.current_user(request)["id"])
    topic = _clean_id(request.query_params.get("topic", ""))
    q = _clean_id(request.query_params.get("q", ""))
    if topic not in havel_topics.TOPIC_IDS:
        topic, q = "", ""
    page = NAV_TO_PAGE.get(request.query_params.get("page", ""), "guide")
    ctx = _page_context(request, uid, [], [], topic=topic, q=q, page=page,
                        return_to=security.safe_local_path(request.query_params.get("return_to", ""), "/havel"))
    if request.headers.get("x-havel") == "1":
        ctx["havel_fragment"] = True
        return render(request, "_havel_fragment.html", ctx)
    return render(request, "havel.html", ctx)
```

   d. In `havel_send`, replace `    topic = re.sub(r"[^a-z_]", "", str(form.get("topic", "")))[:30]` with:

```python
    topic = _clean_id(str(form.get("topic", "")))
    q = _clean_id(str(form.get("q", "")))
    if topic not in havel_topics.TOPIC_IDS:
        topic, q = "", ""
```

   Replace `    page = page if page in havel.PAGES else ""` with:

```python
    page = NAV_TO_PAGE.get(page, page)
    page = page if page in havel.PAGES else ""
```

   Replace the `Host(` construction `properties=_properties(request), page=page, topic=topic)` with `properties=_properties(request), page=page, topic=topic, read_keys=havel_topics.read_keys(topic, q))`.

   In the two `_page_context(` calls at the end of `havel_send`, add `q=q,` right after `topic=topic,`, and replace `return render(request, "_havel_thread.html", ctx)` with `return render(request, "_havel_fragment.html", ctx)`.

   Command: `cd App && .venv/bin/python -c "from app.main import app" && grep -c "havel_topics" app/routes/havel.py`. Expected: no error, `6` or more.

5. **Templates.**

   a. Create `App/app/templates/_havel_topics.html`:

```jinja
{#- 0313: quick help (plan 17c). Three screens: the five topics, a topic's
    questions, one answer built from the guide. Every row is a real link, so
    the layer works on /havel without JavaScript; havel.js fetches the same
    URLs with X-Havel: 1 inside the panel. -#}
{% from "_icons.html" import icon with context %}
<div class="havel-topics" data-havel-topics>
  {% if havel_answer %}
  <a class="ui-btn ui-btn-quiet ui-btn-compact" href="/havel?topic={{ havel_topic }}" data-havel-topic-link>{{ icon('chevron-left', 16) }}{{ t(havel_topic_data.label) }}</a>
  <h3 class="havel-answer-title">{{ t(havel_answer.question.label) }}</h3>
  <div class="havel-msg havel-msg-havel havel-answer" tabindex="-1">
    <div class="havel-who"><span class="havel-avatar" aria-hidden="true">{{ icon('message-circle-question', 16) }}</span><span class="havel-name">{{ t('havel.name') }}</span></div>
    <div class="havel-bubble">{% for p in havel_answer.paragraphs %}<p>{{ p }}</p>{% endfor %}</div>
    <div class="havel-links">
      {% if havel_answer.page %}{% set url = page_url(havel_answer.page) %}{% if url %}<a class="ui-btn ui-btn-secondary ui-btn-compact" href="{{ url }}">{{ t('havel.topic.guide') if havel_answer.page.startswith('guide_') else t(pages[havel_answer.page][1]) }}{{ icon('chevron-right', 16) }}</a>{% endif %}{% endif %}
      {% if havel_answer.support and operator().email %}<a class="ui-btn ui-btn-secondary ui-btn-compact" href="mailto:{{ operator().email }}">{{ icon('send', 16) }}{{ t('havel.support.mailto') }}</a>{% endif %}
    </div>
  </div>
  {% if not havel_state %}<a class="ui-btn ui-btn-secondary havel-ask" href="#havel-message" data-havel-ask data-topic="{{ havel_topic }}" data-q="{{ havel_q }}">{{ t('havel.topic.ask') }}</a>{% endif %}
  {% elif havel_topic_data %}
  <a class="ui-btn ui-btn-quiet ui-btn-compact" href="/havel" data-havel-topic-link>{{ icon('chevron-left', 16) }}{{ t('havel.topic.back') }}</a>
  <h3 class="havel-answer-title">{{ t(havel_topic_data.label) }}</h3>
  <nav class="ui-menu-panel" aria-label="{{ t(havel_topic_data.label) }}">
    {% for q in havel_topic_data.questions %}<a class="ui-menu-item havel-topic" href="/havel?topic={{ havel_topic }}&q={{ q.id }}" data-havel-topic-link>{{ t(q.label) }}<span class="grow"></span>{{ icon('chevron-right', 16) }}</a>{% endfor %}
  </nav>
  {% else %}
  <h3 class="havel-answer-title">{{ t('havel.topics_title') }}</h3>
  <nav class="ui-menu-panel" aria-label="{{ t('havel.topics_title') }}">
    {% for tp in havel_topics %}<a class="ui-menu-item havel-topic" href="/havel?topic={{ tp.id }}" data-havel-topic-link>{{ icon(tp.icon, 16) }}{{ t(tp.label) }}<span class="grow"></span>{{ icon('chevron-right', 16) }}</a>{% endfor %}
  </nav>
  {% endif %}
</div>
```

   `page_url` and `pages` come from `_page_context`: add two entries to its returned dict, before `"havel_show_topics"`:

```python
        "pages": havel.PAGES,
        "page_url": lambda page_id: havel.page_url(page_id, None, [p["id"] for p in _properties(request)]),
```

   (`havel.page_url` with `property_id=None` uses the first owned property or `/apartments`; check `grep -n "def page_url" -A12 App/app/havel.py` and pass `ids[0] if ids else None` yourself if it does not.)

   b. Create `App/app/templates/_havel_fragment.html` (what `havel.js` will receive in 0324):

```jinja
{#- 0313: a fragment for havel.js (0324): the topics layer when the thread is
    empty, the new thread items, then a fresh form (history, counter, state). -#}
<div data-havel-items data-mode="{{ 'replace' if havel_show_topics else 'append' }}">
  {% if havel_show_topics %}{% include "_havel_topics.html" %}{% endif %}
  {% include "_havel_thread.html" %}
</div>
<div data-havel-form-wrap>{% include "_havel_form.html" %}</div>
```

   c. In `App/app/templates/_havel_form.html` (0312), directly after the line `  <input type="hidden" name="topic" value="{{ havel_topic }}" data-havel-topic>` add:

```jinja
  <input type="hidden" name="q" value="{{ havel_q }}" data-havel-q>
```

   d. In `App/app/templates/havel.html` (0312), replace `    {% include "_havel_thread.html" %}` with:

```jinja
    {% if havel_show_topics %}{% include "_havel_topics.html" %}{% endif %}
    {% include "_havel_thread.html" %}
```


   e. In `havel.html` (0312) change `{% set nav = 'guide' %}` to `{% set nav = 'havel' %}` (the sidebar launcher in 0324 marks `/havel` as current).

   Command: `cd App && .venv/bin/python -c "from app.main import app" && grep -c "havel_show_topics" app/templates/havel.html app/templates/_havel_fragment.html`. Expected: no error, `1`, `1`.

6. **CSS, catalog, page note.** Append to the very end of `App/app/static/host2.css` (after the 0312 block):

```css

/* 0313: quick-help topics (plan 17c): five menu rows, a question list, one answer. Tokens only. */
.host-workspace .havel-topics { display: flex; flex-direction: column; gap: var(--space-2); }
.host-workspace .havel-topics .ui-btn-quiet { align-self: flex-start; }
.host-workspace .havel-answer-title { margin: 0; font-size: var(--size-15); font-weight: 600; color: var(--ink); }
.host-workspace .havel-topic { min-height: var(--control-h); }
.host-workspace .havel-topics .havel-answer { max-width: none; }
.host-workspace .havel-ask { align-self: flex-start; }
```

   Then `sed -i 's/host2.css?v=20261024-0312"/host2.css?v=20261024-0313"/' App/app/templates/base.html && grep -c 'host2.css?v=20261024-0313"' App/app/templates/base.html` (expected `1`), then `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`. From the repo root:

```python
import json
from pathlib import Path
p = Path("docs/design/catalog.json")
c = json.loads(p.read_text(encoding="utf-8"))
c["classes"] += [k for k in ["havel-answer-title", "havel-ask"] if k not in c["classes"]]
for t in ["App/app/templates/_havel_topics.html", "App/app/templates/_havel_fragment.html"]:
    if t not in c["enforced_templates"]:
        c["enforced_templates"].append(t)
p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("catalog ok")
```

   Append to `docs/design/pages/havel.md` (0312):

```markdown

## Quick help (0313)
- Empty state: `_havel_topics.html`, five topics from `havel_topics.py` (page-aware order); `/havel?topic=<id>&q=<id>` are real pages; `X-Havel: 1` returns `_havel_fragment.html` (items + form) for the panel (0324).
```

   Command: `python3 scripts/design_lint.py 2>&1 | tail -3`. Expected: OK or only pre-existing warnings.

7. **Tests.** Create `App/tests/test_havel_topics.py`:

```python
"""0313: quick-help topics and the panel."""
from __future__ import annotations

import re

import pytest

from app import ai, config, db, havel, havel_topics, host_i18n
from tests.ai_fake import FakeClient, reply
from tests.test_submission_retry_cap import host as host  # noqa: F401

ANSWER = {"kind": "answer", "reply": "Open Stays.\n1. Tap Add stay.", "sources": ["guide.stays.body"],
          "links": [], "action": None, "support_summary": None}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    db.init_db()
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    yield
    ai.set_client_for_tests(None)


def test_every_topic_key_resolves_in_both_languages():
    for lang in ("en", "cs"):
        for topic in havel_topics.TOPICS:
            assert host_i18n.translate(lang, topic["label"]) not in ("", topic["label"])
            for q in topic["questions"]:
                answer = havel_topics.answer(lang, topic["id"], q["id"])
                assert len(answer["paragraphs"]) == len(q["keys"]), (lang, topic["id"], q["id"])
                for p in answer["paragraphs"]:
                    assert "%(" not in p and "<" not in p and not p.startswith(("guide.", "havel."))


def test_page_aware_order_and_read_keys():
    assert havel_topics.ordered("apartments")[0]["id"] == "guest_link"
    assert havel_topics.ordered("dashboard")[0]["id"] == "reporting"
    assert [t["id"] for t in havel_topics.ordered("")] == havel_topics.TOPIC_IDS
    assert havel_topics.read_keys("reporting", "when")[0] == "guide.reporting.body"
    assert havel_topics.read_keys("wrong", "error") == []
    assert havel_topics.answer("en", "nope", "x") is None



def test_topics_render_on_the_page_and_as_fragments(host):
    page = host.get("/havel").text
    assert page.count('data-havel-topic-link') == 5
    questions = host.get("/havel?topic=guest_link").text
    assert 'href="/havel?topic=guest_link&q=how"' in questions
    answer = host.get("/havel?topic=guest_link&q=where", headers={"X-Havel": "1"}).text
    assert "<html" not in answer and 'data-mode="replace"' in answer
    assert 'data-havel-ask data-topic="guest_link" data-q="where"' in answer
    assert host_i18n.translate("en", "guide.setup.step3")[:20] in answer or \
        host_i18n.translate("cs", "guide.setup.step3")[:20] in answer
    support = host.get("/havel?topic=wrong&q=error").text
    assert "mailto:" in support
    assert host.get("/havel?topic=evil&q=../x").status_code == 200



def test_hand_off_sends_topic_and_read_keys_to_the_engine(host, monkeypatch):
    seen = {}
    real = havel.ask

    def spy(h, history, message, today=None):
        seen["host"] = h
        return real(h, history, message, today)

    monkeypatch.setattr(havel, "ask", spy)
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    page = host.get("/havel").text
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
    res = host.post("/havel", data={"_csrf": csrf, "message": "And a cancelled one?", "history": "", "history_sig": "",
                                    "page": "reservations", "device": "phone", "topic": "stays", "q": "cancelled"},
                    headers={"X-Havel": "1"})
    assert res.status_code == 200
    assert seen["host"].topic == "stays" and seen["host"].page == "stays"
    assert seen["host"].read_keys == ["guide.stays.cancelled", "guide.stays.dates_changed"]
    assert 'data-mode="append"' in res.text and "havel-msg-havel" in res.text
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_havel_topics.py tests/test_havel_page.py -q 2>&1 | tail -30`. Expected: all pass.


8. **Screenshot** (rule 7). With the harness 0312 step 9 used (`tests/browser_support.py`, as `test_host_wide_geometry_browser.py` does; `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`), capture `/havel?topic=stays&q=cancelled` at 390 as `docs/tasks/screenshots-0313/havel-topic-390.png` and look at it once: back button, question title, the answer bubble with two paragraphs, a link button, "Still need help? Ask Havel", the composer under it. Then run the guards: `cd App && .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q 2>&1 | tail -30` (expected: pass, 0 skipped).

## 5. Do not touch

`App/app/ai.py`, `App/app/havel.py`, `App/app/havel_prompt.py` (0310, 0311), the migrations, `requirements*.txt`, `base.html` beyond the key, the shell templates, any JavaScript, any `guide_*` file, the cards (0314), the panel (0324). Rules: no hard-coded copy, no colour outside tokens, no new dependency, no push.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

1. `.venv/bin/python -c "from app.main import app" && echo import-ok` → `import-ok`.
2. `.venv/bin/python -m pytest tests/test_havel_topics.py tests/test_havel_page.py tests/test_havel_engine.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_static_versions.py -q 2>&1 | tail -30` → all passed.
3. `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q 2>&1 | tail -30` → passed, 0 skipped.
4. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -3` → OK.

## 7. Acceptance

- [ ] `/havel` shows "What do you need help with?" and five rows; a row opens its questions; a question shows the guide text as Havel's bubble, a link button to the real page (or the e-mail support exit for "I see an error") and "Still need help? Ask Havel"; the back links work; all without JavaScript.
- [ ] `/havel?topic=…&q=…` with `X-Havel: 1` returns the fragment (`data-havel-items`, `data-mode="replace"`, the form) and nothing else.
- [ ] A message sent with `topic=stays&q=cancelled` reaches `havel.ask` with `Host.topic == "stays"` and `read_keys == ["guide.stays.cancelled", "guide.stays.dates_changed"]`; the hosting page's nav key (`reservations`) maps to the page id (`stays`).
- [ ] Every key in `havel_topics.TOPICS` resolves in en and cs; a bad `topic` or `q` renders the topics list (200, no error).
- [ ] Screenshot at 390 saved and looked at; guards pass, 0 skipped; design lint OK; static manifest written.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: a 0312 anchor is missing (0312 not merged or changed), `havel.page_url` does not accept `None` as `property_id`, or `host_i18n.translate` returns something other than the text or the key for a missing key.

## 9. Report

Write `docs/tasks/0313-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, one sentence on the screenshot.

## Risk list (for the reviewer)

`App/app/havel_topics.py` (the keys: a renamed guide key must break the test, never the page), `App/app/routes/havel.py` (`q` and `topic` sanitising, nav → page mapping, `read_keys` reach `Host`), `App/app/templates/_havel_topics.html` (all text through autoescape; `mailto:` only with `operator().email`).

## Owner steps

1. Open the pull request and look at `docs/tasks/screenshots-0313/havel-topic-390.png`.
2. On staging open `/havel`, tap "Guest link and PIN", then "Where do I find the link and PIN?". The answer is the guide's sentence; the button under it opens your property's Guest links card. Tap "Still need help? Ask Havel": the cursor lands in the box.
3. Read the five topic names and the thirteen questions in en and cs (plan 17e) and change any wording you want before 0324 ships the panel.
4. Have a Vietnamese speaker check the one new sentence `havel.topic.support_body` (owner item 8).
