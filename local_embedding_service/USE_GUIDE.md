# 本模块使用方法以及启动流程

## 1. 依赖安装（Ubuntu）
sudo apt update
sudo apt install -y protobuf-compiler-grpc libprotobuf-dev libgrpc++-dev

# gRPC plugin
which grpc_cpp_plugin || true
which protoc-gen-grpc || true

# 如果没有 grpc_cpp_plugin，可使用 vcpkg（推荐）：
# git clone https://github.com/microsoft/vcpkg.git
# cd vcpkg
# ./bootstrap-vcpkg.sh
# ./vcpkg install grpc protobuf openssl zlib

## 2. CMake 构建
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service
mkdir -p build && cd build

# 默认使用本地生成流程（需 grpc_cpp_plugin 可用）
cmake -DCMAKE_BUILD_TYPE=Release ..

# 或通过预生成 pb 代码免生成插件依赖
cmake -DUSE_PREGENERATED_PROTO=ON -DCMAKE_BUILD_TYPE=Release ..

cmake --build . -j

## 3. 运行服务
cd /home/liyufeng/go_projects/OmniGateway/local_embedding_service/build
./embedding_server

# 可选环境变量
# SERVE_PORT=50051 LOCAL_EMBED_DIMENSIONS=1536 LOCAL_EMBED_PROVIDER=local-mock LOCAL_EMBED_MODEL=local-mock-embedding ./embedding_server

## 4. 调试验证
# Info 请求
grpcurl -plaintext localhost:50051 embedding.EmbeddingService/Info

# GetEmbedding 请求
grpcurl -plaintext -d '{"text":"hello"}' localhost:50051 embedding.EmbeddingService/GetEmbedding
