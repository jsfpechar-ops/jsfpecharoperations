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
