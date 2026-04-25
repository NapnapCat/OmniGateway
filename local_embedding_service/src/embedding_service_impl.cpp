#include "embedding_service_impl.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <iostream>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

#include "mock_embedding_backend.h"

#ifdef ENABLE_ONNX_BACKEND
#include "onnx_embedding_backend.h"
#endif

namespace embedding_service {

namespace {

std::vector<std::string> TokenizeForRerank(const std::string& text) {
  std::vector<std::string> tokens;
  std::string current;
  current.reserve(text.size());
  for (unsigned char ch : text) {
    if (std::isalnum(ch)) {
      current.push_back(static_cast<char>(std::tolower(ch)));
    } else if (!current.empty()) {
      tokens.push_back(current);
      current.clear();
    }
  }
  if (!current.empty()) {
    tokens.push_back(current);
  }
  return tokens;
}

std::unordered_set<std::string> TokenSetForRerank(const std::string& text) {
  std::vector<std::string> tokens = TokenizeForRerank(text);
  return std::unordered_set<std::string>(tokens.begin(), tokens.end());
}

}  // namespace

static std::string ReadStringEnv(const char* name, const char* default_value) {
  const char* value = std::getenv(name);
  if (value == nullptr || value[0] == '\0') {
    return default_value;
  }
  return value;
}

EmbeddingServiceImpl::EmbeddingServiceImpl() {
  std::string backend_type = ReadStringEnv("EMBEDDING_BACKEND", "mock");
  const bool onnx_requested = (backend_type == "onnx");

  if (onnx_requested) {
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
    if (onnx_requested) {
      std::cerr << "[Warning] Falling back to mock embedding backend."
                << std::endl;
      backend_ = std::make_unique<MockEmbeddingBackend>();
      std::string fallback_error;
      if (!backend_->Init(&fallback_error)) {
        init_error_ = "Fallback mock backend init failed: " + fallback_error;
        std::cerr << "[Error] " << init_error_ << std::endl;
      } else {
        init_error_.clear();
        std::cout << "[Info] Fallback backend initialized: provider="
                  << backend_->GetProvider() << ", model=" << backend_->GetModel()
                  << ", dimensions=" << backend_->GetDimensions() << std::endl;
      }
    }
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

grpc::Status EmbeddingServiceImpl::GetEmbeddings(
    grpc::ServerContext*, const embedding::EmbeddingBatchRequest* request,
    embedding::EmbeddingBatchResponse* response) {
  if (!init_error_.empty()) {
    response->set_error("Backend initialization failed: " + init_error_);
    return grpc::Status::OK;
  }

  const int text_count = request->texts_size();
  if (text_count <= 0) {
    response->set_error("texts must not be empty");
    return grpc::Status::OK;
  }

  std::vector<std::string> texts;
  texts.reserve(static_cast<size_t>(text_count));
  for (const auto& text : request->texts()) {
    texts.push_back(text);
  }

  std::vector<std::vector<float>> embeddings;
  std::string error_msg;
  if (!backend_->EncodeBatch(texts, &embeddings, &error_msg)) {
    response->set_error(error_msg);
    return grpc::Status::OK;
  }

  if (embeddings.size() != texts.size()) {
    response->set_error("backend returned inconsistent batch size");
    return grpc::Status::OK;
  }

  for (const auto& emb : embeddings) {
    auto* item = response->add_items();
    for (float value : emb) {
      item->add_embedding(value);
    }
    item->set_error("");
  }
  response->set_error("");
  return grpc::Status::OK;
}

grpc::Status EmbeddingServiceImpl::Rerank(grpc::ServerContext*,
                                          const embedding::RerankRequest* request,
                                          embedding::RerankResponse* response) {
  const int query_count = request->queries_size();
  if (query_count <= 0) {
    response->set_error("queries must not be empty");
    return grpc::Status::OK;
  }

  for (const auto& query : request->queries()) {
    auto* result = response->add_results();
    if (query.query().empty()) {
      result->set_error("query must not be empty");
      continue;
    }
    if (query.documents_size() <= 0) {
      result->set_error("documents must not be empty");
      continue;
    }

    const auto query_tokens = TokenSetForRerank(query.query());
    if (query_tokens.empty()) {
      result->set_error("query must not be empty");
      continue;
    }

    struct Candidate {
      int index;
      std::string document;
      float score;
    };

    std::vector<Candidate> candidates;
    candidates.reserve(static_cast<size_t>(query.documents_size()));
    for (int i = 0; i < query.documents_size(); ++i) {
      const std::string& document = query.documents(i);
      const auto doc_tokens = TokenSetForRerank(document);
      int overlap = 0;
      for (const auto& token : doc_tokens) {
        if (query_tokens.count(token) > 0) {
          ++overlap;
        }
      }
      candidates.push_back({i, document, static_cast<float>(overlap)});
    }

    std::stable_sort(candidates.begin(), candidates.end(),
                     [](const Candidate& lhs, const Candidate& rhs) {
                       return lhs.score > rhs.score;
                     });

    int top_k = query.top_k();
    if (top_k <= 0 || top_k > static_cast<int>(candidates.size())) {
      top_k = static_cast<int>(candidates.size());
    }

    for (int i = 0; i < top_k; ++i) {
      const auto& candidate = candidates[static_cast<size_t>(i)];
      auto* item = result->add_items();
      item->set_index(candidate.index);
      item->set_document(candidate.document);
      item->set_score(candidate.score);
    }
    result->set_error("");
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
