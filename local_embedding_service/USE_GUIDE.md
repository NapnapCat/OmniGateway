# 本模块使用方法以及启动流程

## 0. 先决条件
- 操作系统：Ubuntu/Debian（推荐）
- 安装 gRPC/Protobuf 相关包：
  - `sudo apt update`
  - `sudo apt install -y build-essential cmake git curl wget unzip`
  - `sudo apt install -y protobuf-compiler-grpc libprotobuf-dev libgrpc++-dev libgrpc-dev`

## 0.1 可选：vcpkg（若系统安装失败）
```bash
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.sh
./vcpkg install grpc protobuf openssl zlib
```
构建时可补充：
```bash
-DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake
```

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
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service/build
./embedding_server
```
- 默认 `SERVE_PORT=50051`
- 如果不设置 `LOCAL_EMBED_DIMENSIONS` 默认 1536

## 4. 一键自测
```bash
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
bash check_embedding_service.sh
```

## 5. 手动验证（grpcurl）
- Info：
  ```bash
grpcurl -plaintext -import-path proto -proto proto/embedding.proto localhost:50051 embedding.EmbeddingService/Info
  ```
- GetEmbedding：
  ```bash
grpcurl -plaintext -import-path proto -proto proto/embedding.proto -d '{"text":"hello"}' localhost:50051 embedding.EmbeddingService/GetEmbedding
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
pkill -f embedding_server || true
```

---

### 说明
本服务基于 `proto/embedding.proto`，提供兼容 Go gateway 的本地 mock embedding 实现，主要用于本地开发与测试。
