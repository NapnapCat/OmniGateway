#!/usr/bin/env bash

# Comprehensive test for embedding service implementation
# Covers build-time checks, runtime checks, and gRPC contract validation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${BUILD_DIR:-${SCRIPT_DIR}/build}"
PROTO_FILE="${PROTO_FILE:-${SCRIPT_DIR}/proto/embedding.proto}"
PROTO_DIR="$(dirname "$PROTO_FILE")"
GRPCURL_BIN="${GRPCURL_BIN:-grpcurl}"
SERVICE_HOST="${SERVICE_HOST:-127.0.0.1}"
SERVICE_PORT="${SERVICE_PORT:-50051}"
SERVICE_ADDR="${SERVICE_HOST}:${SERVICE_PORT}"
SERVER_BIN="${SERVER_BIN:-${BUILD_DIR}/embedding_server}"
SERVER_LOG=""
SERVER_PID=""
STARTED_SERVER=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

fail() {
  echo -e "${RED}✗ FAILED${NC}: $*" >&2
  FAILED_TESTS=$((FAILED_TESTS + 1))
}

pass() {
  echo -e "${GREEN}✓ PASSED${NC}: $*"
  PASSED_TESTS=$((PASSED_TESTS + 1))
}

warn() {
  echo -e "${YELLOW}⚠ WARNING${NC}: $*"
}

test_result() {
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  if [ "$1" -eq 0 ]; then
    pass "$2"
  else
    fail "$2"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo -e "${RED}Missing required command:${NC} $1" >&2
    exit 1
  }
}

grpcurl_call() {
  if [[ "${1:-}" == "-d" ]]; then
    local data="$2"
    shift 2
    "$GRPCURL_BIN" -plaintext -import-path "$PROTO_DIR" -proto "$PROTO_FILE" -d "$data" "$SERVICE_ADDR" "$@"
    return
  fi
  "$GRPCURL_BIN" -plaintext -import-path "$PROTO_DIR" -proto "$PROTO_FILE" "$SERVICE_ADDR" "$@"
}

service_is_ready() {
  grpcurl_call list >/dev/null 2>&1
}

cleanup() {
  if [ "$STARTED_SERVER" -eq 1 ] && [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "$SERVER_LOG" ] && [ -f "$SERVER_LOG" ]; then
    rm -f "$SERVER_LOG"
  fi
}

wait_for_service() {
  local attempts=30
  local i
  for ((i = 1; i <= attempts; i++)); do
    if service_is_ready; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_local_server_if_needed() {
  if service_is_ready; then
    return 0
  fi

  if [ ! -x "$SERVER_BIN" ]; then
    test_result 1 "embedding_server binary exists"
    return 1
  fi

  if [ "$SERVICE_HOST" != "127.0.0.1" ] && [ "$SERVICE_HOST" != "localhost" ]; then
    echo -e "${RED}Cannot start a local fallback server for SERVICE_HOST=${SERVICE_HOST}.${NC}" >&2
    echo -e "${YELLOW}Start the service separately or use SERVICE_HOST=localhost / 127.0.0.1.${NC}" >&2
    return 1
  fi

  SERVER_LOG="$(mktemp -t embedding_server.XXXXXX.log)"
  warn "Service at ${SERVICE_ADDR} is not reachable; starting local embedding_server"
  SERVE_PORT="$SERVICE_PORT" "$SERVER_BIN" >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  STARTED_SERVER=1
  trap cleanup EXIT

  if ! wait_for_service; then
    echo "[Error] embedding_server failed to become ready. Log follows:" >&2
    cat "$SERVER_LOG" >&2
    return 1
  fi

  test_result 0 "Started embedding service successfully"
  return 0
}

check_file_contains() {
  local file="$1"
  local pattern="$2"
  local description="$3"
  if grep -Fq "$pattern" "$file"; then
    test_result 0 "$description"
  else
    test_result 1 "$description"
  fi
}

main() {
  trap cleanup EXIT

  echo "=========================================="
  echo "Embedding Service Implementation Test"
  echo "=========================================="
  echo ""

  require_cmd "$GRPCURL_BIN"
  [ -f "$PROTO_FILE" ] || {
    echo -e "${RED}Proto file not found:${NC} $PROTO_FILE" >&2
    exit 1
  }

  echo "阶段一：ONNX Runtime 环境搭建"
  echo "----------------------------------------"
  if [ -f "/usr/include/onnxruntime_cxx_api.h" ] || [ -n "${ONNXRUNTIME_INCLUDE_DIR:-}" ]; then
    test_result 0 "ONNX Runtime headers found (optional)"
  else
    warn "ONNX Runtime headers not found (optional for mock mode)"
  fi
  echo ""

  echo "阶段二：CMake 配置更新"
  echo "----------------------------------------"
  check_file_contains "$SCRIPT_DIR/CMakeLists.txt" "EMBEDDING_WITH_ONNXRUNTIME" "CMakeLists.txt has EMBEDDING_WITH_ONNXRUNTIME option"

  if [ -f "$SERVER_BIN" ]; then
    test_result 0 "embedding_server binary exists"
  elif service_is_ready; then
    warn "embedding_server binary not found, but target service is already reachable at ${SERVICE_ADDR}"
  else
    test_result 1 "embedding_server binary not found"
  fi
  echo ""

  echo "阶段三：实现模型管理类"
  echo "----------------------------------------"
  if [ -f "$SCRIPT_DIR/include/embedding_backend.h" ]; then
    test_result 0 "IEmbeddingBackend interface exists"
  else
    test_result 1 "IEmbeddingBackend interface not found"
  fi

  if [ -f "$SCRIPT_DIR/include/mock_embedding_backend.h" ] && [ -f "$SCRIPT_DIR/src/mock_embedding_backend.cpp" ]; then
    test_result 0 "MockEmbeddingBackend implementation exists"
  else
    test_result 1 "MockEmbeddingBackend implementation not found"
  fi

  if [ -f "$SCRIPT_DIR/include/onnx_embedding_backend.h" ] && [ -f "$SCRIPT_DIR/src/onnx_embedding_backend.cpp" ]; then
    test_result 0 "OnnxEmbeddingBackend implementation exists"
  else
    test_result 1 "OnnxEmbeddingBackend implementation not found"
  fi
  echo ""

  echo "阶段四：实现 tokenizer 与批处理接口"
  echo "----------------------------------------"
  if [ -f "$SCRIPT_DIR/include/tokenizer.h" ] && [ -f "$SCRIPT_DIR/src/tokenizer.cpp" ]; then
    test_result 0 "Tokenizer implementation exists"
  else
    test_result 1 "Tokenizer implementation not found"
  fi

  if grep -Fq "Encode" "$SCRIPT_DIR/include/tokenizer.h"; then
    test_result 0 "Tokenizer has Encode method"
  else
    test_result 1 "Tokenizer missing Encode method"
  fi
  echo ""

  echo "阶段五：实现核心推理逻辑"
  echo "----------------------------------------"
  check_file_contains "$SCRIPT_DIR/src/onnx_embedding_backend.cpp" "LOCAL_EMBED_MODEL_PATH" "OnnxEmbeddingBackend reads LOCAL_EMBED_MODEL_PATH"
  check_file_contains "$SCRIPT_DIR/src/onnx_embedding_backend.cpp" "error_msg" "Error handling implemented"
  check_file_contains "$SCRIPT_DIR/src/onnx_embedding_backend.cpp" "GetTensorMutableData" "Embedding extraction from ONNX output implemented"
  echo ""

  echo "阶段六：模型加载与集成测试"
  echo "----------------------------------------"
  if start_local_server_if_needed; then
    echo ""
    echo "运行时测试 (Runtime Tests)"
    echo "----------------------------------------"

    INFO_OUTPUT="$(grpcurl_call embedding.EmbeddingService/Info 2>&1)"
    echo "$INFO_OUTPUT"
    if echo "$INFO_OUTPUT" | grep -q '"provider"'; then
      test_result 0 "Info endpoint returns provider"
    else
      test_result 1 "Info endpoint doesn't return provider"
    fi

    if echo "$INFO_OUTPUT" | grep -q '"model"'; then
      test_result 0 "Info endpoint returns model"
    else
      test_result 1 "Info endpoint doesn't return model"
    fi

    if echo "$INFO_OUTPUT" | grep -q '"dimensions"'; then
      test_result 0 "Info endpoint returns dimensions"
    else
      test_result 1 "Info endpoint doesn't return dimensions"
    fi

    EMBED_OUTPUT="$(grpcurl_call -d '{"text":"hello world"}' embedding.EmbeddingService/GetEmbedding 2>&1)"
    echo "$EMBED_OUTPUT"
    if echo "$EMBED_OUTPUT" | grep -q '"embedding"'; then
      test_result 0 "GetEmbedding endpoint returns embedding"
    else
      test_result 1 "GetEmbedding endpoint doesn't return embedding"
    fi

    if echo "$EMBED_OUTPUT" | grep -Eq '"embedding"[[:space:]]*:[[:space:]]*\[[[:space:]]*\]'; then
      test_result 1 "GetEmbedding returned an empty embedding"
    else
      test_result 0 "GetEmbedding returns non-empty embedding values"
    fi

    EMBED_OUTPUT2="$(grpcurl_call -d '{"text":"test message"}' embedding.EmbeddingService/GetEmbedding 2>&1)"
    if echo "$EMBED_OUTPUT2" | grep -q '"embedding"'; then
      test_result 0 "GetEmbedding works with different text"
    else
      test_result 1 "GetEmbedding fails with different text"
    fi

    EMBED_OUTPUT3="$(grpcurl_call -d '{"text":""}' embedding.EmbeddingService/GetEmbedding 2>&1)"
    if echo "$EMBED_OUTPUT3" | grep -q '"embedding"'; then
      test_result 0 "GetEmbedding handles empty text"
    else
      warn "GetEmbedding with empty text may be rejected by the backend"
    fi

    BATCH_OUTPUT="$(grpcurl_call -d '{"texts":["hello world","test message",""]}' embedding.EmbeddingService/GetEmbeddings 2>&1)"
    echo "$BATCH_OUTPUT"
    if echo "$BATCH_OUTPUT" | grep -q '"items"'; then
      test_result 0 "GetEmbeddings endpoint returns items"
    else
      test_result 1 "GetEmbeddings endpoint doesn't return items"
    fi

    EMBEDDING_FIELD_COUNT="$(echo "$BATCH_OUTPUT" | grep -c '"embedding"' || true)"
    if [ "$EMBEDDING_FIELD_COUNT" -ge 2 ]; then
      test_result 0 "GetEmbeddings returns multiple embedding results"
    else
      test_result 1 "GetEmbeddings returns insufficient embedding results"
    fi

    echo ""
  else
    test_result 1 "Embedding service is running"
  fi

  echo "文档检查 (Documentation Check)"
  echo "----------------------------------------"
  if [ -f "$SCRIPT_DIR/ONNX_SETUP.md" ]; then
    test_result 0 "ONNX_SETUP.md documentation exists"
  else
    test_result 1 "ONNX_SETUP.md documentation not found"
  fi

  if [ -x "$SCRIPT_DIR/check_embedding_service.sh" ] || [ -f "$SCRIPT_DIR/check_embedding_service.sh" ]; then
    test_result 0 "check_embedding_service.sh exists"
  else
    test_result 1 "check_embedding_service.sh not found"
  fi

  echo ""
  echo "=========================================="
  echo "测试总结 (Test Summary)"
  echo "=========================================="
  echo -e "Total Tests: ${TOTAL_TESTS}"
  echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}"
  if [ "$FAILED_TESTS" -gt 0 ]; then
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
  else
    echo -e "Failed: ${FAILED_TESTS}"
  fi
  echo ""

  if [ "$FAILED_TESTS" -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Implementation is complete.${NC}"
    exit 0
  else
    echo -e "${YELLOW}⚠ Some tests failed. Review the output above.${NC}"
    exit 1
  fi
}

main "$@"
