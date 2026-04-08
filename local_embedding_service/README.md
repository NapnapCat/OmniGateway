背景：
我们正在开发一个网关项目，整体架构为 Go + Python + C++。
其中 C++ Compute 作为旁路高性能计算引擎，提供两个核心服务：

1. Embedding Service：
- 输入：原始文本或 Chunk 列表
- 处理：C++ 批量推理 + 高效内存管理
- 输出：可写入 Qdrant 的向量

2. Rerank Service：
- 使用 ONNX Runtime 加载 Cross-Encoder 模型（如 bge-reranker-base）
- 输入：(Query, Document List)
- 输出：相关性排序后的 Top-K 文档


当前任务：
你是一名资深 C++ 工程师，需要为现有网关项目补充一个 C++ 版本的 Embedding Service。

项目信息：
- 主项目路径：../gateway
- embedding 服务参考实现：../gateway/embedding（Go版本）
- proto 文件：embedding.proto
- 当前工作目录：.


你的目标：
完成一个“可运行的 C++ embedding gRPC 服务”，并保证可被现有 Go Gateway 调用。


具体要求：

【1】项目结构设计
- 设计清晰的 C++ 项目目录结构（src/, include/, proto/, cmake/ 等）
- 使用 CMake 构建
- 支持后续扩展（embedding / rerank 共用架构）

【2】依赖管理
- 使用 vcpkg 或 Conan（优先 vcpkg）
- 需要包含：
  - gRPC
  - protobuf
  - （预留 ONNX Runtime 接入）

【3】gRPC 服务实现
- 基于 embedding.proto 自动生成代码
- 实现服务端：
  - 接收文本或 chunk 列表
  - 返回 embedding 向量（先 mock）

【4】工程可运行
- 提供：
  - CMakeLists.txt（完整可编译）
  - main.cpp（服务启动）
  - service 实现代码
- 可以通过命令启动：
  ./embedding_server

【5】与 Go 版本对齐
- 接口字段必须完全兼容 embedding.proto
- 请求/响应结构一致

【6】输出要求（非常重要）
请按以下顺序输出：
1. 项目目录结构（tree）
2. CMakeLists.txt
3. proto 编译配置
4. 核心代码（main + service）
5. 构建与运行命令

【7】约束
- 使用现代 C++（C++17）
- 代码结构清晰，避免 demo 风格
- 不要省略关键代码
- 不要只给伪代码


目标结果：
得到一个“可以直接编译运行 + 可接入网关”的 C++ embedding 服务骨架。


4.5
Embedding 模型接入与 tokenizer 流程实现（ONNX Runtime）
阶段一：ONNX Runtime 环境搭建（任务5前置）
- 通过 vcpkg / 系统包安装 onnxruntime，确认头文件与库路径。
- 约定环境变量（如 ONNXRUNTIME_INCLUDE_DIR / ONNXRUNTIME_LIB_DIR）。

阶段二：CMake 配置更新
- 增加 EMBEDDING_WITH_ONNXRUNTIME 选项（默认 OFF，保持 mock 行为）。
- 在开启时引入 onnxruntime 头文件与链接库，关闭时完全不依赖 onnxruntime。

阶段三：实现模型管理类
- 设计 IEmbeddingBackend 接口，抽象 Init / Encode 接口。
- 提供 MockEmbeddingBackend（沿用现有 hash 向量逻辑）。
- 预留 OnnxEmbeddingBackend（封装 onnxruntime Session 与模型加载）。

阶段四：实现 tokenizer 与批处理接口
- 定义 Tokenizer 抽象类，先实现简单分词（空格 + 基本归一化）。
- 设计批处理 EncodeBatch 接口，内部支持一次推理多条文本。

阶段五：实现核心推理逻辑
- 在 OnnxEmbeddingBackend 中：
  - 从环境变量读取模型路径（如 LOCAL_EMBED_MODEL_PATH）。
  - 将 tokenizer 输出转换为 onnxruntime 输入张量。
  - 从模型输出中提取 embedding（CLS 向量或平均池化）。
- 失败时通过 error 字段返回错误信息，并保留 Info 接口可用。

阶段六：模型加载与集成测试
- 在服务启动时加载模型并打印关键配置（provider / model / dimensions）。
- 使用 check_embedding_service.sh 与 grpcurl 做端到端验证。
- 选择轻量化模型，如 bge-embedder-base，确保推理效率和内存占用在可控范围内。

## 实现状态

✅ **任务 4.5 已完成** (2026-04-05)

所有六个阶段已完整实现并测试通过（20/20 测试通过）。

详细更新日志请查看: [CHANGELOG.md](CHANGELOG.md)

### 快速验证
```bash
# 运行全面测试
bash test_all_features.sh

# 或快速测试
bash check_embedding_service.sh
```

### Issue #15 验收说明(2026-04-08)
- ✅ gRPC 接口已支持批量请求：新增 `GetEmbeddings(EmbeddingBatchRequest) -> EmbeddingBatchResponse`
- ✅ 批处理逻辑已实现：`IEmbeddingBackend` 新增 `EncodeBatch`，Mock/ONNX 后端均已接入
- ✅ 内存复用优化：批量编码路径中使用 `reserve` 和复用中间容器，减少重复分配


### 文档
- [USE_GUIDE.md](USE_GUIDE.md) - 完整使用指南（已更新 v4.5.0）
- [ONNX_SETUP.md](ONNX_SETUP.md) - ONNX Runtime 安装配置
- [CHANGELOG.md](CHANGELOG.md) - 详细变更日志
