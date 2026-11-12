import asyncio
import logging
from typing import Literal

from deal_pilot.event.message.card_schema import CONTENT_ID, create_card_json
from deal_pilot.feishu.api import Card

logger = logging.getLogger(__name__)

# 演示用的切片大小与间隔；接入模型后应改为消费真实的 token 流。
CHUNK_SIZE = 20
CHUNK_INTERVAL = 0.05

ReceiveIdType = Literal["open_id", "union_id", "user_id", "email", "chat_id"]


async def reply(
    receive_id: str,
    receive_text: str,
    *,
    receive_id_type: ReceiveIdType = "open_id",
) -> None:
    """创建流式卡片并投递，按切片提交累计全文，最后结束流式。"""
    card = await Card.create(
        create_card_json(),
        receive_id=receive_id,
        receive_id_type=receive_id_type,
    )
    streamed = ""
    try:
        for index in range(0, len(receive_text), CHUNK_SIZE):
            streamed += receive_text[index:index + CHUNK_SIZE]
            await card.stream_text(CONTENT_ID, streamed)
            await asyncio.sleep(CHUNK_INTERVAL)
    except BaseException:
        # 尽量关闭流式模式，保留原始异常。
        try:
            await card.finish()
        except Exception as error:
            logger.warning("关闭卡片流式模式失败：%s", type(error).__name__)
        raise
    await card.finish()
