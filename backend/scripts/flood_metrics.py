import asyncio
import uuid
import sys
from pathlib import Path

# Add backend to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend.app.services import qa_service
from backend.app.db.session import async_session_factory

async def fire_rag_requests():
    print("🔥 正在 API 进程空间内连续触发 10 次 RAG 请求...")
    user_id = 1
    # 找一个真实的 KB ID (刚才入库产生的)
    kb_id = 12 
    
    questions = [
        "如何安装 FastAPI？",
        "如何安装 FastAPI？", # 重复提问，触发 L1 Cache Hit
        "pgvector 支持哪些索引？",
        "pgvector 支持哪些索引？", # 再次重复，触发 L1 Cache Hit
        "什么是 Pydantic？",
        "FastAPI 的核心特性有哪些？",
        "如何创建 Next.js 路由？",
        "Next.js 的 Layouts 是什么？",
        "如何激活虚拟环境？",
        "什么是 HNSW 索引？"
    ]

    async with async_session_factory() as db:
        # 1. 先创建一个真实的对话，并绑定知识库
        print("📝 创建测试对话...")
        conv = await qa_service.create_conversation(
            db, user_id=user_id, knowledge_base_id=kb_id
        )
        conv_id = conv.id
        print(f"✅ 对话已创建: {conv_id}")

        for i, q in enumerate(questions):
            print(f"[{i+1}/10] 提问: {q}")
            # 直接调用 stream_answer 产生真实指标
            async for _ in qa_service.stream_answer(
                db, conv_id=conv_id, user_id=user_id, question=q
            ):
                pass
            # 模拟请求间隔，让 Prometheus 有时间抓取
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(fire_rag_requests())
