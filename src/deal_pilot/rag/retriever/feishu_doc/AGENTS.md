# 飞书文档检索

## 接口与参数

- `search(question: str, *, filter: str | None = None, config: RetrieverConfig | None = None, threshold: float = 0) -> list[SearchResult]`；`SearchResult` 是 dataclass，含 `doc: Document` 与 `score: float`。
- `config` 为 `RetrieverConfig`：`fetch_k`（每路候选，默认 10）、`k`（最终返回，默认 4）、`param`（检索参数，默认 None；单路可用 `dict`，双路用按 `vector_field=["dense", "sparse"]` 顺序的 `list[dict]`，长度须与向量字段数一致）、`reranker`（`RerankerConfig`）。
- 直接调用 `store.asimilarity_search_with_score(query=..., fetch_k=..., k=..., param=..., expr=filter, reranker=...)`，不自己实现召回或打分。`fetch_k` 经 `**kwargs` 透传给 langchain-milvus，是否真正限制每路召回数量未验证。
- `filter` 原样作为 Milvus 表达式传入，模块不做转义、字段名校验或空值处理；非法表达式由 Milvus 报错。
- 结果按 `score >= threshold` 过滤，默认 0。分数含义随重排方式变化（实测 rrf 约 0.03，weighted 与模型重排约 0.9），不同重排模式的阈值不可互相套用。

## 重排契约

- `_resolve_reranker_function(question, config)` 构造 pymilvus `Function(function_type=FunctionType.RERANK)`，重排由 Milvus 服务端执行，不是本地计算；服务端如何调用外部 rerank 服务由 `docker/milvus/user.yaml` 的 `function.rerank.model.providers` 决定。
- `rrf`：`input_field_names=[]`，`params.k` 默认 60。
- `weighted`：`input_field_names=[]`，`params.weights` 默认 `[0.5, 0.5]`，顺序对应 dense、sparse；固定 `norm_score=True`，不提供关闭开关。
- `model`：固定 `provider="cohere"`、`input_field_names=["text"]`、`queries=[question]`；`params.model_name` 默认 `rerank`，必须是 Milvus 端能解析的模型名。本地默认值会返回 `2400 ... /rerank: Invalid model name passed in model=rerank`，改成 LiteLLM 别名（如 `rerank-basic`）后可用。
- `RerankerConfig.reranker` 之外的取值由 schema 拒绝；`params` 是自由字典，缺少键时用上述默认值，多余键原样传给 Milvus。模块不校验 `k` 与 `fetch_k` 的关系、权重个数与训练无关的边界。

## 验证边界

- 2026-11-13 本地真实检索（集合 `deal_pilot.feishu_doc`，18 篇 180 行）：`rrf`、`weighted`（`weights=[0.7, 0.3]`）、`model`（`model_name=rerank-basic`）各返回 4 条结果；`model` 用默认 `rerank` 报 Milvus 2400。
- 没有自动化测试；`threshold`、`filter` 表达式、多知识空间过滤、`fetch_k` 的实际效果，以及模型重排的排序质量均未验证。
