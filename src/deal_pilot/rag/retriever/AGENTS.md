# RAG 检索

## 职责与结构

- 当前只有 `feishu_doc/feishu_doc_retriever.py`，负责把检索参数、Milvus 混合召回与重排组装成一次查询。不负责切片、向量化写入、旧版本清理或答案生成，也不读取 Nacos。
- 调用方自己读取 `get_config("rag_config", RagConfig).retriever` 并显式传入 `config=`；省略时使用 `RetrieverConfig()` 的本地默认值，不能把这种结果描述为读取了远程配置。
- 检索复用 `rag/store/feishu_doc` 的 `get_store()` 单例，与索引写入使用同一个 `Milvus` 实例和向量维度；首次调用会触发存储初始化。
- 具体接口、重排与验证边界见 `feishu_doc/AGENTS.md`。

## 边界

- 本模块未注册为 Agent 工具，也未接入主 Agent、服务启动流程或评测流程；`retrieve_agent` 图经 `middlewares/retrieve_context.py` 读取 `rag_config.retriever` 后调用 `search(config=...)`。
- 仓库中没有检索的单元测试或集成测试；引用真实检索结果时须注明数据范围与时间。
