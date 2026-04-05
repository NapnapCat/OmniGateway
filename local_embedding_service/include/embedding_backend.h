#ifndef LOCAL_EMBEDDING_SERVICE_EMBEDDING_BACKEND_H_
#define LOCAL_EMBEDDING_SERVICE_EMBEDDING_BACKEND_H_

#include <string>
#include <vector>

namespace embedding_service {

class IEmbeddingBackend {
 public:
  virtual ~IEmbeddingBackend() = default;

  virtual bool Init(std::string* error_msg) = 0;

  virtual bool Encode(const std::string& text, std::vector<float>* embedding,
                      std::string* error_msg) = 0;

  virtual std::string GetProvider() const = 0;
  virtual std::string GetModel() const = 0;
  virtual int GetDimensions() const = 0;
};

}  // namespace embedding_service

#endif  // LOCAL_EMBEDDING_SERVICE_EMBEDDING_BACKEND_H_
