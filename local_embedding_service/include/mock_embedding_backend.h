#ifndef LOCAL_EMBEDDING_SERVICE_MOCK_EMBEDDING_BACKEND_H_
#define LOCAL_EMBEDDING_SERVICE_MOCK_EMBEDDING_BACKEND_H_

#include "embedding_backend.h"

#include <string>
#include <vector>

namespace embedding_service {

class MockEmbeddingBackend : public IEmbeddingBackend {
 public:
  MockEmbeddingBackend();
  ~MockEmbeddingBackend() override = default;

  bool Init(std::string* error_msg) override;

  bool Encode(const std::string& text, std::vector<float>* embedding,
              std::string* error_msg) override;
  bool EncodeBatch(const std::vector<std::string>& texts,
                   std::vector<std::vector<float>>* embeddings,
                   std::string* error_msg) override;

  std::string GetProvider() const override { return provider_; }
  std::string GetModel() const override { return model_; }
  int GetDimensions() const override { return dimensions_; }

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

#endif  // LOCAL_EMBEDDING_SERVICE_MOCK_EMBEDDING_BACKEND_H_
