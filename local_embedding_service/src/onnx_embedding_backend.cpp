#include "onnx_embedding_backend.h"

#include <cstdlib>
#include <iostream>

#ifdef ENABLE_ONNX_BACKEND
#include <onnxruntime_cxx_api.h>
#endif

namespace embedding_service {

std::string OnnxEmbeddingBackend::ReadStringEnv(const char* name,
                                                const char* default_value) {
  const char* value = std::getenv(name);
  if (value == nullptr || value[0] == '\0') {
    return default_value;
  }
  return value;
}

int OnnxEmbeddingBackend::ReadIntEnv(const char* name, int default_value) {
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

OnnxEmbeddingBackend::OnnxEmbeddingBackend()
    : provider_(ReadStringEnv("LOCAL_EMBED_PROVIDER", "onnx-runtime")),
      model_(ReadStringEnv("LOCAL_EMBED_MODEL", "bge-base-en-v1.5")),
      model_path_(ReadStringEnv("LOCAL_EMBED_MODEL_PATH", "")),
      dimensions_(ReadIntEnv("LOCAL_EMBED_DIMENSIONS", 768)),
      max_length_(ReadIntEnv("LOCAL_EMBED_MAX_LENGTH", 512)),
      tokenizer_(std::make_unique<SimpleTokenizer>(max_length_)) {
#ifdef ENABLE_ONNX_BACKEND
  ort_env_ = nullptr;
  ort_session_ = nullptr;
  session_options_ = nullptr;
  memory_info_ = nullptr;
#endif
}

OnnxEmbeddingBackend::~OnnxEmbeddingBackend() = default;

bool OnnxEmbeddingBackend::Init(std::string* error_msg) {
#ifndef ENABLE_ONNX_BACKEND
  *error_msg =
      "ONNX backend not compiled. Rebuild with -DEMBEDDING_WITH_ONNXRUNTIME=ON";
  return false;
#else
  if (model_path_.empty()) {
    *error_msg =
        "LOCAL_EMBED_MODEL_PATH environment variable not set. Please provide "
        "path to ONNX model file.";
    return false;
  }

  try {
    ort_env_ = std::make_unique<Ort::Env>(ORT_LOGGING_LEVEL_WARNING,
                                          "EmbeddingBackend");
    session_options_ = std::make_unique<Ort::SessionOptions>();
    session_options_->SetIntraOpNumThreads(1);
    session_options_->SetGraphOptimizationLevel(
        GraphOptimizationLevel::ORT_ENABLE_ALL);

    std::cout << "[Info] Loading ONNX model from: " << model_path_ << std::endl;
    ort_session_ = std::make_unique<Ort::Session>(
        *ort_env_, model_path_.c_str(), *session_options_);

    // Cache MemoryInfo to avoid per-call allocation
    memory_info_ = std::make_unique<Ort::MemoryInfo>(
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault));

    Ort::AllocatorWithDefaultOptions allocator;
    size_t num_input_nodes = ort_session_->GetInputCount();
    size_t num_output_nodes = ort_session_->GetOutputCount();

    input_names_str_.reserve(num_input_nodes);
    input_names_.reserve(num_input_nodes);
    for (size_t i = 0; i < num_input_nodes; ++i) {
      auto name_ptr = ort_session_->GetInputNameAllocated(i, allocator);
      input_names_str_.push_back(name_ptr.get());
      input_names_.push_back(input_names_str_.back().c_str());
    }

    output_names_str_.reserve(num_output_nodes);
    output_names_.reserve(num_output_nodes);
    for (size_t i = 0; i < num_output_nodes; ++i) {
      auto name_ptr = ort_session_->GetOutputNameAllocated(i, allocator);
      output_names_str_.push_back(name_ptr.get());
      output_names_.push_back(output_names_str_.back().c_str());
    }

    // Pre-allocate inference buffers
    buf_input_ids_.reserve(static_cast<size_t>(max_length_));
    buf_attention_mask_.reserve(static_cast<size_t>(max_length_));
    buf_input_shape_.resize(2);

    std::cout << "[Info] ONNX model loaded successfully. Inputs: "
              << num_input_nodes << ", Outputs: " << num_output_nodes
              << std::endl;
    return true;
  } catch (const Ort::Exception& e) {
    *error_msg = std::string("ONNX Runtime error: ") + e.what();
    return false;
  } catch (const std::exception& e) {
    *error_msg = std::string("Error loading ONNX model: ") + e.what();
    return false;
  }
#endif
}

bool OnnxEmbeddingBackend::Encode(const std::string& text,
                                  std::vector<float>* embedding,
                                  std::string* error_msg) {
#ifndef ENABLE_ONNX_BACKEND
  *error_msg = "ONNX backend not enabled";
  return false;
#else
  if (!ort_session_) {
    *error_msg = "ONNX session not initialized. Call Init() first.";
    return false;
  }

  try {
    auto token_ids = tokenizer_->Encode(text);

    // Reuse pre-allocated buffers
    buf_input_ids_.assign(token_ids.begin(), token_ids.end());
    buf_attention_mask_.assign(buf_input_ids_.size(), 1);

    buf_input_shape_[0] = 1;
    buf_input_shape_[1] = static_cast<int64_t>(buf_input_ids_.size());

    std::vector<Ort::Value> input_tensors;
    input_tensors.reserve(2);
    input_tensors.push_back(Ort::Value::CreateTensor<int64_t>(
        *memory_info_, buf_input_ids_.data(), buf_input_ids_.size(),
        buf_input_shape_.data(), buf_input_shape_.size()));
    input_tensors.push_back(Ort::Value::CreateTensor<int64_t>(
        *memory_info_, buf_attention_mask_.data(), buf_attention_mask_.size(),
        buf_input_shape_.data(), buf_input_shape_.size()));

    auto output_tensors = ort_session_->Run(
        Ort::RunOptions{nullptr}, input_names_.data(), input_tensors.data(),
        input_tensors.size(), output_names_.data(), output_names_.size());

    if (output_tensors.empty()) {
      *error_msg = "ONNX model returned no output";
      return false;
    }

    float* output_data = output_tensors[0].GetTensorMutableData<float>();
    auto output_shape = output_tensors[0].GetTensorTypeAndShapeInfo().GetShape();

    int embedding_dim = dimensions_;
    if (output_shape.size() >= 2) {
      embedding_dim = static_cast<int>(output_shape[output_shape.size() - 1]);
    }

    embedding->assign(output_data, output_data + embedding_dim);

    return true;
  } catch (const Ort::Exception& e) {
    *error_msg = std::string("ONNX inference error: ") + e.what();
    return false;
  } catch (const std::exception& e) {
    *error_msg = std::string("Error during encoding: ") + e.what();
    return false;
  }
#endif
}

bool OnnxEmbeddingBackend::EncodeBatch(
    const std::vector<std::string>& texts,
    std::vector<std::vector<float>>* embeddings, std::string* error_msg) {
#ifndef ENABLE_ONNX_BACKEND
  *error_msg = "ONNX backend not enabled";
  return false;
#else
  if (!ort_session_) {
    *error_msg = "ONNX session not initialized. Call Init() first.";
    return false;
  }

  if (texts.empty()) {
    embeddings->clear();
    return true;
  }

  try {
    const int64_t batch_size = static_cast<int64_t>(texts.size());

    // Tokenize all texts and find max sequence length for padding
    std::vector<std::vector<int64_t>> all_token_ids;
    all_token_ids.reserve(texts.size());
    int64_t max_seq_len = 0;
    for (const auto& text : texts) {
      all_token_ids.push_back(tokenizer_->Encode(text));
      auto len = static_cast<int64_t>(all_token_ids.back().size());
      if (len > max_seq_len) max_seq_len = len;
    }

    // Build padded flat tensors for batched inference
    const size_t total_elements =
        static_cast<size_t>(batch_size) * static_cast<size_t>(max_seq_len);
    buf_input_ids_.assign(total_elements, 0);
    buf_attention_mask_.assign(total_elements, 0);

    for (size_t i = 0; i < all_token_ids.size(); ++i) {
      const auto& ids = all_token_ids[i];
      size_t offset = i * static_cast<size_t>(max_seq_len);
      for (size_t j = 0; j < ids.size(); ++j) {
        buf_input_ids_[offset + j] = ids[j];
        buf_attention_mask_[offset + j] = 1;
      }
    }

    std::vector<int64_t> shape = {batch_size, max_seq_len};

    std::vector<Ort::Value> input_tensors;
    input_tensors.reserve(2);
    input_tensors.push_back(Ort::Value::CreateTensor<int64_t>(
        *memory_info_, buf_input_ids_.data(), total_elements, shape.data(),
        shape.size()));
    input_tensors.push_back(Ort::Value::CreateTensor<int64_t>(
        *memory_info_, buf_attention_mask_.data(), total_elements, shape.data(),
        shape.size()));

    auto output_tensors = ort_session_->Run(
        Ort::RunOptions{nullptr}, input_names_.data(), input_tensors.data(),
        input_tensors.size(), output_names_.data(), output_names_.size());

    if (output_tensors.empty()) {
      *error_msg = "ONNX model returned no output";
      return false;
    }

    float* output_data = output_tensors[0].GetTensorMutableData<float>();
    auto output_shape = output_tensors[0].GetTensorTypeAndShapeInfo().GetShape();

    int embedding_dim = dimensions_;
    if (output_shape.size() >= 2) {
      embedding_dim = static_cast<int>(output_shape[output_shape.size() - 1]);
    }

    embeddings->clear();
    embeddings->reserve(texts.size());
    for (size_t i = 0; i < texts.size(); ++i) {
      float* start = output_data + i * embedding_dim;
      embeddings->emplace_back(start, start + embedding_dim);
    }

    return true;
  } catch (const Ort::Exception& e) {
    *error_msg = std::string("ONNX batch inference error: ") + e.what();
    embeddings->clear();
    return false;
  } catch (const std::exception& e) {
    *error_msg = std::string("Error during batch encoding: ") + e.what();
    embeddings->clear();
    return false;
  }
#endif
}

}  // namespace embedding_service
