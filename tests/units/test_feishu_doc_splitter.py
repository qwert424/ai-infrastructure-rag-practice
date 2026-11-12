"""飞书 Documents 切片的本地契约测试，不调用飞书、模型或存储。"""

from copy import deepcopy
from typing import Any

import pytest
from langchain_core.documents import Document

from deal_pilot.rag.loader.feishu_doc.feishu_doc_loader import load_feishu_doc_structre
from deal_pilot.rag.splitter.feishu_doc.feishu_doc_splitter import split_feishu_doc
from deal_pilot.rag.splitter.feishu_doc.references import ReferenceProtector
from deal_pilot.rag.splitter.feishu_doc.text import separate_title, split_text
from deal_pilot.rag.structure.feishu_doc.block_node import BlockNode
from deal_pilot.rag.structure.feishu_doc.block_type import BlockType


SOURCE_FIELDS = {
    "block_id", "block_type", "kind", "payload", "order",
    "parent_document_id", "title_path", "references",
}
CHUNK_FIELDS = {"chunk_index", "chunk_count"}
PLACEHOLDER_RANGES = ((0xF0000, 0xFFFFD), (0x100000, 0x10FFFD))


def node(
    block_id: str, block_type: int = BlockType.TEXT, content: str = "",
    *children: BlockNode, payload: dict[str, Any] | None = None,
) -> BlockNode:
    result = BlockNode(block_id, block_type, content, payload or {})
    for child in children:
        result.append(child)
    return result


def page(*children: BlockNode, title: str = "页面") -> BlockNode:
    return node("page", BlockType.PAGE, title, *children)


def load(*children: BlockNode, title: str = "页面") -> list[Document]:
    return load_feishu_doc_structre(page(*children, title=title))


def table(rows: int, columns: int, texts: list[str], merges: Any = None) -> BlockNode:
    payload: dict[str, Any] = {"row_size": rows, "column_size": columns}
    if merges is not None:
        payload["merge_info"] = merges
    cells = [
        node(f"cell-{index}", BlockType.TABLE_CELL, text)
        for index, text in enumerate(texts)
    ]
    return node("table", BlockType.TABLE, "", *cells, payload=payload)


def document(
    block_id: str = "doc", kind: str = "page", content: str = "", *,
    titles: list[Any] | None = None, payload: Any = None,
    references: Any = None,
) -> Document:
    return Document(
        id=block_id,
        page_content=content,
        metadata={
            "block_id": block_id,
            "block_type": 1,
            "kind": kind,
            "payload": {} if payload is None else payload,
            "order": 0,
            "parent_document_id": None,
            "title_path": [] if titles is None else titles,
            "references": [] if references is None else references,
        },
    )


def chunks_of(chunks: list[Document], block_id: str) -> list[Document]:
    return [chunk for chunk in chunks if chunk.metadata["block_id"] == block_id]


def reference(block_id: str, kind: str = "image", label: str = "图片") -> str:
    return f'<document-ref id="{block_id}" kind="{kind}">{label}</document-ref>'


def boundary_overlap(left: str, right: str) -> int:
    for length in range(min(len(left), len(right)), 0, -1):
        if left.endswith(right[:length]):
            return length
    return 0


def has_private_char(text: str) -> bool:
    return any(
        start <= ord(char) <= end
        for char in text
        for start, end in PLACEHOLDER_RANGES
    )


def test_empty_input_returns_empty() -> None:
    assert split_feishu_doc([]) == []


@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, "10", None])
def test_invalid_chunk_size(value: Any) -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        split_feishu_doc([], chunk_size=value)


@pytest.mark.parametrize("value", [-1, True, 1.0, "0", None])
def test_invalid_chunk_overlap(value: Any) -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        split_feishu_doc([], chunk_overlap=value)


@pytest.mark.parametrize("value", [1000, 1001, 5000])
def test_chunk_overlap_must_be_smaller_than_size(value: int) -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        split_feishu_doc([], chunk_size=1000, chunk_overlap=value)


@pytest.mark.parametrize("bad", [
    "id-mismatch", "empty-block-id", "unsupported-kind", "reserved-chunk-index",
    "reserved-chunk-count", "reserved-table-row-index", "titles-not-list",
    "titles-not-str", "payload-not-dict", "references-not-list",
    "reference-not-dict", "reference-missing-key", "reference-not-str",
])
def test_invalid_source_documents(bad: str) -> None:
    source = document("doc", "page", "正文")
    if bad == "id-mismatch":
        source.id = "other"
    elif bad == "empty-block-id":
        source.metadata["block_id"] = " "
    elif bad == "unsupported-kind":
        source.metadata["kind"] = "text"
    elif bad == "reserved-chunk-index":
        source.metadata["chunk_index"] = 0
    elif bad == "reserved-chunk-count":
        source.metadata["chunk_count"] = 1
    elif bad == "reserved-table-row-index":
        source.metadata["table_row_index"] = 0
    elif bad == "titles-not-list":
        source.metadata["title_path"] = "页面"
    elif bad == "titles-not-str":
        source.metadata["title_path"] = [1]
    elif bad == "payload-not-dict":
        source.metadata["payload"] = []
    elif bad == "references-not-list":
        source.metadata["references"] = {}
    elif bad == "reference-not-dict":
        source.metadata["references"] = ["x"]
    elif bad == "reference-missing-key":
        source.metadata["references"] = [{"id": "a", "kind": "image"}]
    else:
        source.metadata["references"] = [{"id": "a", "kind": "image", "placeholder": 1}]
    with pytest.raises(ValueError):
        split_feishu_doc([source])


def test_duplicate_source_documents_are_rejected() -> None:
    source = document("doc", "image", "说明")
    with pytest.raises(ValueError, match="重复 Document ID"):
        split_feishu_doc([source, deepcopy(source)])


def test_chunk_id_conflicting_with_source_is_rejected() -> None:
    first = document("a", "page", "# 标题\n\n" + "很长的正文内容。" * 50, titles=["标题"])
    second = document("a::chunk:0", "image", "说明")
    with pytest.raises(ValueError, match="切片 ID"):
        split_feishu_doc([first, second], chunk_size=40, chunk_overlap=0)


def test_image_and_code_are_kept_whole_beyond_budget() -> None:
    image = document("image", "image", "图片说明" * 100)
    code = document("code", "code", "print(1)\n" * 100)
    chunks = split_feishu_doc([image, code], chunk_size=20, chunk_overlap=0)
    by_id = {chunk.id: chunk for chunk in chunks}
    assert set(by_id) == {"image", "code"}
    assert by_id["image"].page_content == "图片说明" * 100
    assert by_id["code"].page_content == "print(1)\n" * 100
    assert all(chunk.metadata["chunk_index"] == 0 for chunk in by_id.values())
    assert all(chunk.metadata["chunk_count"] == 1 for chunk in by_id.values())


def test_literal_reference_tags_allowed_in_image_and_code() -> None:
    literal = reference("literal", "image", "示例")
    image = node("image", BlockType.IMAGE, literal)
    code = node("code", BlockType.CODE, f"# {literal}", payload={"language": 49})
    chunks = split_feishu_doc(load(image, code), chunk_size=1000)
    for chunk in chunks_of(chunks, "image") + chunks_of(chunks, "code"):
        assert chunk.metadata["references"] == []
        assert literal in chunk.page_content


def test_code_keeps_real_child_reference_and_ignores_literal_tag() -> None:
    literal = reference("literal", "image", "示例")
    code = node("code", BlockType.CODE, f"# {literal}\nprint(1)",
                node("image", BlockType.IMAGE, "图片说明"), payload={"language": 49})
    chunks = chunks_of(split_feishu_doc(load(code), chunk_size=1000), "code")
    assert len(chunks) == 1
    assert [ref["id"] for ref in chunks[0].metadata["references"]] == ["image"]
    assert reference("image") in chunks[0].page_content
    assert literal in chunks[0].page_content


def test_literal_reference_tag_in_text_is_rejected() -> None:
    source = document("doc", "page", reference("literal"), titles=["页面"])
    with pytest.raises(ValueError, match="不一致"):
        split_feishu_doc([source])


def test_text_split_respects_budget_titles_and_ids() -> None:
    body = ("第一段正文内容。" * 40) + "\n\n" + ("第二段正文内容。" * 40)
    chunks = split_feishu_doc(
        load(node("h", BlockType.HEADING_1, "章节标题", node("body", content=body))),
        chunk_size=120, chunk_overlap=0,
    )
    heading_chunks = chunks_of(chunks, "h")
    prefix = "# 页面\n\n## 章节标题"
    assert len(heading_chunks) > 1
    assert all(chunk.page_content.startswith(prefix) for chunk in heading_chunks)
    assert all(len(chunk.page_content) <= 120 for chunk in heading_chunks)
    assert [chunk.metadata["chunk_index"] for chunk in heading_chunks] == list(
        range(len(heading_chunks))
    )
    assert {chunk.metadata["chunk_count"] for chunk in heading_chunks} == {
        len(heading_chunks)
    }
    assert [chunk.id for chunk in heading_chunks] == [
        f"h::chunk:{index}" for index in range(len(heading_chunks))
    ]
    joined = "".join(chunk.page_content[len(prefix):] for chunk in heading_chunks)
    assert "第一段正文内容。" in joined and "第二段正文内容。" in joined


def test_content_within_budget_keeps_source_id() -> None:
    chunks = split_feishu_doc(load(node("h", BlockType.HEADING_1, "短正文")), chunk_size=1000)
    assert [chunk.id for chunk in chunks] == ["page", "h"]
    assert chunks[1].page_content == "# 页面\n\n## 短正文"
    assert chunks[1].metadata["chunk_index"] == 0
    assert chunks[1].metadata["chunk_count"] == 1


def test_overlap_repeats_boundary_text() -> None:
    body = " ".join(f"sentence{index:03d} end." for index in range(60))
    sources = load(node("h", BlockType.HEADING_1, "Chapter", node("body", content=body)))
    prefix = "# Page\n\n## Chapter\n\n"
    chunks = chunks_of(
        split_feishu_doc(sources, chunk_size=120, chunk_overlap=30), "h"
    )
    bodies = [chunk.page_content[len(prefix):] for chunk in chunks]
    overlaps = [
        boundary_overlap(bodies[index], bodies[index + 1])
        for index in range(len(bodies) - 1)
    ]
    assert overlaps and all(overlap > 0 for overlap in overlaps)
    assert all(len(chunk.page_content) <= 120 for chunk in chunks)


def test_zero_overlap_does_not_repeat_boundary_text() -> None:
    body = " ".join(f"sentence{index:03d} end." for index in range(60))
    sources = load(node("h", BlockType.HEADING_1, "Chapter", node("body", content=body)))
    prefix = "# Page\n\n## Chapter\n\n"
    chunks = chunks_of(split_feishu_doc(sources, chunk_size=120, chunk_overlap=0), "h")
    bodies = [chunk.page_content[len(prefix):] for chunk in chunks]
    assert all(
        boundary_overlap(bodies[index], bodies[index + 1]) == 0
        for index in range(len(bodies) - 1)
    )


def test_references_are_filtered_per_chunk_in_order() -> None:
    filler = "填充正文内容。" * 20
    sources = load(
        node("intro", content=filler),
        node("image-a", BlockType.IMAGE, "图一说明"),
        node("middle", content=filler),
        node("image-b", BlockType.IMAGE, "图二说明"),
        node("tail", content=filler),
    )
    chunks = split_feishu_doc(sources, chunk_size=120, chunk_overlap=0)
    page_chunks = chunks_of(chunks, "page")
    assert len(page_chunks) >= 2
    for chunk in page_chunks:
        expected = [
            ref for ref in sources[0].metadata["references"]
            if ref["placeholder"] in chunk.page_content
        ]
        assert chunk.metadata["references"] == expected
        assert [ref["id"] for ref in chunk.metadata["references"]] == sorted(
            [ref["id"] for ref in chunk.metadata["references"]],
            key=lambda value: chunk.page_content.index(
                next(ref["placeholder"] for ref in expected if ref["id"] == value)
            ),
        )
        assert all(
            chunk.page_content.count(ref["placeholder"]) == 1 for ref in expected
        )
        assert not has_private_char(chunk.page_content)
    assert {ref["id"] for chunk in page_chunks for ref in chunk.metadata["references"]} == {
        "image-a", "image-b",
    }


def test_placeholder_is_never_split_or_leaked() -> None:
    placeholder = reference("img")
    source = document(
        "doc", "page", "# 页面\n\n" + ("正文。" * 40) + placeholder + ("更多。" * 40),
        titles=["页面"],
        references=[{"id": "img", "kind": "image", "placeholder": placeholder}],
    )
    chunks = split_feishu_doc([source], chunk_size=60, chunk_overlap=0)
    holders = [chunk for chunk in chunks if placeholder in chunk.page_content]
    assert len(holders) == 1
    assert holders[0].metadata["references"] == [
        {"id": "img", "kind": "image", "placeholder": placeholder}
    ]
    assert all(not has_private_char(chunk.page_content) for chunk in chunks)


def test_placeholder_longer_than_budget_raises() -> None:
    placeholder = reference("x" * 60, "image", "图片")
    source = document(
        "doc", "page", "# 页面\n\n正文。" * 20 + placeholder,
        titles=["页面"],
        references=[{"id": "x" * 60, "kind": "image", "placeholder": placeholder}],
    )
    with pytest.raises(ValueError, match="占位符长度超过"):
        split_feishu_doc([source], chunk_size=40, chunk_overlap=0)


def test_title_exceeding_budget_raises() -> None:
    source = document(
        "doc", "page", "# " + "标" * 40 + "\n\n" + "正文。" * 20,
        titles=["标" * 40],
    )
    with pytest.raises(ValueError, match="标题长度过大"):
        split_feishu_doc([source], chunk_size=20, chunk_overlap=0)


def test_title_mismatch_raises() -> None:
    source = document("doc", "page", "没有标题的正文", titles=["页面"])
    with pytest.raises(ValueError, match="title_path"):
        split_feishu_doc([source], chunk_size=5, chunk_overlap=0)


@pytest.mark.parametrize("bad", [
    "missing-placeholder", "not-a-list", "incomplete-tag", "unknown-tag",
    "duplicate-reference", "reference-not-dict", "reference-missing-key",
    "reference-not-str",
])
def test_reference_validation_errors(bad: str) -> None:
    placeholder = reference("img")
    content = "# 页面\n\n" + placeholder
    references: Any = [{"id": "img", "kind": "image", "placeholder": placeholder}]
    if bad == "missing-placeholder":
        content = "# 页面\n\n缺少引用"
    elif bad == "not-a-list":
        references = ({"id": "img", "kind": "image", "placeholder": placeholder},)
    elif bad == "incomplete-tag":
        content = '# 页面\n\n<document-ref id="img">图片'
        references = []
    elif bad == "unknown-tag":
        content = "# 页面\n\n" + placeholder + reference("other")
    elif bad == "duplicate-reference":
        references = [references[0], deepcopy(references[0])]
    elif bad == "reference-not-dict":
        references = ["img"]
    elif bad == "reference-missing-key":
        references = [{"id": "img", "kind": "image"}]
    elif bad == "reference-not-str":
        references = [{"id": "img", "kind": "image", "placeholder": 1}]
    source = document("doc", "page", content, titles=["页面"], references=references)
    with pytest.raises(ValueError):
        split_feishu_doc([source], chunk_size=1000)


def test_source_documents_and_tree_are_not_modified() -> None:
    sources = load(
        node("h", BlockType.HEADING_1, "章节", node("body", content="正文。" * 200)),
        node("image", BlockType.IMAGE, "图片说明"),
    )
    snapshot = deepcopy([(doc.id, doc.page_content, doc.metadata) for doc in sources])
    split_feishu_doc(sources, chunk_size=80, chunk_overlap=10)
    assert [(doc.id, doc.page_content, doc.metadata) for doc in sources] == snapshot


def test_output_metadata_preserves_source_fields_and_is_independent() -> None:
    sources = load(
        node("h", BlockType.HEADING_1, "章节",
             node("body", content="正文。" * 200),
             node("image", BlockType.IMAGE, "图片说明")),
    )
    chunks = split_feishu_doc(sources, chunk_size=80, chunk_overlap=0)
    heading_chunks = chunks_of(chunks, "h")
    assert len(heading_chunks) > 1
    for chunk in heading_chunks:
        assert set(chunk.metadata) == SOURCE_FIELDS | CHUNK_FIELDS
        assert chunk.metadata["block_id"] == "h"
        assert chunk.metadata["parent_document_id"] == "page"
        assert chunk.metadata["title_path"] == ["页面", "章节"]
        assert chunk.metadata["order"] == 1
    heading_chunks[0].metadata["payload"]["changed"] = True
    heading_chunks[0].metadata["title_path"].append("changed")
    heading_chunks[0].metadata["references"].clear()
    assert sources[1].metadata["payload"] == {}
    assert sources[1].metadata["title_path"] == ["页面", "章节"]
    assert [ref["id"] for ref in sources[1].metadata["references"]] == ["image"]
    assert heading_chunks[1].metadata["title_path"] == ["页面", "章节"]


def test_table_splits_header_plus_each_data_row() -> None:
    sources = load(table(3, 2, ["头一", "头二", "行一甲", "行一乙", "行二甲", "行二乙"]))
    chunks = chunks_of(split_feishu_doc(sources, chunk_size=1000), "table")
    assert [chunk.metadata["table_row_index"] for chunk in chunks] == [1, 2]
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == [0, 1]
    assert {chunk.metadata["chunk_count"] for chunk in chunks} == {2}
    assert [chunk.id for chunk in chunks] == ["table::chunk:0", "table::chunk:1"]
    for chunk, row in zip(chunks, ("行一", "行二")):
        assert chunk.page_content.startswith("# 页面\n\n<table>")
        assert "头一" in chunk.page_content and "头二" in chunk.page_content
        assert f"{row}甲" in chunk.page_content and f"{row}乙" in chunk.page_content
        assert chunk.page_content.count("<tr>") == 2


def test_table_with_only_header_keeps_single_chunk() -> None:
    chunks = chunks_of(split_feishu_doc(load(table(1, 2, ["甲", "乙"]))), "table")
    assert len(chunks) == 1
    assert chunks[0].id == "table"
    assert chunks[0].metadata["table_row_index"] == 0
    assert chunks[0].metadata["chunk_count"] == 1
    assert "甲" in chunks[0].page_content and "乙" in chunks[0].page_content


def test_table_keeps_colspan_and_expands_rowspan() -> None:
    sources = load(table(
        2, 2, ["合并单元格", "", "", ""],
        merges=[{"row_span": 2, "col_span": 2}] + [{"row_span": 0, "col_span": 0}] * 3,
    ))
    chunks = chunks_of(split_feishu_doc(sources, chunk_size=1000), "table")
    assert len(chunks) == 1
    content = chunks[0].page_content
    assert 'colspan="2"' in content
    assert "rowspan" not in content
    assert content.count("合并单元格") == 2
    assert content.count("<tr>") == 2


def test_table_references_are_deduplicated_across_rows() -> None:
    cells = [
        node("cell-0", BlockType.TABLE_CELL, "头一"),
        node("cell-1", BlockType.TABLE_CELL, "头二"),
        node("cell-2", BlockType.TABLE_CELL, "", node("row-image", BlockType.IMAGE, "行图片")),
        node("cell-3", BlockType.TABLE_CELL, "行文本"),
    ]
    sources = load(node("table", BlockType.TABLE, "", *cells,
                        payload={"row_size": 2, "column_size": 2}))
    chunks = chunks_of(split_feishu_doc(sources, chunk_size=1000), "table")
    assert len(chunks) == 1
    references = chunks[0].metadata["references"]
    assert [ref["id"] for ref in references] == ["row-image"]
    assert chunks[0].page_content.count(references[0]["placeholder"]) == 1


def test_table_over_budget_raises() -> None:
    sources = load(table(2, 2, ["很长的表头一", "很长的表头二", "很长的数据一", "很长的数据二"]))
    with pytest.raises(ValueError, match="超过 chunk_size"):
        split_feishu_doc(sources, chunk_size=100, chunk_overlap=0)


@pytest.mark.parametrize("bad", [
    "two-tables", "missing-cells", "row-count-mismatch", "overlap",
    "invalid-rowspan", "negative-rowspan", "zero-rowspan", "overflow-column",
])
def test_invalid_table_documents(bad: str) -> None:
    html = (
        "<table>\n<tr><td>a</td><td>b</td></tr>\n"
        "<tr><td>c</td><td>d</td></tr>\n</table>"
    )
    payload: Any = {"row_size": 2, "column_size": 2}
    if bad == "two-tables":
        html = html + "\n" + html
    elif bad == "missing-cells":
        html = "<table>\n<tr><td>a</td><td>b</td></tr>\n<tr><td>c</td></tr>\n</table>"
    elif bad == "row-count-mismatch":
        payload = {"row_size": 3, "column_size": 2}
    elif bad == "overlap":
        html = (
            '<table>\n<tr><td>a</td><td rowspan="2">b</td></tr>\n'
            '<tr><td colspan="2">c</td></tr>\n</table>'
        )
    elif bad == "invalid-rowspan":
        html = (
            '<table>\n<tr><td>a</td><td rowspan="x">b</td></tr>\n'
            '<tr><td>c</td><td>d</td></tr>\n</table>'
        )
    elif bad == "negative-rowspan":
        html = (
            '<table>\n<tr><td>a</td><td rowspan="-1">b</td></tr>\n'
            '<tr><td>c</td><td>d</td></tr>\n</table>'
        )
    elif bad == "zero-rowspan":
        html = (
            '<table>\n<tr><td>a</td><td rowspan="0">b</td></tr>\n'
            '<tr><td>c</td><td>d</td></tr>\n</table>'
        )
    else:
        html = (
            '<table>\n<tr><td>a</td><td colspan="2">b</td></tr>\n'
            '<tr><td>c</td><td>d</td></tr>\n</table>'
        )
    source = document("table", "table", "# 页面\n\n" + html, titles=["页面"], payload=payload)
    with pytest.raises(ValueError):
        split_feishu_doc([source], chunk_size=1000)


@pytest.mark.parametrize("payload", [
    {}, {"row_size": 0, "column_size": 1}, {"row_size": True, "column_size": 1},
    {"row_size": "2", "column_size": 1}, {"row_size": 1, "column_size": None},
])
def test_invalid_table_payload(payload: Any) -> None:
    html = "<table>\n<tr><td>a</td></tr>\n</table>"
    source = document("table", "table", "# 页面\n\n" + html, titles=["页面"], payload=payload)
    with pytest.raises(ValueError):
        split_feishu_doc([source], chunk_size=1000)


def test_each_document_is_split_independently() -> None:
    first = document("a", "page", "# 甲页\n\n" + "甲" * 100, titles=["甲页"])
    second = document("b", "page", "# 乙页\n\n" + "乙" * 100, titles=["乙页"])
    chunks = split_feishu_doc([first, second], chunk_size=60, chunk_overlap=0)
    for chunk in chunks:
        assert ("甲" in chunk.page_content) != ("乙" in chunk.page_content)


def test_separate_title_contract() -> None:
    assert separate_title("正文", []) == ("", "正文")
    assert separate_title("# 页面", ["页面"]) == ("# 页面", "")
    assert separate_title("# 页面\n\n正文", ["页面"]) == ("# 页面\n\n", "正文")
    with pytest.raises(ValueError, match="title_path"):
        separate_title("# 其他\n\n正文", ["页面"])


def test_split_text_rejects_budget_without_room() -> None:
    protector = ReferenceProtector("正文", [])
    with pytest.raises(ValueError, match="标题长度过大"):
        split_text("# 标题\n\n" + "正文" * 10, ["标题"], protector,
                   chunk_size=4, chunk_overlap=0)
    assert split_text("短", [], protector, chunk_size=10, chunk_overlap=0) == ["短"]
