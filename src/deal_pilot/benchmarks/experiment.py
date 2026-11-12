from langfuse import get_client
from deal_pilot.benchmarks.dataset import get_items
from deal_pilot.benchmarks.evaluators.shared import EvalConfig
from deal_pilot.benchmarks.evaluators.retrieve import retrieve_eval_config

langfuse = get_client()


_config: dict[str, EvalConfig] = {"retrieve": retrieve_eval_config}


def registered_datasets() -> set[str]:
    return set(_config)


def metric_names(dataset_name: str) -> list[str] | None:
    """返回数据集声明的评分名；未注册的数据集返回 None。"""
    config = _config.get(dataset_name)
    return list(config.metric_names) if config else None


def run_experiment(name: str, dataset_name: str, description: str | None = ""):
    config = _config.get(dataset_name)
    if config is None:
        raise RuntimeError(f"当前数据集{dataset_name}没有对应的评估配置")
    items = get_items(dataset_name)

    # 运行实验
    return langfuse.run_experiment(
        # 给实验取个名字
        name=name,
        # 如果不配置，则使用name+当前时间自动生成
        run_name=None,
        description=description,
        # 此次实验针对哪些数据项
        data=items,
        evaluators=config.evaluators,
        composite_evaluator=config.composite_evaluator,
        task=config.task,  # type: ignore
    )
