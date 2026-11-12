from deal_pilot.config.base_settings import BaseSettingsWithEnv


class FeishuSettings(BaseSettingsWithEnv):
    app_id: str = ""
    app_secret: str = ""
    # 是否在应用启动时建立 IM 事件长连接；关闭后不接收消息，其余 API 不受影响。
    events_enabled: bool = True

    model_config = {"env_prefix": "FEISHU_"}


feishu_settings = FeishuSettings()
