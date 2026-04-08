#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${1:-${SERVICE_HOST:-localhost}}"
PORT="${2:-${SERVICE_PORT:-50051}}"
PROTO_FILE="${3:-${PROTO_FILE:-${SCRIPT_DIR}/proto/embedding.proto}}"
GRPCURL_BIN="${GRPCURL_BIN:-grpcurl}"
ADDR="${HOST}:${PORT}"
PROTO_DIR="$(dirname "$PROTO_FILE")"

fail() {
  echo "[Error] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

grpcurl_call() {
  if [[ "${1:-}" == "-d" ]]; then
    local data="$2"
    shift 2
    "$GRPCURL_BIN" -plaintext -import-path "$PROTO_DIR" -proto "$PROTO_FILE" -d "$data" "$ADDR" "$@"
    return
  fi
  "$GRPCURL_BIN" -plaintext -import-path "$PROTO_DIR" -proto "$PROTO_FILE" "$ADDR" "$@"
}

require_cmd "$GRPCURL_BIN"
[[ -f "$PROTO_FILE" ]] || fail "Proto file not found: $PROTO_FILE"

echo "=========================================="
echo "Embedding Service Quick Check"
echo "Target: ${ADDR}"
echo "Proto:  ${PROTO_FILE}"
echo "=========================================="
echo ""

echo "[1/5] Listing service"
LIST_OUTPUT="$(grpcurl_call list)"
echo "$LIST_OUTPUT"
echo "$LIST_OUTPUT" | grep -q "embedding.EmbeddingService" || fail "Service list does not include embedding.EmbeddingService"
echo ""

echo "[2/5] Describing service"
DESCRIBE_OUTPUT="$(grpcurl_call describe embedding.EmbeddingService)"
echo "$DESCRIBE_OUTPUT"
echo "$DESCRIBE_OUTPUT" | grep -q "GetEmbedding" || fail "Service description missing GetEmbedding"
echo "$DESCRIBE_OUTPUT" | grep -q "GetEmbeddings" || fail "Service description missing GetEmbeddings"
echo "$DESCRIBE_OUTPUT" | grep -q "Info" || fail "Service description missing Info"
echo ""

echo "[3/5] Calling Info"
INFO_OUTPUT="$(grpcurl_call embedding.EmbeddingService/Info)"
echo "$INFO_OUTPUT"
echo "$INFO_OUTPUT" | grep -q '"provider"' || fail "Info response missing provider"
echo "$INFO_OUTPUT" | grep -q '"model"' || fail "Info response missing model"
echo "$INFO_OUTPUT" | grep -q '"dimensions"' || fail "Info response missing dimensions"
echo ""

echo "[4/5] Calling GetEmbedding"
EMBED_OUTPUT="$(grpcurl_call -d '{"text":"hello world"}' embedding.EmbeddingService/GetEmbedding)"
echo "$EMBED_OUTPUT"
echo "$EMBED_OUTPUT" | grep -q '"embedding"' || fail "GetEmbedding response missing embedding field"
if echo "$EMBED_OUTPUT" | grep -Eq '"embedding"[[:space:]]*:[[:space:]]*\[[[:space:]]*\]'; then
  fail "GetEmbedding returned an empty embedding"
fi
echo ""

echo "[5/5] Calling GetEmbeddings"
BATCH_OUTPUT="$(grpcurl_call -d '{"texts":["hello world","test message"]}' embedding.EmbeddingService/GetEmbeddings)"
echo "$BATCH_OUTPUT"
echo "$BATCH_OUTPUT" | grep -q '"items"' || fail "GetEmbeddings response missing items field"
echo "$BATCH_OUTPUT" | grep -q '"embedding"' || fail "GetEmbeddings response missing embedding values"
if echo "$BATCH_OUTPUT" | grep -Eq '"items"[[:space:]]*:[[:space:]]*\[[[:space:]]*\]'; then
  fail "GetEmbeddings returned empty items"
fi

echo ""
echo "[OK] Quick check passed"
