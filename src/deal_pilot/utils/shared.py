from langgraph.config import get_config


def get_thread_id() -> str | None:
    """取当前会话的 thread_id，不在 graph 运行时上下文内返回 None。"""
    try:
        config = get_config()
    except RuntimeError:  # 例如脚本、评测等场景没有 runnable 上下文
        return None
    return config.get("configurable", {}).get("thread_id", None)


def get_user_id() -> str:
    config = get_config()
    user_id = config.get("configurable", {}).get("langgraph_auth_user_id", None)
    if not user_id:
        raise RuntimeError("无法通过langgraph_auth_user_id获取当前认证用户的ID")
    return user_id
