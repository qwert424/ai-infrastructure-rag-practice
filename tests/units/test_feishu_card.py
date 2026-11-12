"""飞书卡片实体的序号、流式收尾与回复流。"""
import asyncio
from unittest.mock import AsyncMock

import pytest

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
