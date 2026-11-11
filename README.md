# Deal Pilot

## 启动服务

**启动基础设施环境**

```shell
make docker-recreate
```

**启动Agent服务**

```shell
# 开发模式
make dev
# debug模式
make debug
```

## 服务说明

### 常用服务

- **Agent服务**

  API访问地址：http://localhost

  langsmith调试地址：https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:80

- **Langfuse 管理后台**

  访问地址： http://localhost:3000
  
- **LiteLLM**

  管理后台：http://localhost:4000/ui/
  
  账号/密码：`.env` 中的 `LITELLM_UI_USERNAME` / `LITELLM_UI_PASSWORD`
  
  API 地址：http://localhost:4000/v1

- **Nacos 管理后台**

  访问地址：http://localhost:8080/

  账号：nacos

  密码：初始界面自行设定

  API接口文档：https://nacos.io/swagger/client/

- **OpenSandbox Server**

  API 接口：http://127.0.0.1:8090/docs

- **Shared MinIO（共享对象存储）**

  管理后台：http://localhost:9003

  账号/密码：`.env` 中的 `SHARED_MINIO_ROOT_USER` / `SHARED_MINIO_ROOT_PASSWORD`

  宿主机访问 API：http://localhost:9002

  应用凭证：`.env` 中的 `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`，由专用服务账号（svcacct）签发，
  权限限定在 `deal-pilot` 桶（策略见 `resources/minio-policy.json`），应用不使用 root 凭证。

  **服务账号的创建 / 查看 / 撤销**（管理员在容器内执行 mc）

  ```shell
  # 配置管理员别名（使用 root 凭证）
  docker exec deal-pilot-shared-minio-1 mc alias set shared http://localhost:9000 <root账号> <root密码>

  # 创建：按策略签发专用凭据，输出中的 accessKey / secretKey 写入 .env
  docker cp resources/minio-policy.json deal-pilot-shared-minio-1:/tmp/minio-policy.json
  docker exec deal-pilot-shared-minio-1 mc admin user svcacct add --policy /tmp/minio-policy.json shared root

  # 查看
  docker exec deal-pilot-shared-minio-1 mc admin user svcacct ls shared root

  # 撤销：占位值替换为实际的 Access Key
  docker exec deal-pilot-shared-minio-1 mc admin user svcacct rm shared '<实际生成的 Access Key>'
  ```

  **集成测试凭证**：`make test-integrations` 读取 `.env` 的 `MINIO_TEST_ACCESS_KEY` /
  `MINIO_TEST_SECRET_KEY`，只有 `minio-it-*` 测试桶的建删权限（策略见
  `resources/minio-test-policy.json`）；应用凭证不需要建桶权限。

  **沙箱内使用**：`docker/sandbox/Dockerfile` 会把 `src/deal_pilot/utils/minio.py` 复制到
  `/sandbox_utils`。沙箱里没有 `deal_pilot` 包，`MinIO.from_settings()` 会自动退回读取同名
  环境变量（`MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET` /
  `MINIO_SECURE`）。创建沙箱时这些变量由 `deal_pilot.utils.sandbox` 自动注入，回环地址会替换为
  `host.docker.internal`（可用 `.env` 的 `MINIO_SANDBOX_ENDPOINT` 覆盖），并注入
  `PYTHONPATH=/sandbox_utils`。


### 不常用服务

- Langfuse MinIO 管理后台

  访问地址： http://localhost:9001

  账号/密码：`.env` 中的 `LANGFUSE_MINIO_ROOT_USER` / `LANGFUSE_MINIO_ROOT_PASSWORD`

