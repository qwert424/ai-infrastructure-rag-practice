"""飞书事件监听的启停开关与启动失败降级。"""
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import deal_pilot.event.listener as listener_module
from deal_pilot.event.listener import start_feishu_events


def test_disabled_switch_skips_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        listener_module, "feishu_settings", SimpleNamespace(events_enabled=False)
    )
    listener = Mock()
    monkeypatch.setattr(listener_module, "feishu_event_listener", listener)

    asyncio.run(start_feishu_events())

    listener.register.assert_not_called()
    listener.start_listener.assert_not_called()


def test_start_failure_does_not_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        listener_module, "feishu_settings", SimpleNamespace(events_enabled=True)
    )
    listener = Mock()
    listener.start_listener.side_effect = RuntimeError("boom")
    monkeypatch.setattr(listener_module, "feishu_event_listener", listener)

    asyncio.run(start_feishu_events())

    listener.register.assert_called_once()
    listener.start_listener.assert_called_once()
