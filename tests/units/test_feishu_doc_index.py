"""飞书文档索引主图：取批、扇出与统计累加。"""

import asyncio
from types import SimpleNamespace

import pytest

import deal_pilot.graphs.feishu_doc_index.graph as index_graph


def _node(token: str, obj_type: str = "docx") -> SimpleNamespace:
    return SimpleNamespace(node_token=token, title=token, obj_type=obj_type)


class _FakeWikiAPI:
    def __init__(self, nodes: list[SimpleNamespace]) -> None:
        self._nodes = nodes

    async def list_all_space_nodes(self):
        for node in self._nodes:
            yield node


class _FakeDocGraph:
    def __init__(self, *, status: str = "success", error: Exception | None = None) -> None:
        self.status = status
        self.error = error
        self.calls: list[str] = []

    async def ainvoke(self, state: dict) -> dict:
        token = state["node"].node_token
        self.calls.append(token)
        if self.error is not None:
            raise self.error
        return {"status": self.status}


def _install(
    monkeypatch: pytest.MonkeyPatch,
    nodes: list[SimpleNamespace],
    *,
    status: str = "success",
    error: Exception | None = None,
) -> _FakeDocGraph:
    doc_graph = _FakeDocGraph(status=status, error=error)
    monkeypatch.setattr(index_graph, "WikiAPI", lambda: _FakeWikiAPI(nodes))
    monkeypatch.setattr(index_graph, "doc_graph", doc_graph)
    return doc_graph


def _run(concurrency: int) -> dict:
    async def scenario() -> dict:
        graph = await index_graph.factory()
        return await graph.ainvoke({}, context={"concurrency": concurrency})

    return asyncio.run(scenario())


def test_non_docx_nodes_do_not_consume_batch_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    """非 Docx 节点占满一批时，后续 Docx 仍要处理，不能提前结束。"""
    doc_graph = _install(
        monkeypatch,
        [_node("sheet1", "sheet"), _node("sheet2", "sheet"), _node("d1")],
    )

    result = _run(2)

    assert doc_graph.calls == ["d1"]
    assert result["batch_count"] == 1
    assert result["node_count"] == 1
    assert result["indexed_count"] == 1
    assert result["skipped_count"] == 0
    assert result["failure_count"] == 0


def test_full_batches_keep_fetching_until_iteration_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_graph = _install(monkeypatch, [_node("d1"), _node("d2"), _node("d3")])

    result = _run(2)

    assert sorted(doc_graph.calls) == ["d1", "d2", "d3"]
    assert result["batch_count"] == 2
    assert result["node_count"] == 3
    assert result["indexed_count"] == 3


def test_skipped_document_is_counted_separately(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, [_node("d1"), _node("d2")], status="skipped")

    result = _run(2)

    assert result["batch_count"] == 1
    assert result["node_count"] == 2
    assert result["indexed_count"] == 0
    assert result["skipped_count"] == 2


def test_document_failure_is_recorded_and_others_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc_graph = _install(monkeypatch, [_node("d1"), _node("d2")], error=RuntimeError("boom"))

    result = _run(2)

    assert sorted(doc_graph.calls) == ["d1", "d2"]
    assert result["failure_count"] == 2
    assert [item["node_token"] for item in result["failures"]] == ["d1", "d2"]
    assert all(item["message"] == "boom" for item in result["failures"])


def test_empty_iteration_ends_without_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    doc_graph = _install(monkeypatch, [])

    result = _run(3)

    assert doc_graph.calls == []
    # 没有可取节点时不产生任何状态更新
    assert not result
