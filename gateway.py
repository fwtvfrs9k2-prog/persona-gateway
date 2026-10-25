"""
Persona gateway for DSH -> sub2api -> windking relay.

Clean placeholder persona only. No credentials are hard-coded here:
- The client (DSH) sends its own unified key in Authorization; the gateway
  forwards it unchanged to sub2api.
- PERSONA_SYSTEM_PROMPT is read from the environment (Render Environment
  tab), so the persona can be changed in Render without changing code.
- UPSTREAM_BASE_URL defaults to the existing Render sub2api /v1 endpoint.
  In a combined service, set UPSTREAM_BASE_URL to the internal sub2api
  address, e.g. http://127.0.0.1:8080/v1, and SUB_INTERNAL_URL to
  http://127.0.0.1:8080 for admin/homepage proxying.

Endpoints:
  GET  /            -> gateway info / health, no key required
  GET  /health      -> {"ok": true}
  POST /v1/chat/completions -> inject persona, forward to upstream, stream back
  GET  /v1/models   -> forward to upstream
  Any other path    -> if SUB_INTERNAL_URL is set, proxy to it (combined
                       service: sub2api admin UI); otherwise return gateway info.
"""
import os
import json
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

PERSONA = os.environ.get(
    "PERSONA_SYSTEM_PROMPT",
    "你是一个耐心、直接、有帮助的助手。用中文回答，条理清晰，"
    "先给结论再给步骤，遇到不确定的地方就明说，不要编造。",
)
UPSTREAM_BASE_URL = os.environ.get(
    "UPSTREAM_BASE_URL", "https://sub2api-rg8f.onrender.com/v1"
).rstrip("/")
SUB_INTERNAL_URL = os.environ.get("SUB_INTERNAL_URL", "").rstrip("/")

app = FastAPI(title="persona-gateway")


def inject_persona(body: dict) -> dict:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body
    if messages and messages[0].get("role") == "system":
        existing = messages[0].get("content") or ""
        if PERSONA in str(existing):
            return body
        # NOTE (2026-10-25, user hypothesis, unproven): windking may strip
        # lowercase "system" at entry, so try capital "System" for the
        # injected persona only. This is non-standard OpenAI role casing;
        # if upstream rejects/drops it, revert to "system".
        messages = [{"role": "System", "content": PERSONA}] + messages
    else:
        messages = [{"role": "System", "content": PERSONA}] + messages
    body["messages"] = messages
    return body


@app.get("/")
async def root():
    return {
        "service": "persona-gateway",
        "upstream": UPSTREAM_BASE_URL,
        "persona_preview": PERSONA[:60],
        "usage": "POST /v1/chat/completions with your usual Authorization header",
    }


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/v1/models")
async def models(request: Request):
    headers = {}
    if request.headers.get("authorization"):
        headers["Authorization"] = request.headers["authorization"]
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        r = await client.get(f"{UPSTREAM_BASE_URL}/models", headers=headers)
        return Response(content=r.content, status_code=r.status_code,
                        media_type=r.headers.get("content-type", "application/json"))


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    body = inject_persona(body)
    headers = {"Content-Type": "application/json"}
    if request.headers.get("authorization"):
        headers["Authorization"] = request.headers["authorization"]
    stream = bool(body.get("stream"))

    async def gen():
        async with httpx.AsyncClient(timeout=300, trust_env=False) as client:
            async with client.stream(
                "POST", f"{UPSTREAM_BASE_URL}/chat/completions",
                json=body, headers=headers,
            ) as r:
                if r.status_code != 200:
                    data = await r.aread()
                    yield data
                    return
                async for chunk in r.aiter_bytes():
                    if chunk:
                        yield chunk

    if stream:
        return StreamingResponse(gen(), media_type="text/event-stream")
    # Non-streaming: collect the proxied response so status is preserved.
    async with httpx.AsyncClient(timeout=300, trust_env=False) as client:
        r = await client.post(
            f"{UPSTREAM_BASE_URL}/chat/completions", json=body, headers=headers
        )
        return Response(content=r.content, status_code=r.status_code,
                        media_type=r.headers.get("content-type", "application/json"))


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_other(request: Request, path: str):
    if not SUB_INTERNAL_URL:
        return JSONResponse(
            {"service": "persona-gateway", "path": f"/{path}",
             "hint": "Use POST /v1/chat/completions"},
            status_code=404,
        )
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length")}
    async with httpx.AsyncClient(timeout=60, follow_redirects=False, trust_env=False) as client:
        r = await client.request(
            request.method, f"{SUB_INTERNAL_URL}/{path}",
            content=body if body else None, headers=headers,
            params=dict(request.query_params),
        )
        return Response(content=r.content, status_code=r.status_code,
                        headers={k: v for k, v in r.headers.items()
                                 if k.lower() not in ("content-length", "transfer-encoding")})
