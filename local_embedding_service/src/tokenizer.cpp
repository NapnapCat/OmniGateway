#include "tokenizer.h"

#include <algorithm>
#include <cctype>
#include <sstream>

namespace embedding_service {

SimpleTokenizer::SimpleTokenizer(int max_length) : max_length_(max_length) {}

std::vector<int64_t> SimpleTokenizer::Encode(const std::string& text) {
  std::vector<int64_t> token_ids;
  token_ids.reserve(max_length_);

  std::string normalized = text;
  std::transform(normalized.begin(), normalized.end(), normalized.begin(),
                 [](unsigned char c) { return std::tolower(c); });

  std::istringstream stream(normalized);
  std::string word;
  int count = 0;
  while (stream >> word && count < max_length_) {
    uint32_t hash = 2166136261u;
    for (unsigned char ch : word) {
      hash ^= static_cast<uint32_t>(ch);
      hash *= 16777619u;
    }
    token_ids.push_back(static_cast<int64_t>(hash % 30000));
    ++count;
  }

  if (token_ids.empty()) {
    token_ids.push_back(0);
  }

  return token_ids;
}

}  // namespace embedding_service
