#include "embedding_service_impl.h"

#include <cstdlib>
#include <limits>

namespace embedding_service {

int EmbeddingServiceImpl::ReadIntEnv(const char* name, int default_value) {
  const char* value = std::getenv(name);
  if (value == nullptr || value[0] == '\0') {
    return default_value;
  }

  try {
    return std::stoi(value);
  } catch (...) {
    return default_value;
  }
}

std::string EmbeddingServiceImpl::ReadStringEnv(const char* name,
                                                const char* default_value) {
  const char* value = std::getenv(name);
  if (value == nullptr || value[0] == '\0') {
    return default_value;
  }
  return value;
}

uint32_t EmbeddingServiceImpl::HashText(const std::string& text, int counter) {
  uint32_t hash = 2166136261u;
  for (unsigned char ch : text) {
    hash ^= static_cast<uint32_t>(ch);
    hash *= 16777619u;
  }
  hash ^= static_cast<uint32_t>(counter);
  hash *= 16777619u;
  return hash;
}

std::vector<float> EmbeddingServiceImpl::BuildVector(const std::string& text,
                                                     int dimensions) {
  std::vector<float> values;
  values.reserve(dimensions);

  int counter = 0;
  while (static_cast<int>(values.size()) < dimensions) {
    uint32_t state = HashText(text, counter++);
    for (int i = 0; i < 8 && static_cast<int>(values.size()) < dimensions;
         ++i) {
      state = state * 1664525u + 1013904223u;
      const float normalized =
          static_cast<float>(state) /
          static_cast<float>(std::numeric_limits<uint32_t>::max()) * 2.0f -
          1.0f;
      values.push_back(normalized);
    }
  }

  return values;
}

EmbeddingServiceImpl::EmbeddingServiceImpl()
    : provider_(ReadStringEnv("LOCAL_EMBED_PROVIDER", "local-mock")),
      model_(ReadStringEnv("LOCAL_EMBED_MODEL", "local-mock-embedding")),
      dimensions_(ReadIntEnv("LOCAL_EMBED_DIMENSIONS",
                             ReadIntEnv("EMBED_DIMENSIONS", 1536))) {}

grpc::Status EmbeddingServiceImpl::GetEmbedding(
    grpc::ServerContext*, const embedding::EmbeddingRequest* request,
    embedding::EmbeddingResponse* response) {
  const auto values = BuildVector(request->text(), dimensions_);
  for (float value : values) {
    response->add_embedding(value);
  }
  response->set_error("");
  return grpc::Status::OK;
}

grpc::Status EmbeddingServiceImpl::Info(
    grpc::ServerContext*, const google::protobuf::Empty*,
    embedding::InfoResponse* response) {
  response->set_provider(provider_);
  response->set_model(model_);
  response->set_dimensions(dimensions_);
  return grpc::Status::OK;
}

}  // namespace embedding_service
