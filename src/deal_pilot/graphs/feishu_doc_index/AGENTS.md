# 飞书文档索引主图

## 职责与结构

- 负责知识库目录分批、动态扇出、批次循环和统计；单文档业务归属 `document_index/`。
- `graph.py:async factory()` 创建 `WikiAPI().list_all_space_nodes()` 异步迭代器及编译图；`factory_with_trace = trace_wrapper(factory)` 复用现有追踪包装，在 `langgraph.json` 以 `feishu_doc_index` 注册。
- `state.py` 定义 `FeishuDocIndexContext` 和 `FeishuDocIndexState`。Context 只有 `concurrency: int`；状态的 batch_count、node_count、indexed_count、skipped_count、failure_count 与 failures 均使用 add reducer。失败记录只保存字符串 node_token、title、message，不保存异常对象。

## 取批、扇出和错误边界

- 主图为 START → fetch_batch → 非空批 Send 到 index_document → 本批全部完成后取下一批；空批直接结束。
- 每次取批持续读取迭代器直到收集满 concurrency 个 Docx 或迭代器结束，默认并发量为 3，可用 `context={"concurrency": N}` 覆盖；调用方应传正整数，当前未额外校验。
- `list_all_space_nodes` 只产出 Docx，并在遍历时跳过其他类型的节点本身、继续读取它们的子节点，因此混合类型目录不会中断取批；取批层的 `obj_type == "docx"` 判断只作防御，非 Docx 不占批次名额，也不会让本轮提前结束。
- 非空批通过 Command.update 累加 batch_count=1、node_count=本批 Docx 数量，再通过 `Send("index_document", node)` 直接传递 WikiNode。过滤掉的其他类型不计入 node_count。
- index_document 以 `{"node": node}` 调用子图 ainvoke；status 为 success 时返回 indexed_count=1，其他返回状态计为 skipped_count=1，不将子图正文和切片合并进主图状态。
- 单文档边界捕获 Exception，返回 failure_count=1 及 failures 记录后继续其他文档和批次；当前未专门放行继承 Exception 的 GraphBubbleUp / GraphInterrupt，不能保证主动中断语义保持不变。不捕获 BaseException，任务取消继续传播。目录迭代异常在此边界之外，直接终止主图。

## 生命周期与验证

- 每次工厂调用有独立的闭包迭代器；本地新运行也应重新 `await factory()`。导入及构图只定义流程，开始消费目录才请求飞书；没有跨进程恢复迭代器进度或自动注册调度计划的实现。
- 子图已接通版本读取与比较、元数据、正文、构树、Loader、Splitter、Milvus 写入及旧版本实体清理；构树会真实执行图片下载、MinIO 上传与模型识图，任一图片失败会使整篇文档记为失败，具体限制见 `document_index/AGENTS.md`。
- `tests/units/test_feishu_doc_index.py` 用假迭代器与假子图覆盖取批：非 Docx 占满一批后仍处理后续 Docx、批次满时继续取下一批、skipped/failure 统计与失败记录、空目录不产生状态更新；不连接飞书、Milvus 或模型。`tests/units/test_feishu.py` 覆盖全库遍历跳过非 Docx 节点但继续读取其子目录，以及 `space_name` 填充范围；`tests/units/test_feishu_doc_schema.py` 覆盖 `build_metadata` 的空间标题来源与校验、Schema 同步及标题回填。子图其余节点（正文、构树、Loader、Splitter、写入与旧版本清理）没有专门自动化测试，不能因上述测试通过就声称整条流水线已验证。
- 源码类型检查可用 `uv run pyright --pythonpath .venv/bin/python src/deal_pilot/graphs/feishu_doc_index`，Windows 上解释器路径按实际虚拟环境调整，执行结果需另行记录。
- 已有一轮真实运行（2026-11-12）：18 个 Docx 节点中 11 篇无图文档写入成功（集合 `feishu_doc` 共 102 行），7 篇含图文档在图片下载处失败（飞书 `99991672`，缺 `docs:document.media:download`）。
- 2026-11-13 再跑一轮：飞书应用已具备图片下载权限，先删除 7 篇含图文档的切片强制重建，主图统计为 `node_count=18`、`indexed_count=7`、`skipped_count=11`、`failure_count=0`；集合恢复为 18 篇 180 行，8 个图片切片都有实际图片描述，`feishu-images` 桶为私有（无 BucketPolicy）且累计 24 个对象。本轮识图模型是在调用进程内临时覆盖为 LiteLLM 别名 `vl-basic`（`qwen_ai_platform/qwen3-vl-plus`），不是持久配置。
- 当前配置差距：Nacos `public` 命名空间、`deal_pilot` group 下没有 `rag_config`（客户端读取返回 `20004 resource not found`），RagConfig 实际取 schema 默认值，识图模型因此回落到 `OPENAI_DEFAULT_MODEL`（`chat-basic` → 纯文本的 `qwen-flash`），图片只会被写成"图片内容无法辨认"。持久生效需要在 Nacos 发布 `rag_config` 并把 `image_parser.vl_model_config.name` 指向视觉模型别名；`image_parser_prompt` 走 Nacos AI Prompt registry，与 `rag_config` 无关。
- `adelete` 旧版本清理、版本变化后的增量覆盖仍未在真实服务上触发；源码检查、单元测试和一次成功重跑都不能证明全库索引与检索可用。真实运行会写入并删除实体，应使用明确授权的数据范围。
