#ifndef LOCAL_EMBEDDING_SERVICE_ONNX_EMBEDDING_BACKEND_H_
#define LOCAL_EMBEDDING_SERVICE_ONNX_EMBEDDING_BACKEND_H_

#include "embedding_backend.h"
#include "tokenizer.h"

#include <memory>
#include <string>
#include <vector>

#ifdef ENABLE_ONNX_BACKEND
#include <onnxruntime_cxx_api.h>
#endif

namespace embedding_service {

class OnnxEmbeddingBackend : public IEmbeddingBackend {
 public:
  OnnxEmbeddingBackend();
  ~OnnxEmbeddingBackend() override;

  bool Init(std::string* error_msg) override;

  bool Encode(const std::string& text, std::vector<float>* embedding,
              std::string* error_msg) override;

  std::string GetProvider() const override { return provider_; }
  std::string GetModel() const override { return model_; }
  int GetDimensions() const override { return dimensions_; }

 private:
  std::string provider_;
  std::string model_;
  std::string model_path_;
  int dimensions_;
  int max_length_;

  std::unique_ptr<ITokenizer> tokenizer_;

#ifdef ENABLE_ONNX_BACKEND
  std::unique_ptr<Ort::Env> ort_env_;
  std::unique_ptr<Ort::Session> ort_session_;
  std::unique_ptr<Ort::SessionOptions> session_options_;
  std::vector<std::string> input_names_str_;
  std::vector<std::string> output_names_str_;
  std::vector<const char*> input_names_;
  std::vector<const char*> output_names_;
#endif

  static std::string ReadStringEnv(const char* name, const char* default_value);
  static int ReadIntEnv(const char* name, int default_value);
};

}  // namespace embedding_service

#endif  // LOCAL_EMBEDDING_SERVICE_ONNX_EMBEDDING_BACKEND_H_
