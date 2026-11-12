import asyncio
import logging

from deal_pilot.config.feishu_settings import feishu_settings
from deal_pilot.event.message.message_handler import message_handler
from deal_pilot.feishu.event import feishu_event_listener

logger = logging.getLogger(__name__)

HANDLERS = {"im.message.receive_v1": message_handler}


async def start_feishu_events() -> None:
    """注册回调并启动监听；事件监听是可选能力，失败不阻断服务启动。"""
    if not feishu_settings.events_enabled:
        logger.info("FEISHU_EVENTS_ENABLED 为 false，未启动飞书事件监听")
        return
    try:
        # 在 Agent Server 的异步启动逻辑中调用，注册时记录 Server 的事件循环。
        for event_name, handler in HANDLERS.items():
            feishu_event_listener.register(event_name, handler)
        await asyncio.to_thread(feishu_event_listener.start_listener)
    except Exception:
        logger.exception("飞书事件监听启动失败，本次运行不会处理飞书事件")


def cancel_feishu_events() -> None:
    """释放整个监听器；异步调用方需在线程中执行。"""
    feishu_event_listener.close()
