# ONNX Runtime Setup Guide

## Prerequisites
To enable the ONNX Runtime backend for real embedding models, you need to install ONNX Runtime.

## Installation Options

### Option 1: vcpkg (Recommended)
```bash
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.sh
./vcpkg install onnxruntime-cpu
```

Then build with:
```bash
cmake -B build -S . \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake \
  -DUSE_PREGENERATED_PROTO=OFF \
  -DEMBEDDING_WITH_ONNXRUNTIME=ON \
  -DONNXRUNTIME_LIBS="onnxruntime" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

### Option 2: System Installation
Download pre-built ONNX Runtime from:
https://github.com/microsoft/onnxruntime/releases

Extract and build with:
```bash
export ONNX_ROOT=/path/to/onnxruntime

cmake -B build -S . \
  -DUSE_PREGENERATED_PROTO=OFF \
  -DEMBEDDING_WITH_ONNXRUNTIME=ON \
  -DONNXRUNTIME_INCLUDE_DIR=$ONNX_ROOT/include \
  -DONNXRUNTIME_LIB_DIR=$ONNX_ROOT/lib \
  -DONNXRUNTIME_LIBS="onnxruntime" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

## Running with ONNX Backend

### 1. Prepare an ONNX Model
Download a BGE embedding model in ONNX format (e.g., bge-base-en-v1.5).

### 2. Set Environment Variables
```bash
export EMBEDDING_BACKEND=onnx
export LOCAL_EMBED_MODEL_PATH=/path/to/model.onnx
export LOCAL_EMBED_DIMENSIONS=768  # Model-dependent
export LOCAL_EMBED_MAX_LENGTH=512
```

### 3. Start the Server
```bash
cd build
./embedding_server
```

You should see:
```
[Info] Using ONNX embedding backend
[Info] Loading ONNX model from: /path/to/model.onnx
[Info] ONNX model loaded successfully. Inputs: 2, Outputs: 1
[Info] Embedding backend initialized: provider=onnx-runtime, model=bge-base-en-v1.5, dimensions=768
[Info] Local embedding mock listening on port 50051
```

## Testing
```bash
# Info endpoint
grpcurl -plaintext -import-path proto -proto proto/embedding.proto \
  localhost:50051 embedding.EmbeddingService/Info

# Get embedding
grpcurl -plaintext -import-path proto -proto proto/embedding.proto \
  -d '{"text":"hello world"}' localhost:50051 embedding.EmbeddingService/GetEmbedding
```

## Fallback Behavior
- If `EMBEDDING_BACKEND=onnx` but ONNX Runtime is not compiled in, falls back to mock backend
- If model path is not set or model fails to load, error is returned in response
- Mock backend remains the default when `EMBEDDING_BACKEND` is not set
