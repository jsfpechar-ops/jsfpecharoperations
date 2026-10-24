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
