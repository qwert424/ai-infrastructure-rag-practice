from deal_pilot.benchmarks.experiment import registered_datasets, run_experiment
from deal_pilot.benchmarks.dataset import get_all_datasets


def run_benchmark(dataset_name: str):
    exp_name = f"实验数据集:{dataset_name}"
    description = f"对实验数据集{dataset_name}的离线评估"
    return run_experiment(exp_name, dataset_name, description)


def run_all_benchmarks():
    """只运行已注册评估配置的数据集；未注册的数据集不参与。"""
    registered = registered_datasets()
    return [
        run_benchmark(dataset.name)
        for dataset in get_all_datasets()
        if dataset.name in registered
    ]
