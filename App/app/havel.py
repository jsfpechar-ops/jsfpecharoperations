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
from collections import Counter
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
    "finding": "guide.nav.finding", "glossary": "guide.nav.glossary", "cleaning": "guide.nav.cleaning",
    "guest_links": "guide.nav.guest_links", "business": "guide.nav.business", "archive": "guide.nav.archive",
    "privacy_requests": "guide.nav.privacy_requests",
    "add-property": "guide.setup.add_title", "setup-guide": "guide.setup.wizard_title",
    "connect-calendar": "guide.stays.calendar_title", "add-stay": "guide.stays.add_title",
    "stay-fee-setup": "guide.stay_fee.setup_title", "stay-fee-pay": "guide.stay_fee.pay_title",
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
_PHONE = re.compile(r"(?<![A-Za-z\d])\+?\d(?:[\s-]?\d){6,}")
_NUMBER = re.compile(r"\b(?:\d{6,}|[A-Za-z]{1,4}\d{6,})\b")


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
    """exchanges: [{"host": "...", "havel": "..."}, ...], newest last. Keeps the last MAX_EXCHANGES (the conversation cap counts them)."""
    trimmed = [{"host": str(e.get("host", ""))[:MAX_MESSAGE_CHARS], "havel": str(e.get("havel", ""))[:MAX_REPLY_CHARS]}
                  for e in exchanges[-MAX_EXCHANGES:]]
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
    return clean[-MAX_EXCHANGES:]


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


def model_history(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """The part of the conversation the model sees: the last MAX_HISTORY_EXCHANGES within MAX_HISTORY_CHARS."""
    trimmed = history[-MAX_HISTORY_EXCHANGES:]
    while trimmed and sum(len(e["host"]) + len(e["havel"]) for e in trimmed) > MAX_HISTORY_CHARS:
        trimmed = trimmed[1:]
    return trimmed


def build_messages(host: Host, history: List[Dict[str, str]], message: str, today: date,
                   mapping: Dict[str, str]) -> List[Dict[str, str]]:
    """The Messages API list: earlier exchanges (redacted), then the new user turn."""
    messages: List[Dict[str, str]] = []
    for exchange in model_history(history):
        host_text, _ = redact(exchange["host"], mapping)
        messages.append({"role": "user", "content": f"<message>{host_text}</message>"})
        havel_text, _ = redact(exchange["havel"], mapping)
        messages.append({"role": "assistant", "content": havel_text})
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
_ADDRESS = re.compile(r"https?:|www\.|@|/[A-Za-z]|\+?\d(?:[\s-]?\d){6,}|\b[\w-]+\.(?:com|cz|net|org|io|eu|sk|de|app|info)\b", re.I)
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


def _int(value: Any) -> Optional[int]:
    """An int from the model's JSON, or None (bool is not an int here)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


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
            pid = _int(item.get("property_id"))
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
        pid = _int(action.get("property_id"))
        if action["type"] != "sync_calendars":
            if len(host.properties) == 1 and pid is None:
                pid = host.property_ids[0]
            if pid not in host.property_ids:
                return _fail("action_property")
        elif pid not in host.property_ids:
            pid = None
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
            guests = action.get("guests")
            if guests is not None and (_int(guests) is None or not 1 <= guests <= 60):
                return _fail("action_guests")
        if action["type"] == "create_cleaning" and not action.get("date_from"):
            return _fail("action_dates")
        for name in ("note", "guest_email"):
            value = action.get(name)
            if value is None:
                continue
            if not isinstance(value, str) or _FORBIDDEN_SCRIPTS.search(value) or _MARKUP.search(value):
                return _fail("action_text")
            if name == "note" and _ADDRESS.search(_DATEISH.sub("", value)):
                return _fail("action_text")
        if action["guest_email"] is not None and not _EMAIL.fullmatch(action["guest_email"]):
            return _fail("action_email")

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
            record_stat("guardrail_fail", today)
            return _fail(exc.reason)
    else:  # pragma: no cover - the loop always breaks or returns
        return _fail("input_too_large")
    reply = validate(data, host, message, history, mapping, today)
    record_stat("guardrail_fail" if reply.kind == "fail" else reply.kind, today)
    return reply


# --- 0320: gap log ----------------------------------------------------------
GAP_KINDS = ("escalate", "fail", "not_helped")


def record_gap(lang: str, page: str, kind: str, question: str) -> None:
    """Store the redacted question, with no user and no property (plan section 12)."""
    text = redact(question)[0].strip()[:MAX_MESSAGE_CHARS]
    if not text or kind not in GAP_KINDS:
        return
    db.insert("havel_gap", {"created_at": db.utcnow(), "lang": (lang or "en")[:5],
                            "page": page if page in PAGES else None, "kind": kind, "question": text})


# --- 0331: the owner's gap list on /admin/operations --------------------------
GAP_REASON_KEYS = {"escalate": "ops.havel.reason.escalate", "not_helped": "ops.havel.reason.not_helped",
                   "fail": "ops.havel.reason.fail"}
# Plan section 6 page id -> the guide section to fix (an anchor in templates/guide.html).
GUIDE_FOR_PAGE = {
    "dashboard": "overview", "stays": "stays", "add_stay": "add-stay", "property_calendars": "connect-calendar",
    "reports": "reporting", "property_reporting": "reporting", "housebook": "housebook",
    "stay_fees": "stay_fee", "invoices": "invoices", "invoice_settings": "invoices",
    "properties": "setup", "property": "setup", "property_details": "setup", "business": "business",
    "property_guests": "guest_links", "property_lock": "door-codes", "smart_locks": "door-codes",
    "cleaning": "cleaning", "cleaning_properties": "cleaning", "settings": "settings", "security": "settings",
    "data": "settings", "archive": "archive", "privacy_requests": "privacy_requests",
}
GAP_GROUPS_SHOWN = 30
GAP_ROWS_READ = 2000


def normalise_question(text: str) -> str:
    """Case, punctuation and spacing do not make two questions different."""
    kept = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in (text or "").casefold())
    return " ".join(kept.split())


def guide_section(page: Optional[str]) -> str:
    """The guide anchor to fix for a page; Common questions when there is none yet."""
    anchor = GUIDE_FOR_PAGE.get(page or "", "faq")
    return anchor if anchor in GUIDE_ANCHORS else "faq"


def gap_groups(limit: int = GAP_GROUPS_SHOWN) -> List[Dict[str, Any]]:
    """Gap rows grouped by normalised question, most asked first, then newest."""
    rows = db.query("SELECT created_at, lang, page, kind, question FROM havel_gap "
                    "ORDER BY created_at DESC, id DESC LIMIT ?", (GAP_ROWS_READ,))
    groups: Dict[str, Dict[str, Any]] = {}
    for row in rows:  # newest first, so a group's first row is its newest wording
        key = normalise_question(row["question"])
        if not key:
            continue
        group = groups.setdefault(key, {"question": row["question"], "count": 0, "newest": row["created_at"],
                                        "langs": Counter(), "pages": Counter(), "kinds": Counter()})
        group["count"] += 1
        group["langs"][row["lang"]] += 1
        group["pages"][row["page"] or ""] += 1
        group["kinds"][row["kind"]] += 1
    ordered = sorted(groups.values(), key=lambda g: (g["count"], g["newest"]), reverse=True)
    result = []
    for group in ordered[:limit]:
        page = group["pages"].most_common(1)[0][0]
        anchor = guide_section(page)
        result.append({
            "question": group["question"], "count": group["count"], "newest": str(group["newest"])[:10],
            "langs": ", ".join(sorted(group["langs"])), "page": page,
            "reasons": [GAP_REASON_KEYS[k] for k, _ in group["kinds"].most_common() if k in GAP_REASON_KEYS],
            "guide_anchor": anchor, "guide_label": GUIDE_ANCHORS[anchor],
        })
    return result


def admin_overview(day: Optional[date] = None) -> Dict[str, Any]:
    day = day or ai.today()
    spent = ai.month_spend_usd(FEATURE, day)
    cap = config.ai_monthly_usd(FEATURE)
    since = (day - timedelta(days=29)).isoformat()
    stats = db.query("SELECT kind, SUM(count) AS n FROM havel_stats WHERE day >= ? GROUP BY kind ORDER BY kind", (since,))
    return {
        "enabled": ai.enabled(FEATURE), "spent": f"{spent:.2f}", "cap": f"{cap:.2f}",
        "percent": int(spent / cap * 100) if cap > 0 else 0,
        "stats": [{"kind": r["kind"], "n": int(r["n"] or 0)} for r in stats],
        "gaps": gap_groups(),
    }
