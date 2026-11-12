"""图片上下文提取：跳过空白兄弟块与其他图片，不触网。"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from deal_pilot.config.nacos.nacos_schemas import RagConfig
from deal_pilot.rag.structure.feishu_doc import image_parser
from deal_pilot.rag.structure.feishu_doc.block_node import BlockNode
from deal_pilot.rag.structure.feishu_doc.block_type import BlockType


def node(block_id: str, block_type: BlockType, content: str = "") -> BlockNode:
    return BlockNode(block_id=block_id, block_type=block_type, content=content)


@pytest.fixture(autouse=True)
def mock_config(monkeypatch: pytest.MonkeyPatch):
    """_attachment_info 会读取 Nacos 配置，测试改为本地配置对象。"""

    def install(sibling_count: int = 3) -> None:
        config = RagConfig()
        config.image_parser.sibling_count = sibling_count
        monkeypatch.setattr(image_parser, "get_config", AsyncMock(return_value=config))

    return install


def build() -> BlockNode:
    heading = node("h", BlockType.HEADING_2, "产品外观与内部照片")
    heading.append(node("p1", BlockType.TEXT, ""))
    heading.append(node("p2", BlockType.TEXT, "前文说明"))
    heading.append(node("blank-before", BlockType.TEXT, "   "))
    image = node("img", BlockType.IMAGE, "token-a")
    heading.append(image)
    heading.append(node("blank-after", BlockType.TEXT, ""))
    heading.append(node("n1", BlockType.TEXT, "后文一"))
    heading.append(node("img2", BlockType.IMAGE, "token-b"))
    heading.append(node("n2", BlockType.TEXT, "后文二"))
    return image


def test_skips_blank_text_and_other_images(mock_config) -> None:
    mock_config(3)
    info = asyncio.run(image_parser._attachment_info(build()))
    assert info.parent_trace == ["产品外观与内部照片"]
    assert info.prevs == ["前文说明"]
    assert info.nexts == ["后文一", "后文二"]


def test_respects_sibling_count_after_filtering(mock_config) -> None:
    mock_config(1)
    info = asyncio.run(image_parser._attachment_info(build()))
    assert info.prevs == ["前文说明"]
    assert info.nexts == ["后文一"]


def test_empty_context_when_only_blank_siblings(mock_config) -> None:
    mock_config(3)
    heading = node("h", BlockType.HEADING_2, "章节")
    heading.append(node("blank", BlockType.TEXT, ""))
    image = node("img", BlockType.IMAGE, "token")
    heading.append(image)
    heading.append(node("blank2", BlockType.TEXT, "\n"))
    info = asyncio.run(image_parser._attachment_info(image))
    assert info.prevs == []
    assert info.nexts == []


def test_negative_sibling_count_rejected(mock_config) -> None:
    mock_config(-1)
    with pytest.raises(ValueError, match="sibling_count"):
        asyncio.run(image_parser._attachment_info(build()))


def test_generate_dataurl_prefixes_mime_and_base64() -> None:
    assert image_parser._generate_dataurl(b"\x00\xff", "image/png") == "data:image/png;base64,AP8="
