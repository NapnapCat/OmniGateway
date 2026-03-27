#!/usr/bin/env bash
set -euo pipefail

HOST=${1:-localhost}
PORT=${2:-50051}
TIMEOUT=${3:-5}  # 去掉 's'，使用数字

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTO_DIR="${SCRIPT_DIR}/proto"
PROTO_FILE="${PROTO_DIR}/embedding.proto"

SERVICE=embedding.EmbeddingService

echo "[info] Checking ${SERVICE} at ${HOST}:${PORT}"

# Ensure grpcurl exists
if ! command -v grpcurl >/dev/null 2>&1; then
  cat <<EOF
[error] grpcurl not found. Please install grpcurl:
  - Using Go: go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
  - Download binary: https://github.com/fullstorydev/grpcurl/releases
EOF
  exit 1
fi

# Check if proto file exists
if [ ! -f "${PROTO_FILE}" ]; then
  echo "[error] Proto file not found: ${PROTO_FILE}"
  exit 1
fi

# 1. List services (using proto file)
echo "[info] Listing services..."
grpcurl -plaintext -proto "${PROTO_FILE}" -max-time ${TIMEOUT} ${HOST}:${PORT} list || {
  echo "[error] Failed to list services"
  exit 1
}

# 2. Info RPC
INFO_OUTPUT=$(grpcurl -plaintext -proto "${PROTO_FILE}" -max-time ${TIMEOUT} ${HOST}:${PORT} ${SERVICE}/Info 2>&1) || {
  echo "[error] Info RPC failed:"
  echo "${INFO_OUTPUT}"
  exit 1
}

echo "[info] Info response: ${INFO_OUTPUT}"

# 3. GetEmbedding RPC
TEXT='hello world'
EMB_OUTPUT=$(grpcurl -plaintext -proto "${PROTO_FILE}" -max-time ${TIMEOUT} -d "{\"text\": \"${TEXT}\"}" ${HOST}:${PORT} ${SERVICE}/GetEmbedding 2>&1) || {
  echo "[error] GetEmbedding RPC failed:"
  echo "${EMB_OUTPUT}"
  exit 2
}

echo "[info] GetEmbedding response: ${EMB_OUTPUT}"

# 4. Basic validation
if echo "${EMB_OUTPUT}" | grep -qi 'error'; then
  echo "[warn] response contains 'error' field, check payload"
fi

if ! echo "${EMB_OUTPUT}" | grep -q 'embedding'; then
  echo "[error] no embedding vector returned"
  exit 3
fi

echo "[success] embedding service is available and responding"
exit 0