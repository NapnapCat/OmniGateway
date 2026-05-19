#ifndef LOCAL_EMBEDDING_SERVICE_ONNX_RERANK_BACKEND_H_
#define LOCAL_EMBEDDING_SERVICE_ONNX_RERANK_BACKEND_H_

#include "rerank_backend.h"
#include "tokenizer.h"

#include <memory>
#include <string>
#include <vector>

#ifdef ENABLE_ONNX_BACKEND
#include <onnxruntime_cxx_api.h>
#endif

namespace embedding_service {

class OnnxRerankBackend : public IRerankBackend {
 public:
  OnnxRerankBackend();
  ~OnnxRerankBackend() override;

  bool Init(std::string* error_msg) override;

  bool Rerank(const std::string& query,
              const std::vector<std::string>& documents, int top_k,
              std::vector<RerankItem>* results,
              std::string* error_msg) override;

  std::string GetProvider() const override { return provider_; }
  std::string GetModel() const override { return model_; }

 private:
  std::string provider_;
  std::string model_;
  std::string model_path_;
  std::string vocab_path_;
  int max_length_;

  std::unique_ptr<ITokenizer> tokenizer_;

#ifdef ENABLE_ONNX_BACKEND
  std::unique_ptr<Ort::Env> ort_env_;
  std::unique_ptr<Ort::Session> ort_session_;
  std::unique_ptr<Ort::SessionOptions> session_options_;
  std::unique_ptr<Ort::MemoryInfo> memory_info_;
  std::vector<std::string> input_names_str_;
  std::vector<std::string> output_names_str_;
  std::vector<const char*> input_names_;
  std::vector<const char*> output_names_;

  // Pre-allocated buffers for batched rerank inference
  std::vector<int64_t> buf_input_ids_;
  std::vector<int64_t> buf_attention_mask_;
  std::vector<int64_t> buf_token_type_ids_;
  std::vector<int64_t> buf_shape_;

  float ExtractScore(Ort::Value& output_tensor);
#endif

  static std::string ReadStringEnv(const char* name,
                                   const char* default_value);
  static int ReadIntEnv(const char* name, int default_value);
};

}  // namespace embedding_service

#endif  // LOCAL_EMBEDDING_SERVICE_ONNX_RERANK_BACKEND_H_
