# Changelog

All notable changes to the Local Embedding Service project will be documented in this file.

## [v4.12.0] - 2026-05-19

### Optimized - Issue #19 推理性能优化：内存管理与矩阵计算

#### 内存池与缓冲区复用
- ✅ `OnnxEmbeddingBackend`: 缓存 `Ort::MemoryInfo`，避免每次推理重复创建
- ✅ `OnnxEmbeddingBackend`: 预分配 `buf_input_ids_`, `buf_attention_mask_`, `buf_input_shape_` 推理缓冲区
- ✅ `OnnxRerankBackend`: 缓存 `Ort::MemoryInfo`，避免每次推理重复创建
- ✅ `OnnxRerankBackend`: 预分配 `buf_input_ids_`, `buf_attention_mask_`, `buf_token_type_ids_`, `buf_shape_` 缓冲区
- ✅ 使用 `std::move` 将 tokenizer 输出直接移入缓冲区，零拷贝传递

#### 真批量推理（EncodeBatch）
- ✅ `OnnxEmbeddingBackend::EncodeBatch` 重写为单次 ONNX Session::Run 调用
- ✅ 将多条文本 tokenize 后 pad 到统一长度，构建 [batch_size, max_seq_len] 张量
- ✅ 单次推理取回所有 embedding，消除逐条推理的 Session::Run 开销

#### Move 语义与拷贝消除
- ✅ `Encode()`: 使用 `assign()` 替代 `resize() + copy()`，利用 memcpy 快速路径
- ✅ `EmbeddingServiceImpl`: gRPC 请求中 texts/documents 使用 `emplace_back` 避免额外拷贝
- ✅ `BertTokenizer::EncodePair` 结果通过 `std::move` 传递给推理缓冲

#### 截断算法优化
- ✅ `BertTokenizer::EncodePair` 截断逻辑从 O(n) pop_back 循环改为 O(1) resize

### Performance Impact
- 内存占用下降：消除 per-call MemoryInfo 分配和重复 vector 分配
- 吞吐提升：EncodeBatch 从 N 次 Session::Run 减少到 1 次；Rerank 消除重复缓冲区分配

---

## [v4.11.0] - 2026-05-12

### Added - Issue #18 Rerank ONNX 推理与多模型切换
- ✅ 新增 `IRerankBackend` 抽象接口 (`include/rerank_backend.h`)
  - `Rerank(query, documents, top_k, results, error_msg)` — 对文档列表打分排序
  - `GetProvider()`, `GetModel()` — 获取后端信息
- ✅ 新增 `MockRerankBackend` (`include/mock_rerank_backend.h`, `src/mock_rerank_backend.cpp`)
  - 基于 token overlap 的启发式排序（保持与 v4.10.0 兼容）
  - 通过 `LOCAL_RERANK_MODEL` 环境变量配置
- ✅ 新增 `OnnxRerankBackend` (`include/onnx_rerank_backend.h`, `src/onnx_rerank_backend.cpp`)
  - ONNX Runtime 跨编码器（cross-encoder）推理
  - 自动检测输出格式：单 score 或双 logits（softmax 转换）
  - 支持通过环境变量切换模型：`LOCAL_RERANK_MODEL_PATH`, `LOCAL_RERANK_MODEL`
- ✅ 新增 `BertTokenizer` (`include/bert_tokenizer.h`, `src/bert_tokenizer.cpp`)
  - 基于 WordPiece 算法的分词器
  - 读取标准 `vocab.txt` 格式词表
  - 支持 `EncodePair(query, document)` 生成跨编码器输入（input_ids + token_type_ids + attention_mask）
  - 自动处理 CJK 字符、标点符号分割
- ✅ `ITokenizer` 接口扩展：新增 `TokenPairEncoding` 结构体和 `EncodePair()` 虚方法

### Changed
- 🔄 `EmbeddingServiceImpl::Rerank()` 重构为委托 `IRerankBackend` 接口
- 🔄 构造函数新增 rerank 后端初始化，ONNX 模式自动选择 `OnnxRerankBackend`，失败时回退至 `MockRerankBackend`
- 🔄 移除 `embedding_service_impl.cpp` 中的内联启发式 rerank 逻辑
- 🔄 `CMakeLists.txt` 新增 `mock_rerank_backend.cpp`, `bert_tokenizer.cpp`, `onnx_rerank_backend.cpp` 编译

### Documentation
- ✅ `USE_GUIDE.md` 新增 Rerank ONNX 配置章节
- ✅ `ONNX_SETUP.md` 新增跨编码器模型配置说明
- ✅ `README.md` 更新 Issue #18 验收状态
- ✅ `test_all_features.sh` 新增 Rerank 推理实现文件检查

### Testing
- ✅ 新增文件结构检查：`IRerankBackend`, `MockRerankBackend`, `OnnxRerankBackend`, `BertTokenizer`
- ✅ 新增运行时得分验证：rerank 返回数值分数并降序排列
- ✅ 保持现有 mock 模式下 rerank 行为完全兼容

### Known Limitations
- `BertTokenizer` 为基础 WordPiece 实现，高级特性（lowercase/uncase 自动检测、NFC 归一化）可后续增强
- 跨编码器逐对推理（未使用 batch），大规模文档时性能可优化

---


### Added - Issue #17 Rerank 接口与批量排序
- ✅ 新增 `Rerank(RerankRequest) -> RerankResponse` gRPC 接口
- ✅ `RerankRequest` 支持批量 query 与 `top_k` 截断
- ✅ 基础排序逻辑（token overlap + 稳定排序）
- ✅ `test_all_features.sh` 增加 Rerank 端到端验证
- ✅ 更新 README / USE_GUIDE / 使用方法文档

## [v4.5.0] - 2026-04-05

### Added - ONNX Runtime 集成与 Embedding 模型接入

#### 阶段一：ONNX Runtime 环境搭建
- ✅ 新增 CMake 可选支持 ONNX Runtime 集成
- ✅ 支持通过环境变量配置 ONNX Runtime 路径
  - `ONNXRUNTIME_INCLUDE_DIR` - ONNX Runtime 头文件目录
  - `ONNXRUNTIME_LIB_DIR` - ONNX Runtime 库目录
  - `ONNXRUNTIME_LIBS` - 需要链接的库名称
- ✅ 新增 `ONNX_SETUP.md` 文档，详细说明 ONNX Runtime 安装和配置流程

#### 阶段二：CMake 配置更新
- ✅ 新增 `EMBEDDING_WITH_ONNXRUNTIME` CMake 选项（默认 OFF）
  - OFF 时：完全不依赖 ONNX Runtime，保持 mock 行为
  - ON 时：引入 ONNX Runtime 头文件与链接库，启用真实模型推理
- ✅ 新增条件编译支持，通过 `ENABLE_ONNX_BACKEND` 宏控制 ONNX 代码编译
- ✅ CMakeLists.txt 支持灵活的库链接配置

#### 阶段三：实现模型管理类
- ✅ 新增 `IEmbeddingBackend` 抽象接口 (`include/embedding_backend.h`)
  - `bool Init(std::string* error_msg)` - 初始化后端
  - `bool Encode(const std::string& text, std::vector<float>* embedding, std::string* error_msg)` - 编码文本
  - `GetProvider()`, `GetModel()`, `GetDimensions()` - 获取后端信息
- ✅ 新增 `MockEmbeddingBackend` 实现 (`include/mock_embedding_backend.h`, `src/mock_embedding_backend.cpp`)
  - 基于 FNV-1a 哈希算法生成确定性 mock 向量
  - 输出 1536 维向量（与常见 embedding 模型对齐）
  - 无需任何外部依赖
- ✅ 新增 `OnnxEmbeddingBackend` 实现 (`include/onnx_embedding_backend.h`, `src/onnx_embedding_backend.cpp`)
  - 封装 ONNX Runtime Session 管理
  - 支持模型加载、初始化和推理
  - 完整的错误处理机制

#### 阶段四：实现 Tokenizer 与批处理接口
- ✅ 新增 `ITokenizer` 抽象接口 (`include/tokenizer.h`)
  - `std::vector<int64_t> Encode(const std::string& text)` - 文本分词和编码
  - `int GetMaxLength()` - 获取最大序列长度
- ✅ 新增 `SimpleTokenizer` 实现 (`src/tokenizer.cpp`)
  - 基于空格的简单分词
  - 文本归一化（小写转换）
  - 基于 FNV-1a hash 生成 token ID
  - 可配置最大长度限制（默认 512）
- 📝 批处理接口 `EncodeBatch` 预留接口，可在未来需要时添加

#### 阶段五：实现核心推理逻辑
- ✅ 环境变量读取支持
  - `EMBEDDING_BACKEND` - 后端类型选择（mock/onnx，默认 mock）
  - `LOCAL_EMBED_MODEL_PATH` - ONNX 模型文件路径
  - `LOCAL_EMBED_PROVIDER` - 提供者名称（默认 onnx-runtime）
  - `LOCAL_EMBED_MODEL` - 模型名称（默认 bge-base-en-v1.5）
  - `LOCAL_EMBED_DIMENSIONS` - 向量维度（默认 768）
  - `LOCAL_EMBED_MAX_LENGTH` - 最大文本长度（默认 512）
- ✅ Tokenizer 输出转换为 ONNX 输入张量
  - 自动生成 `input_ids` 和 `attention_mask`
  - 支持动态 batch size 和 sequence length
- ✅ Embedding 向量提取逻辑
  - 从 ONNX 模型输出提取第一个 token (CLS) 的向量
  - 自动适配输出维度
- ✅ 完整的错误处理
  - 初始化失败时记录错误，保持 Info 接口可用
  - 推理失败通过 `response.error` 字段返回详细错误信息
  - ONNX Runtime 异常捕获和转换

#### 阶段六：模型加载与集成测试
- ✅ 服务启动时自动加载并初始化后端
- ✅ 启动时打印关键配置信息
  - Provider（local-mock / onnx-runtime）
  - Model name
  - Dimensions
- ✅ 新增测试脚本
  - `check_embedding_service.sh` - 基础功能测试
  - `test_all_features.sh` - 全面的六阶段测试脚本
- ✅ gRPC 接口端到端验证
  - Info 端点正常工作
  - GetEmbedding 端点正常工作
  - 错误场景处理验证

### Changed
- 🔄 重构 `EmbeddingServiceImpl` 使用后端接口模式
  - 支持运行时切换不同的后端实现
  - 通过 `EMBEDDING_BACKEND` 环境变量控制
- 🔄 更新 `main.cpp` 启动流程
  - 自动初始化选择的后端
  - 打印详细的启动信息

### Documentation
- ✅ 新增 `ONNX_SETUP.md` - ONNX Runtime 安装和配置指南
- ✅ 更新 `USE_GUIDE.md` - 添加 ONNX 后端使用说明
- ✅ 新增 `test_all_features.sh` - 全面测试脚本
- ✅ 新增 `CHANGELOG.md` - 变更日志

### Technical Details

#### 架构设计
```
后端接口层 (IEmbeddingBackend)
    ├── MockEmbeddingBackend (无依赖，哈希向量)
    └── OnnxEmbeddingBackend (ONNX Runtime 推理)
            ├── ITokenizer (分词抽象)
            │   └── SimpleTokenizer (空格分词 + hash)
            └── ONNX Runtime Session
```

#### 编译选项
- **默认模式** (EMBEDDING_WITH_ONNXRUNTIME=OFF)
  - 仅编译 Mock 后端
  - 无 ONNX Runtime 依赖
  - 二进制体积小，启动快

- **ONNX 模式** (EMBEDDING_WITH_ONNXRUNTIME=ON)
  - 编译 Mock + ONNX 后端
  - 需要 ONNX Runtime 库
  - 支持真实模型推理

#### 运行时行为
- 默认使用 Mock 后端（快速验证和开发）
- 设置 `EMBEDDING_BACKEND=onnx` 切换到 ONNX 后端
- ONNX 后端未启用时自动降级到 Mock

### Testing
- ✅ 20/20 测试用例通过
- ✅ 编译配置验证
- ✅ 代码结构检查
- ✅ 运行时功能测试
- ✅ gRPC 接口测试
- ✅ 错误处理测试
- ✅ 文档完整性检查

### Performance
- Mock 后端：极低延迟（< 1ms），适合开发和测试
- ONNX 后端：取决于模型大小和硬件（bge-base-en-v1.5 约 10-50ms/文本）

### Known Limitations
- SimpleTokenizer 为基础实现，不支持 WordPiece/BPE
- 真实生产环境建议使用专业 tokenizer 库（如 sentencepiece）
- 批处理接口 EncodeBatch 暂未实现

### Future Work
- [ ] 实现批处理接口 EncodeBatch
- [ ] 集成专业 tokenizer（sentencepiece/HuggingFace tokenizers）
- [ ] 支持更多 ONNX 模型格式
- [ ] GPU 加速支持
- [ ] 性能优化和缓存机制

---

## [v4.9.0] - 2026-04-18

### Added - Issue #16 ONNX Runtime 编译部署与回退能力
- ✅ 补充 ONNX Runtime 编译与部署验收内容
- ✅ 新增 `test_onnx_fallback.sh`，验证 ONNX 请求但模型加载失败时的自动回退行为
- ✅ `test_all_features.sh` 增加对 `test_onnx_fallback.sh` 存在性的检查

### Changed
- 🔄 `EmbeddingServiceImpl` 增强回退逻辑：当 `EMBEDDING_BACKEND=onnx` 且 ONNX 后端初始化失败时，自动切换到 `MockEmbeddingBackend`
- 🔄 ONNX 初始化失败后服务继续可用，`Info` 与 embedding 接口可通过 Mock 后端正常响应

### Documentation
- ✅ 更新 `README.md` 的 Issue #16 验收说明
- ✅ 更新 `USE_GUIDE.md` 与 `使用方法.md` 的 ONNX 编译、验证和 fallback 说明

### Testing
- ✅ 新增 ONNX fallback 自动化验证脚本
- ✅ 保持现有功能回归测试通过（`test_all_features.sh`）

---

## [v4.0.0] - 2026-03-30

### Added
- ✅ 初始 C++ embedding service 实现
- ✅ 基于 embedding.proto 的 gRPC 服务
- ✅ Mock embedding 后端（哈希向量生成）
- ✅ CMake 构建系统
- ✅ Docker 支持
- ✅ 基础测试脚本

### Features
- gRPC 服务端实现
- Info 接口 - 返回服务信息
- GetEmbedding 接口 - 返回文本向量
- 与 Go gateway 完全兼容

---

## [v4.8.0] - 2026-04-30
- ✅ gRPC 接口已支持批量请求：新增 `GetEmbeddings(EmbeddingBatchRequest) -> EmbeddingBatchResponse`
- ✅ 批处理逻辑已实现：`IEmbeddingBackend` 新增 `EncodeBatch`，Mock/ONNX 后端均已接入
- ✅ 内存复用优化：批量编码路径中使用 `reserve` 和复用中间容器，减少重复分配

---
## Version History
- **v4.8.0** (2026-04-08) - 将 embedding 能力封装为 gRPC 服务。
- **v4.5.0** (2026-04-05) - ONNX Runtime 集成，真实模型支持
- **v4.0.0** (2026-03-30) - 初始版本，Mock 实现
