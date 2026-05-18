from dataclasses import dataclass
import re

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
MAX_CHUNKS = 2000

_HEADERS_TO_SPLIT = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]


@dataclass
class ChunkResult:
    content: str
    heading_path: str
    chunk_index: int


_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")


@dataclass
class _SectionBlock:
    content: str
    atomic: bool


def _is_table_header(line: str, next_line: str) -> bool:
    return "|" in line and bool(_TABLE_SEPARATOR_RE.match(next_line))


def _split_section_blocks(section_text: str) -> list[_SectionBlock]:
    lines = section_text.splitlines()
    blocks: list[_SectionBlock] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("```") or line.startswith("~~~"):
            fence = line[:3]
            block_lines = [line]
            i += 1
            while i < len(lines):
                block_lines.append(lines[i])
                if lines[i].startswith(fence):
                    i += 1
                    break
                i += 1
            blocks.append(_SectionBlock(content="\n".join(block_lines), atomic=True))
            continue

        if i + 1 < len(lines) and _is_table_header(line, lines[i + 1]):
            block_lines = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                block_lines.append(lines[i])
                i += 1
            blocks.append(_SectionBlock(content="\n".join(block_lines), atomic=True))
            continue

        if _LIST_ITEM_RE.match(line):
            block_lines = [line]
            i += 1
            while i < len(lines):
                current = lines[i]
                if not current.strip():
                    break
                if (
                    _LIST_ITEM_RE.match(current)
                    or current.startswith("  ")
                    or current.startswith("\t")
                ):
                    block_lines.append(current)
                    i += 1
                    continue
                break
            blocks.append(_SectionBlock(content="\n".join(block_lines), atomic=True))
            continue

        blocks.append(_SectionBlock(content=line, atomic=False))
        i += 1

    return blocks


def _split_prose(char_splitter: RecursiveCharacterTextSplitter, text: str) -> list[str]:
    if not text.strip():
        return []
    return [chunk for chunk in char_splitter.split_text(text) if chunk.strip()]


def _split_structured_section(
    char_splitter: RecursiveCharacterTextSplitter,
    section_text: str,
) -> list[str]:
    blocks = _split_section_blocks(section_text)
    chunks: list[str] = []
    prose_buffer: list[str] = []

    def flush_prose() -> None:
        if not prose_buffer:
            return
        prose_text = "\n".join(prose_buffer).strip()
        chunks.extend(_split_prose(char_splitter, prose_text))
        prose_buffer.clear()

    for block in blocks:
        if block.atomic:
            flush_prose()
            if block.content.strip():
                chunks.append(block.content.strip())
            continue
        prose_buffer.append(block.content)

    flush_prose()
    return chunks


# 将 Markdown 文档按标题和长度切分为带有 heading metadata 的 chunk，供后续 embedding 和检索使用。
def split_markdown(markdown: str, source_url: str) -> list[ChunkResult]:
    """Split markdown into chunks with heading metadata."""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT,
        strip_headers=False,
    )
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    header_docs = header_splitter.split_text(markdown)
    all_chunks: list[ChunkResult] = []

    for doc in header_docs:
        heading_parts = [
            doc.metadata.get(h, "") for _, h in _HEADERS_TO_SPLIT if doc.metadata.get(h)
        ]
        heading_path = " > ".join(heading_parts) if heading_parts else ""

        sub_chunks = _split_structured_section(char_splitter, doc.page_content)
        for text in sub_chunks:
            if not text.strip():
                continue
            all_chunks.append(
                ChunkResult(
                    content=text,
                    heading_path=heading_path,
                    chunk_index=len(all_chunks),
                )
            )

    if len(all_chunks) > MAX_CHUNKS:
        raise ValueError(
            f"Document too large: {len(all_chunks)} chunks exceeds limit of {MAX_CHUNKS}. source_url={source_url}"
        )

    return all_chunks
