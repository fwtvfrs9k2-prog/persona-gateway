#!/bin/sh
# Combined service start script (Render, one service, two processes).
# Public port: $PORT (Render sets this, e.g. 10000)
# Internal sub2api port: 8080
# Gateway proxies /v1 to internal sub2api and other paths to its admin UI.
# If the sub2api binary is not found at the guessed paths, the gateway
# still starts in separate-service mode (UPSTREAM_BASE_URL = public sub URL).
set -e
export SUB_INTERNAL_URL="http://127.0.0.1:8080"
export UPSTREAM_BASE_URL="http://127.0.0.1:8080/v1"
SUB_BIN=""
for p in /app/sub2api /sub2api /usr/local/bin/sub2api sub2api; do
  if [ -x "$p" ]; then SUB_BIN="$p"; break; fi
  if command -v "$p" >/dev/null 2>&1; then SUB_BIN="$p"; break; fi
done
if [ -n "$SUB_BIN" ]; then
  echo "Starting sub2api from $SUB_BIN on 8080"
  SERVER_PORT=8080 PORT=8080 "$SUB_BIN" &
  SUB_PID=$!
else
  echo "sub2api binary not found, gateway will proxy to public sub URL"
  export UPSTREAM_BASE_URL="https://sub2api-rg8f.onrender.com/v1"
  export SUB_INTERNAL_URL=""
fi
echo "Starting persona gateway on $PORT"
exec uvicorn gateway:app --host 0.0.0.0 --port "${PORT:-10000}"
