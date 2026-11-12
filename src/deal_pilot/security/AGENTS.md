# 身份认证与资源授权

## 职责与入口

`auth.py:auth` 是 `langgraph.json` 的鉴权入口，通过 `Auth` 注册认证和资源授权处理器。`agent_token.py` 负责业务入口与 Agent Server 之间的短期身份令牌；当前不接入用户中心，也不再有模拟用户表。

## 当前授权契约

- 认证只接受 `Authorization: Bearer <JWT>`：校验 HS256 签名、issuer=`deal-pilot`、audience=`deal-pilot-agent`、必需 claims（`sub`/`iss`/`aud`/`iat`/`exp`）与有效期，subject 非空才返回 `{"identity": sub}`。
- `AGENT_TOKEN_SECRET` 少于 32 字节视为配置错误：签发抛 ValueError，认证返回 503；不要在日志或响应中回显密钥、原始 token 或 SDK 细节。
- 令牌只由已验证的业务入口签发（当前是 Feishu 消息回调，按发送者 OpenID），不提供按任意 ID 签发的 HTTP 接口；`BENCHMARK_USER_ID` 作为评测身份同样经 `create_agent_token` 签发。
- Store 只允许访问第一段等于当前 identity 的 namespace，不满足返回 False；Assistants 是系统共享资源，不施加 owner 过滤。
- 通用处理器为线程等用户资源写入 `metadata.owner` 并返回 owner 过滤条件；不要误称所有资源都使用同一套 owner 过滤。
- 身份缺失、scheme 不是 Bearer、token 无效或过期返回 401；无权限返回拒绝结果，不能回退到默认用户或管理员。
- `langgraph.json` 当前禁用 Studio 鉴权且未启用自定义路由鉴权，Webhook 由 `app` 自行验签。

## 修改指引

- 轮换 `AGENT_TOKEN_SECRET` 会使在途与已签发令牌失效，需同时更新签发端（Feishu 服务）和 Agent Server；TTL 默认 300 秒，长任务由调用方重新签发。
- 身份变化影响 `utils/shared.py`、沙箱 key、卷名和 Deploy 对象前缀；跨用户访问规则必须一并核对。
- 调整 claims 或授权处理器时同步 `security/agent_token.py`、`tests/units/test_agent_token.py` 与调用方。

## 验证方式

`tests/units/test_agent_token.py` 覆盖签名、过期、audience/issuer、缺失 claims、空 subject、错误算法、非 Bearer scheme、旧明文 token、缺密钥配置以及 Store/Assistants/owner 授权。Deploy 集成测试注入上下文，只验证工具使用身份，不能证明完整 Agent Server 鉴权正确。
