from openai import AsyncOpenAI

from backend.app.core.config import settings

TITLE_MODEL = "gpt-4o"
TITLE_INPUT_LIMIT = 4000

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """复用 OpenAI 异步客户端，避免每次生成标题都重复初始化连接。"""

    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _build_title_prompt(markdown: str) -> str:
    excerpt = markdown[:TITLE_INPUT_LIMIT]
    return f"""你是一个开发者技术文档知识库的命名助手。

请根据下面这份文档内容，为知识库生成一个简洁、准确的中文标题。

要求：
1. 只返回标题，不要解释。
2. 标题长度控制在 6 到 6 中文字符之间。
3. 优先体现产品名、框架名、API 名或核心主题。
4. 不要使用书名号、引号、句号等结尾标点。
5. 如果内容明显是某个官方文档、SDK 文档或 API 文档，标题要直接点出它的主题。

文档内容：
{excerpt}
"""


async def generate_knowledge_base_title(markdown: str) -> str | None:
    """基于抓取到的 Markdown 内容生成知识库标题。

    这是一个增强体验的 best-effort 步骤；返回 None 时，调用方继续保留默认标题。
    """

    if not settings.OPENAI_API_KEY:
        return None

    client = get_openai_client()
    response = await client.responses.create(
        model=TITLE_MODEL,
        input=_build_title_prompt(markdown),
    )
    title = response.output_text.strip()
    if not title:
        return None
    return title[:40].strip()
