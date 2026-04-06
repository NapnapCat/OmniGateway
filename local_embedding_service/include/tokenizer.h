#ifndef LOCAL_EMBEDDING_SERVICE_TOKENIZER_H_
#define LOCAL_EMBEDDING_SERVICE_TOKENIZER_H_

#include <string>
#include <vector>

namespace embedding_service {

class ITokenizer {
 public:
  virtual ~ITokenizer() = default;

  virtual std::vector<int64_t> Encode(const std::string& text) = 0;

  virtual int GetMaxLength() const = 0;
};

class SimpleTokenizer : public ITokenizer {
 public:
  explicit SimpleTokenizer(int max_length = 512);
  ~SimpleTokenizer() override = default;

  std::vector<int64_t> Encode(const std::string& text) override;

  int GetMaxLength() const override { return max_length_; }

 private:
  int max_length_;
};

}  // namespace embedding_service

#endif  // LOCAL_EMBEDDING_SERVICE_TOKENIZER_H_
