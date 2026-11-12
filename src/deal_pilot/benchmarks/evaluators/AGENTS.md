# 评分器与实验配置

## 职责与入口

- `shared.py` 提供 `EvalConfig`（`task`、`evaluators`、可选 `composite_evaluator`）、`run_agent(agent_name, input)`、`create_llm_score_evaluator(name, output_extract=None, threshold=0.8)`，以及 `correctness`/`completeness` 的内置 Prompt 与 `AnswerEvaluation` 结构。
- `retrieve.py` 提供 `retrieve_precision_eval`、`retrieve_recall_eval`、`experiment_task` 和 `retrieve_eval_config`。
- `experiment.py` 按数据集名从 `_config` 取配置；未注册的数据集抛 `RuntimeError`（`DS=all` 在调用前就跳过），不会回退到其他数据集的评分器。

## 评分契约

- 所有评分器返回 Langfuse `Evaluation`，阈值写在 `metadata={"test": {"threshold": ...}}`；回归脚本逐个评分读取该阈值判定，不再使用统一的总体相似度门槛。
- `retrieve_precision_eval`：分母是本次 `structured_response.sources` 去重后的条数，分子是与 `metadata.related_documents` 的交集；来源为空时记 0。
- `retrieve_recall_eval`：分母是 `metadata.related_documents` 的条数，分子同上。
- 两个检索评分都要求 `metadata.related_documents` 非空，否则抛 `ValueError`；并依赖 `output["sources"]` 每项含 `title`，标题必须与数据集中的文档标题一致，否则计为未命中。
- `create_llm_score_evaluator` 读取 Nacos Prompt `correctness_eval_prompt`/`completeness_eval_prompt`，缺失时回退 `shared.py` 内置 Prompt；通过 `ToolStrategy(AnswerEvaluation)` 取 0–1 分与理由。input、output 或 expected_output 任一为空时直接返回 0 分，不调用评审模型。
- `retrieve_eval_config` 未设置 `composite_evaluator`（为 None），当前没有总体加权分；报告和文档不能假设存在组合评分。

## 修改与验证

- 新增评分维度时同步更新 `experiment.py` 的 `_config`、远程 Prompt 与阈值；阈值随评分器返回，不在回归脚本里硬编码。
- 报告层有 `tests/units/test_benchmark_report.py` 覆盖阈值判定、缺失/重复评分、非法分数与阈值；评分器本身没有单测，真实评分质量需运行 Benchmark，依赖 Langfuse、Agent Server 与模型。
