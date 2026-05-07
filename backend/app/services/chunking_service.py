from dataclasses import dataclass

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
# 一篇大 Markdown 文档 -> 被拆成很多小片段 -> 每个片段都带着“它原来属于文档哪个位置”的标签
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
    content: str#文档的内容
    heading_path: str #文档的标题路径，例如 "API Reference > Authentication > Login"
    chunk_index: int # chunk 在原文切分结果中的顺序


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
        heading_parts = [doc.metadata.get(h, "") for _, h in _HEADERS_TO_SPLIT if doc.metadata.get(h)]
        heading_path = " > ".join(heading_parts) if heading_parts else ""

        sub_chunks = char_splitter.split_text(doc.page_content)
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
