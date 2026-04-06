#include "embedding_service_impl.h"

#include <cstdlib>
#include <iostream>

#include "mock_embedding_backend.h"

#ifdef ENABLE_ONNX_BACKEND
#include "onnx_embedding_backend.h"
#endif

namespace embedding_service {

static std::string ReadStringEnv(const char* name, const char* default_value) {
  const char* value = std::getenv(name);
  if (value == nullptr || value[0] == '\0') {
    return default_value;
  }
  return value;
}

EmbeddingServiceImpl::EmbeddingServiceImpl() {
  std::string backend_type = ReadStringEnv("EMBEDDING_BACKEND", "mock");

  if (backend_type == "onnx") {
#ifdef ENABLE_ONNX_BACKEND
    backend_ = std::make_unique<OnnxEmbeddingBackend>();
    std::cout << "[Info] Using ONNX embedding backend" << std::endl;
#else
    std::cerr << "[Warning] ONNX backend requested but not compiled. Falling "
                 "back to mock backend."
              << std::endl;
    backend_ = std::make_unique<MockEmbeddingBackend>();
#endif
  } else {
    backend_ = std::make_unique<MockEmbeddingBackend>();
    std::cout << "[Info] Using mock embedding backend" << std::endl;
  }

  if (!backend_->Init(&init_error_)) {
    std::cerr << "[Error] Failed to initialize embedding backend: "
              << init_error_ << std::endl;
  } else {
    std::cout << "[Info] Embedding backend initialized: provider="
              << backend_->GetProvider() << ", model=" << backend_->GetModel()
              << ", dimensions=" << backend_->GetDimensions() << std::endl;
  }
}

grpc::Status EmbeddingServiceImpl::GetEmbedding(
    grpc::ServerContext*, const embedding::EmbeddingRequest* request,
    embedding::EmbeddingResponse* response) {
  if (!init_error_.empty()) {
    response->set_error("Backend initialization failed: " + init_error_);
    return grpc::Status::OK;
  }

  std::vector<float> embedding;
  std::string error_msg;
  if (!backend_->Encode(request->text(), &embedding, &error_msg)) {
    response->set_error(error_msg);
    return grpc::Status::OK;
  }

  for (float value : embedding) {
    response->add_embedding(value);
  }
  response->set_error("");
  return grpc::Status::OK;
}

grpc::Status EmbeddingServiceImpl::Info(
    grpc::ServerContext*, const google::protobuf::Empty*,
    embedding::InfoResponse* response) {
  response->set_provider(backend_->GetProvider());
  response->set_model(backend_->GetModel());
  response->set_dimensions(backend_->GetDimensions());
  return grpc::Status::OK;
}

}  // namespace embedding_service
