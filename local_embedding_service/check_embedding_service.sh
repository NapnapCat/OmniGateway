# 测试1：列出所有服务（使用 proto 文件）
grpcurl -plaintext -proto proto/embedding.proto localhost:50051 list

# 测试2：查看服务详情
grpcurl -plaintext -proto proto/embedding.proto localhost:50051 describe embedding.EmbeddingService

# 测试3：调用 Info
grpcurl -plaintext -proto proto/embedding.proto localhost:50051 embedding.EmbeddingService/Info

# 测试4：调用 GetEmbedding
grpcurl -plaintext -proto proto/embedding.proto -d '{"text":"hello world"}' localhost:50051 embedding.EmbeddingService/GetEmbedding