"""飞书卡片实体的序号、流式收尾与回复流。"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import deal_pilot.event.message.reply as reply_module
import deal_pilot.feishu.api.card as card_module
from deal_pilot.feishu.api import Card


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    fake = AsyncMock()
    fake.create = AsyncMock(return_value="card_1")
    fake.send_card = AsyncMock(return_value="om_1")
    monkeypatch.setattr(card_module, "CardAPI", lambda: fake)
    return fake


def test_stream_and_finish_use_incrementing_sequence(api: AsyncMock) -> None:
    async def run() -> Card:
        card = await Card.create(
            {"schema": "2.0"}, receive_id="oc_1", receive_id_type="chat_id"
        )
        await card.stream_text("answer", "你")
        await card.stream_text("answer", "你好")
        await card.finish()
        return card

    card = asyncio.run(run())

    assert [call.kwargs["sequence"] for call in api.stream_text.await_args_list] == [1, 2]
    assert api.set_streaming.await_args.args == ("card_1", False)
    assert api.set_streaming.await_args.kwargs["sequence"] == 3
    assert api.send_card.await_args.kwargs["receive_id_type"] == "chat_id"
    assert card.message_id == "om_1"
    assert card.sequence == 3


def test_message_send_failure_closes_streaming(api: AsyncMock) -> None:
    api.send_card.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(Card.create({"schema": "2.0"}, receive_id="oc_1"))

    assert api.set_streaming.await_args.args == ("card_1", False)


def test_reply_streams_cumulative_text(monkeypatch: pytest.MonkeyPatch) -> None:
    streamed: list[str] = []
    card = Mock()
    card.stream_text = AsyncMock(side_effect=lambda _, text: streamed.append(text))
    card.finish = AsyncMock()

    async def fake_create(card_json, *, receive_id=None, receive_id_type="open_id", uuid=None):
        assert receive_id == "oc_1"
        assert receive_id_type == "chat_id"
        return card

    monkeypatch.setattr(reply_module, "Card", SimpleNamespace(create=fake_create))
    monkeypatch.setattr(reply_module, "CHUNK_SIZE", 2)
    monkeypatch.setattr(reply_module, "CHUNK_INTERVAL", 0)

    asyncio.run(reply_module.reply("oc_1", "abcdef", receive_id_type="chat_id"))

    assert streamed == ["ab", "abcd", "abcdef"]
    card.finish.assert_awaited_once()


def test_reply_finishes_when_stream_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Mock()
    card.stream_text = AsyncMock(side_effect=RuntimeError("boom"))
    card.finish = AsyncMock()

    async def fake_create(card_json, *, receive_id=None, receive_id_type="open_id", uuid=None):
        return card

    monkeypatch.setattr(reply_module, "Card", SimpleNamespace(create=fake_create))
    monkeypatch.setattr(reply_module, "CHUNK_SIZE", 2)
    monkeypatch.setattr(reply_module, "CHUNK_INTERVAL", 0)

    with pytest.raises(RuntimeError):
        asyncio.run(reply_module.reply("oc_1", "abc"))

    card.finish.assert_awaited_once()
