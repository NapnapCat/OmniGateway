#include "bert_tokenizer.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <unordered_set>

namespace embedding_service {

BertTokenizer::BertTokenizer(const std::string& vocab_path, int max_length)
    : max_length_(max_length) {
  std::string error_msg;
  if (!LoadVocab(vocab_path, &error_msg)) {
    std::cerr << "[Warning] BertTokenizer vocab load failed: " << error_msg
              << std::endl;
  }
}

bool BertTokenizer::LoadVocab(const std::string& vocab_path,
                              std::string* error_msg) {
  std::ifstream file(vocab_path);
  if (!file.is_open()) {
    *error_msg = "Cannot open vocab file: " + vocab_path;
    return false;
  }

  vocab_.clear();
  std::string line;
  int64_t id = 0;
  while (std::getline(file, line)) {
    if (!line.empty() && line.back() == '\r') {
      line.pop_back();
    }
    if (!line.empty()) {
      vocab_[line] = id;
    }
    ++id;
  }

  // Detect special token IDs from vocab
  auto it_cls = vocab_.find("[CLS]");
  if (it_cls != vocab_.end()) cls_id_ = it_cls->second;

  auto it_sep = vocab_.find("[SEP]");
  if (it_sep != vocab_.end()) sep_id_ = it_sep->second;

  auto it_pad = vocab_.find("[PAD]");
  if (it_pad != vocab_.end()) pad_id_ = it_pad->second;

  auto it_unk = vocab_.find("[UNK]");
  if (it_unk != vocab_.end()) unk_id_ = it_unk->second;

  return true;
}

std::string BertTokenizer::Normalize(const std::string& text) {
  std::string result;
  result.reserve(text.size());
  for (unsigned char ch : text) {
    if (std::isupper(ch)) {
      result.push_back(static_cast<char>(std::tolower(ch)));
    } else {
      result.push_back(static_cast<char>(ch));
    }
  }
  return result;
}

std::vector<std::string> BertTokenizer::BasicTokenize(
    const std::string& text) const {
  std::vector<std::string> tokens;
  std::string current;

  for (size_t i = 0; i < text.size(); ++i) {
    unsigned char ch = static_cast<unsigned char>(text[i]);

    // Chinese character range (UTF-8 multi-byte start)
    if (ch >= 0x80) {
      if (!current.empty()) {
        tokens.push_back(current);
        current.clear();
      }
      // For simplicity, treat each CJK character as a token
      int len = 1;
      if ((ch & 0xE0) == 0xC0)
        len = 2;
      else if ((ch & 0xF0) == 0xE0)
        len = 3;
      else if ((ch & 0xF8) == 0xF0)
        len = 4;
      std::string cjk;
      for (int j = 0; j < len && (i + j) < text.size(); ++j) {
        cjk.push_back(text[i + j]);
      }
      i += static_cast<size_t>(len) - 1;
      // Check if this CJK character is in vocab as-is; add as token
      tokens.push_back(cjk);
      continue;
    }

    if (std::isalnum(ch)) {
      current.push_back(static_cast<char>(ch));
    } else if (std::isspace(ch)) {
      if (!current.empty()) {
        tokens.push_back(current);
        current.clear();
      }
    } else {
      // Punctuation: flush current word, then add punctuation as its own token
      if (!current.empty()) {
        tokens.push_back(current);
        current.clear();
      }
      std::string punct(1, static_cast<char>(ch));
      tokens.push_back(punct);
    }
  }

  if (!current.empty()) {
    tokens.push_back(current);
  }

  return tokens;
}

std::vector<std::string> BertTokenizer::WordPiece(
    const std::string& word) const {
  std::vector<std::string> subwords;

  if (word.empty()) return subwords;

  // Try the full word first
  if (vocab_.count(word) > 0) {
    subwords.push_back(word);
    return subwords;
  }

  // WordPiece: greedy longest-prefix matching
  size_t start = 0;
  while (start < word.size()) {
    size_t end = word.size();
    bool found = false;

    while (end > start) {
      std::string sub = word.substr(start, end - start);
      // For continuation subwords, prepend "##"
      std::string candidate = (start == 0) ? sub : ("##" + sub);
      if (vocab_.count(candidate) > 0) {
        subwords.push_back(candidate);
        found = true;
        break;
      }
      --end;
    }

    if (!found) {
      // No matching subword found; use [UNK]
      subwords.clear();
      subwords.push_back("[UNK]");
      return subwords;
    }

    start = end;
  }

  return subwords;
}

std::vector<int64_t> BertTokenizer::TokenizeToIds(const std::string& text) {
  std::string normalized = Normalize(text);
  auto words = BasicTokenize(normalized);

  std::vector<int64_t> ids;
  for (const auto& word : words) {
    auto subwords = WordPiece(word);
    for (const auto& sw : subwords) {
      auto it = vocab_.find(sw);
      if (it != vocab_.end()) {
        ids.push_back(it->second);
      } else {
        ids.push_back(unk_id_);
      }
    }
  }
  return ids;
}

std::vector<int64_t> BertTokenizer::Encode(const std::string& text) {
  auto ids = TokenizeToIds(text);

  // Reserve space for [CLS] and [SEP]
  size_t max_content = static_cast<size_t>(max_length_) > 2
                           ? static_cast<size_t>(max_length_) - 2
                           : 0;
  if (ids.size() > max_content) {
    ids.resize(max_content);
  }

  std::vector<int64_t> result;
  result.reserve(ids.size() + 2);
  result.push_back(cls_id_);
  result.insert(result.end(), ids.begin(), ids.end());
  result.push_back(sep_id_);
  return result;
}

TokenPairEncoding BertTokenizer::EncodePair(const std::string& text_a,
                                            const std::string& text_b) {
  auto tokens_a = TokenizeToIds(text_a);
  auto tokens_b = TokenizeToIds(text_b);

  // Reserve: [CLS] + A + [SEP] + B + [SEP] = 3 special tokens
  int max_a_plus_b = max_length_ - 3;
  if (max_a_plus_b < 0) max_a_plus_b = 0;

  // Truncate to fit within max_length (proportional truncation)
  size_t total = tokens_a.size() + tokens_b.size();
  if (static_cast<int>(total) > max_a_plus_b) {
    size_t budget = static_cast<size_t>(max_a_plus_b);
    size_t max_a = (budget + 1) / 2;
    size_t max_b = budget / 2;
    if (tokens_a.size() <= max_a) {
      max_b = budget - tokens_a.size();
    } else if (tokens_b.size() <= max_b) {
      max_a = budget - tokens_b.size();
    }
    if (tokens_a.size() > max_a) tokens_a.resize(max_a);
    if (tokens_b.size() > max_b) tokens_b.resize(max_b);
  }

  int total_len = 1 + static_cast<int>(tokens_a.size()) + 1 +
                  static_cast<int>(tokens_b.size()) + 1;

  std::vector<int64_t> input_ids;
  std::vector<int64_t> token_type_ids;
  std::vector<int64_t> attention_mask;

  input_ids.reserve(static_cast<size_t>(max_length_));
  token_type_ids.reserve(static_cast<size_t>(max_length_));
  attention_mask.reserve(static_cast<size_t>(max_length_));

  // [CLS]
  input_ids.push_back(cls_id_);
  token_type_ids.push_back(0);
  attention_mask.push_back(1);

  // Text A
  for (auto id : tokens_a) {
    input_ids.push_back(id);
    token_type_ids.push_back(0);
    attention_mask.push_back(1);
  }

  // [SEP]
  input_ids.push_back(sep_id_);
  token_type_ids.push_back(0);
  attention_mask.push_back(1);

  // Text B
  for (auto id : tokens_b) {
    input_ids.push_back(id);
    token_type_ids.push_back(1);
    attention_mask.push_back(1);
  }

  // [SEP]
  input_ids.push_back(sep_id_);
  token_type_ids.push_back(1);
  attention_mask.push_back(1);

  // Pad to max_length_
  int pad_len = max_length_ - total_len;
  if (pad_len > 0) {
    for (int i = 0; i < pad_len; ++i) {
      input_ids.push_back(pad_id_);
      token_type_ids.push_back(0);
      attention_mask.push_back(0);
    }
  }

  TokenPairEncoding result;
  result.input_ids = std::move(input_ids);
  result.token_type_ids = std::move(token_type_ids);
  result.attention_mask = std::move(attention_mask);
  return result;
}

}  // namespace embedding_service
