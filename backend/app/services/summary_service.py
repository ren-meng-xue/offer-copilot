import logging
from openai import AsyncOpenAI
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

async def generate_knowledge_base_summary(markdown_text: str) -> str:
    """
    使用 LLM 根据 Markdown 正文生成 300-500 字的全局摘要。
    """
    if not markdown_text:
        return ""

    client = _get_client()
    try:
        # 截取前 10000 个字符，防止超长文本浪费 Token
        content_sample = markdown_text[:10000]
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "你是一个专业的文档摘要助手。请阅读以下文档内容，生成一段 300-500 字的详细全局摘要。要求逻辑清晰，涵盖文档的主要核心观点、适用场景和关键结论。直接输出摘要正文，不要有“以下是摘要”等废话。"
                },
                {"role": "user", "content": content_sample}
            ],
            temperature=0.3,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        return ""
