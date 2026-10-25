"""0334: the Mistral backup goes through the same caps and ledger as Anthropic."""
from __future__ import annotations

import json

import pytest

from app import ai, config, db

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["kind"],
          "properties": {"kind": {"type": "string"}}}


@pytest.fixture
def mistral(monkeypatch):
    db.init_db()
    db.execute("DELETE FROM ai_usage", ())
    monkeypatch.setattr(config, "AI_PROVIDER", "mistral")
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "MISTRAL_API_KEY", "m-key")
    monkeypatch.setattr(config, "ai_monthly_usd", lambda feature: 10.0)
    sent = []

    def fake_post(body, replies=[]):
        sent.append(body)
        return replies.pop(0) if replies else {
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"kind": "answer"})}}],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 80}}

    monkeypatch.setattr(ai, "_mistral_post", fake_post)
    return sent


def test_mistral_needs_its_own_key(mistral, monkeypatch):
    assert ai.enabled("havel")
    monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
    assert not ai.enabled("havel")


def test_request_shape_and_ledger(mistral):
    out = ai.call("havel", ["prompt", "guide"], [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                  SCHEMA, max_tokens=800)
    assert out == {"kind": "answer"}
    body = mistral[0]
    assert body["model"] == config.MISTRAL_MODEL and body["max_tokens"] == 800
    assert body["messages"][0] == {"role": "system", "content": "prompt\n\nguide"}
    assert body["messages"][1] == {"role": "user", "content": "hi"}
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    row = db.query("SELECT requests, input_tokens, output_tokens FROM ai_usage WHERE feature = 'havel'")[0]
    assert (row["requests"], row["input_tokens"], row["output_tokens"]) == (1, 1200, 80)


def test_cut_off_and_bad_json_raise(mistral, monkeypatch):
    for data, reason in [
        ({"choices": [{"finish_reason": "length", "message": {"content": "{"}}], "usage": {}}, "max_tokens"),
        ({"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}], "usage": {}}, "json"),
        ({"choices": [{"finish_reason": "stop", "message": {"content": ""}}], "usage": {}}, "no_text"),
    ]:
        monkeypatch.setattr(ai, "_mistral_post", lambda body, d=data: d)
        with pytest.raises(ai.AIError) as err:
            ai.call("havel", ["p"], [{"role": "user", "content": "hi"}], SCHEMA)
        assert err.value.reason == reason


def test_network_error_is_api_and_caps_still_apply(mistral, monkeypatch):
    def boom(body):
        raise OSError("down")
    monkeypatch.setattr(ai, "_mistral_post", boom)
    with pytest.raises(ai.AIError) as err:
        ai.call("havel", ["p"], [{"role": "user", "content": "hi"}], SCHEMA)
    assert err.value.reason == "api"
    monkeypatch.setattr(config, "AI_MAX_INPUT_TOKENS", 10)
    with pytest.raises(ai.AIError) as err:
        ai.call("havel", ["x" * 100], [{"role": "user", "content": "hi"}], SCHEMA)
    assert err.value.reason == "input_too_large"
