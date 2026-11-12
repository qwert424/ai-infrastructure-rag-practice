# 飞书卡片封装

基于 lark-oapi 的 CardKit V1（API 版本）与 IM 消息接口，卡片内容使用飞书 JSON 2.0。封装覆盖实体创建、流式文本、配置、全量/批量/组件级更新，以及卡片消息发送、回复、按消息 ID 更新、撤回、延时更新与临时卡片；不重复实现官方组件 Schema 或可视化搭建器。仅本地 Mock 与类型检查验证，真实权限、渲染与流式效果须在租户验证。

## 快速开始

```python
from deal_pilot.feishu.api import Card

card = await Card.create({
    "schema": "2.0",
    "body": {"elements": [
        {"tag": "markdown", "element_id": "answer", "content": "正在思考..."}
    ]},
}, receive_id="ou_xxx")          # 传 receive_id 同时投递；群聊用 receive_id_type="chat_id"

await card.stream_text("answer", "第一段")        # 传累计全文
await card.stream_text("answer", "第一段 + 第二段")
await card.finish()                              # 关闭流式，保留已提交内容

print(card.card_id, card.message_id, card.sequence)
```

`Card.create` / `Card.create_template` 会自动把 `config.streaming_mode` 和 `update_multi` 置为 True（不修改传入字典）；模板创建后会先用配置接口开启流式，因此返回时 `sequence` 为 1。发送本身不消耗更新序号。

## Card 对象

| 操作 | 接口 | 说明 |
| --- | --- | --- |
| 创建并投递 | `await Card.create(card_json, receive_id=...)` / `await Card.create_template(template_id, receive_id=..., variables=..., version=...)` | 返回 Card 对象 |
| 发送 / 回复 | `await card.send(receive_id, receive_id_type=..., uuid=None)` / `await card.reply(message_id, reply_in_thread=False)` | 用实体引用投递或回复 |
| 流式更新 | `await card.stream_text(element_id, text)` | text 是累计全文 |
| 结束流式 | `await card.finish()` | 不重写整卡；再次流式前先 `set_streaming(True)` |
| 配置 / 全量更新 | `await card.update_settings(settings)` / `await card.set_streaming(bool)` / `await card.update(card_json)` | 消耗序号 |
| 组件更新 | `add_elements` / `update_element` / `patch_element` / `delete_element` / `batch_update` | 消耗序号 |
| 接管已有卡片 | `Card(card_id, sequence=已用序号)` / `await Card.from_message(message_id, sequence=...)` | 接口不会查询远端序号 |

同一对象的更新共用严格递增的 `sequence` 与一把 `asyncio.Lock`，必须复用对象且在同一事件循环执行；分配过的序号不回退，取消排队不消耗序号，取消执行不保证远端已停止。创建与投递是两次请求，投递失败会尽力关闭流式并抛原异常。没有自动重试、限流、持久化或跨进程协调。

## CardAPI：无状态底层入口

`send_card(receive_id, card, receive_id_type=..., uuid=None)`、`reply_card(message_id, card, reply_in_thread=False, uuid=None)`、`update_card(message_id, card)`（按消息 ID 更新共享卡片，不使用 sequence）、`recall(message_id)`、`delayed_update_card(token, card, open_ids=None)`、`send_ephemeral_card(chat_id, open_id, card)`、`delete_ephemeral_card(message_id)`。后三个历史接口在 SDK 中没有生成式 Builder，通过官方 `Client.request` 调用，Token/HTTP 仍由 SDK 管理。

不要同时用 `CardAPI` 和 `Card` 对象更新同一卡片，否则对象内的序号会失去同步。CardKit 当前没有「读取完整卡片」或「删除卡片实体」接口，本封装不编造此类方法；移除会话中的卡片请用消息撤回或临时卡片删除。

## 事件与交互

卡片消息复用现有 `feishu/event` 长连接与分发。若要做按钮/表单等交互，需要在飞书后台另外订阅新版回调 `card.action.trigger`（不要选旧版卡片回调），并把处理器注册到 `feishu_event_listener`；本项目目前只注册 `im.message.receive_v1`。

## 权限与后台配置

应用需开启机器人能力，并具备：

- `cardkit:card:write`：创建、配置和更新卡片实体。
- `im:message:send_as_bot`（或 `im:message`）：发送、回复卡片消息。
- `im:message.p2p_msg:readonly`：接收单聊文本；群聊 @ 触发另需 `im:message.group_at_msg:readonly`。
- 更新/撤回等额外操作按接口申请，如 `im:message:update`、`im:message:recall`，以后台显示的可选权限和实际授权为准。

事件订阅选「长连接」并添加 `im.message.receive_v1`；改完权限与事件后需要发布新版本并对测试用户生效。

## 验证

```bash
uv run pytest -q tests/units/test_feishu_card.py tests/units/test_feishu_message_handler.py
```

## 官方参考

- [CardKit 资源概述](https://open.feishu.cn/document/cardkit-v1/feishu-card-resource-overview)
- [卡片 JSON 2.0](https://open.feishu.cn/document/feishu-cards/card-json-v2-structure)
- [回调概述及长连接接入](https://open.feishu.cn/document/event-subscription-guide/callback-subscription/callback-overview)
