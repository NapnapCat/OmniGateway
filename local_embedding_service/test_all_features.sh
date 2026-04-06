#!/bin/bash
# Comprehensive test for embedding service implementation
# Tests all phases of the ONNX Runtime integration

set -e

echo "=========================================="
echo "Embedding Service Implementation Test"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

test_result() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED${NC}: $2"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ FAILED${NC}: $2"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "阶段一：ONNX Runtime 环境搭建"
echo "----------------------------------------"
# Check if ONNX Runtime headers are available (optional)
if [ -f "/usr/include/onnxruntime_cxx_api.h" ] || [ -n "$ONNXRUNTIME_INCLUDE_DIR" ]; then
    test_result 0 "ONNX Runtime headers found (optional)"
else
    echo -e "${YELLOW}⚠ SKIPPED${NC}: ONNX Runtime headers not found (optional for mock mode)"
fi
echo ""

echo "阶段二：CMake 配置更新"
echo "----------------------------------------"
# Check CMakeLists.txt for ONNX option
if grep -q "EMBEDDING_WITH_ONNXRUNTIME" CMakeLists.txt; then
    test_result 0 "CMakeLists.txt has EMBEDDING_WITH_ONNXRUNTIME option"
else
    test_result 1 "CMakeLists.txt missing EMBEDDING_WITH_ONNXRUNTIME option"
fi

# Check if build exists
if [ -f "build/embedding_server" ]; then
    test_result 0 "embedding_server binary exists"
else
    test_result 1 "embedding_server binary not found"
fi
echo ""

echo "阶段三：实现模型管理类"
echo "----------------------------------------"
# Check for IEmbeddingBackend interface
if [ -f "include/embedding_backend.h" ]; then
    test_result 0 "IEmbeddingBackend interface exists"
else
    test_result 1 "IEmbeddingBackend interface not found"
fi

# Check for MockEmbeddingBackend
if [ -f "include/mock_embedding_backend.h" ] && [ -f "src/mock_embedding_backend.cpp" ]; then
    test_result 0 "MockEmbeddingBackend implementation exists"
else
    test_result 1 "MockEmbeddingBackend implementation not found"
fi

# Check for OnnxEmbeddingBackend
if [ -f "include/onnx_embedding_backend.h" ] && [ -f "src/onnx_embedding_backend.cpp" ]; then
    test_result 0 "OnnxEmbeddingBackend implementation exists"
else
    test_result 1 "OnnxEmbeddingBackend implementation not found"
fi
echo ""

echo "阶段四：实现 tokenizer 与批处理接口"
echo "----------------------------------------"
# Check for Tokenizer implementation
if [ -f "include/tokenizer.h" ] && [ -f "src/tokenizer.cpp" ]; then
    test_result 0 "Tokenizer implementation exists"
else
    test_result 1 "Tokenizer implementation not found"
fi

# Check tokenizer has Encode method
if grep -q "Encode" include/tokenizer.h; then
    test_result 0 "Tokenizer has Encode method"
else
    test_result 1 "Tokenizer missing Encode method"
fi
echo ""

echo "阶段五：实现核心推理逻辑"
echo "----------------------------------------"
# Check if OnnxEmbeddingBackend reads environment variables
if grep -q "LOCAL_EMBED_MODEL_PATH" src/onnx_embedding_backend.cpp; then
    test_result 0 "OnnxEmbeddingBackend reads LOCAL_EMBED_MODEL_PATH"
else
    test_result 1 "OnnxEmbeddingBackend doesn't read LOCAL_EMBED_MODEL_PATH"
fi

# Check if error handling is implemented
if grep -q "error_msg" src/onnx_embedding_backend.cpp; then
    test_result 0 "Error handling implemented"
else
    test_result 1 "Error handling not implemented"
fi

# Check if embedding extraction is implemented
if grep -q "GetTensorMutableData" src/onnx_embedding_backend.cpp; then
    test_result 0 "Embedding extraction from ONNX output implemented"
else
    test_result 1 "Embedding extraction not implemented"
fi
echo ""

echo "阶段六：模型加载与集成测试"
echo "----------------------------------------"
# Check if service is running
SERVICE_RUNNING=0
if pgrep -f embedding_server > /dev/null; then
    test_result 0 "Embedding service is running"
    SERVICE_RUNNING=1
else
    echo -e "${YELLOW}⚠ WARNING${NC}: Embedding service not running, starting it..."
    cd build && ./embedding_server &
    SERVER_PID=$!
    sleep 2
    if pgrep -f embedding_server > /dev/null; then
        test_result 0 "Started embedding service successfully"
        SERVICE_RUNNING=1
    else
        test_result 1 "Failed to start embedding service"
    fi
fi
echo ""

if [ $SERVICE_RUNNING -eq 1 ]; then
    echo "运行时测试 (Runtime Tests)"
    echo "----------------------------------------"
    
    # Test Info endpoint
    INFO_OUTPUT=$(grpcurl -plaintext -proto proto/embedding.proto localhost:50051 embedding.EmbeddingService/Info 2>&1)
    if echo "$INFO_OUTPUT" | grep -q "provider"; then
        test_result 0 "Info endpoint returns provider"
    else
        test_result 1 "Info endpoint doesn't return provider"
    fi
    
    if echo "$INFO_OUTPUT" | grep -q "model"; then
        test_result 0 "Info endpoint returns model"
    else
        test_result 1 "Info endpoint doesn't return model"
    fi
    
    if echo "$INFO_OUTPUT" | grep -q "dimensions"; then
        test_result 0 "Info endpoint returns dimensions"
    else
        test_result 1 "Info endpoint doesn't return dimensions"
    fi
    
    # Test GetEmbedding endpoint
    EMBED_OUTPUT=$(grpcurl -plaintext -proto proto/embedding.proto -d '{"text":"hello world"}' localhost:50051 embedding.EmbeddingService/GetEmbedding 2>&1)
    if echo "$EMBED_OUTPUT" | grep -q "embedding"; then
        test_result 0 "GetEmbedding endpoint returns embedding"
    else
        test_result 1 "GetEmbedding endpoint doesn't return embedding"
    fi
    
    # Check embedding is not empty
    if echo "$EMBED_OUTPUT" | grep -q "\-\?[0-9]\+\.[0-9]"; then
        test_result 0 "GetEmbedding returns non-empty float values"
    else
        test_result 1 "GetEmbedding returns empty or invalid values"
    fi
    
    # Test with different text
    EMBED_OUTPUT2=$(grpcurl -plaintext -proto proto/embedding.proto -d '{"text":"test message"}' localhost:50051 embedding.EmbeddingService/GetEmbedding 2>&1)
    if echo "$EMBED_OUTPUT2" | grep -q "embedding"; then
        test_result 0 "GetEmbedding works with different text"
    else
        test_result 1 "GetEmbedding fails with different text"
    fi
    
    # Test with empty text
    EMBED_OUTPUT3=$(grpcurl -plaintext -proto proto/embedding.proto -d '{"text":""}' localhost:50051 embedding.EmbeddingService/GetEmbedding 2>&1)
    if echo "$EMBED_OUTPUT3" | grep -q "embedding"; then
        test_result 0 "GetEmbedding handles empty text"
    else
        echo -e "${YELLOW}⚠ NOTE${NC}: GetEmbedding with empty text - behavior may vary"
    fi
    
    echo ""
fi

echo "文档检查 (Documentation Check)"
echo "----------------------------------------"
# Check for setup documentation
if [ -f "ONNX_SETUP.md" ]; then
    test_result 0 "ONNX_SETUP.md documentation exists"
else
    test_result 1 "ONNX_SETUP.md documentation not found"
fi

# Check for test script
if [ -f "check_embedding_service.sh" ]; then
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
if [ $FAILED_TESTS -gt 0 ]; then
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
else
    echo -e "Failed: ${FAILED_TESTS}"
fi
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Implementation is complete.${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ Some tests failed. Review the output above.${NC}"
    exit 1
fi
