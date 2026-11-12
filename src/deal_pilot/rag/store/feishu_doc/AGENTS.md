# 飞书文档 Milvus 存储

## Schema 与索引参数

- `schema.py:create_schema(dim: int) -> CollectionSchema` 同步构造 Schema；`index_params.py` 的 `create_dense_index_params(config: RagStoreConfig) -> IndexParams`、`create_sparse_index_params() -> IndexParams` 分别构造稠密、稀疏索引参数。这些工厂不连接 Milvus、不创建集合或索引、不写入数据。
- Schema 使用手动主键 `id: VARCHAR(64)`，对应飞书切片 `Document.id`；导出 Markdown 中的 `document_id` 是该 ID 的展示名称，不另设字段。`text` 上限为 10000 字节；切片预算按字符计量（默认 `chunk_size=1000`），中文按 UTF-8 最多 3 字节/字符，图片/代码还可能整体保留，写入前须另核对 UTF-8 字节长度。
- 来源字段为 `space_id`、`node_token`、`node_title`、`obj_token`、`revision_id`，以及 `block_id`、`block_type`、`kind`、`payload`、`order`、`parent_block_id`、`url`、`parent_node_token`、`title_path`、`references`。切片位置保存 `chunk_index`、`chunk_count` 和表格专用 `table_row_index`。`payload`、`title_path`、`references` 用 JSON 保留原结构；`parent_block_id`、`parent_node_token`、`table_row_index` 可空，索引图依赖该设置写入根节点（`parent_node_token=None`）和非表格切片（无 `table_row_index`）。关系 ID 仍指向来源 `block_id`，不能改成切片主键含义；`url`（≤200）按必填字段定义。
- 开启动态字段；`dense` 为 `FLOAT_VECTOR`，维度由 `dim` 传入。`text` 开启中文分析器，`text_to_bm25` Function 从正文生成 `sparse` 稀疏向量。
- `DENSE_INDEX_NAME="dense_index"` 用于 `dense`，类型与度量来自 `RagStoreConfig`，当前没有传入构建参数。`SPARSE_INDEX_NAME="sparse_index"` 用于 `sparse`，固定 `SPARSE_INVERTED_INDEX/BM25`，遍历算法使用服务端默认值；当前没有标量索引。搜索时若显式指定度量，须与相应索引一致。

## 初始化及重建

- `init_store.py:await init_store() -> None` 读取 `get_config("rag_config", RagConfig)`，直接取 `milves_stores["feishu_doc"]`，使用 `milvus_settings.uri` 创建一个 `AsyncMilvusClient`。从默认数据库连接开始，目标 `db_name` 缺失则创建，再切换到目标数据库。
- 集合名固定为 `feishu_doc`。缺失时用 `create_schema(rag_config.embedding_model.dimensions)` 创建集合，依次创建 dense、sparse 索引，再加载集合。
- Schema 变更不会迁移：`init_store` 只在集合缺失时调用 `create_schema`，已有集合沿用原字段定义。调整 `schema.py`（字段、长度、`nullable`、向量维度）后必须手工重建集合，否则新写入可能因长度或空值约束失败；重建会丢失现有实体。
- 已有集合只通过 `has_index_changed` 比较稠密索引；变化时调用 `drop_index`，重建稠密索引并重新加载。类型与度量未变时不做写操作，也不重新加载；不迁移 Schema/向量维度，不检查或补建稀疏索引，不比较构建参数。
- `await has_index_changed(config, collection_name, index_name, *, client) -> bool` 使用调用方客户端；集合不存在或 `describe_index` 返回 `None` 时返回 True，否则直接比较返回字典的 `index_type`、`metric_type`。不展开或归一化参数；SDK 抛出的索引缺失等异常原样传播，不能据此保证所有索引缺失情况都能自动重建。
- `await drop_index(collection_name, *, client) -> None` 先 `release_collection`，再按 `DENSE_INDEX_NAME` 删除稠密索引；不删除集合、实体或稀疏索引，不负责重建或重新加载。释放期间集合不可查询/检索；后续操作失败时不会自动恢复加载状态。
- 辅助函数不创建或关闭客户端；`init_store` 统一在 `finally` 中关闭。异常及取消不被捕获转换；已完成的数据库操作不回滚。初始化必须显式调用，尚未接入 Agent 或服务启动流程。

## 向量库实例

- `get_store.py:await get_store() -> Milvus` 返回 langchain-milvus 的 `Milvus` 实例，进程内单例：首次调用在模块级 `asyncio.Lock` 保护下先 `await init_store()`，再读取 `get_config("rag_config", RagConfig)`、用 `create_embedding_model(config.embedding_model)` 构造 embeddings，通过 `asyncio.to_thread` 创建 `Milvus` 后写入模块级 `_store`，后续调用直接返回该实例。
- 构造参数固定：`collection_name="feishu_doc"`（取自 `init_store.COLLECTION_NAME`）、`primary_field="id"`、`text_field="text"`、`vector_field=["dense", "sparse"]`、`builtin_function=BM25BuiltInFunction(input_field_names="text", output_field_names="sparse")`、`enable_dynamic_field=True`、`auto_id=False`、`drop_old=False`；连接参数使用 `milvus_settings.uri` 与 `db_name`。
- `Milvus` 构造及其内部客户端连接是同步调用，现通过 `asyncio.to_thread` 在线程中执行，不阻塞事件循环。缓存没有失效或重载机制：Nacos 配置、向量维度或索引重建后需重启进程才生效。锁只覆盖首次构造，不保护后续并发读写。
- 本模块只构造并缓存实例，不封装写入或检索流程；写入与旧版本删除由 `graphs/feishu_doc_index` 直接调用 `aupsert`/`adelete`，检索尚未实现，也未接入 Agent。该模块依赖 `langchain-milvus`。

## 验证边界

- 当前没有对应的存储单元测试或集成测试文件；源码与本地 SDK 参数构造不能证明真实 Milvus 行为。
- 需要真实验证时使用隔离临时数据库，分别核对首次创建、配置未变、稠密索引重建及数据/稀疏索引保留；Nacos 若使用 Mock，应单独注明，不能称为完整联调。
