# 文档结构化

- 按来源文档类型组织结构化模型；当前仅有 `feishu_doc`。
- 飞书 API 读取仍归属 `deal_pilot.feishu.api`，本目录负责读取结果的后续结构表达。
- 异步 `await feishu_doc.tree_builder.build_tree(blocks)` 校验完整 `list[DocxBlock]` 的原始关系，按标题层级组织为有序树；content 初始为本节点纯文本或图片 token，payload 保存代码 language 编号或表格 column_size/row_size/merge_info。构树完成后按文档顺序收集全部图片节点，串行调用 `image_parser.parse_image_block`，等待其原地处理完成再返回；该函数已编排图片下载、私有桶上传与模型识图，缺权限或图片服务不可用会中止整篇文档。
