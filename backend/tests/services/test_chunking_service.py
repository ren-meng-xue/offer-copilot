from backend.app.services.chunking_service import CHUNK_SIZE, split_markdown


def test_split_markdown_keeps_fenced_code_block_atomic() -> None:
    markdown = """
# API

## Example

Before code.

```python
def create_app():
    return "ok"
```

After code.
""".strip()

    chunks = split_markdown(markdown, "https://docs.example.com/api")

    code_chunks = [chunk for chunk in chunks if "def create_app()" in chunk.content]
    assert len(code_chunks) == 1
    assert "```python" in code_chunks[0].content
    assert 'return "ok"' in code_chunks[0].content


def test_split_markdown_keeps_markdown_table_atomic() -> None:
    markdown = """
# Config

## Env Vars

| Name | Description |
| --- | --- |
| OPENAI_API_KEY | API key |
| REDIS_URL | Redis connection |
""".strip()

    chunks = split_markdown(markdown, "https://docs.example.com/config")

    table_chunks = [
        chunk for chunk in chunks if "| OPENAI_API_KEY | API key |" in chunk.content
    ]
    assert len(table_chunks) == 1
    assert "| Name | Description |" in table_chunks[0].content
    assert "| REDIS_URL | Redis connection |" in table_chunks[0].content


def test_split_markdown_keeps_list_block_atomic() -> None:
    markdown = """
# Install

## Steps

1. Install Python
2. Create virtualenv
3. Run migrations
""".strip()

    chunks = split_markdown(markdown, "https://docs.example.com/install")

    list_chunks = [chunk for chunk in chunks if "1. Install Python" in chunk.content]
    assert len(list_chunks) == 1
    assert "2. Create virtualenv" in list_chunks[0].content
    assert "3. Run migrations" in list_chunks[0].content


def test_split_markdown_still_splits_long_plain_text() -> None:
    long_text = "A" * (CHUNK_SIZE + 200)
    markdown = f"""
# Intro

## Overview

{long_text}
""".strip()

    chunks = split_markdown(markdown, "https://docs.example.com/intro")

    assert len(chunks) >= 2
    assert all(chunk.heading_path == "Intro > Overview" for chunk in chunks)


def test_split_markdown_preserves_sequential_chunk_indexes() -> None:
    markdown = """
# Intro

## Overview

Some text.

```python
print("hello")
```

More text.
""".strip()

    chunks = split_markdown(markdown, "https://docs.example.com/intro")

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
