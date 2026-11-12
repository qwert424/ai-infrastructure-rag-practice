import json
import logging
import re
from collections import OrderedDict

from deal_pilot.event.message.reply import reply
from deal_pilot.feishu.event.models import FeishuEvent

logger = logging.getLogger(__name__)

# 飞书可能重复推送同一事件，按 message_id 做进程内幂等；跨进程不共享。
_SEEN_LIMIT = 2000
_seen_ids: OrderedDict[str, None] = OrderedDict()
# 群聊文本中的提及占位符，回显给用户没有意义。
_MENTION = re.compile(r"@_user_\d+\s*")


def _is_duplicate(message_id: str) -> bool:
    if message_id in _seen_ids:
        return True
    _seen_ids[message_id] = None
    if len(_seen_ids) > _SEEN_LIMIT:
        _seen_ids.popitem(last=False)
    return False


def _nested(payload: dict, *path: str) -> object:
    value: object = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


async def message_handler(event: FeishuEvent) -> None:
    message = _nested(event.payload, "event", "message")
    sender = _nested(event.payload, "event", "sender")
    if not isinstance(message, dict) or not isinstance(sender, dict):
        logger.warning("飞书消息事件缺少 event.message 或 event.sender")
        return
    if sender.get("sender_type") != "user" or message.get("message_type") != "text":
        return

    message_id = message.get("message_id")
    chat_id = message.get("chat_id")
    content = message.get("content")
    sender_id = sender.get("sender_id")
    open_id = sender_id.get("open_id") if isinstance(sender_id, dict) else None
    if not isinstance(message_id, str) or not message_id:
        logger.warning("飞书消息事件缺少 message_id")
        return
    if _is_duplicate(message_id):
        return
    if not isinstance(chat_id, str) or not chat_id or not isinstance(content, str):
        logger.warning("飞书消息事件缺少 chat_id 或 content：%s", message_id)
        return
    if not isinstance(open_id, str) or not open_id:
        logger.warning("飞书消息事件缺少 sender open_id：%s", message_id)
        return

    try:
        text = json.loads(content).get("text")
    except json.JSONDecodeError:
        logger.warning("飞书消息内容不是 JSON：%s", message_id)
        return
    if not isinstance(text, str):
        return
    text = _MENTION.sub("", text).strip()
    if not text:
        return

    try:
        await reply(
            chat_id,
            text,
            user_id=open_id,
            receive_id_type="chat_id",
        )
    except Exception:
        logger.exception("回复飞书消息失败：%s", message_id)
        # 发送失败不占用幂等标记，飞书重投时仍可尝试。
        _seen_ids.pop(message_id, None)
