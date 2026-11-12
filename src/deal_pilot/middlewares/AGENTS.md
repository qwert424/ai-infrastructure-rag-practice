# Agent 中间件

## 职责与入口

- `turn_summary.py` 提供 `@after_agent` 中间件，由 `MainAgentFactory.get_middlewares()` 挂载，生成状态字段 `turn_summary`。
- `retrieve_context.py` 提供 `@before_agent` 中间件，由 `RetrieveAgentFactory.get_middlewares()`（`agents/retrieve_agent.py`）挂载，不新增状态字段，只向 `messages` 注入一条检索结果消息。

## 当前状态契约

- 从 `state['messages']` 筛选，返回 `{'turn_summary': [{'role': msg.type, 'content': msg.content}, ...]}`；字段定义见 `agents/main_agent_state.py`。
- 当前每次根据所收到的全部 messages 重新生成列表，不是把新消息追加到旧 summary，也不是 LLM 摘要。
- HumanMessage 可见；字符串内容的 AIMessage 可见；列表内容的 AIMessage 在没有 `type=tool_use` 块时可见。
- ToolMessage 只有内容字符串以 `Returning structured response:` 开头时保留。不能把当前过滤描述为覆盖所有工具调用表示形式。
- 保留原始 content 的字符串或块列表，不擅自转换为纯文本或丢失结构；role 当前是消息类型名，不是重新映射的 HTTP 角色名。

## 检索中间件契约

- 触发阶段固定为 `before_agent`，每轮开始前执行一次；消息列表为空、最后一条不是 HumanMessage、最后一条就是本中间件注入的消息，或用户文本为空时抛 `ValueError`，不静默跳过。
- 直接以最后一条用户消息的文本调用 `rag/retriever/feishu_doc.search()`，`config` 取自 Nacos `rag_config.retriever`（未发布时回退 `RetrieverConfig()` 默认值），不传 `filter`、`threshold`。
- Nacos 内容存在但无法通过 `RagConfig` 校验时，`get_config` 直接抛 `ValidationError`，不会静默回退默认值；排查配置不生效时先确认 dataId=`rag_config`、group=`deal_pilot`。
- 返回 `{'messages': [HumanMessage(...)]}`：内容为 `doc`（`Document.model_dump(mode='json')`）与 `score` 组成的 JSON 数组，`name` 固定为 `retrieval_results`；该消息追加在用户查询之后，用于与普通用户消息区分。
- 检索异常直接向上传播，不转换为空结果；检索结果内容仅供模型参考，不截断。

## 修改与验证

- 新中间件明确触发阶段、读取字段和返回更新，在 Agent 工厂中注册；增加状态字段同步对应 state schema。
- 修改筛选时用 Human、AI 字符串、AI 内容块、工具调用和 ToolMessage 样例验证，并检查重复执行不会意外叠加旧结果。
- 当前没有专门的中间件测试。消息样例验证不等于完整 Agent 运行验证；若影响最终输出或评测，继续检查实际 Agent 和消费者。
