"""飞书消息回调的过滤、幂等与回复目标。"""
import asyncio
import json
from collections import OrderedDict
from unittest.mock import AsyncMock

import pytest

import deal_pilot.event.message_handler as handler_module
from deal_pilot.event.message_handler import message_handler
from deal_pilot.feishu.event.models import FeishuEvent


@pytest.fixture(autouse=True)
def _clear_seen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handler_module, "_seen_ids", OrderedDict())


@pytest.fixture
def send_text(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    api = AsyncMock()
    monkeypatch.setattr(handler_module, "MessageAPI", lambda: api)
    return api.send_text


def _text_message(**overrides: object) -> dict:
    message = {
        "message_id": "om_1",
        "chat_id": "oc_1",
        "message_type": "text",
        "content": json.dumps({"text": "你好"}, ensure_ascii=False),
    }
    message.update(overrides)
    return message


def _event(message: dict | None = None, sender: dict | None = None) -> FeishuEvent:
    return FeishuEvent(
        event_type="im.message.receive_v1",
        event_id="evt-1",
        payload={
            "event": {
                "message": _text_message() if message is None else message,
                "sender": {"sender_type": "user"} if sender is None else sender,
            }
        },
    )


def test_replies_to_same_chat(send_text: AsyncMock) -> None:
    asyncio.run(message_handler(_event()))

    send_text.assert_awaited_once_with("oc_1", "你好", receive_id_type="chat_id")


def test_duplicate_message_id_replies_once(send_text: AsyncMock) -> None:
    event = _event()

    asyncio.run(message_handler(event))
    asyncio.run(message_handler(event))

    assert send_text.await_count == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"message_type": "image"},
        {"content": json.dumps({"image_key": "img_1"})},
        {"content": "not json"},
        {"content": json.dumps({"text": "   "})},
        {"chat_id": ""},
    ],
)
def test_unusable_message_is_skipped(send_text: AsyncMock, overrides: dict) -> None:
    asyncio.run(message_handler(_event(message=_text_message(**overrides))))

    send_text.assert_not_awaited()


def test_bot_sender_is_ignored(send_text: AsyncMock) -> None:
    asyncio.run(message_handler(_event(sender={"sender_type": "bot"})))

    send_text.assert_not_awaited()


def test_group_mention_placeholder_is_stripped(send_text: AsyncMock) -> None:
    message = _text_message(content=json.dumps({"text": "@_user_1 你好"}))

    asyncio.run(message_handler(_event(message=message)))

    send_text.assert_awaited_once_with("oc_1", "你好", receive_id_type="chat_id")


def test_missing_event_body_is_skipped(send_text: AsyncMock) -> None:
    event = FeishuEvent(event_type="im.message.receive_v1", event_id=None, payload={})

    asyncio.run(message_handler(event))

    send_text.assert_not_awaited()


def test_send_failure_is_logged_not_raised(send_text: AsyncMock) -> None:
    send_text.side_effect = RuntimeError("boom")

    asyncio.run(message_handler(_event()))

    assert send_text.await_count == 1
    assert "om_1" not in handler_module._seen_ids
