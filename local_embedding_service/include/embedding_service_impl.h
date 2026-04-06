#ifndef LOCAL_EMBEDDING_SERVICE_EMBEDDING_SERVICE_IMPL_H_
#define LOCAL_EMBEDDING_SERVICE_EMBEDDING_SERVICE_IMPL_H_

#include <memory>
#include <string>

#include <google/protobuf/empty.pb.h>
#include <grpcpp/grpcpp.h>

#include "embedding.grpc.pb.h"
#include "embedding_backend.h"

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
  std::unique_ptr<IEmbeddingBackend> backend_;
  std::string init_error_;
};

}  // namespace embedding_service

#endif  // LOCAL_EMBEDDING_SERVICE_EMBEDDING_SERVICE_IMPL_H_
