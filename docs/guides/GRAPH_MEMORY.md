# 在本 fork 中运行专用记忆抽取服务

本分支为 [Octo Memory Graph](https://github.com/Ranwanglc/octo-memory-graph) 提供无状态的记忆抽取 Agent。它复用 iGraph 的 `model_factory.create_model` 和 Agno 结构化输出，将一条渠道消息转成带逐字证据的候选事实。后台对候选做校验后写入独立 Neo4j 图。

这个服务不创建普通聊天会话，不启用 Agno 用户自动学习，不持有 Neo4j 凭证，也不向模型开放通用图工具。普通 iGraph Agent 的配置仍要求 Graph Engine MCP 地址；独立记忆服务显式选择无 Graph Engine 的配置路径。

## 启动

推荐把本 fork 的 `feat/memory-extraction` 和 `octo-memory-graph` 放在相邻目录，在后者按 README 启动整个 Compose。它会构建这里的 `deploy/docker/memory-service.Dockerfile`，无需下载图学习模型或启动普通 iGraph 栈。

单独运行时：

```bash
uv venv --python 3.12
uv pip install --python .venv/bin/python -r deploy/requirements/memory-service.txt
export IGRAPH_MEMORY_SERVICE_KEY='<独立的至少 24 字符服务密钥>'
export IGRAPH_MEMORY_MODEL='<模型 ID>'
export LLM_API_KEY='<模型服务密钥>'
export LLM_BASE_URL='https://your-model-provider/v1'
.venv/bin/python -m agent_runtime.memory_service
```

也可以设置环境变量后运行 `docker compose -f compose.memory.yaml up -d --build`。默认仅暴露本机 `21113`。完整后台的 Compose 与这个独立 Compose 二选一，避免端口冲突。

## 接口与行为

- `GET /internal/memory/health`：进程存活与协议版本；不表示模型配置正确或供应商可用。
- `POST /internal/memory/extract`：要求 `X-iGraph-Memory-Key`；请求为 `event`、同作用域 `context`、`existing_facts`，响应为 `MemoryPatch`。
- DTO 位于 `agent_runtime/memory_contract.py`，与后台协议有独立的一致性检查，两个仓库修改协议时一起更新。
- 只有人类入站消息触发模型；Bot、未知作者和送达事件返回空事实。
- 第一人称使用 `$speaker`。`cardinality=single` 表示同主体关系的新值替代旧值，`multiple` 允许共存；时间和最终身份由后台决定。
- 引用必须是当前消息中的逐字片段，`supersedes` 只能引用给定候选事实；无效输出报错。模型请求有并发与时间上限。没有有效模型配置时直接报错，不生成替代事实。
- 此独立进程抑制 Agno 原始供应商错误日志，只返回固定错误类别。不要开启会打印请求正文的网关调试日志。

## 验证

```bash
uv pip install --python .venv/bin/python pytest
.venv/bin/python -m pytest -q tests/test_memory_extraction_service.py
```

后台的 `scripts/smoke_stack.py` 会启动本模块，使用真实 Agno 模型适配器连接一个明确标注的本地模拟供应商，再通过插件 MCP 客户端和真实 Neo4j 验证整条链路。测试替身不能证明真实模型能正确提取偏好、承诺或关系；模型效果需要另行用真实凭证与人工标注对话评估。
