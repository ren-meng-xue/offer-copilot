import asyncio
import uuid
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.session import async_session_factory
from backend.app.models.knowledge_base import KnowledgeBaseStatus, KnowledgeBase
from backend.app.models.document_chunk import DocumentChunk
from backend.app.repositories import knowledge_repository
from backend.app.services.chunking_service import split_markdown
from backend.app.services.embedding_service import generate_embeddings
from backend.app.services.summary_service import generate_knowledge_base_summary
from backend.app.services.title_generation_service import generate_knowledge_base_title

DOCS = [
    {
        "name": "FastAPI 中文教程",
        "url": "https://fastapi.tiangolo.com/zh/tutorial/",
        "content": """# 教程 - 用户指南

本教程将一步步向您展示如何使用 FastAPI 的绝大部分特性。

各个章节的内容循序渐进，但是又围绕着单独的主题，所以您可以直接跳转到某个章节以解决您的特定 API 需求。本教程同样可以作为将来的参考手册，您可以随时回到这里查阅需要的内容。

## 运行代码

所有代码片段都可以复制后直接使用（它们实际上是经过测试的 Python 文件）。

要运行任何示例，请将代码复制到 `main.py` 文件中，然后启动 `fastapi dev`：

```bash
fastapi dev main.py
```

## 安装 FastAPI

第一步是安装 FastAPI。请确保您创建并激活一个虚拟环境，然后安装：

```bash
pip install "fastapi[standard]"
```

## 进阶用户指南

在完成本教程（用户指南）后，您可以阅读**进阶用户指南**。
"""
    },
    {
        "name": "pgvector README",
        "url": "https://github.com/pgvector/pgvector#readme",
        "content": """# pgvector

Open-source vector similarity search for Postgres

Store your vectors with the rest of your data. Supports:

- exact and approximate nearest neighbor search
- L2 distance, inner product, cosine distance, L1 distance, Hamming distance, and Jaccard distance

## Getting Started

1. **Enable the extension**:
   ```sql
   CREATE EXTENSION vector;
   ```

2. **Create a table with a vector column**:
   ```sql
   CREATE TABLE items (id bigserial PRIMARY KEY, embedding vector(3));
   ```

3. **Query nearest neighbors (L2 distance)**:
   ```sql
   SELECT * FROM items ORDER BY embedding <-> '[3,1,2]' LIMIT 5;
   ```

## Indexing

### HNSW
Better query performance and speed-recall tradeoff.
```sql
CREATE INDEX ON items USING hnsw (embedding vector_l2_ops);
```

### IVFFlat
Faster build times and lower memory usage.
```sql
CREATE INDEX ON items USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
```
"""
    },
    {
        "name": "Pydantic Models",
        "url": "https://docs.pydantic.dev/latest/concepts/models/",
        "content": """# Pydantic Models

在 Pydantic 中，定义 Schema 的主要方式是通过 Models。模型是继承自 `BaseModel` 的类，通过类型注解来定义字段。

## 核心概念
- **验证保证**：Pydantic 保证模型实例的字段在验证后完全符合定义的类型。
- **数据转换**：Pydantic 会尝试将输入数据强制转换为定义的类型。

## 基本用法
```python
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    id: int
    name: str = 'Jane Doe'
    model_config = ConfigDict(str_length=10)

user = User(id='123')
assert user.id == 123
```

## 高级特性
- **嵌套模型**：支持将模型作为另一个模型的字段类型。
- **动态模型创建**：使用 `create_model()` 在运行时创建模型。
- **不可变性**：通过 `ConfigDict(frozen=True)` 设置模型为不可变。
"""
    },
    {
        "name": "Next.js Routing",
        "url": "https://nextjs.org/docs/app/building-your-application/routing",
        "content": """# Layouts and Pages

Next.js uses file-system based routing.

## Creating a page

A page is UI that is rendered on a specific route.

```tsx
// app/page.tsx
export default function Page() {
  return <h1>Hello Next.js!</h1>
}
```

## Creating a layout

A layout is UI that is shared between multiple pages.

```tsx
// app/layout.tsx
export default function DashboardLayout({ children }) {
  return (
    <html lang="en">
      <body><main>{children}</main></body>
    </html>
  )
}
```

## Dynamic Segments

Wrap a folder name in square brackets: `[segmentName]`.

```tsx
// app/blog/[slug]/page.tsx
export default async function BlogPostPage({ params }) {
  const { slug } = await params
  return <h1>{post.title}</h1>
}
```
"""
    }
]

async def ingest_doc(db: AsyncSession, user_id: int, doc: dict):
    print(f"Ingesting {doc['name']}...")
    
    # 1. Create Knowledge Base
    kb = KnowledgeBase(
        user_id=user_id,
        name=doc['name'],
        source_type="url",
        source_url=doc['url'],
        status=KnowledgeBaseStatus.PROCESSING
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    kb_id = kb.id
    
    markdown = doc['content']
    
    # 2. Summary & Title
    try:
        summary = await generate_knowledge_base_summary(markdown)
        if summary:
            kb.summary = summary
    except Exception as e:
        print(f"  Summary failed: {e}")

    # 3. Split
    chunks = split_markdown(markdown, doc['url'])
    if not chunks:
        print(f"  No chunks for {doc['name']}")
        return

    # 4. Embed
    texts_for_embedding = [
        f"章节路径: {c.heading_path}\n内容: {c.content}" for c in chunks
    ]
    embeddings = await generate_embeddings(texts_for_embedding)

    # 5. Save Chunks
    db_chunks = [
        DocumentChunk(
            knowledge_base_id=kb_id,
            content=chunk.content,
            embedding=embedding,
            source_url=doc['url'],
            heading_path=chunk.heading_path,
            chunk_index=chunk.chunk_index,
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    await knowledge_repository.bulk_create_chunks(db, db_chunks)
    
    kb.status = KnowledgeBaseStatus.DONE
    await db.commit()
    print(f"  Done! KB ID: {kb_id}, Chunks: {len(db_chunks)}")

async def main():
    user_id = 1
    async with async_session_factory() as db:
        for doc in DOCS:
            await ingest_doc(db, user_id, doc)

if __name__ == "__main__":
    asyncio.run(main())
