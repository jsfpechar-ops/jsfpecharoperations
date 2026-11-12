"""Minimal Mistral chat completion with the official Python SDK.

Install the SDK:
    pip install mistralai

Generate an API key in Mistral Studio:
    1. Sign in at https://console.mistral.ai
    2. In the left sidebar open "API keys" (under your workspace)
    3. Click "Create new key", give it a name, and copy the value once

Set MISTRAL_API_KEY in your terminal (macOS/Linux):
    export MISTRAL_API_KEY="your-key-here"
Windows (PowerShell):
    $env:MISTRAL_API_KEY = "your-key-here"

Run from the project folder (the repository root):
    python main.py

Docs: https://docs.mistral.ai/inference/conversations/chat-completion
"""

import os
import sys

from mistralai.client import Mistral

MODEL = "mistral-small-latest"


def main() -> int:
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        print(
            "MISTRAL_API_KEY is not set; export it first, e.g. "
            'export MISTRAL_API_KEY="your-key-here"',
            file=sys.stderr,
        )
        return 1

    client = Mistral(api_key=api_key)
    chat_response = client.chat.complete(
        model=MODEL,
        messages=[
            {"role": "user", "content": "Say hello in one short sentence."},
        ],
    )
    print(chat_response.choices[0].message.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
