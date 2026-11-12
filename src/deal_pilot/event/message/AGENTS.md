# 飞书消息业务

## 文件职责与调用链

- 上层 `../listener.py` 注册 `im.message.receive_v1` → `message_handler.py:message_handler`；本目录不启动监听或配置远程订阅。
- `message_handler.py` 只处理 `sender_type == "user"` 且 `message_type == "text"` 的事件；按 `message_id` 做进程内幂等（最近 2000 条，发送失败释放标记），剥离群聊 `@_user_N` 占位符后调用 `reply(chat_id, text, receive_id_type="chat_id")`。
- `card_schema.py` 定义 `CONTENT_ID = "answer"` 与 `create_card_json()`：JSON 2.0、fill 宽度、单个 Markdown 组件，初始内容为“正在思考...”。组件 ID 必须与更新目标一致。
- `reply.py:reply(receive_id, receive_text, *, receive_id_type="open_id")` 创建流式卡片并投递，按 `CHUNK_SIZE` 切片提交累计全文（`CHUNK_INTERVAL` 仅控制演示节奏），最后 `finish()`；中途异常或取消会尽力关闭流式再抛出原异常。
- `__init__.py` 为空；没有导入时执行逻辑。旧入口 `event/message_handler.py` 已移除。

## 当前边界与修改约束

- 回复目标是原消息 `chat_id`，单聊与群聊都回到同一会话；使用发送新消息而非飞书 reply 接口，不形成话题回复。消息 ID 只用于幂等，不用于更新已发卡片。
- 当前不是 Agent 回答，只是把用户文本分段流式回显；接入模型时替换 `reply` 的文本来源（消费真实 token 流），保留 `finish()` 收尾与异常处理。
- 未接入 Agent、RAG、索引、会话管理或飞书用户到认证用户的映射；`open_id` 不能当作项目用户身份。
- 业务异常在 handler 内记录 ERROR，底层分发器不持有 Future，不能把失败视为已重试或监听器故障。
- 卡片结构、权限与流式状态由飞书服务端校验；本目录不复制官方组件 Schema。

## 验证

- `tests/units/test_feishu_message_handler.py` 覆盖过滤、幂等、`chat_id` 目标、缺字段、非 JSON 内容与失败释放标记；`tests/units/test_feishu_card.py` 覆盖序号递增、投递失败关闭流式、`reply` 累计全文与异常收尾。
- 真实订阅、卡片渲染与流式效果未验证；本地 Mock 不能当作真实投递验证。
