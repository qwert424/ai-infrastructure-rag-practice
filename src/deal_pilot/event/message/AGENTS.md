# 飞书消息业务

## 文件职责与调用链

- 上层 `../listener.py` 注册 `im.message.receive_v1` → `message_handler.py:message_handler`；本目录不启动监听或配置远程订阅。
- `message_handler.py` 只处理 `sender_type == "user"` 且 `message_type == "text"` 的事件；按 `message_id` 做进程内幂等（最近 2000 条，失败释放标记），剥离群聊 `@_user_N` 占位符后调用 `reply(chat_id, text, user_id=发送者 open_id, receive_id_type="chat_id")`。缺少 open_id、chat_id 或 content 时记录 WARNING 跳过。
- `card_schema.py` 定义 `STATUS_ID="status"`、`CONTENT_ID="answer"` 与 `create_card_json(content="")`：JSON 2.0、fill 宽度、状态行 + 分隔线 + 正文 Markdown；组件 ID 必须与更新目标一致。
- `reply.py:reply(receive_id, receive_text, *, user_id=None, receive_id_type="open_id")` 创建卡片后启动 `utils/run_agent("main_agent", ...)` 流：后台任务持续读取最新快照，主循环每 `CARD_UPDATE_INTERVAL`（0.2 秒）提交一次状态/正文差异，结束后再刷新一次并 `finish()`；异常、取消或卡片请求失败都会关闭读取任务和流并尽力 `finish()`，原始异常继续抛出。`user_id` 默认等于 `receive_id`，仅单聊可直接省略。
- `status.py:CardStatus` 把 `AgentStatus` 与载荷（`tool_name`/`reason`）转成展示文案，缺字段时回退通用文案；未知状态抛 ValueError。

## 当前边界与修改约束

- 认证身份来自飞书事件发送者 open_id，经 `security/agent_token.py` 签发短期令牌调用 Agent Server；消息正文不能作为身份，也不能用于选择其他用户的沙箱或对象前缀。
- 卡片使用发送新消息，不是飞书 reply 接口；消息 ID 只用于幂等，不用于更新已发卡片。
- 卡片刷新只保留最新快照，不排队历史版本；飞书请求慢时读取任务不阻塞，但结束时必须等最后一次提交完成再 `finish()`。
- 子 Agent 正文超过 200 字符会在 `utils/run_agent` 截断展示，主 Agent 正文完整；展示内容只包含正文，不含 reasoning 与工具参数。
- 业务异常在 handler 内记录 ERROR，底层分发器不持有 Future，不能把失败视为已重试或监听器故障。
- 未接入会话持久化、卡片交互回调（`card.action.trigger`）或飞书用户到项目用户中心的映射；`open_id` 直接作为 Agent 身份。

## 验证

- `tests/units/test_message_reply.py` 覆盖快照合并、状态与正文更新、失败保留部分内容、慢卡片不阻塞 Agent、取消与异常收尾、创建失败不启动 Agent、`chat_id` 投递与发送者身份分离。
- `tests/units/test_run_agent.py` 覆盖流协议解析与状态映射；`tests/units/test_feishu_message_handler.py` 覆盖过滤、幂等与参数传递。
- 真实订阅、卡片渲染、Agent Server 联调与流式效果未验证。
