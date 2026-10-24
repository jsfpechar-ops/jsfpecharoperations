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
