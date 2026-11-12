"""Nacos rag_config 示例必须能被 RagConfig 校验。"""
from pathlib import Path

import yaml

from deal_pilot.config.nacos.nacos_schemas import RagConfig

_EXAMPLE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "deal_pilot"
    / "config"
    / "nacos"
    / "rag_config_example.yaml"
)


def test_example_yaml_validates_into_rag_config():
    config = RagConfig.model_validate(
        yaml.safe_load(_EXAMPLE.read_text(encoding="utf-8"))
    )
    assert config.retriever.fetch_k == 10
    assert config.retriever.k == 4
    assert [param["metric_type"] for param in config.retriever.param] == [
        "COSINE",
        "BM25",
    ]
    assert config.retriever.reranker.reranker == "rrf"
