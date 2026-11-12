# Deal Pilot

## 基础设施环境

本仓库从 `ai-infrastructure-practice` 复制而来，Compose 项目名是 `deal-pilot-rag`（旧项目是
`deal-pilot`），**容器 / 网络独立，宿主端口与数据卷则和旧项目共用**：

- **端口一致**：Langfuse 3000、LiteLLM 4000、Nacos 8080/8848/9848、OpenSandbox 8090、
  Langfuse MinIO 9000/9001、Shared MinIO 9002/9003。`.env` 里的端点无需修改。
- **数据卷复用**：`docker-compose.yml` 里的 volumes 用 `external: true` + `name:` 指向旧项目的
  `deal-pilot_*` 数据卷，Langfuse 的组织/项目/密钥与历史 trace、Nacos 配置、LiteLLM 模型、
  MinIO 桶与凭证全部沿用，切换项目不需要重新配置任何东西。
- **同一时间只启动一个**：端口和数据卷都是同一套，切换前先停掉当前那套
  （本仓库 `docker compose down`，旧项目 `docker compose -p deal-pilot down`），
  再在目标项目里执行 `make docker-recreate`。`down` 不会删除共享数据卷（volumes 声明为 external）。

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
  docker compose exec shared-minio mc alias set shared http://localhost:9000 <root账号> <root密码>

  # 创建：按策略签发专用凭据，输出中的 accessKey / secretKey 写入 .env
  docker compose cp resources/minio-policy.json shared-minio:/tmp/minio-policy.json
  docker compose exec shared-minio mc admin user svcacct add --policy /tmp/minio-policy.json shared root

  # 查看
  docker compose exec shared-minio mc admin user svcacct ls shared root

  # 撤销：占位值替换为实际的 Access Key
  docker compose exec shared-minio mc admin user svcacct rm shared '<实际生成的 Access Key>'
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

