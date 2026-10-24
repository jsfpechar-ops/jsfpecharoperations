# 0311: Havel engine (prompt, page map, redaction, request, guardrails, limits)

Status: todo
Depends on: 0310 | Base commit: 92646d3 plus the 0310 commits | Branch: task/0311-havel-engine
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `App/app/havel_prompt.py` (the system prompt, verbatim from the plan) and `App/app/havel.py`: the page allowlist and response schema, redaction, request building with the cached system blocks, the server-side guardrails that turn an unsafe reply into "I don't know", the scarce limits, history signing and the free local replies. No route and no template yet (0312); everything is unit-tested with canned JSON through the fake client from 0310.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` sections 2, 4 (prompt, copy it exactly), 5 (schema), 6 (pages), 9 (limits), 9a (guardrails), 10 (redaction). Rules: AGENTS.md 2 (no personal data in logs), 5 (SQL through `db.py`).

Repo facts, verified 2026-10-24:
- `App/app/ai.py` (0310): `ai.call(feature, system_blocks, messages, schema, key=None, max_tokens=None) -> dict` (clamped to `config.AI_MAX_TOKENS`, default 4000), raises `ai.AIDisabled`, `ai.AIBudgetError` (`.reason` in `month`, `day`), `ai.AIError` (`.reason`; `input_too_large` before any API call when the estimated input passes `config.AI_MAX_INPUT_TOKENS`, 60,000); `ai.today()`, `ai.now()` in Europe/Prague; `ai.enabled("havel")`.
- `App/app/guide_i18n.py`: `GUIDE_STRINGS = {"en": {...}, "cs": {...}}`, keys like `guide.nav.stays`, `guide.stays.body`. There is no `vi` guide yet (English is used for vi). Anchors in `templates/guide.html`: `overview, statuses, setup, stays, guests, reporting, manual-filing, ubyport-credentials, filters, housebook, stay_fee, invoices, settings, door-codes, faster, faq, legal, demo`. Nav label keys exist for all but `manual-filing` (label key `guide.reporting.manual_filing_title`), `ubyport-credentials` (`apartment.form.ubyport.credentials_help_heading`) and `door-codes` (`guide.nav.door-codes`).
- `App/app/host_i18n.py`: `translate(lang, key, **kwargs)`, `LANGUAGES = ("en", "cs", "vi")`, `DEFAULT_LANGUAGE = "en"`; Vietnamese falls back to English through `lookup`.
- `App/app/rate_limit.py`:

```python
def record(scope: str, key: str) -> None:
```

```python
def blocked(scope: str, key: str, max_events: int, window: int = _WINDOW_SECONDS) -> bool:
```

  `blocked()` prunes events older than `window` **inside that scope**, so every limit gets its own scope.
- `App/app/config.py` (0310): `HAVEL_WEEKLY_MESSAGES`, `HAVEL_MONTHLY_MESSAGES`, `secret_key()`, `TIMEZONE`.
- `App/app/access.py`: `apartments(request, columns="*", include_archived=False)` returns rows with `id`, `internal_name`, `addr_obec`, `active`, `archived_at`. The engine takes a plain list of dicts so it never touches the request.
- `App/app/db.py`: `query_one`, `execute`; upsert with `ON CONFLICT ... DO UPDATE` as in 0310.
- URLs in the page map were checked against the routes on 2026-10-24: `/`, `/reservations`, `/reservations?new=1`, `/submissions`, `/housebook`, `/stay-fees`, `/invoices`, `/apartments`, `/apartments/{id}?view=...`, `/entities`, `/cleaning`, `/cleaning/properties`, `/smart-locks`, `/settings`, `/settings/archived`, `/privacy-requests`, `/guide`. Before step 2, grep each `@router.get("<path>")` once (`grep -rn '@router.get("/cleaning/properties")' App/app/routes/`); a path that is not found is removed from `PAGES` and named in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/havel_prompt.py | new | `HAVEL_SYSTEM_PROMPT` |
| App/app/havel.py | new | the engine |
| App/tests/test_havel_engine.py | new | unit tests |
| docs/tasks/0311-report.md | new | report |

No other file may change.

## 4. Steps

Commit after each step: `0311 step k`.

1. **Prompt.** Create `App/app/havel_prompt.py` with this header, then paste the fenced `text` block of plan section 4 **verbatim** (from the line `You are Havel, the AI support assistant built into UbyHost.` to the line `support_summary is null unless kind is "escalate". action is null unless kind is "action".`) as the value of the string:

```python
"""Havel's system prompt (docs/plans/havel-support-assistant.md, section 4).

The plan is the source: a change happens there first, then here, in the same
PR, and the test set (plan section 13) runs after every change. The text is a
constant so the prompt cache hits on every request.
"""
HAVEL_SYSTEM_PROMPT = """\
<paste the plan's prompt here, exactly>
"""
```

   Command: `cd App && .venv/bin/python -c "from app.havel_prompt import HAVEL_SYSTEM_PROMPT as p; print(len(p) > 5000, p.startswith('You are Havel'), 'NEVER MAKE THINGS UP' in p, 'SEVERAL THINGS AT ONCE' in p, p.rstrip().endswith('action is null unless kind is \"action\".'))"`. Expected: `True True True True True`.

2. **Engine.** Create `App/app/havel.py`:

```python
"""Havel, the host support assistant: everything between the form and the model.

Plan: docs/plans/havel-support-assistant.md. The model only ever sees the
system prompt, the guide, the page list, redacted text and a few facts in
<host_context>. The server, not the model, decides what the host sees:
validate() turns anything unsafe into "I don't know" plus the support card.
Nothing here writes to the database except rate-limit events and daily stats.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from . import ai, config, db, guide_i18n, host_i18n, rate_limit
from .havel_prompt import HAVEL_SYSTEM_PROMPT

FEATURE = "havel"
MAX_TOKENS = 2500  # plan §3: room for beginner steps plus low-effort thinking
MAX_MESSAGE_CHARS = 600
MAX_REPLY_CHARS = 1500
MAX_SUMMARY_CHARS = 800
MAX_HISTORY_EXCHANGES = 4
MAX_HISTORY_CHARS = 4000
MAX_EXCHANGES = 6  # owner 2026-10-24: at most 6 messages per conversation
BURST_MAX, BURST_WINDOW = 5, 600
REFUSALS_MAX = 3
SUPPORT_MAX = 3

# --- pages ---------------------------------------------------------------------
# id -> (url, label key, purpose). "{id}" needs a property that belongs to the host;
# without one the link falls back to the Properties list. Labels for guide anchors
# come from the guide strings. Plan section 6.
PAGES: Dict[str, Tuple[str, str, str]] = {
    "dashboard": ("/", "nav.overview", "what needs you, upcoming arrivals"),
    "stays": ("/reservations", "nav.stays", "all stays"),
    "add_stay": ("/reservations?new=1", "stays.add_stay", "the normal Add stay form"),
    "reports": ("/submissions", "nav.reports", "police reports (UbyPort)"),
    "housebook": ("/housebook", "nav.housebook", "guest register and export"),
    "stay_fees": ("/stay-fees", "nav.stay_fees", "stay fees"),
    "invoices": ("/invoices", "nav.invoices", "invoices"),
    "properties": ("/apartments", "nav.properties", "properties list"),
    "property": ("/apartments/{id}?view=overview", "nav.properties", "one property"),
    "property_details": ("/apartments/{id}?view=settings&section=property", "host.property_details", "name, address, basics"),
    "property_reporting": ("/apartments/{id}?view=settings&section=reporting", "host.reporting", "UbyPort login, automation, stay fee rate"),
    "property_guests": ("/apartments/{id}?view=settings&section=guests#communication", "nav.guest_links", "guest link, PIN, messages"),
    "property_lock": ("/apartments/{id}?view=settings&section=lock#door-code", "host.door_code", "door code settings"),
    "property_calendars": ("/apartments/{id}?view=bookings#calendars", "wizard.overview.calendars", "calendar links (iCal)"),
    "business": ("/entities", "host.business", "business and operator details"),
    "cleaning": ("/cleaning", "nav.cleaning", "cleaning schedule"),
    "cleaning_properties": ("/cleaning/properties", "nav.cleaning", "cleaning settings per property"),
    "smart_locks": ("/smart-locks", "properties.shared.lock", "TTLock connection"),
    "settings": ("/settings", "nav.settings", "account settings"),
    "security": ("/settings#settings-group-security", "settings.group.security", "passkeys, two-factor"),
    "data": ("/settings#settings-group-data", "settings.group.data", "retention, export"),
    "archive": ("/settings/archived", "settings.nav.archive", "archived records"),
    "privacy_requests": ("/privacy-requests", "nav.privacy_requests", "guests' data requests"),
    "guide": ("/guide", "nav.guide", "Help & guide"),
}
GUIDE_ANCHORS: Dict[str, str] = {
    "overview": "guide.nav.overview", "statuses": "guide.nav.statuses", "setup": "guide.nav.setup",
    "stays": "guide.nav.stays", "guests": "guide.nav.guests", "reporting": "guide.nav.reporting",
    "manual-filing": "guide.reporting.manual_filing_title", "ubyport-credentials": "apartment.form.ubyport.credentials_help_heading",
    "filters": "guide.nav.filters", "housebook": "guide.nav.housebook", "stay_fee": "guide.nav.stay_fee",
    "invoices": "guide.nav.invoices", "settings": "guide.nav.settings", "door-codes": "guide.nav.door-codes",
    "faster": "guide.nav.faster", "faq": "guide.nav.faq", "legal": "guide.nav.legal",
}
for _anchor, _key in GUIDE_ANCHORS.items():
    PAGES["guide_" + _anchor.replace("-", "_")] = ("/guide#" + _anchor, _key, "Help & guide: " + _anchor)
PAGE_IDS: Tuple[str, ...] = tuple(PAGES)
ACTIONS = ("show_guest_link", "create_stay", "create_cleaning", "sync_calendars", "new_pin")
KINDS = ("answer", "clarify", "action", "escalate", "refuse")

SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "reply", "sources", "links", "action", "support_summary", "next"],
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "reply": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
        "links": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["page", "property_id"],
                "properties": {"page": {"type": "string", "enum": list(PAGE_IDS)},
                               "property_id": {"type": ["integer", "null"]}},
            },
        },
        "action": {
            "type": ["object", "null"], "additionalProperties": False,
            "required": ["type", "property_id", "date_from", "date_to", "guests", "guest_email", "start_time", "end_time", "note"],
            "properties": {
                "type": {"type": "string", "enum": list(ACTIONS)},
                "property_id": {"type": ["integer", "null"]},
                "date_from": {"type": ["string", "null"]},
                "date_to": {"type": ["string", "null"]},
                "guests": {"type": ["integer", "null"]},
                "guest_email": {"type": ["string", "null"]},
                "start_time": {"type": ["string", "null"]},
                "end_time": {"type": ["string", "null"]},
                "note": {"type": ["string", "null"]},
            },
        },
        "support_summary": {"type": ["string", "null"]},
        "next": {"type": "array", "items": {"type": "string"}},  # the host's remaining requests (plan 9a "Next")
    },
}


def guide_lang(lang: str) -> str:
    return lang if lang in guide_i18n.GUIDE_STRINGS else "en"


def guide_strings(lang: str) -> Dict[str, str]:
    return guide_i18n.GUIDE_STRINGS[guide_lang(lang)]


def label(lang: str, key: str) -> str:
    if key.startswith("guide."):
        return guide_strings(lang).get(key) or guide_i18n.GUIDE_STRINGS["en"].get(key, key)
    return host_i18n.translate(lang, key)


def page_url(page: str, property_id: Optional[int], owned_ids: List[int]) -> Optional[str]:
    """The URL for a page id, or None for an unknown id. A property page without an
    owned property falls back to the Properties list."""
    if page not in PAGES:
        return None
    url = PAGES[page][0]
    if "{id}" in url:
        if property_id in owned_ids:
            return url.replace("{id}", str(property_id))
        return PAGES["properties"][0]
    return url


# --- system blocks (constant per language, cached) --------------------------------

def guide_block(lang: str) -> str:
    strings = guide_strings(lang)
    lines = [f"{key}: {' '.join(str(text).split())}" for key, text in sorted(strings.items())]
    return f'<guide lang="{guide_lang(lang)}">\n' + "\n".join(lines) + "\n</guide>"


def pages_block(lang: str) -> str:
    lines = [f"{page} | {label(lang, key)} | {purpose}" for page, (_url, key, purpose) in PAGES.items()]
    return "<pages>\nid | label | what it is for\n" + "\n".join(lines) + "\n</pages>"


def system_blocks(lang: str) -> List[str]:
    return [HAVEL_SYSTEM_PROMPT, guide_block(lang), pages_block(lang)]


# --- redaction ---------------------------------------------------------------

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\b\d{1,2}\.\s?\d{1,2}\.(?:\s?\d{4})?|\b\d{1,2}:\d{2}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\d(?:[\s-]?\d){6,}")
_NUMBER = re.compile(r"\b(?:\d{6,}|[A-Za-z]{1,3}\d{6,9})\b")


def redact(text: str, mapping: Optional[Dict[str, str]] = None) -> Tuple[str, Dict[str, str]]:
    """Replace e-mails, phone numbers and ID-like tokens with [email 1], [phone 1], [number 1].

    Dates and times stay (stays need them). The mapping (placeholder -> real
    value) lives in memory for one request only and is reused across the turns
    of that request so the same value always gets the same placeholder."""
    mapping = mapping if mapping is not None else {}
    keep: List[str] = []

    def park(match: re.Match) -> str:
        keep.append(match.group(0))
        return f"\x00{len(keep) - 1}\x00"

    def placeholder(kind: str, value: str) -> str:
        for name, real in mapping.items():
            if real == value and name.startswith(f"[{kind} "):
                return name
        name = f"[{kind} {sum(1 for n in mapping if n.startswith(f'[{kind} ')) + 1}]"
        mapping[name] = value
        return name

    out = _DATE.sub(park, text)
    out = _EMAIL.sub(lambda m: placeholder("email", m.group(0)), out)
    out = _PHONE.sub(lambda m: placeholder("phone", m.group(0)), out)
    out = _NUMBER.sub(lambda m: placeholder("number", m.group(0)), out)
    out = re.sub("\x00(\\d+)\x00", lambda m: keep[int(m.group(1))], out)
    return out, mapping


def restore(text: Optional[str], mapping: Dict[str, str]) -> Optional[str]:
    if not text:
        return text
    for name, real in mapping.items():
        text = text.replace(name, real)
    return text


# --- history (signed by the server, carried by the browser) -------------------------

def _sig(user_id: int, payload: str) -> str:
    return hmac.new(config.secret_key().encode("utf-8"), f"{user_id}\n{payload}".encode("utf-8"), hashlib.sha256).hexdigest()


def sign_history(user_id: int, exchanges: List[Dict[str, str]]) -> Tuple[str, str]:
    """exchanges: [{"host": "...", "havel": "..."}, ...], newest last. Capped before signing."""
    trimmed = exchanges[-MAX_HISTORY_EXCHANGES:]
    while trimmed and sum(len(e.get("host", "")) + len(e.get("havel", "")) for e in trimmed) > MAX_HISTORY_CHARS:
        trimmed = trimmed[1:]
    payload = json.dumps(trimmed, ensure_ascii=False, separators=(",", ":"))
    return payload, _sig(user_id, payload)


def read_history(user_id: int, payload: str, sig: str) -> List[Dict[str, str]]:
    """A bad or missing signature empties the history; it never fails the request."""
    if not payload or not sig or not hmac.compare_digest(_sig(user_id, payload), sig):
        return []
    try:
        items = json.loads(payload)
    except ValueError:
        return []
    if not isinstance(items, list):
        return []
    clean = [{"host": str(e.get("host", ""))[:MAX_MESSAGE_CHARS], "havel": str(e.get("havel", ""))[:MAX_REPLY_CHARS]}
             for e in items if isinstance(e, dict)]
    return clean[-MAX_HISTORY_EXCHANGES:]


# --- request --------------------------------------------------------------------

@dataclass
class Host:
    user_id: int
    lang: str
    device: str                      # "phone" or "computer"
    properties: List[Dict[str, Any]]  # [{"id", "name", "city"}]
    page: str = ""                   # page id from PAGES, or ""
    topic: str = ""                  # quick-help topic id, or ""
    read_keys: List[str] = field(default_factory=list)

    @property
    def property_ids(self) -> List[int]:
        return [int(p["id"]) for p in self.properties]


def host_context(host: Host, today: date) -> str:
    props = "; ".join(f"id {p['id']}: {p['name']} ({p['city']})" if p.get("city") else f"id {p['id']}: {p['name']}"
                      for p in host.properties) or "none"
    lines = [
        f"today: {today.isoformat()} ({today.strftime('%A')})",
        f"lang: {host.lang}",
        f"device: {host.device}",
        f"properties: {props}",
        f"page: {host.page or 'unknown'}",
    ]
    if host.topic:
        lines.append(f"topic: {host.topic}")
    if host.read_keys:
        lines.append("read_keys: " + ", ".join(host.read_keys))
    return "<host_context>\n" + "\n".join(lines) + "\n</host_context>"


def build_messages(host: Host, history: List[Dict[str, str]], message: str, today: date,
                   mapping: Dict[str, str]) -> List[Dict[str, str]]:
    """The Messages API list: earlier exchanges (redacted), then the new user turn."""
    messages: List[Dict[str, str]] = []
    for exchange in history:
        host_text, _ = redact(exchange["host"], mapping)
        messages.append({"role": "user", "content": f"<message>{host_text}</message>"})
        messages.append({"role": "assistant", "content": exchange["havel"]})
    text, _ = redact(message, mapping)
    messages.append({"role": "user", "content": host_context(host, today) + f"\n<message>{text}</message>"})
    return messages


# --- free local replies -------------------------------------------------------------

_GREETING = re.compile(r"^(hi|hello|hey|good (morning|afternoon|evening)|ahoj|dobr[ýy] den|zdrav[ií]m|čau|xin ch[àa]o|ch[àa]o)\b[\s!.,]*$", re.I)
_THANKS = re.compile(r"^(thanks?|thank you|thx|ok(ay)?|d[íi]ky|d[ěe]kuj[iu]|super|c[ảa]m [ơo]n)\b[\s!.,]*$", re.I)


def local_reply(message: str) -> Optional[str]:
    """A copy key for a message that needs no model: greetings and thanks."""
    text = message.strip()
    if len(text) > 40:
        return None
    if _GREETING.match(text):
        return "havel.greeting"
    if _THANKS.match(text):
        return "havel.thanks"
    return None


# --- limits ----------------------------------------------------------------------

def _since_week_start(now: datetime) -> int:
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((now - start).total_seconds()) + 1)


def _since_month_start(now: datetime) -> int:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((now - start).total_seconds()) + 1)


def limit_state(user_id: int, now: Optional[datetime] = None) -> Optional[str]:
    """None when the host may send, else the copy key suffix: paused, burst, week, month."""
    now = now or ai.now()
    key = str(user_id)
    if rate_limit.blocked("havel_refuse", key, REFUSALS_MAX, _since_week_start(now)):
        return "paused"
    if rate_limit.blocked("havel_burst", key, BURST_MAX, BURST_WINDOW):
        return "limit_burst"
    if rate_limit.blocked("havel_week", key, config.HAVEL_WEEKLY_MESSAGES, _since_week_start(now)):
        return "limit_week"
    if rate_limit.blocked("havel_month", key, config.HAVEL_MONTHLY_MESSAGES, _since_month_start(now)):
        return "limit_month"
    return None


def remaining(user_id: int, now: Optional[datetime] = None) -> Tuple[int, str]:
    """(messages left, 'week' or 'month'): whichever runs out first."""
    now = now or ai.now()
    key = str(user_id)
    week = config.HAVEL_WEEKLY_MESSAGES - rate_limit._count("havel_week", key, _since_week_start(now))
    month = config.HAVEL_MONTHLY_MESSAGES - rate_limit._count("havel_month", key, _since_month_start(now))
    return (max(0, month), "month") if month < week else (max(0, week), "week")


def record_message(user_id: int) -> None:
    """Called once per message that reached the model."""
    for scope in ("havel_burst", "havel_week", "havel_month"):
        rate_limit.record(scope, str(user_id))


def record_refusal(user_id: int) -> None:
    rate_limit.record("havel_refuse", str(user_id))


def support_blocked(user_id: int, now: Optional[datetime] = None) -> bool:
    return rate_limit.blocked("havel_support", str(user_id), SUPPORT_MAX, _since_week_start(now or ai.now()))


def record_stat(kind: str, day: Optional[date] = None) -> None:
    day = day or ai.today()
    db.execute(
        "INSERT INTO havel_stats (day, kind, count) VALUES (?, ?, 1) "
        "ON CONFLICT (day, kind) DO UPDATE SET count = havel_stats.count + 1",
        (day.isoformat(), kind),
    )


# --- validation (the guardrails, plan 9a) -------------------------------------------------

@dataclass
class Reply:
    kind: str                                   # answer, clarify, action, escalate, refuse, or fail
    text: str = ""                              # what the host reads (restored, safe)
    links: List[Tuple[str, str]] = field(default_factory=list)   # (label, url)
    action: Optional[Dict[str, Any]] = None     # restored values, checked for shape and ownership
    support_summary: Optional[str] = None
    fail_reason: str = ""                       # set when kind == "fail"
    sources: List[str] = field(default_factory=list)
    next: List[str] = field(default_factory=list)   # remaining requests, shown as buttons (0332)


_FORBIDDEN_SCRIPTS = re.compile(r"[Ѐ-ӿ֐-׿؀-ۿ฀-๿぀-ヿ一-鿿가-힯]")
_ADDRESS = re.compile(r"https?:|www\.|@|/[A-Za-z]|\+?\d(?:[\s-]?\d){6,}", re.I)
_MARKUP = re.compile(r"[<>`]|\*\*|^#", re.M)
_DIGITS = re.compile(r"\d+")
_DATEISH = re.compile(r"\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?|\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HHMM = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
EMERGENCY_NUMBERS = "112 150 155 158"   # always allowed digits (plan 9a): "call 112" never fails on a missing guide key
MAX_NEXT = 3
MAX_NEXT_CHARS = 100


def _fail(reason: str) -> Reply:
    return Reply(kind="fail", fail_reason=reason)


def _numbers_ok(reply: str, allowed_text: str) -> bool:
    """Every digit run in the reply must be a step number, part of a date or time,
    present in the host's text or context, or present in a cited guide text."""
    cleaned = _DATEISH.sub("", re.sub(r"(?m)^\d{1,2}\.\s", "", reply))
    return all(run in allowed_text for run in _DIGITS.findall(cleaned))


def validate(data: Dict[str, Any], host: Host, message: str, history: List[Dict[str, str]],
             mapping: Dict[str, str], today: date) -> Reply:
    """Turn the model's JSON into what the host may see, or a ``fail`` Reply."""
    if not isinstance(data, dict) or data.get("kind") not in KINDS or not isinstance(data.get("reply"), str):
        return _fail("schema")
    kind = data["kind"]
    reply = data["reply"].strip()
    if not reply or len(reply) > MAX_REPLY_CHARS:
        return _fail("length")
    if _FORBIDDEN_SCRIPTS.search(reply):
        return _fail("script")
    if _ADDRESS.search(_DATEISH.sub("", reply)):  # dates and times are not phone numbers
        return _fail("address")
    if _MARKUP.search(reply):
        return _fail("markup")
    prompt = HAVEL_SYSTEM_PROMPT
    for start in range(0, max(1, len(prompt) - 40), 20):
        if prompt[start:start + 40] in reply:
            return _fail("prompt_leak")
    for real in mapping.values():
        if real in reply:
            return _fail("secret")

    strings = guide_strings(host.lang)
    sources_raw = data.get("sources") if isinstance(data.get("sources"), list) else []
    sources = [s for s in sources_raw if isinstance(s, str) and s in strings][:8]
    if kind == "answer":
        if not sources:
            return _fail("sources")
        allowed = " ".join(strings[s] for s in sources) + " " + message + " " + host_context(host, today)
        allowed += " " + " ".join(e["host"] for e in history) + " " + EMERGENCY_NUMBERS
        if not _numbers_ok(reply, allowed):
            return _fail("number")

    nxt: List[str] = []
    if kind != "refuse":
        known = message + " " + host_context(host, today) + " " + " ".join(e["host"] for e in history) + " " + EMERGENCY_NUMBERS
        for item in (data.get("next") or []):
            if len(nxt) == MAX_NEXT:
                break
            if not isinstance(item, str):
                continue
            item = item.strip()[:MAX_NEXT_CHARS]
            if not item or _FORBIDDEN_SCRIPTS.search(item) or _MARKUP.search(item) or _ADDRESS.search(_DATEISH.sub("", item)):
                continue
            if not all(run in known for run in _DIGITS.findall(_DATEISH.sub("", item))):
                continue
            nxt.append(restore(item, mapping) or "")

    links: List[Tuple[str, str]] = []
    if kind in ("answer", "clarify", "escalate"):
        for item in (data.get("links") or []):
            if len(links) == 3:
                break
            if not isinstance(item, dict) or item.get("page") not in PAGES:
                continue
            pid = item.get("property_id") if isinstance(item.get("property_id"), int) else None
            url = page_url(item["page"], pid, host.property_ids)
            if url:
                links.append((label(host.lang, PAGES[item["page"]][1]), url))

    summary = None
    if kind == "escalate":
        summary = data.get("support_summary")
        if not isinstance(summary, str) or not summary.strip():
            return _fail("summary")
        if len(summary) > MAX_SUMMARY_CHARS:
            return _fail("length")
        summary = restore(summary.strip(), mapping)

    action = None
    if kind == "action":
        raw = data.get("action")
        if not isinstance(raw, dict) or raw.get("type") not in ACTIONS:
            return _fail("action")
        action = {k: raw.get(k) for k in SCHEMA["properties"]["action"]["required"]}
        action["guest_email"] = restore(action.get("guest_email"), mapping)
        action["note"] = restore(action.get("note"), mapping)
        pid = action.get("property_id")
        if action["type"] != "sync_calendars":
            if len(host.properties) == 1 and pid is None:
                pid = host.property_ids[0]
            if pid not in host.property_ids:
                return _fail("action_property")
            action["property_id"] = pid
        for name in ("date_from", "date_to"):
            if action.get(name) is not None and not _ISO.match(str(action[name])):
                return _fail("action_dates")
        for name in ("start_time", "end_time"):
            if action.get(name) is not None and not _HHMM.match(str(action[name])):
                return _fail("action_times")
        if action["type"] == "create_stay":
            if not action.get("date_from") or not action.get("date_to") or action["date_to"] <= action["date_from"]:
                return _fail("action_dates")
            if action.get("guests") is not None and not 1 <= int(action["guests"]) <= 60:
                return _fail("action_guests")
        if action["type"] == "create_cleaning" and not action.get("date_from"):
            return _fail("action_dates")

    return Reply(kind=kind, text=restore(reply, mapping) or "", links=links, action=action,
                 support_summary=summary, sources=sources, next=nxt)


# --- one call, end to end ----------------------------------------------------------------

def ask(host: Host, history: List[Dict[str, str]], message: str, today: Optional[date] = None) -> Reply:
    """Build, call, validate. Raises ai.AIDisabled / ai.AIBudgetError; any other
    failure (API, refusal, bad JSON, guardrail) comes back as kind 'fail'.
    input_too_large (0310's input cap): drop the oldest history turn and retry once;
    a second refusal is a 'fail', which the page shows as havel.dont_know plus the support card."""
    today = today or ai.today()
    for attempt in range(2):
        mapping: Dict[str, str] = {}
        messages = build_messages(host, history, message, today, mapping)
        try:
            data = ai.call(FEATURE, system_blocks(host.lang), messages, SCHEMA, max_tokens=MAX_TOKENS)
            break
        except (ai.AIDisabled, ai.AIBudgetError):
            raise
        except ai.AIError as exc:
            if exc.reason == "input_too_large" and attempt == 0 and history:
                history = history[1:]
                continue
            return _fail(exc.reason)
    else:  # pragma: no cover - the loop always breaks or returns
        return _fail("input_too_large")
    reply = validate(data, host, message, history, mapping, today)
    record_stat("guardrail_fail" if reply.kind == "fail" else reply.kind, today)
    return reply
```

   Command: `cd App && .venv/bin/python -c "from app import havel; print(len(havel.PAGES), 'guide_door_codes' in havel.PAGES, len(havel.system_blocks('cs')[1]) > 4000)"`. Expected: `41 True True` (the count may be smaller if step 2's grep removed a page; say which).

3. **Tests.** Create `App/tests/test_havel_engine.py`:

```python
"""0311: the Havel engine never shows the host anything the server did not check."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app import ai, config, db, havel, rate_limit
from tests.ai_fake import FakeClient, reply

TODAY = date(2026, 10, 23)  # Friday
PROPS = [{"id": 11, "name": "Vinohrady flat", "city": "Praha"}, {"id": 12, "name": "Brno studio", "city": "Brno"}]


def host(lang="en", props=PROPS, **kw):
    return havel.Host(user_id=7, lang=lang, device="phone", properties=props, page="dashboard", **kw)


def ok(**over):
    data = {"kind": "answer", "reply": "Open Stays and tap Add stay.", "sources": ["guide.stays.body"],
            "links": [{"page": "add_stay", "property_id": None}], "action": None, "support_summary": None, "next": []}
    data.update(over)
    return data


@pytest.fixture(autouse=True)
def _db():
    db.init_db()
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse", "havel_support"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    yield
    ai.set_client_for_tests(None)


# --- redaction

def test_redact_emails_phones_and_ids_but_keeps_dates():
    text = "Guest jan.novak@example.com, +420 777 123 456, passport AB1234567, 5.11.2026 to 2026-11-08 at 10:00"
    out, mapping = havel.redact(text)
    assert out == "Guest [email 1], [phone 1], passport [number 1], 5.11.2026 to 2026-11-08 at 10:00"
    assert mapping == {"[email 1]": "jan.novak@example.com", "[phone 1]": "+420 777 123 456", "[number 1]": "AB1234567"}
    again, mapping = havel.redact("mail jan.novak@example.com again", mapping)
    assert again == "mail [email 1] again" and len(mapping) == 3
    assert havel.restore("send to [email 1]", mapping) == "send to jan.novak@example.com"


# --- pages and schema

def test_page_urls_and_schema_enum_agree():
    assert havel.SCHEMA["properties"]["links"]["items"]["properties"]["page"]["enum"] == list(havel.PAGES)
    assert havel.page_url("property_guests", 11, [11, 12]) == "/apartments/11?view=settings&section=guests#communication"
    assert havel.page_url("property_guests", 99, [11, 12]) == "/apartments"
    assert havel.page_url("guide_door_codes", None, []) == "/guide#door-codes"
    assert havel.page_url("nope", None, []) is None
    assert "nav.stays" not in havel.pages_block("cs") and "Pobyty" in havel.pages_block("cs")


# --- request

def test_messages_carry_context_and_redacted_history():
    mapping = {}
    msgs = havel.build_messages(host(topic="guest_link", read_keys=["guide.guests.body"]),
                                [{"host": "my mail is a@b.cz", "havel": "Sure."}], "What is the PIN?", TODAY, mapping)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "<message>my mail is [email 1]</message>"
    last = msgs[-1]["content"]
    assert "today: 2026-10-23 (Friday)" in last and "device: phone" in last
    assert "id 11: Vinohrady flat (Praha)" in last and "topic: guest_link" in last and "read_keys: guide.guests.body" in last
    assert last.endswith("<message>What is the PIN?</message>")
    blocks = havel.system_blocks("en")
    assert blocks[0].startswith("You are Havel") and blocks[1].startswith('<guide lang="en">') and blocks[2].startswith("<pages>")
    assert havel.system_blocks("vi")[1].startswith('<guide lang="en">')


# --- guardrails (plan 9a, cases 49-51)

def test_answer_without_a_real_guide_key_fails():
    assert havel.validate(ok(sources=["guide.made_up"]), host(), "q", [], {}, TODAY).kind == "fail"
    assert havel.validate(ok(sources=[]), host(), "q", [], {}, TODAY).fail_reason == "sources"


def test_numbers_not_in_the_guide_are_blocked_but_dates_steps_and_host_numbers_pass():
    assert havel.validate(ok(reply="It costs 299 Kč a month."), host(), "q", [], {}, TODAY).fail_reason == "number"
    good = "1. Open Stays.\n2. Tap Add stay for 31.10. to 2.11.2026 (2026-10-31), check-in at 15:00 for 3 guests."
    assert havel.validate(ok(reply=good), host(), "a stay for 3 guests", [], {}, TODAY).kind == "answer"


def test_addresses_markup_scripts_and_secrets_are_blocked():
    for bad, reason in (("See https://x.cz", "address"), ("Write to a@b.cz", "address"), ("Go to /settings", "address"),
                        ("Call 777 123 456", "address"), ("Use **Stays**", "markup"), ("Привет", "script")):
        assert havel.validate(ok(reply=bad), host(), "q", [], {}, TODAY).fail_reason == reason, bad
    mapping = {"[email 1]": "jan@example.com"}
    assert havel.validate(ok(reply="Your mail jan@example.com is set"), host(), "q", [], mapping, TODAY).fail_reason in ("address", "secret")
    assert havel.validate(ok(reply="Your mail [email 1] is set"), host(), "q", [], mapping, TODAY).text == "Your mail jan@example.com is set"
    leak = havel.HAVEL_SYSTEM_PROMPT[100:160]
    assert havel.validate(ok(reply="They told me: " + leak), host(), "q", [], {}, TODAY).fail_reason == "prompt_leak"


def test_emergency_numbers_pass_without_a_guide_key():
    out = havel.validate(ok(reply="Call 112 now. Then open the Lock page."), host(), "fire in the flat", [], {}, TODAY)
    assert out.kind == "answer"
    assert havel.validate(ok(reply="Call 112 or 777 now."), host(), "fire", [], {}, TODAY).fail_reason == "number"


def test_next_keeps_three_clean_entries_and_drops_the_rest():  # plan case 75
    raw = ["Add a stay at Vinohrady flat Friday to Sunday for 2", "See https://x.cz", "It costs 299 Kč", "Sync my calendars",
           "Show the PIN for Brno studio", "What does the red badge mean?"]
    out = havel.validate(ok(next=raw), host(), "guest link, stay Friday to Sunday for 2, sync, pin, badge", [], {}, TODAY)
    assert out.next == ["Add a stay at Vinohrady flat Friday to Sunday for 2", "Sync my calendars", "Show the PIN for Brno studio"]
    mapping = {"[email 1]": "jan@example.com"}
    assert havel.validate(ok(next=["Add a stay for [email 1]"]), host(), "q", [], mapping, TODAY).next == ["Add a stay for jan@example.com"]
    assert havel.validate(ok(next=["x" * 300]), host(), "q", [], {}, TODAY).next == ["x" * 100]
    assert havel.validate(ok(next=[1, "", "Use **bold**", "<b>hi</b>"]), host(), "q", [], {}, TODAY).next == []
    assert havel.validate(ok(kind="refuse", reply="I can only help with UbyHost.", sources=[], links=[], next=["Sync my calendars"]),
                          host(), "q", [], {}, TODAY).next == []


def test_links_are_filtered_and_resolved():
    data = ok(links=[{"page": "property_guests", "property_id": 11}, {"page": "nope", "property_id": None},
                     {"page": "property_lock", "property_id": 99}, {"page": "stays", "property_id": None}])
    out = havel.validate(data, host(), "q", [], {}, TODAY)
    assert [u for _l, u in out.links] == ["/apartments/11?view=settings&section=guests#communication", "/apartments", "/reservations"]


def test_actions_need_an_owned_property_and_sane_dates():
    base = {"type": "create_stay", "property_id": 12, "date_from": "2026-10-31", "date_to": "2026-11-02", "guests": 3,
            "guest_email": "[email 1]", "start_time": None, "end_time": None, "note": None}
    data = ok(kind="action", reply="Check the card.", sources=[], links=[], action=base)
    out = havel.validate(data, host(), "q", [], {"[email 1]": "jan@example.com"}, TODAY)
    assert out.kind == "action" and out.action["guest_email"] == "jan@example.com" and out.action["property_id"] == 12
    assert havel.validate(ok(kind="action", reply="x", sources=[], links=[], action={**base, "property_id": 99}),
                          host(), "q", [], {}, TODAY).fail_reason == "action_property"
    assert havel.validate(ok(kind="action", reply="x", sources=[], links=[], action={**base, "date_to": "2026-10-30"}),
                          host(), "q", [], {}, TODAY).fail_reason == "action_dates"
    one = host(props=PROPS[:1])
    pin = {**base, "type": "new_pin", "property_id": None, "date_from": None, "date_to": None, "guests": None, "guest_email": None}
    assert havel.validate(ok(kind="action", reply="x", sources=[], links=[], action=pin), one, "q", [], {}, TODAY).action["property_id"] == 11
    sync = {**pin, "type": "sync_calendars"}
    assert havel.validate(ok(kind="action", reply="x", sources=[], links=[], action=sync), host(), "q", [], {}, TODAY).kind == "action"


def test_escalate_needs_a_summary_and_refuse_is_plain():
    esc = ok(kind="escalate", reply="I can send this to the team.", sources=[], links=[], support_summary="Host reports error 4 on a report.")
    assert havel.validate(esc, host(), "q", [], {}, TODAY).support_summary == "Host reports error 4 on a report."
    assert havel.validate({**esc, "support_summary": None}, host(), "q", [], {}, TODAY).fail_reason == "summary"
    assert havel.validate(ok(kind="refuse", reply="I can only help with UbyHost.", sources=[], links=[]), host(), "q", [], {}, TODAY).kind == "refuse"


# --- ask(): end to end through the fake client

def test_ask_returns_fail_for_api_problems_and_records_stats(monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(ai, "today", lambda: TODAY)
    fake = FakeClient([reply(ok()), reply(ok(), stop_reason="refusal"), reply(text="{not json")])
    ai.set_client_for_tests(fake)
    assert havel.ask(host(), [], "How do I add a stay?", TODAY).kind == "answer"
    assert havel.ask(host(), [], "x", TODAY).fail_reason == "refusal"
    assert havel.ask(host(), [], "x", TODAY).fail_reason == "json"
    assert fake.calls[0]["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert fake.calls[0]["system"][0]["text"] == havel.HAVEL_SYSTEM_PROMPT
    rows = {r["kind"]: r["count"] for r in db.query("SELECT kind, count FROM havel_stats WHERE day = ?", (TODAY.isoformat(),))}
    assert rows["answer"] == 1 and rows["guardrail_fail"] == 2


def test_ask_drops_the_oldest_turn_once_when_the_input_is_too_large(monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(ai, "today", lambda: TODAY)
    fake = FakeClient([reply(ok())])
    ai.set_client_for_tests(fake)
    history = [{"host": "old " * 300, "havel": "a"}, {"host": "new", "havel": "b"}]
    sizes = []
    real_call = ai.call

    def capped(feature, system_blocks, messages, schema, **kw):
        sizes.append(len(str(messages)))
        if len(sizes) == 1:
            raise ai.AIError("input_too_large")
        return real_call(feature, system_blocks, messages, schema, **kw)

    monkeypatch.setattr(ai, "call", capped)
    assert havel.ask(host(), history, "q", TODAY).kind == "answer"
    assert len(sizes) == 2 and sizes[1] < sizes[0]
    monkeypatch.setattr(ai, "call", lambda *a, **k: (_ for _ in ()).throw(ai.AIError("input_too_large")))
    assert havel.ask(host(), history, "q", TODAY).fail_reason == "input_too_large"


# --- limits (cases 52-54) and local replies (case 41)

def test_local_replies_need_no_model():
    assert havel.local_reply("Hi!") == "havel.greeting" and havel.local_reply("Dobrý den") == "havel.greeting"
    assert havel.local_reply("Thanks") == "havel.thanks" and havel.local_reply("Děkuji.") == "havel.thanks"
    assert havel.local_reply("Hi, how do I add a stay?") is None


def test_weekly_monthly_burst_and_refusal_limits(monkeypatch):
    monkeypatch.setattr(config, "HAVEL_WEEKLY_MESSAGES", 10)
    monkeypatch.setattr(config, "HAVEL_MONTHLY_MESSAGES", 20)
    now = datetime(2026, 10, 23, 12, 0, tzinfo=ZoneInfo("Europe/Prague"))
    assert havel.limit_state(7, now) is None
    assert havel.remaining(7, now) == (10, "week")
    for _ in range(10):
        havel.record_message(7)
    assert havel.remaining(7, now) == (0, "week")
    assert havel.limit_state(7, now) in ("limit_burst", "limit_week")
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'havel_burst'", ())
    assert havel.limit_state(7, now) == "limit_week"
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'havel_week'", ())
    for _ in range(10):
        rate_limit.record("havel_month", "7")
    assert havel.limit_state(7, now) == "limit_month"
    for _ in range(3):
        havel.record_refusal(7)
    assert havel.limit_state(7, now) == "paused"
    assert havel.limit_state(8, now) is None


def test_calendar_windows_start_on_monday_and_the_first():
    monday = datetime(2026, 10, 19, 0, 0, 30, tzinfo=ZoneInfo("Europe/Prague"))
    assert havel._since_week_start(monday) == 31
    first = datetime(2026, 11, 1, 0, 1, 0, tzinfo=ZoneInfo("Europe/Prague"))
    assert havel._since_month_start(first) == 61


# --- history signing

def test_history_is_signed_capped_and_dropped_when_forged():
    exchanges = [{"host": f"q{i}", "havel": "a" * 1500} for i in range(6)]
    payload, sig = havel.sign_history(7, exchanges)
    back = havel.read_history(7, payload, sig)
    assert 1 <= len(back) <= 2 and back[-1]["host"] == "q5"
    assert havel.read_history(7, payload, sig[:-1] + ("0" if sig[-1] != "0" else "1")) == []
    assert havel.read_history(8, payload, sig) == []
    assert havel.read_history(7, payload.replace("q5", "q9"), sig) == []
    assert havel.read_history(7, "", "") == []
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_havel_engine.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. If `rate_limit._count` is renamed, use the public function that counts and note it; if `db.query` does not exist, use `db.query_one` per kind.

## 5. Do not touch

Anything not in section 3: no route, template, CSS, i18n (0312), no `ai.py` change (0310; if it needs one, STOP). AGENTS.md rules 2 and 5.

## 6. Commands (from `App/`)

```
.venv/bin/python -m pytest tests/test_havel_engine.py tests/test_ai.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all pass.

## 7. Acceptance

- [ ] `havel_prompt.py` holds the plan's prompt verbatim (the five `True`s in step 1).
- [ ] `test_havel_engine.py` passes: redaction keeps dates, schema enum equals the page map, every 9a guardrail has a failing and a passing case (including `next` and the emergency numbers), limits reset on Monday and the 1st, history signature rejects forgery.
- [ ] `grep -n 'log\.' App/app/havel.py` prints nothing (the engine logs nothing; `ai.py` logs counts).

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: a page URL in `PAGES` has no route (remove it and report), a test fails twice.

## 9. Report

`docs/tasks/0311-report.md` (600 tokens at most), `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/havel.py`: `validate()` (every branch returns `fail` on doubt), `redact()` (dates kept, no false negatives on Czech phone formats), `_since_week_start` / `_since_month_start`, `read_history`.

## Owner steps

None. Nothing is visible yet; 0312 adds the page.
