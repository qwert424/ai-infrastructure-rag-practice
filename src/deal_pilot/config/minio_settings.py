from deal_pilot.config.base_settings import BaseSettingsWithEnv

# 容器内不可用的回环地址，注入沙箱时需替换为宿主机别名。
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}
_HOST_ALIAS = "host.docker.internal"


class MinioSettings(BaseSettingsWithEnv):
    # 专用服务账号的访问密钥（不使用 root 凭证）。
    access_key: str = ""
    # 专用服务账号的秘密密钥。
    secret_key: str = ""
    # MinIO API 地址，不包含协议前缀。
    endpoint: str = "localhost:9002"
    # 沙箱容器内访问 MinIO 的地址；留空时把 endpoint 的回环地址替换为 host.docker.internal。
    sandbox_endpoint: str = ""
    # 是否使用 HTTPS 连接。
    secure: bool = False
    # 默认存储桶，服务账号的权限仅限该桶。
    bucket: str = "deal-pilot"
    # 集成测试专用凭证（需要建桶/删桶权限）；留空时回退到上面的应用凭证。
    test_access_key: str = ""
    test_secret_key: str = ""

    model_config = {"env_prefix": "MINIO_"}

    @property
    def endpoint_in_sandbox(self) -> str:
        """实际注入沙箱的地址，由 sandbox_endpoint / endpoint 推导。"""
        host, sep, port = (self.sandbox_endpoint or self.endpoint).partition(":")
        if host in _LOOPBACK_HOSTS:
            host = _HOST_ALIAS
        return f"{host}{sep}{port}"


minio_settings = MinioSettings()
