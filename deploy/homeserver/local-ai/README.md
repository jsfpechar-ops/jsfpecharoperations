# Local AI on the homeserver (Ollama + Open WebUI)

Single compose stack: Ollama serves the OpenAI-compatible API on port **11434**
(for coding tools), Open WebUI is the chat UI on port **3000**. The models
already in the `local-ai_ollama_data` volume are reused untouched.

## Deploy (on the homeserver)

```bash
mkdir -p ~/local-ai
cp /path/to/this/repo/deploy/homeserver/local-ai/docker-compose.yml ~/local-ai/
docker rm -f ollama        # old standalone container; its models volume stays
cd ~/local-ai && docker compose up -d
```

## Verify

```bash
docker compose ps                                  # ollama + open-webui Up
docker exec ollama ollama list                     # qwen2.5-coder:7b and deepseek-r1 must appear
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000            # 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:11434/api/tags  # 200
```

## Use

- Chat UI: `http://<homeserver-ip>:3000` (fresh install, no old history).
- API for coding tools: `http://<homeserver-ip>:11434/v1` (OpenAI-compatible),
  model `qwen2.5-coder:7b`.

Set `LOCAL_AI_BIND=127.0.0.1` before `docker compose up` to keep both ports
local-only instead of LAN-wide.
