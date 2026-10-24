# 0310: `ai.py`, the one door to the Claude API (shared by Havel and the guest bot)

Status: todo
Depends on: owner decision 15.1 in the Havel plan (the `anthropic` dependency line; this brief writes it) | Base commit: 92646d3 | Branch: task/0310-ai-core
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `App/app/ai.py`, the only module that imports the Anthropic SDK: `ai.call(feature, system_blocks, messages, schema, key=None, max_tokens=None)` sends one structured-output request to `claude-haiku-5-5`, records token usage per day, feature and key in a new `ai_usage` ledger, and refuses to call when that feature's monthly budget, today's share of it, or the caller's per-key daily cap is used up. Havel (`feature="havel"`, no key, 0311–0314) and the guest bot ("leon", `feature="leon"` with `key=<property id>`, and `feature="guide_import"`) both build on it; a provider swap is this one file.

## 2. Context

Plans: `docs/plans/havel-support-assistant.md` sections 3 (model call), 9 (spend), 12 (storage). Rules: AGENTS.md 2 (no personal data in logs), 3 (public repo, no keys), 4 (dependency needs the decision line, step 7), 5 (SQL through `db.py`, migration file, Postgres-portable).

API facts (verified against the Claude API reference on 2026-10-24; do not change them):
- Model id is exactly `claude-haiku-5-5`. Thinking is adaptive by default: do **not** send `thinking`, `temperature`, `top_p` or `top_k` (all rejected). Effort goes inside `output_config`.
- Structured output: `output_config={"effort": "low", "format": {"type": "json_schema", "schema": <dict>}}`. The first `text` content block is valid JSON for the schema. Content blocks are read by `type`; a `thinking` block may come first.
- Caching: `system` is a list of `{"type": "text", "text": ...}` blocks; the last one carries `"cache_control": {"type": "ephemeral"}`.
- Client: `anthropic.Anthropic(api_key=..., timeout=20.0, max_retries=1)`. Usage fields on the response: `usage.input_tokens`, `usage.cache_creation_input_tokens`, `usage.cache_read_input_tokens`, `usage.output_tokens`; `response.stop_reason` is `end_turn`, `max_tokens` or `refusal`; `response._request_id` is public despite the underscore.

Repo facts:
- `App/requirements.txt` holds `==` pins (line `webauthn==3.0.1`). `App/requirements.lock` holds the hashes; its header is the command that regenerates it:

```
#    pip-compile --allow-unsafe --cert=None --client-cert=None --generate-hashes --index-url=None --no-index --output-file=requirements.lock --pip-args=None requirements.txt
```

- `App/app/config.py` boolean pattern, line 308:

```python
SIGNUP_ENABLED = os.environ.get("UBYHOST_SIGNUP_ENABLED", "0").lower() in ("1", "true", "yes")
```

  and line 310, the anchor for step 3:

```python
SIGNUP_NOTIFY_EMAIL = os.environ.get("UBYHOST_SIGNUP_NOTIFY_EMAIL", "").strip() or OPERATOR_EMAIL
```

- `App/app/db.py` helpers used here: `db.query_one(sql, params)`, `db.execute(sql, params)`. Upserts use `ON CONFLICT ... DO UPDATE` (rule 5), as `App/app/cleaning.py` line 78 does with `ON CONFLICT (source_reservation_id) DO NOTHING`.
- Migrations: the guest plan (0291–0309) owns 0013 and 0014. Run `python3 scripts/context_lint.py | grep 'next free'` first; if it prints `migration 0015` name the file `0015_ai_usage.sql`, otherwise use the number it prints and say so in the report.
- `docs/context/decisions.md` is at its lint cap (2198 of 2200 tokens). Step 7 moves six lines to `docs/archive/decisions-2026.md` first (workflow.md "Compaction"), then appends the new line.
- `docs/ENVIRONMENT.md` has one table per section; the anchor for the new section is the heading `## Development and test only`.
- `docs/context/architecture.md` row anchor: `| Mail | \`App/app/mail.py\` (SES and outbox), \`App/app/mail_notify.py\`, \`App/app/lifecycle_mail.py\` |`.
- `docs/context/test-map.md` row anchor: `| Cleaning | \`test_cleaning*.py\` |`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/requirements.txt | edit | `anthropic==<version>` after `webauthn==3.0.1` |
| App/requirements.lock | regenerate | pip-compile with hashes |
| App/app/migrations/0015_ai_usage.sql | new | `ai_usage`, `havel_stats` (number from the lint) |
| App/app/config.py | edit | AI settings, per feature |
| App/app/ai.py | new | the module |
| App/tests/ai_fake.py | new | fake client shared with 0311 and the guest bot |
| App/tests/test_ai.py | new | unit tests, no network |
| docs/ENVIRONMENT.md | edit | new section |
| docs/context/architecture.md | edit | one row |
| docs/context/test-map.md | edit | one row |
| docs/context/decisions.md | edit | compaction plus one line |
| docs/archive/decisions-2026.md | new | the six moved lines |
| docs/tasks/0310-report.md | new | report |

No other file may change.

## 4. Steps

Commit after each step: `0310 step k`.

1. **Dependency.** Pin `anthropic==2.3.0` (orchestrator checked 2026-10-24: 2.3.0 has `messages.create(output_config=..., thinking=...)` and the usage fields this brief reads). Confirm it exists (from `App/`):

```
.venv/bin/python -m pip index versions anthropic 2>&1 | head -2
```

   The list must contain `2.3.0` (if it does not, STOP and ask). Add one line after `webauthn==3.0.1` in `App/requirements.txt`: `anthropic==2.3.0`. Then regenerate the lock and install:

```
cd App && .venv/bin/python -m pip install pip-tools 2>&1 | tail -2
.venv/bin/pip-compile --allow-unsafe --generate-hashes --output-file=requirements.lock requirements.txt 2>&1 | tail -5
.venv/bin/python -m pip install --require-hashes -r requirements.lock 2>&1 | tail -3
grep -c 'anthropic==' requirements.lock; git diff requirements.lock | grep '^+[a-z]' | cut -d= -f1 | sort -u | tr '\n' ' '
```

   Expected: `anthropic==` found once; the last command prints the new top-level package names (something like `anthropic anyio distro docstring-parser httpx2 jiter pydantic pydantic-core sniffio typing-extensions`). Copy that list into your report; step 7 needs it. No network: STOP and hand the three commands to the owner.

2. **Migration.** Create `App/app/migrations/0015_ai_usage.sql` (or the number the lint printed):

```sql
-- Brief 0310: the shared model-API ledger (docs/plans/havel-support-assistant.md, section 12).
--
-- ai_usage: tokens per day, feature and key. No user, no text. feature is the
-- caller ("havel", "leon", "guide_import"); key is the caller's own grouping
-- for a per-key daily cap (the guest bot passes the property id, Havel passes
-- nothing and the row has key ''). ai.py prices these rows to enforce the
-- per-feature monthly budget, today's share of it and the per-key cap.
-- havel_stats: Havel replies per day and kind (answer, clarify, action,
-- escalate, refuse, guardrail_fail, limit_hit), no user, no text.
-- havel_gap (redacted questions) comes with brief 0320 and its retention line:
-- this migration holds no personal data.
CREATE TABLE IF NOT EXISTS ai_usage (
    day                TEXT NOT NULL,
    feature            TEXT NOT NULL,
    key                TEXT NOT NULL DEFAULT '',
    requests           INTEGER NOT NULL DEFAULT 0,
    input_tokens       INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, feature, key)
);

CREATE TABLE IF NOT EXISTS havel_stats (
    day   TEXT NOT NULL,
    kind  TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, kind)
);
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_migrations.py -q --tb=short -x 2>&1 | tail -5`. Expected: all pass.

3. **Config.** In `App/app/config.py`, directly after the line `SIGNUP_NOTIFY_EMAIL = os.environ.get("UBYHOST_SIGNUP_NOTIFY_EMAIL", "").strip() or OPERATOR_EMAIL`, insert:

```python

# Model API (docs/plans/havel-support-assistant.md section 3; shared by Havel and
# the guest bot). A feature is on only when it is listed in UBYHOST_AI_FEATURES
# AND the key is set. The key is passed to the SDK explicitly; the SDK's own
# ANTHROPIC_API_KEY lookup is never used.
AI_FEATURES = frozenset(
    part.strip().lower() for part in os.environ.get("UBYHOST_AI_FEATURES", "").split(",") if part.strip()
)
ANTHROPIC_API_KEY = os.environ.get("UBYHOST_ANTHROPIC_API_KEY", "").strip()
AI_MODEL = os.environ.get("UBYHOST_AI_MODEL", "claude-haiku-5-5")
AI_MAX_TOKENS = int(os.environ.get("UBYHOST_AI_MAX_TOKENS", "4000"))
# Haiku 5.5 costs 5x more once one request's input passes 100,000 tokens. ai.call
# estimates input as 1 token per 2 characters (more than real text uses, also for
# Czech and Vietnamese) and refuses above this cap. The env var may only lower it.
AI_INPUT_TOKENS_HARD_CAP = 60_000
AI_MAX_INPUT_TOKENS = min(int(os.environ.get("UBYHOST_AI_MAX_INPUT_TOKENS", "60000")), AI_INPUT_TOKENS_HARD_CAP)
# Real input tokens above this in one response are logged as an error (never expected).
AI_LONG_CONTEXT_TOKENS = 100_000
# USD per million tokens, Anthropic table for claude-haiku-5-5 (2026-10-06): input
# 0.10, output 0.50, cache read a tenth of input, a 5-minute cache write 1.25x.
AI_PRICE_USD_PER_MTOK = {
    "input": float(os.environ.get("UBYHOST_AI_PRICE_INPUT", "0.10")),
    "output": float(os.environ.get("UBYHOST_AI_PRICE_OUTPUT", "0.50")),
    "cache_read": float(os.environ.get("UBYHOST_AI_PRICE_CACHE_READ", "0.01")),
    "cache_write": float(os.environ.get("UBYHOST_AI_PRICE_CACHE_WRITE", "0.125")),
}


def ai_monthly_usd(feature: str) -> float:
    """Monthly budget for one feature: UBYHOST_AI_MONTHLY_USD_<FEATURE>, else 10."""
    return float(os.environ.get(f"UBYHOST_AI_MONTHLY_USD_{feature.upper()}", "10"))


def ai_key_daily_usd(feature: str) -> float:
    """Per-key daily cap for one feature: UBYHOST_AI_KEY_DAILY_USD_<FEATURE>; 0 means no per-key cap."""
    return float(os.environ.get(f"UBYHOST_AI_KEY_DAILY_USD_{feature.upper()}", "0"))


HAVEL_WEEKLY_MESSAGES = int(os.environ.get("UBYHOST_HAVEL_WEEKLY", "8"))
HAVEL_MONTHLY_MESSAGES = int(os.environ.get("UBYHOST_HAVEL_MONTHLY", "15"))
```

   Command: `cd App && .venv/bin/python -c "from app import config; print(sorted(config.AI_FEATURES), config.AI_MODEL, config.ai_monthly_usd('havel'), config.ai_key_daily_usd('leon'))"`. Expected: `[] claude-haiku-5-5 10.0 0.0`.

4. **The module.** Create `App/app/ai.py`:

```python
"""One door to the model API (docs/plans/havel-support-assistant.md, section 3).

Every feature that talks to a model calls ``call()``; nothing else imports the
SDK, so a provider swap is this file plus the test sets. The module also keeps
the spend honest: every response's tokens land in ``ai_usage`` (per day,
feature and key) and three caps are checked before each call: the feature's
monthly budget, today's even share of what is left, and, when the caller
passes a key, that key's daily cap.

Features: "havel" (the host support assistant, no key, pacing only), "leon"
(the guest bot, key = property id), "guide_translate" (guide translation for guests) and "guide_import" (the guest bot's
one-off imports). Never log message text. Log ids, counts and timings only.
"""
from __future__ import annotations

import calendar
import json
import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from . import config, db

log = logging.getLogger(__name__)

_TZ = ZoneInfo(config.TIMEZONE)
_client: Any = None
_client_override: Any = None


class AIError(Exception):
    """The call failed, was refused or returned nothing usable. ``reason`` is a short word."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AIDisabled(AIError):
    """The feature is not switched on, or there is no key."""


def estimate_input_tokens(system_blocks: List[str], messages: List[Dict[str, Any]]) -> int:
    """Over-estimate of a request's input tokens: 1 token per 2 characters, rounded up."""
    chars = sum(len(text) for text in system_blocks) + len(json.dumps(messages, ensure_ascii=False))
    return (chars + 1) // 2


class AIBudgetError(AIError):
    """``reason`` is ``month`` (budget spent), ``day`` (today's share spent) or ``key`` (this key's daily cap)."""


def enabled(feature: str) -> bool:
    return bool(feature in config.AI_FEATURES and config.ANTHROPIC_API_KEY)


def set_client_for_tests(client: Any) -> None:
    """Tests pass a fake with ``messages.create(**kwargs)``; ``None`` restores the real one."""
    global _client_override
    _client_override = client


def _get_client() -> Any:
    global _client
    if _client_override is not None:
        return _client_override
    if _client is None:
        import anthropic  # imported here so tests and a deploy with AI off never need it

        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=20.0, max_retries=1)
    return _client


def now() -> datetime:
    return datetime.now(_TZ)


def today() -> date:
    return now().date()


# --- spend -------------------------------------------------------------------

def _usd(row: Any) -> float:
    if not row:
        return 0.0
    price = config.AI_PRICE_USD_PER_MTOK
    return (
        (row["input_tokens"] or 0) * price["input"]
        + (row["cache_write_tokens"] or 0) * price["cache_write"]
        + (row["cache_read_tokens"] or 0) * price["cache_read"]
        + (row["output_tokens"] or 0) * price["output"]
    ) / 1_000_000


_SUM = (
    "SELECT COALESCE(SUM(input_tokens), 0) AS input_tokens, "
    "COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens, "
    "COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens, "
    "COALESCE(SUM(output_tokens), 0) AS output_tokens FROM ai_usage WHERE feature = ? AND "
)


def month_spend_usd(feature: str, day: Optional[date] = None) -> float:
    day = day or today()
    return _usd(db.query_one(_SUM + "day >= ? AND day <= ?", (feature, day.replace(day=1).isoformat(), day.isoformat())))


def day_spend_usd(feature: str, day: Optional[date] = None) -> float:
    day = day or today()
    return _usd(db.query_one(_SUM + "day = ?", (feature, day.isoformat())))


def key_day_spend_usd(feature: str, key: str, day: Optional[date] = None) -> float:
    day = day or today()
    return _usd(db.query_one(_SUM + "day = ? AND key = ?", (feature, day.isoformat(), key)))


def daily_allowance_usd(feature: str, day: Optional[date] = None) -> float:
    """What today may spend: the budget left, spread evenly over the days left in the month."""
    day = day or today()
    days_left = calendar.monthrange(day.year, day.month)[1] - day.day + 1
    # Budget left at the start of today, so today's own spend does not shrink today's share.
    left = config.ai_monthly_usd(feature) - (month_spend_usd(feature, day) - day_spend_usd(feature, day))
    return max(0.0, left / days_left)


def budget_fraction(feature: str, day: Optional[date] = None) -> float:
    """0.0 to 1.0 and beyond: how much of the feature's monthly budget is spent (0319 mails at 0.8)."""
    cap = config.ai_monthly_usd(feature)
    if cap <= 0:
        return 1.0
    return month_spend_usd(feature, day) / cap


def budget_state(feature: str, key: Optional[str] = None, day: Optional[date] = None) -> str:
    """``ok``, ``month``, ``day`` or ``key`` (see ``AIBudgetError``)."""
    day = day or today()
    if month_spend_usd(feature, day) >= config.ai_monthly_usd(feature):
        return "month"
    if day_spend_usd(feature, day) >= daily_allowance_usd(feature, day):
        return "day"
    key_cap = config.ai_key_daily_usd(feature)
    if key is not None and key_cap > 0 and key_day_spend_usd(feature, key, day) >= key_cap:
        return "key"
    return "ok"


def _record(feature: str, key: str, usage: Any, day: Optional[date] = None) -> None:
    day = day or today()
    values = (
        day.isoformat(),
        feature,
        key,
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )
    db.execute(
        "INSERT INTO ai_usage (day, feature, key, requests, input_tokens, cache_write_tokens, cache_read_tokens, output_tokens) "
        "VALUES (?, ?, ?, 1, ?, ?, ?, ?) "
        "ON CONFLICT (day, feature, key) DO UPDATE SET "
        "requests = ai_usage.requests + 1, "
        "input_tokens = ai_usage.input_tokens + excluded.input_tokens, "
        "cache_write_tokens = ai_usage.cache_write_tokens + excluded.cache_write_tokens, "
        "cache_read_tokens = ai_usage.cache_read_tokens + excluded.cache_read_tokens, "
        "output_tokens = ai_usage.output_tokens + excluded.output_tokens",
        values,
    )


# --- the call ----------------------------------------------------------------

def call(feature: str, system_blocks: List[str], messages: List[Dict[str, Any]], schema: Dict[str, Any],
         key: Optional[str] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """One structured-output request. Returns the parsed JSON object.

    ``system_blocks`` are constant texts in cache order (the last one is the
    cache breakpoint); nothing per-request may be in them. ``messages`` is the
    Messages API list ending with a user turn. ``key`` groups usage for the
    per-key daily cap (the guest bot passes the property id as a string).
    Raises ``AIDisabled``, ``AIBudgetError`` or ``AIError``; the caller shows
    its own fallback.
    """
    if not enabled(feature):
        raise AIDisabled("disabled")
    key_text = "" if key is None else str(key)
    state = budget_state(feature, key_text if key is not None else None)
    if state != "ok":
        raise AIBudgetError(state)
    if estimate_input_tokens(system_blocks, messages) > config.AI_MAX_INPUT_TOKENS:
        # Never send a request that could reach the 100k long-context price. The caller
        # trims history (Havel) or splits the input (guide import) and tries again.
        log.warning("ai call refused feature=%s reason=input_too_large", feature)
        raise AIError("input_too_large")
    system = [{"type": "text", "text": text} for text in system_blocks]
    system[-1]["cache_control"] = {"type": "ephemeral"}
    started = time.monotonic()
    try:
        response = _get_client().messages.create(
            model=config.AI_MODEL,
            # Callers may ask for less (leon chat ~800), never more than the global cap.
            max_tokens=min(max_tokens or config.AI_MAX_TOKENS, config.AI_MAX_TOKENS),
            system=system,
            messages=messages,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        )
    except Exception as exc:  # the SDK's own classes are not imported here on purpose
        log.warning("ai call failed feature=%s error=%s", feature, type(exc).__name__)
        raise AIError("api") from exc
    usage = getattr(response, "usage", None)
    _record(feature, key_text, usage)
    total_in = sum(getattr(usage, name, 0) or 0 for name in
                   ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    if total_in > config.AI_LONG_CONTEXT_TOKENS:
        log.error("ai long context feature=%s in_total=%d", feature, total_in)
    log.info(
        "ai call feature=%s request_id=%s stop=%s in=%s cache_w=%s cache_r=%s out=%s ms=%d",
        feature,
        getattr(response, "_request_id", None),
        getattr(response, "stop_reason", None),
        getattr(usage, "input_tokens", None),
        getattr(usage, "cache_creation_input_tokens", None),
        getattr(usage, "cache_read_input_tokens", None),
        getattr(usage, "output_tokens", None),
        int((time.monotonic() - started) * 1000),
    )
    stop = getattr(response, "stop_reason", None)
    if stop == "refusal":
        raise AIError("refusal")
    if stop == "max_tokens":
        raise AIError("max_tokens")
    text = next((block.text for block in response.content if getattr(block, "type", "") == "text"), None)
    if text is None:
        raise AIError("no_text")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise AIError("json") from exc
    if not isinstance(data, dict):
        raise AIError("json")
    return data
```

   Command: `cd App && .venv/bin/python -c "import app.ai as ai; print(ai.enabled('havel'))"`. Expected: `False`.

5. **Fake client and tests.** Create `App/tests/ai_fake.py`:

```python
"""A stand-in for the Anthropic client. Tests never call the network."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional


def usage(input_tokens=1000, cache_write=8000, cache_read=0, output=200):
    return SimpleNamespace(
        input_tokens=input_tokens,
        cache_creation_input_tokens=cache_write,
        cache_read_input_tokens=cache_read,
        output_tokens=output,
    )


def reply(data: Optional[Dict[str, Any]] = None, *, text: Optional[str] = None,
          stop_reason: str = "end_turn", thinking_first: bool = True, usage_=None):
    """A response like the SDK's: content blocks read by type, usage, stop reason."""
    content: List[Any] = []
    if thinking_first:
        content.append(SimpleNamespace(type="thinking", thinking="", signature="x"))
    if text is None and data is not None:
        text = json.dumps(data)
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage_ or usage(), _request_id="req_test")


class FakeClient:
    """``FakeClient([reply(...), ...])``; ``.calls`` holds every ``messages.create`` kwargs."""

    def __init__(self, replies: List[Any]):
        self.replies = list(replies)
        self.calls: List[Dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
```

   Create `App/tests/test_ai.py`:

```python
"""0310: ai.py calls the model through one door, records usage and respects the per-feature caps."""
from __future__ import annotations

from datetime import date

import pytest

from app import ai, config, db
from tests.ai_fake import FakeClient, reply, usage

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["kind"],
          "properties": {"kind": {"type": "string"}}}
ROW = ("INSERT INTO ai_usage (day, feature, key, requests, input_tokens, cache_write_tokens, cache_read_tokens, output_tokens) "
       "VALUES (?, ?, ?, 1, ?, 0, 0, 0)")


@pytest.fixture
def on(monkeypatch):
    db.init_db()
    db.execute("DELETE FROM ai_usage", ())
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel", "leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "ai_monthly_usd", lambda feature: 10.0)
    monkeypatch.setattr(config, "ai_key_daily_usd", lambda feature: 0.2 if feature == "leon" else 0.0)  # below leon's daily share, so the key cap bites first
    yield
    ai.set_client_for_tests(None)


def _call(fake, feature="havel", key=None):
    ai.set_client_for_tests(fake)
    return ai.call(feature, ["prompt", "guide", "pages"], [{"role": "user", "content": "hi"}], SCHEMA, key=key)


def test_disabled_unless_listed_and_keyed(monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    with pytest.raises(ai.AIDisabled):
        ai.call("havel", ["p"], [], SCHEMA)
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    with pytest.raises(ai.AIDisabled):
        ai.call("havel", ["p"], [], SCHEMA)


def test_call_sends_structured_output_and_caches_the_last_system_block(on):
    fake = FakeClient([reply({"kind": "answer"})])
    assert _call(fake) == {"kind": "answer"}
    kw = fake.calls[0]
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["max_tokens"] == config.AI_MAX_TOKENS
    assert kw["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert "thinking" not in kw and "temperature" not in kw
    assert kw["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert all("cache_control" not in block for block in kw["system"][:-1])


def test_call_max_tokens_is_clamped_to_the_global_cap(on):
    fake = FakeClient([reply({"kind": "a"}), reply({"kind": "b"})])
    ai.set_client_for_tests(fake)
    ai.call("havel", ["p"], [{"role": "user", "content": "hi"}], SCHEMA, max_tokens=800)
    ai.call("havel", ["p"], [{"role": "user", "content": "hi"}], SCHEMA, max_tokens=99_999)
    assert [c["max_tokens"] for c in fake.calls] == [800, config.AI_MAX_TOKENS]


def test_input_cap_cannot_be_raised_above_the_hard_cap():
    assert config.AI_INPUT_TOKENS_HARD_CAP == 60_000
    assert config.AI_MAX_INPUT_TOKENS <= config.AI_INPUT_TOKENS_HARD_CAP
    # 60k estimated tokens is at most 120k characters: well under 100k real tokens.


def test_too_large_input_is_refused_before_any_api_call(on, monkeypatch):
    monkeypatch.setattr(config, "AI_MAX_INPUT_TOKENS", 1_000)
    fake = FakeClient([reply({"kind": "answer"})])
    ai.set_client_for_tests(fake)
    with pytest.raises(ai.AIError) as err:
        ai.call("havel", ["x" * 2_100], [{"role": "user", "content": "hi"}], SCHEMA)
    assert err.value.reason == "input_too_large"
    assert fake.calls == []
    assert ai.month_spend_usd("havel", ai.today()) == 0.0
    assert ai.call("havel", ["x" * 1_900], [{"role": "user", "content": "hi"}], SCHEMA) == {"kind": "answer"}


def test_call_records_usage_per_day_feature_and_key(on):
    _call(FakeClient([reply({"kind": "a"}), reply({"kind": "b"}, usage_=usage(500, 0, 8000, 100))]))
    ai.call("havel", ["p"], [{"role": "user", "content": "x"}], SCHEMA)
    _call(FakeClient([reply({"kind": "c"})]), feature="leon", key=11)
    row = db.query_one("SELECT * FROM ai_usage WHERE feature = 'havel' AND key = ''", ())
    assert row["requests"] == 2 and row["input_tokens"] == 1500
    assert row["cache_write_tokens"] == 8000 and row["cache_read_tokens"] == 8000 and row["output_tokens"] == 300
    assert db.query_one("SELECT requests FROM ai_usage WHERE feature = 'leon' AND key = '11'", ())["requests"] == 1


def test_refusal_max_tokens_missing_text_and_bad_json_raise(on):
    for item, reason in (
        (reply({"kind": "x"}, stop_reason="refusal"), "refusal"),
        (reply({"kind": "x"}, stop_reason="max_tokens"), "max_tokens"),
        (reply(thinking_first=True), "no_text"),
        (reply(text="not json"), "json"),
        (RuntimeError("boom"), "api"),
    ):
        with pytest.raises(ai.AIError) as err:
            _call(FakeClient([item]))
        assert err.value.reason == reason


def test_budget_month_day_and_key(on, monkeypatch):
    day = date(2026, 10, 10)
    monkeypatch.setattr(ai, "today", lambda: day)
    db.execute(ROW, ("2026-10-02", "havel", "", 30_000_000))  # $3.00 this month
    assert round(ai.month_spend_usd("havel", day), 2) == 3.0
    assert round(ai.daily_allowance_usd("havel", day), 3) == round(7 / 22, 3)  # 22 days left, the 10th included
    assert ai.budget_state("havel", day=day) == "ok"
    db.execute(ROW, ("2026-10-10", "havel", "", 4_000_000))  # $0.40 today > $0.318 (share unchanged by today's spend)
    assert ai.budget_state("havel", day=day) == "day"
    with pytest.raises(ai.AIBudgetError) as err:
        _call(FakeClient([reply({"kind": "a"})]))
    assert err.value.reason == "day"
    db.execute(ROW, ("2026-10-03", "havel", "", 70_000_000))  # +$7.00 => over $10
    assert ai.budget_state("havel", day=day) == "month"
    assert ai.budget_fraction("havel", day) > 1.0
    # Features are separate: leon is untouched by havel's spend, but its key cap bites.
    assert ai.budget_state("leon", "11", day) == "ok"
    db.execute(ROW, ("2026-10-10", "leon", "11", 2_500_000))  # $0.25 for property 11 today > $0.20, < share $0.4545
    assert ai.budget_state("leon", "11", day) == "key"
    assert ai.budget_state("leon", "12", day) == "ok"
    assert ai.budget_state("leon", None, day) == "ok"
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_ai.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. If `db.execute` refuses an empty params tuple, pass no second argument and note it under Deviations.

6. **Environment docs.** In `docs/ENVIRONMENT.md`, directly before the line `## Development and test only`, insert:

```markdown
## Model API (Havel and the guest bot)

Plans: [havel-support-assistant](plans/havel-support-assistant.md). Everything is per feature: `havel` (host support assistant), `leon` (guest bot), `guide_import` (the guest bot's imports), `guide_translate` (guide translation for guests). Every model call goes through `App/app/ai.py`.

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_AI_FEATURES` | unset (all off) | Comma list of features that may call the model, for example `havel` or `havel,leon`. A feature not listed shows its no-AI fallback (Havel: quick help and the support form). |
| `UBYHOST_ANTHROPIC_API_KEY` | unset | Anthropic API key, created in the Anthropic Console with its own monthly spend limit. Passed to the SDK explicitly; the SDK's `ANTHROPIC_API_KEY` is not read. Staging first. |
| `UBYHOST_AI_MODEL` | `claude-haiku-5-5` | Model id. Changing it invalidates the prompt cache and needs each feature's test set re-run. |
| `UBYHOST_AI_MAX_TOKENS` | `4000` | Ceiling per call; adaptive thinking counts toward it. Callers pass their own lower `max_tokens` (Havel 2500, Leon chat about 800, the import merge up to the ceiling). |
| `UBYHOST_AI_MAX_INPUT_TOKENS` | `60000` (also the hard maximum) | Largest input one request may send, estimated as 1 token per 2 characters. Haiku 5.5 costs 5x more above 100,000 input tokens, so a larger value is ignored. A request over it raises `input_too_large` and is not sent. |
| `UBYHOST_AI_MONTHLY_USD_<FEATURE>` | `10` | Spend cap per feature per calendar month (Prague), e.g. `UBYHOST_AI_MONTHLY_USD_HAVEL`. Today's share is the budget left divided by the days left in the month. |
| `UBYHOST_AI_KEY_DAILY_USD_<FEATURE>` | `0` (off) | Per-key daily cap, e.g. `UBYHOST_AI_KEY_DAILY_USD_LEON=0.50` caps one property's guest bot at 50 cents a day. Havel passes no key. |
| `UBYHOST_AI_PRICE_INPUT`, `UBYHOST_AI_PRICE_OUTPUT`, `UBYHOST_AI_PRICE_CACHE_READ`, `UBYHOST_AI_PRICE_CACHE_WRITE` | `0.10`, `0.50`, `0.01`, `0.125` | USD per million tokens, Anthropic table 2026-10-06. Update when the price changes. |
| `UBYHOST_HAVEL_WEEKLY`, `UBYHOST_HAVEL_MONTHLY` | `8`, `15` | Havel messages per host per calendar week and month. |

```

   In `docs/context/architecture.md`, directly after the row that starts `| Mail | \`App/app/mail.py\``, insert:

```
| AI | `App/app/ai.py` (the one door to the model API: structured call, usage ledger per day, feature and key, per-feature monthly budget, daily share and per-key cap; nothing else imports the SDK) |
```

   In `docs/context/test-map.md`, directly after the row `| Cleaning | \`test_cleaning*.py\` |`, insert:

```
| AI calls, Havel | `test_ai*.py test_havel*.py`; UI parts also the host pages row |
```

   Command: `grep -c 'UBYHOST_AI_FEATURES' docs/ENVIRONMENT.md; grep -c 'app/ai.py' docs/context/architecture.md; grep -c 'test_havel' docs/context/test-map.md`. Expected: `1`, `1`, `1`.

7. **Decision line with compaction.** `docs/context/decisions.md` is at its token cap. Save this as `/tmp/claude-0/s/compact0310.py` and run it from the repo root with `python3 /tmp/claude-0/s/compact0310.py 2>&1 | tail -3`:

```python
from pathlib import Path

src = Path("docs/context/decisions.md")
dst = Path("docs/archive/decisions-2026.md")
starts = (
    "- 2026-09-26 | Every change goes through an owner-reviewed PR;",
    "- 2026-09-26 | Invoices standalone/host-only;",
    "- 2026-10-03 | Filing: one automatic retry,",
    "- 2026-10-04 | Lightsail 8 GB / 2 vCPU",
    "- 2026-10-05 | Umami only on public pages;",
    "- 2026-10-05 | Ticket Wallet guest UI archived",
)
lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
moved = [l for l in lines if l.startswith(starts)]
assert len(moved) == 6, [l[:40] for l in moved]
kept = [l for l in lines if not l.startswith(starts)]
header = "# Decisions archive 2026\n\nMoved from docs/context/decisions.md (workflow.md, Compaction). Live rules stay in rules.md.\n\n"
dst.write_text((dst.read_text(encoding="utf-8") if dst.exists() else header) + "".join(moved), encoding="utf-8")
new = ("- 2026-10-24 | New dependency `anthropic` (Python SDK 2.3.0, pinned in `App/requirements.txt`, hashes with its "
       "transitive packages in `App/requirements.lock`: PACKAGES); model `claude-haiku-5-5`; every model call through "
       "`App/app/ai.py`, per-feature switch and budget | Havel support assistant and the guest assistant; one module to "
       "swap providers | [plan](../plans/havel-support-assistant.md), task 0310\n")
src.write_text("".join(kept).rstrip("\n") + "\n" + new, encoding="utf-8")
print("moved", len(moved), "added 1")
```

   Then replace `PACKAGES` in the new last line of `docs/context/decisions.md` with the package list from step 1. Command: `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: last line `context lint: OK`.

## 5. Do not touch

Anything not in section 3. No route, template or `havel*.py` (those are 0311–0314); nothing from the guest plan (0291–0309). Never commit a key or `.env`. Run `git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_|sk-ant'` before every commit (`ANTHROPIC_API_KEY = os.environ.get(` and the docs rows are the only expected matches).

## 6. Commands (from `App/`)

```
.venv/bin/python -m pytest tests/test_ai.py tests/test_migrations.py tests/test_db_*.py -q --tb=short -x 2>&1 | tail -30
cd .. && python3 scripts/context_lint.py 2>&1 | tail -3
```

Expected: all pass; `context lint: OK` (the pre-existing WARN lines about other briefs are fine).

## 7. Acceptance

- [ ] `anthropic==2.3.0` in `App/requirements.txt`; `requirements.lock` regenerated with hashes; `pip install --require-hashes -r requirements.lock` succeeds.
- [ ] `App/app/ai.py` is the only file under `App/app/` that contains `import anthropic` (`grep -rl 'import anthropic' App/app`).
- [ ] `test_ai.py` passes: structured output, cache breakpoint, usage upsert per key, error reasons, month, day and key caps, features independent, input cap (refused before any API call, cannot be raised above 60,000).
- [ ] The migration applies with the next free number; `test_migrations.py` passes.
- [ ] ENVIRONMENT.md section, architecture row, test-map row, decision line present; lint OK.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: `anthropic` 2.3.0 is not on PyPI; pip has no network; the compaction script moves a count other than 6; the lint's next free migration is not 0015 (use it, but say so).

## 9. Report

`docs/tasks/0310-report.md` (600 tokens at most): files, each command's last 5 lines, section 7 ticked, the pinned version, the package list and the migration number used, Deviations, Questions, owner steps. Set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/ai.py` (budget maths, cache placement, no text in logs), `App/requirements.lock` (only additions), `docs/context/decisions.md` (six lines moved, one added).

## Owner steps

1. Read the decision line in `docs/context/decisions.md` and the package list in the report. If you would rather add no package, say "requests instead" and 0310 gets a correction brief.
2. In the Anthropic Console, create an API key for a workspace with a monthly spend limit of 10 USD. Do not paste it anywhere in the repo.
3. On Render (staging) add `UBYHOST_ANTHROPIC_API_KEY` with that key. Leave `UBYHOST_AI_FEATURES` unset until 0313 is on staging.
