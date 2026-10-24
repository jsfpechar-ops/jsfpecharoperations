# 0334: AI core: Mistral as a backup provider, one setting away

Status: todo
Depends on: 0310 (merged) | Base commit: check `git rev-parse --short origin/main` and write it here | Branch: task/0334-ai-mistral-backup
Executor: Haiku 5.5 | Fits one session: 18 tool calls, 45k tokens

## 1. Objective

The owner (2026-10-24) keeps Claude Haiku as the model for Havel and Leon but wants Mistral ready as a backup. Add a second provider to `App/app/ai.py`, chosen by `UBYHOST_AI_PROVIDER=mistral`. Default stays `anthropic`, so nothing changes until the owner sets it. Mistral is called over HTTPS with the `requests` library the app already has, so there is **no new dependency**. Every caller (`ai.call(...)`) stays the same: same caps, same input cap, same ledger, same errors.

## 2. Context

- `App/app/ai.py` (0310) is the only door to a model. Read lines 1 to 75 and `def call(` to the end: `grep -n 'def \|^_client\|import' app/ai.py`. `call()` checks `enabled`, `budget_state`, `estimate_input_tokens`, then sends one Anthropic request with `output_config.format` json_schema, records usage with `_record(feature, key_text, usage)` (reads `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens` with `getattr`), and parses the JSON text.
- `App/app/config.py`: AI block from the line `AI_FEATURES = frozenset(` to `def ai_key_daily_usd`. `grep -n 'AI_\|ANTHROPIC' app/config.py`.
- Mistral chat API (docs.mistral.ai/api, checked 2026-10-24): `POST https://api.mistral.ai/v1/chat/completions`, header `Authorization: Bearer <key>`, body `{"model", "messages": [{"role": "system"|"user"|"assistant", "content": str}], "max_tokens", "temperature", "response_format": {"type": "json_schema", "json_schema": {"name": "reply", "schema": <schema>, "strict": true}}}`. The reply JSON text is `choices[0].message.content`, the stop reason is `choices[0].finish_reason` (`stop`, or `length` when cut off), usage is `usage.prompt_tokens` and `usage.completion_tokens`. Mistral is an EU company with EU processing.
- Tests use fakes only; nothing may call the network.

## 3. Files

| File | Change | Why |
|---|---|---|
| App/app/config.py | edit | provider, Mistral key and model, provider-aware price defaults |
| App/app/ai.py | edit | `enabled()` per provider, `_call_mistral`, one branch in `call()` |
| App/tests/test_ai_mistral.py | new | |
| docs/ENVIRONMENT.md | edit | three rows in "Model API" |

## 4. Steps

1. **Config.** In `App/app/config.py`, directly after the line that starts `AI_MODEL = os.environ.get("UBYHOST_AI_MODEL"`, insert:

```python
# 0334: the provider behind ai.call(). "anthropic" (default) or "mistral", the
# owner's EU backup. Switching needs the Mistral key and a re-run of the test sets.
AI_PROVIDER = os.environ.get("UBYHOST_AI_PROVIDER", "anthropic").strip().lower()
if AI_PROVIDER not in ("anthropic", "mistral"):
    AI_PROVIDER = "anthropic"
MISTRAL_API_KEY = os.environ.get("UBYHOST_MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.environ.get("UBYHOST_MISTRAL_MODEL", "mistral-small-latest")
# Default USD per million tokens per provider; UBYHOST_AI_PRICE_* still overrides.
# Mistral Small: check mistral.ai/pricing before switching and set the env vars.
_AI_PRICE_DEFAULTS = {
    "anthropic": {"input": "0.10", "output": "0.50", "cache_read": "0.01", "cache_write": "0.125"},
    "mistral": {"input": "0.10", "output": "0.30", "cache_read": "0.01", "cache_write": "0.10"},
}[AI_PROVIDER]
```

   Then in the `AI_PRICE_USD_PER_MTOK = {` dict replace the four defaults `"0.10")`, `"0.50")`, `"0.01")`, `"0.125")` with `_AI_PRICE_DEFAULTS["input"])`, `_AI_PRICE_DEFAULTS["output"])`, `_AI_PRICE_DEFAULTS["cache_read"])`, `_AI_PRICE_DEFAULTS["cache_write"])`. Check: `.venv/bin/python -c "from app import config as c; print(c.AI_PROVIDER, c.AI_PRICE_USD_PER_MTOK)"` prints `anthropic {'input': 0.1, 'output': 0.5, 'cache_read': 0.01, 'cache_write': 0.125}`.

2. **enabled().** In `App/app/ai.py` replace the body of `def enabled(feature: str) -> bool:` with:

```python
    key = config.MISTRAL_API_KEY if config.AI_PROVIDER == "mistral" else config.ANTHROPIC_API_KEY
    return bool(feature in config.AI_FEATURES and key)
```

3. **Mistral call.** Add `from types import SimpleNamespace` to the imports and, directly above the line `# --- the call ---`, add:

```python
# --- Mistral (0334, the owner's backup provider) -------------------------------

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"


def _mistral_post(body: Dict[str, Any]) -> Dict[str, Any]:
    """One HTTPS request to Mistral; tests replace this function. Retries once on a network error or 5xx."""
    import requests  # already an app dependency

    headers = {"Authorization": f"Bearer {config.MISTRAL_API_KEY}", "Content-Type": "application/json"}
    for attempt in (1, 2):
        try:
            res = requests.post(MISTRAL_URL, json=body, headers=headers, timeout=20)
        except requests.RequestException:
            if attempt == 2:
                raise
            continue
        if res.status_code >= 500 and attempt == 1:
            continue
        res.raise_for_status()
        return res.json()
    raise RuntimeError("unreachable")


def _plain(content: Any) -> str:
    """Anthropic-style content (a string or a list of text blocks) as one string."""
    if isinstance(content, str):
        return content
    return "\n".join(str(block.get("text", "")) for block in content if isinstance(block, dict))


def _call_mistral(feature: str, key_text: str, system_blocks: List[str], messages: List[Dict[str, Any]],
                  schema: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
    body = {
        "model": config.MISTRAL_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "messages": [{"role": "system", "content": "\n\n".join(system_blocks)}]
        + [{"role": m["role"], "content": _plain(m["content"])} for m in messages],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "reply", "schema": schema, "strict": True}},
    }
    started = time.monotonic()
    try:
        data = _mistral_post(body)
    except Exception as exc:
        log.warning("ai call failed provider=mistral feature=%s error=%s", feature, type(exc).__name__)
        raise AIError("api") from exc
    raw = data.get("usage") or {}
    usage = SimpleNamespace(input_tokens=int(raw.get("prompt_tokens") or 0), cache_creation_input_tokens=0,
                            cache_read_input_tokens=0, output_tokens=int(raw.get("completion_tokens") or 0))
    _record(feature, key_text, usage)
    choice = (data.get("choices") or [{}])[0]
    stop = choice.get("finish_reason")
    log.info("ai call provider=mistral feature=%s stop=%s in=%s out=%s ms=%d", feature, stop,
             usage.input_tokens, usage.output_tokens, int((time.monotonic() - started) * 1000))
    if stop in ("length", "model_length"):
        raise AIError("max_tokens")
    text = (choice.get("message") or {}).get("content")
    if not isinstance(text, str) or not text.strip():
        raise AIError("no_text")
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise AIError("json") from exc
    if not isinstance(parsed, dict):
        raise AIError("json")
    return parsed
```

4. **Branch in call().** In `def call(`, directly after the `raise AIError("input_too_large")` line (and its blank line), insert:

```python
    limit = min(max_tokens or config.AI_MAX_TOKENS, config.AI_MAX_TOKENS)
    if config.AI_PROVIDER == "mistral":
        return _call_mistral(feature, key_text, system_blocks, messages, schema, limit)
```

   and in the Anthropic request change `max_tokens=min(max_tokens or config.AI_MAX_TOKENS, config.AI_MAX_TOKENS),` to `max_tokens=limit,`. Update the module docstring's first paragraph by adding the sentence: `UBYHOST_AI_PROVIDER=mistral sends the same request to Mistral instead (0334).`

5. **Tests.** Create `App/tests/test_ai_mistral.py`:

```python
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
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_ai_mistral.py tests/test_ai.py -q --tb=short -x 2>&1 | tail -15`. Expected: all pass (test_ai.py proves Anthropic is unchanged).

6. **Environment docs.** In `docs/ENVIRONMENT.md`, section `## Model API (Havel and the guest bot)`, after the `UBYHOST_AI_MODEL` row add:

```markdown
| `UBYHOST_AI_PROVIDER` | `anthropic` | `mistral` switches every AI feature to Mistral (EU backup, 0334). Set `UBYHOST_MISTRAL_API_KEY` first, update the `UBYHOST_AI_PRICE_*` values from mistral.ai/pricing, and re-run `scripts/havel_eval.py` and Leon's test set. |
| `UBYHOST_MISTRAL_API_KEY` | unset | Mistral API key; used only when the provider is `mistral`. Secret: never in the repo. |
| `UBYHOST_MISTRAL_MODEL` | `mistral-small-latest` | Mistral model id. |
```

## 5. Do not touch

Every caller of `ai.call`, `havel*.py`, Leon's code, `requirements*`. No new dependency, no migration.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_ai_mistral.py tests/test_ai.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -15`
- `grep -rl 'import anthropic' app` prints only `app/ai.py`; from the repo root `python3 scripts/context_lint.py | tail -3`; before committing `git diff --cached | grep -iE 'sk-|api[_-]?key\s*=\s*"[^"]'` prints nothing.

## 7. Acceptance

- [ ] With no new env var, behaviour is exactly as before (test_ai.py passes unchanged).
- [ ] `UBYHOST_AI_PROVIDER=mistral` sends a json_schema request to Mistral, records usage in `ai_usage`, and raises the same `AIError` reasons.
- [ ] Budget, per-key and input caps apply to both providers.
- [ ] ENVIRONMENT.md has the three rows; lint OK; no new dependency.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: an anchor line in section 4 is missing, or `requests` is not in `App/requirements.txt`.

## 9. Report

`docs/tasks/0334-report.md` (400 tokens at most): files, command tails, section 7 ticked, Deviations. Set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/ai.py` (the Anthropic path must be byte-for-byte the same apart from `limit`), `App/app/config.py` (price defaults unchanged for anthropic).

## Owner steps (only when switching)

1. At console.mistral.ai create an API key with a monthly spend limit.
2. In Render (and later the server `.env`) set `UBYHOST_MISTRAL_API_KEY`, the Mistral prices in `UBYHOST_AI_PRICE_INPUT` and `UBYHOST_AI_PRICE_OUTPUT`, then `UBYHOST_AI_PROVIDER=mistral`.
3. Ask Claude to run the Havel and Leon test sets against Mistral before real hosts use it. Switching back is removing `UBYHOST_AI_PROVIDER`.
4. Before real hosts or guests use it, add Mistral AI (France, EU processing) to the subprocessor register and privacy texts, like Anthropic in 0329.
