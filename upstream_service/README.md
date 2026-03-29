# upstream_service 开发说明

## 目录作用

`upstream_service` 是根仓库里的上游流式 mock 服务。

它的职责是：

- 提供 `/health` 健康检查接口
- 提供 `/v1/chat/completions` 接口
- 以 SSE 形式返回流式内容
- 给 `completion-service` 和整条联调链路提供稳定、可复现的上游响应

当前服务实现文件：

- `server.py`
- `Dockerfile`

## 在整条链路里的位置

请求链路大致如下：

`client -> gateway -> completion-service -> upstream-service`

根目录 `docker-compose.yml` 中：

- `upstream-service` 暴露端口 `18080`
- `completion-service` 依赖 `upstream-service`

所以你改动这个目录时，要考虑是否会影响整条 SSE 流式链路。

## 你负责什么

如果你负责 `upstream_service`，通常只需要关注以下内容：

- 上游接口行为是否符合约定
- 返回的 SSE 格式是否稳定
- 同样输入下输出是否可复现
- 是否会破坏端到端测试

一般不要顺手修改：

- 根目录 `docker-compose.yml` 里的服务依赖关系
- `gateway/` 子模块中的其他服务逻辑
- 与你任务无关的测试和配置

## 开发约束

开发时优先遵守这些约束：

- 不要修改接口路径：`/health`、`/v1/chat/completions`
- 不要随意改默认端口 `18080`
- 返回格式必须保持 SSE
- 每个事件块应使用 `data: ...` 格式，并以空行分隔
- 结束时必须返回 `data: [DONE]`
- 同样输入应产生稳定输出，不要依赖随机数
- 如果增加字段或改变响应结构，要先确认不会影响 `completion-service` 的解析逻辑

当前 `server.py` 的关键行为：

- 从请求体中提取最后一条 `user` 消息
- 拼接出稳定的 mock 文本
- 按固定大小切片后逐段输出
- 最后输出 usage 信息和 `[DONE]`

## 推荐开发流程

每次开始开发前：

```bash
make pull
```

首次拉取仓库或更新子模块后：

```bash
make init
```

本地启动整套环境：

```bash
make deploy
```

开发时建议顺序：

1. 阅读 `upstream_service/server.py`
2. 明确你要改的是接口行为、流式格式，还是 mock 返回内容
3. 修改后重新启动整套环境联调
4. 跑端到端测试确认没有破坏链路

## 开发完成后的自检

至少确认以下几点：

- 服务可以正常启动
- `GET /health` 返回 200
- `POST /v1/chat/completions` 可以持续返回 SSE 数据
- 返回流最后有 `data: [DONE]`
- 相同 prompt 多次请求结果一致

推荐执行：

```bash
make test-e2e
```

如果只是快速本地检查，也至少要验证你的流式接口没有 broken pipe、无效 JSON、缺失 `[DONE]` 这类基础问题。

## 提交代码前怎么做

提交前建议按这个顺序执行：

1. 先看本地改动

```bash
git status
```

2. 只暂存你负责的文件

```bash
git add upstream_service/server.py upstream_service/Dockerfile upstream_service/README.md
```

3. 再检查一次暂存内容

```bash
git diff --cached
```

4. 提交

```bash
git commit -m "feat: improve upstream service streaming behavior"
```

5. 推送到你的开发分支

```bash
git push origin <your-branch-name>
```

## 提交时的注意事项

- 不要把别人改的文件一起提交
- 不要提交临时调试文件
- 不要提交本地运行产生的数据目录
- 不要在未确认影响面的情况下改服务名、端口、接口路径
- 如果接口行为变了，最好同步补充或更新 `integration_tests`

## 常见提交信息示例

可以参考下面这些写法：

```bash
git commit -m "feat: add deterministic upstream stream chunks"
git commit -m "fix: keep upstream completion response SSE-compatible"
git commit -m "refactor: simplify upstream mock response generation"
```

## 最简日常命令清单

```bash
make pull
make deploy
make test-e2e
git status
git add upstream_service/server.py
git commit -m "feat: xxx"
git push origin <your-branch-name>
```
