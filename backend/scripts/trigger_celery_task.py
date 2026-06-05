import asyncio
import os

import httpx

BASE_URL = "http://localhost:8080/api/v1"
TOKEN = os.environ.get("DEV_RAG_TOKEN")

async def trigger_celery():
    if not TOKEN:
        raise RuntimeError("请先设置 DEV_RAG_TOKEN，再运行该脚本。")

    print("🚀 正在通过 API 请求发送新建知识库动作以激活 Celery 异步任务...")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }
    
    payload = {
        "name": "Celery 激活测试库",
        "source_url": "http://localhost:8080/health" # 用本地健康检查接口做伪文档，避免外网爬取耗时
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/knowledge",
            headers=headers,
            json=payload,
            timeout=10
        )
        if resp.status_code == 200:
            print("✅ 知识库创建成功，Celery 异步任务 (knowledge.ingest) 已经入队调度！")
            print(resp.json())
        else:
            print(f"❌ 触发失败，状态码: {resp.status_code}")
            print(resp.text)

if __name__ == "__main__":
    asyncio.run(trigger_celery())
