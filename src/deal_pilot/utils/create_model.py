# 统一使用 openai 兼容模式，暂不使用 anthropic api
from collections.abc import Mapping
from typing import Any

from langchain.chat_models import init_chat_model

from deal_pilot.config.nacos.nacos_schemas import AgentModelConfig
from deal_pilot.config.openai_settings import openai_settings
from deal_pilot.utils.shared import get_thread_id


def _resolve_thinking(thinking: bool | str | dict[str, Any]) -> bool:
    """把 thinking 配置归一化为布尔值。

    约定只传 true/false；同时兼容 Langfuse prompt 里常见的
    ``{"type": "enabled" | "disabled"}`` 写法。其余取值直接报错，
    避免脏配置被静默当成「开启」。
    """
    if isinstance(thinking, bool):
        return thinking
    if isinstance(thinking, Mapping):
        thinking = thinking.get("type", "")
    if isinstance(thinking, str):
        normalized = thinking.strip().lower()
        if normalized in {"enabled", "true", "on"}:
            return True
        if normalized in {"disabled", "false", "off"}:
            return False
    raise ValueError(
        "thinking 仅支持 true/false 或 {'type': 'enabled'|'disabled'}，"
        f"实际收到：{thinking!r}"
    )


def create_model(model_config: AgentModelConfig | None = None):
    if model_config is None:
        model_config = AgentModelConfig()

    config = {
        "model": model_config.name,
        "model_provider": "openai_reasoning",
        # qwen 等 OpenAI 兼容网关只接受布尔值 enable_thinking，
        # 传 {"thinking": {...}} 会被判定为不支持参数而 400
        "extra_body": {"enable_thinking": _resolve_thinking(model_config.thinking)},
    }
    if model_config.temperature is not None:
        config["temperature"] = model_config.temperature
    if model_config.top_p is not None:
        config["top_p"] = model_config.top_p

    thread_id = get_thread_id()
    if thread_id:
        config["default_headers"] = {"x-litellm-session-id": thread_id}
    model = init_chat_model(**config)
    return model
