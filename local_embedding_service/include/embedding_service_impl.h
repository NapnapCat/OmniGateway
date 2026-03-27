#ifndef LOCAL_EMBEDDING_SERVICE_EMBEDDING_SERVICE_IMPL_H_
#define LOCAL_EMBEDDING_SERVICE_EMBEDDING_SERVICE_IMPL_H_

#include <string>
#include <vector>

#include <google/protobuf/empty.pb.h>
#include <grpcpp/grpcpp.h>

#include "embedding.grpc.pb.h"

namespace embedding_service {

class EmbeddingServiceImpl final : public embedding::EmbeddingService::Service {
 public:
  EmbeddingServiceImpl();

  grpc::Status GetEmbedding(grpc::ServerContext* context,
                            const embedding::EmbeddingRequest* request,
                            embedding::EmbeddingResponse* response) override;

  grpc::Status Info(grpc::ServerContext* context,
                    const google::protobuf::Empty* request,
                    embedding::InfoResponse* response) override;

 private:
  std::string provider_;
  std::string model_;
  int dimensions_;

  static int ReadIntEnv(const char* name, int default_value);
  static std::string ReadStringEnv(const char* name, const char* default_value);
  static uint32_t HashText(const std::string& text, int counter);
  static std::vector<float> BuildVector(const std::string& text, int dimensions);
};

}  // namespace embedding_service

#endif  // LOCAL_EMBEDDING_SERVICE_EMBEDDING_SERVICE_IMPL_H_
