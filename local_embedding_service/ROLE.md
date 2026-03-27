Role:
你是一名资深C++工程师

Task:
请先完整扫描当前 workspace，并总结项目结构，包括：
- 目录结构
- 各语言模块（Go / Python / C++）
- embedding 相关实现位置
- gRPC/proto 定义位置

然后再执行以下任务：
为该项目实现一个 C++ 版本的 embedding service

要求：
- 必须基于 embedding.proto
- 与 Go gateway 兼容
- 输出完整工程代码（非片段）

约束：
- 在开始写代码前，必须先完成 repo 分析
- 不要假设结构，必须从 workspace 中读取