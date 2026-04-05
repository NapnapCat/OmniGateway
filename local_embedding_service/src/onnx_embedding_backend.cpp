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
    std::vector<int64_t> input_ids = token_ids;
    std::vector<int64_t> attention_mask(input_ids.size(), 1);

    const int64_t batch_size = 1;
    const int64_t seq_length = static_cast<int64_t>(input_ids.size());
    std::vector<int64_t> input_shape = {batch_size, seq_length};

    Ort::MemoryInfo memory_info =
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

    std::vector<Ort::Value> input_tensors;
    input_tensors.push_back(Ort::Value::CreateTensor<int64_t>(
        memory_info, input_ids.data(), input_ids.size(), input_shape.data(),
        input_shape.size()));
    input_tensors.push_back(Ort::Value::CreateTensor<int64_t>(
        memory_info, attention_mask.data(), attention_mask.size(),
        input_shape.data(), input_shape.size()));

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

    embedding->resize(embedding_dim);
    std::copy(output_data, output_data + embedding_dim, embedding->begin());

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

}  // namespace embedding_service
