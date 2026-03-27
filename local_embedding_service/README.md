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