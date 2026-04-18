#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${BUILD_DIR:-${SCRIPT_DIR}/build}"
SERVER_BIN="${SERVER_BIN:-${BUILD_DIR}/embedding_server}"
PROTO_FILE="${PROTO_FILE:-${SCRIPT_DIR}/proto/embedding.proto}"
GRPCURL_BIN="${GRPCURL_BIN:-grpcurl}"
SERVICE_HOST="${SERVICE_HOST:-127.0.0.1}"
SERVICE_PORT="${SERVICE_PORT:-50051}"
SERVICE_ADDR="${SERVICE_HOST}:${SERVICE_PORT}"
SERVER_LOG="$(mktemp -t embedding_onnx_fallback.XXXXXX.log)"
SERVER_PID=""

cleanup() {
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  rm -f "$SERVER_LOG"
}

trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[Error] Missing required command: $1" >&2
    exit 1
  }
}

grpcurl_call() {
  "$GRPCURL_BIN" -plaintext -import-path "$(dirname "$PROTO_FILE")" -proto "$PROTO_FILE" "$SERVICE_ADDR" "$@"
}

wait_for_service() {
  local i
  for ((i = 1; i <= 30; i++)); do
    if grpcurl_call list >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

require_cmd "$GRPCURL_BIN"
[ -x "$SERVER_BIN" ] || { echo "[Error] Server binary not found: $SERVER_BIN" >&2; exit 1; }
[ -f "$PROTO_FILE" ] || { echo "[Error] Proto file not found: $PROTO_FILE" >&2; exit 1; }

echo "[1/3] Start server with ONNX requested but missing model path"
EMBEDDING_BACKEND=onnx SERVE_PORT="$SERVICE_PORT" "$SERVER_BIN" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

wait_for_service || {
  echo "[Error] Server failed to start" >&2
  cat "$SERVER_LOG" >&2
  exit 1
}

echo "[2/3] Validate fallback logs"
if grep -q "ONNX backend requested but not compiled" "$SERVER_LOG"; then
  echo "[Info] ONNX backend not compiled path verified"
elif grep -q "Failed to initialize embedding backend" "$SERVER_LOG" && \
     grep -q "Falling back to mock embedding backend" "$SERVER_LOG"; then
  echo "[Info] ONNX init failure fallback path verified"
else
  echo "[Error] Expected fallback log path not found" >&2
  cat "$SERVER_LOG" >&2
  exit 1
fi
grep -q "provider=local-mock" "$SERVER_LOG" || {
  echo "[Error] Expected fallback log not found" >&2
  cat "$SERVER_LOG" >&2
  exit 1
}

echo "[3/3] Validate Info endpoint after fallback"
INFO_OUTPUT="$(grpcurl_call embedding.EmbeddingService/Info)"
echo "$INFO_OUTPUT"
echo "$INFO_OUTPUT" | grep -q '"provider": "local-mock"' || {
  echo "[Error] Expected provider=local-mock after fallback" >&2
  exit 1
}
echo "$INFO_OUTPUT" | grep -q '"model": "local-mock-embedding"' || {
  echo "[Error] Expected model=local-mock-embedding after fallback" >&2
  exit 1
}

echo "[OK] ONNX fallback test passed"
