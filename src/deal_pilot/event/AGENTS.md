# 业务事件处理

## 职责与入口

- 本目录负责业务事件回调与注册，底层飞书连接、IPC 和并发分发由 `../feishu/event` 提供。
- `listener.py:HANDLERS` 当前仅注册 `im.message.receive_v1` → `message/message_handler.py:message_handler`；没有注册卡片交互回调 `card.action.trigger`。
- `start_feishu_events()` 由 FastAPI lifespan 在 Server 事件循环内 await：`FEISHU_EVENTS_ENABLED=false`（`FeishuSettings.events_enabled`）时直接跳过；否则先注册回调以捕获该循环，再通过 `asyncio.to_thread` 调用单例的 `start_listener()`，不等待远程连接就绪。
- 事件监听是可选能力：注册或启动抛异常时只记录 ERROR 日志，不阻断 FastAPI 启动，本次运行不处理飞书事件。
- `cancel_feishu_events()` 同步关闭整个单例监听器；异步调用方通过 `asyncio.to_thread` 隔离关闭等待。关闭后不能重新启动，不等待或取消已提交的业务回调。
- `__init__.py` 为空；导入本目录不启动监听，实际入口见 `../app/main.py`。

## 当前消息行为与限制

- `message_handler(event: FeishuEvent)` 只处理 `sender.sender_type == "user"` 且 `message.message_type == "text"` 的事件；其他发送者与消息类型静默跳过（不记录日志，避免图片/文件消息刷屏）。
- 按 `message_id` 做进程内幂等：保留最近 2000 条 ID，重复投递直接跳过；跨进程/多副本不共享，重复消费仍可能发生。飞书官方要求用 `message_id` 而不是 `event_id` 去重。
- 解析 `message.content` 的 JSON 并提取 `text`；缺 `message_id`、缺 `chat_id`、内容非 JSON 或文本为空白时记录 WARNING 并跳过，不再抛异常。
- 回复目标是原消息的 `chat_id`，调用 `message/reply.py:reply(chat_id, text, receive_id_type="chat_id")`：创建流式卡片并投递到同一会话，按切片提交累计全文后 `finish()`；不是文本回显，也不是飞书 reply 话题回复。群聊文本中的 `@_user_N` 占位符在回复前去除，去除后为空则跳过。
- 发送失败的异常在回调内捕获并记录 ERROR 日志，同时移除该 `message_id` 的幂等标记，允许飞书重投时重试；底层分发器不持有 Future 或读取业务结果，不能把回调失败视为已重试或监听器故障。
- 未接入 Agent、RAG、索引、会话管理或飞书用户到认证用户的映射。收到 open_id 不代表取得项目用户身份，不能据此选择用户沙箱或对象前缀。

## 设计与修改约束

- 目标：将飞书消息接入服务生命周期并验证业务回调调用路径。选定方案：集中注册表加 `message` 子目录中的流式卡片回复，复用已有监听器与 `Card`。原因：业务处理与 SDK 连接分离，不增加依赖。实现状态：源码已接入，回调过滤/幂等与卡片流式有单元测试；真实订阅、渲染与权限仍未验证。
- 新事件在 HANDLERS 中显式注册；飞书远程订阅和权限需另行配置，本地注册不自动配置远程应用。
- 保持业务处理在本目录；同步 SDK 调用的线程隔离由 API 层负责，不在 Server 循环中直接调用阻塞 SDK。
- 本目录事件回调不经过 LangGraph HTTP 认证；后续接入 Agent 或用户资源时必须明确身份与权限边界。

## 验证

- `tests/units/test_feishu_message_handler.py` 覆盖发送者/消息类型过滤、`message_id` 幂等、`chat_id` 目标、缺失字段与非 JSON 内容跳过、发送失败只记录不抛出；`tests/units/test_feishu_card.py` 覆盖卡片序号、投递失败关闭流式与 `reply` 的累计全文/异常收尾。全部 Mock，不连接飞书。
- 监听器启停、IPC、Server 生命周期与真实订阅仍需真实环境验证；本地测试不能当作真实收发验证。
- 本轮未运行真实订阅、消息收发与 Server 关闭行为验证。
