# 本模块使用方法以及启动流程

> **更新日期**: 2026-04-05  
> **版本**: v4.5.0 - 新增 ONNX Runtime 集成支持

## 目录
1. [先决条件](#0-先决条件)
2. [快速开始 (Mock 模式)](#快速开始-mock-模式)
3. [ONNX Runtime 模式](#使用-onnx-runtime-后端)
4. [测试验证](#4-测试验证)
5. [常见问题](#6-常见问题与排查)

---

## 0. 先决条件
- 操作系统：Ubuntu/Debian（推荐）
- 安装 gRPC/Protobuf 相关包：
  - `sudo apt update`
  - `sudo apt install -y build-essential cmake git curl wget unzip`
  - `sudo apt install -y protobuf-compiler-grpc libprotobuf-dev libgrpc++-dev libgrpc-dev`

## 0.1 可选：vcpkg（若系统安装失败）
```bash
# 一次性安装 vcpkg
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.sh

# 安装依赖（含 ONNX Runtime）
./vcpkg install grpc protobuf openssl zlib onnxruntime-cpu
```

使用 vcpkg 构建（只启用 mock 后端）：
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
cmake -B build -S . \
  -DUSE_PREGENERATED_PROTO=OFF \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

使用 vcpkg 构建并启用 ONNX Runtime 后端：
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
cmake -B build_onnx -S . \
  -DUSE_PREGENERATED_PROTO=OFF \
  -DEMBEDDING_WITH_ONNXRUNTIME=ON \
  -DONNXRUNTIME_LIBS=onnxruntime \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build_onnx -j
```

运行 ONNX Runtime 后端（示例）：
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service/build_onnx
export EMBEDDING_BACKEND=onnx
export LOCAL_EMBED_MODEL_PATH=/path/to/bge-model.onnx
export LOCAL_EMBED_DIMENSIONS=768   # 与模型输出维度保持一致
export LOCAL_EMBED_MAX_LENGTH=512   # 与导出模型保持一致
./embedding_server
```

> 说明：当前仓库的 CMake 已预置 `EMBEDDING_WITH_ONNXRUNTIME` 与相关变量，上述命令即为实际可用的配置流程。

## 1. 清理历史构建
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
rm -rf build
```

## 2. 重新构建
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
mkdir -p build && cd build
cmake -DUSE_PREGENERATED_PROTO=OFF -DCMAKE_BUILD_TYPE=Release ..
cmake --build . -j
```
- 推荐 `USE_PREGENERATED_PROTO=OFF`：避免本地系统 protobuf 版本不一致。
- 如果你确实要用 pre-generated code：
  ```bash
  cmake -DUSE_PREGENERATED_PROTO=ON -DCMAKE_BUILD_TYPE=Release ..
  cmake --build . -j
  ```

## 3. 启动服务

### 3.1 Mock 模式（默认，推荐开发测试使用）
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service/build
./embedding_server
```

**特点**：
- ✅ 无需任何模型文件
- ✅ 启动快速（< 1秒）
- ✅ 返回确定性的 mock 向量（基于文本哈希）
- ✅ 默认 1536 维输出

**输出示例**：
```
[Info] Using mock embedding backend
[Info] Embedding backend initialized: provider=local-mock, model=local-mock-embedding, dimensions=1536
[Info] Local embedding mock listening on port 50051
```

### 3.2 ONNX Runtime 模式（真实模型推理）

详见下方 [使用 ONNX Runtime 后端](#使用-onnx-runtime-后端) 章节。

### 3.3 环境变量配置

**通用配置**：
```bash
export SERVE_PORT=50051              # 服务端口（默认 50051）
export EMBEDDING_BACKEND=mock        # 后端类型: mock 或 onnx（默认 mock）
```

**Mock 后端配置**：
```bash
export LOCAL_EMBED_DIMENSIONS=1536   # 向量维度（默认 1536）
```

**ONNX 后端配置**：
```bash
export EMBEDDING_BACKEND=onnx
export LOCAL_EMBED_MODEL_PATH=/path/to/model.onnx   # 必需：模型文件路径
export LOCAL_EMBED_PROVIDER=onnx-runtime             # 提供者名称（默认）
export LOCAL_EMBED_MODEL=bge-base-en-v1.5            # 模型名称（默认）
export LOCAL_EMBED_DIMENSIONS=768                    # 向量维度（与模型匹配）
export LOCAL_EMBED_MAX_LENGTH=512                    # 最大序列长度（默认 512）
```

## 4. 测试验证

### 4.1 全面测试（推荐）
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
bash test_all_features.sh
```

这将运行 20+ 项测试，包括：
- 编译配置检查
- 代码结构验证
- 运行时功能测试
- gRPC 接口测试

### 4.2 快速验证
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
bash check_embedding_service.sh
```

## 5. 手动验证（grpcurl）

### 5.1 检查服务信息（Info 接口）
```bash
grpcurl -plaintext -import-path proto -proto proto/embedding.proto \
  localhost:50051 embedding.EmbeddingService/Info
```

**预期输出（Mock 模式）**：
```json
{
  "provider": "local-mock",
  "model": "local-mock-embedding",
  "dimensions": 1536
}
```

**预期输出（ONNX 模式）**：
```json
{
  "provider": "onnx-runtime",
  "model": "bge-base-en-v1.5",
  "dimensions": 768
}
```

### 5.2 获取文本向量（GetEmbedding 接口）
```bash
grpcurl -plaintext -import-path proto -proto proto/embedding.proto \
  -d '{"text":"hello world"}' localhost:50051 embedding.EmbeddingService/GetEmbedding
```

**预期输出**：
```json
{
  "embedding": [
    -0.74863195,
    -0.13141733,
    -0.9914516,
    ...
  ],
  "error": ""
}
```

### 5.3 测试不同文本
```bash
# 英文
grpcurl -plaintext -proto proto/embedding.proto \
  -d '{"text":"artificial intelligence"}' localhost:50051 embedding.EmbeddingService/GetEmbedding

# 中文
grpcurl -plaintext -proto proto/embedding.proto \
  -d '{"text":"人工智能"}' localhost:50051 embedding.EmbeddingService/GetEmbedding

# 长文本
grpcurl -plaintext -proto proto/embedding.proto \
  -d '{"text":"This is a longer text to test the embedding service with more content."}' \
  localhost:50051 embedding.EmbeddingService/GetEmbedding
```

## 6. 常见问题与排查
- `grpc_cpp_plugin not found`：
  - `which grpc_cpp_plugin || true`
  - `sudo apt install -y protobuf-compiler-grpc`
  - 或使用 `vcpkg` 安装 grpc protobuf
- `GetArenaForAllocation` / `PROTOBUF_CONSTEXPR` 等错误：
  - protobuf 版本冲突，切换 `-DUSE_PREGENERATED_PROTO=OFF`
  - `protoc --version` 与 `pkg-config --modversion protobuf` 应一致
- `src/main.cpp 非法预处理指令`：该文件应为 C++ 源码，检查是否误写成脚本

## 7. 停止服务
```bash
# 方法1：优雅停止
pkill -f embedding_server

# 方法2：强制停止
pkill -9 -f embedding_server

# 方法3：使用进程ID
ps aux | grep embedding_server
kill <PID>
```

---

## 使用 ONNX Runtime 后端

> **完整指南**: 详见 `ONNX_SETUP.md`

### 步骤 1: 编译 ONNX 支持版本

#### 方法A: 使用 vcpkg（推荐）
```bash
# 安装 vcpkg（如果还没有）
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.sh

# 安装 ONNX Runtime
./vcpkg install onnxruntime-cpu

# 编译 embedding service
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
cmake -B build_onnx -S . \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake \
  -DUSE_PREGENERATED_PROTO=OFF \
  -DEMBEDDING_WITH_ONNXRUNTIME=ON \
  -DONNXRUNTIME_LIBS="onnxruntime" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build_onnx -j
```

#### 方法B: 使用系统安装的 ONNX Runtime
```bash
# 下载 ONNX Runtime
wget https://github.com/microsoft/onnxruntime/releases/download/v1.17.0/onnxruntime-linux-x64-1.17.0.tgz
tar -xzf onnxruntime-linux-x64-1.17.0.tgz
export ONNX_ROOT=$(pwd)/onnxruntime-linux-x64-1.17.0

# 编译
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
cmake -B build_onnx -S . \
  -DUSE_PREGENERATED_PROTO=OFF \
  -DEMBEDDING_WITH_ONNXRUNTIME=ON \
  -DONNXRUNTIME_INCLUDE_DIR=$ONNX_ROOT/include \
  -DONNXRUNTIME_LIB_DIR=$ONNX_ROOT/lib \
  -DONNXRUNTIME_LIBS="onnxruntime" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build_onnx -j
```

### 步骤 2: 准备 ONNX 模型

#### 选项A: 下载预转换的模型
```bash
# 示例：BGE Base 模型（需要自行准备或转换）
# 模型应该是 ONNX 格式 (.onnx 文件)
export MODEL_PATH=/path/to/bge-base-en-v1.5.onnx
```

#### 选项B: 从 HuggingFace 模型转换
```bash
# 安装依赖
pip install transformers onnx optimum

# 转换模型
python -c "
from optimum.onnxruntime import ORTModelForFeatureExtraction
from transformers import AutoTokenizer

model_id = 'BAAI/bge-base-en-v1.5'
model = ORTModelForFeatureExtraction.from_pretrained(model_id, export=True)
model.save_pretrained('./bge-base-en-v1.5-onnx')
"

export MODEL_PATH=$(pwd)/bge-base-en-v1.5-onnx/model.onnx
```

### 步骤 3: 配置和运行

```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service/build_onnx

# 设置环境变量
export EMBEDDING_BACKEND=onnx
export LOCAL_EMBED_MODEL_PATH=/path/to/your/model.onnx
export LOCAL_EMBED_DIMENSIONS=768        # 根据模型调整
export LOCAL_EMBED_MAX_LENGTH=512
export LOCAL_EMBED_MODEL=bge-base-en-v1.5
export SERVE_PORT=50051

# 启动服务
./embedding_server
```

**预期输出**：
```
[Info] Using ONNX embedding backend
[Info] Loading ONNX model from: /path/to/your/model.onnx
[Info] ONNX model loaded successfully. Inputs: 2, Outputs: 1
[Info] Embedding backend initialized: provider=onnx-runtime, model=bge-base-en-v1.5, dimensions=768
[Info] Local embedding mock listening on port 50051
```

### 步骤 4: 验证 ONNX 模式

```bash
# 1. 检查服务信息
grpcurl -plaintext -proto proto/embedding.proto \
  localhost:50051 embedding.EmbeddingService/Info

# 应该返回:
# {
#   "provider": "onnx-runtime",
#   "model": "bge-base-en-v1.5",
#   "dimensions": 768
# }

# 2. 获取真实 embedding
grpcurl -plaintext -proto proto/embedding.proto \
  -d '{"text":"hello world"}' localhost:50051 embedding.EmbeddingService/GetEmbedding

# 返回真实的 768 维向量
```

### ONNX 模式故障排查

**问题 1: "ONNX backend not compiled"**
- 原因：未使用 `-DEMBEDDING_WITH_ONNXRUNTIME=ON` 编译
- 解决：重新编译，参考上方步骤 1

**问题 2: "LOCAL_EMBED_MODEL_PATH environment variable not set"**
- 原因：未设置模型路径
- 解决：`export LOCAL_EMBED_MODEL_PATH=/path/to/model.onnx`

**问题 3: "ONNX Runtime error: ..."**
- 检查模型文件是否存在：`ls -lh $LOCAL_EMBED_MODEL_PATH`
- 检查模型格式是否正确（应该是 .onnx 文件）
- 检查 ONNX Runtime 版本兼容性

**问题 4: 向量维度不匹配**
- 设置 `LOCAL_EMBED_DIMENSIONS` 与模型输出维度一致
- 常见模型维度：
  - bge-small: 384
  - bge-base: 768
  - bge-large: 1024

---

## 架构说明

本服务基于 `proto/embedding.proto`，提供兼容 Go gateway 的本地 embedding 实现。

### 支持的后端

#### 1. Mock 后端（默认）
- **用途**: 本地联调、功能验证、快速开发
- **特点**: 
  - 无需模型文件
  - 基于 FNV-1a 哈希生成确定性向量
  - 相同文本始终返回相同向量
  - 极低延迟（< 1ms）
- **限制**: 向量无实际语义相似度

#### 2. ONNX Runtime 后端（可选）
- **用途**: 生产环境、真实语义搜索
- **特点**:
  - 真实的 embedding 模型推理
  - 支持主流模型（BGE, Sentence-BERT 等）
  - 向量具有语义相似度
- **要求**: 
  - 需要 ONNX 格式模型文件
  - 编译时启用 ONNX Runtime 支持

### 组件架构
```
EmbeddingServiceImpl (gRPC Service)
    │
    ├── IEmbeddingBackend (接口)
    │   ├── MockEmbeddingBackend
    │   │   └── Hash-based vector generation
    │   │
    │   └── OnnxEmbeddingBackend
    │       ├── ITokenizer
    │       │   └── SimpleTokenizer (空格分词 + hash)
    │       │
    │       └── ONNX Runtime Session
    │           └── Model inference
```

### 后端选择机制
1. 检查 `EMBEDDING_BACKEND` 环境变量
2. 如果为 "onnx" 且编译时启用了 ONNX：使用 OnnxEmbeddingBackend
3. 否则：使用 MockEmbeddingBackend
4. 失败时自动降级到 Mock

---

## 性能参考

### Mock 后端
- 延迟: < 1ms
- 内存: < 20MB
- CPU: 忽略不计
- 吞吐: > 10,000 req/s

### ONNX 后端（bge-base-en-v1.5, CPU）
- 延迟: 10-50ms（取决于文本长度和硬件）
- 内存: ~500MB（模型加载后）
- CPU: 中等（推理时）
- 吞吐: 20-100 req/s（单线程）

**优化建议**：
- 使用 GPU 版本 ONNX Runtime
- 启用批处理（未来功能）
- 使用模型量化版本
