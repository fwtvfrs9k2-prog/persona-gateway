# persona-gateway

Simple FastAPI gateway for DSH -> sub2api -> windking relay.

- POST /v1/chat/completions: injects PERSONA_SYSTEM_PROMPT as a system
  message (once, no duplication), forwards Authorization unchanged to
  UPSTREAM_BASE_URL, streams the response back.
- GET /v1/models, GET /health, GET /: proxied / info.
- Other paths: if SUB_INTERNAL_URL is set (combined service), proxy to
  sub2api admin UI; otherwise return gateway info.

Env vars (Render):
- PERSONA_SYSTEM_PROMPT: placeholder persona, default in gateway.py:
  "你是一个耐心、直接、有帮助的助手。用中文回答，条理清晰，先给结论再给步骤，遇到不确定的地方就明说，不要编造。"
- UPSTREAM_BASE_URL: default https://sub2api-rg8f.onrender.com/v1
  (combined service: http://127.0.0.1:8080/v1)
- SUB_INTERNAL_URL: empty for separate service, http://127.0.0.1:8080 for combined.

No secrets are hard-coded in this repo. DSH sends its own unified key.
