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


def _build_conversation_title_prompt(question: str) -> str:
    return f"""你是一个对话标题生成助手。

请根据下面这个用户的问题，生成一个极其简洁的中文标题（6-10个字）。

要求：
1. 只返回标题，不要任何解释或标点符号。
2. 标题要能概括用户的问题核心意图。
3. 严禁使用“关于...的对话”、“问题解答”之类的废话。

用户问题：{question}
"""


async def generate_knowledge_base_title(markdown: str) -> str | None:
    # ... (rest of the function)
    pass


async def generate_conversation_title(question: str) -> str | None:
    """基于用户问题生成对话标题。"""

    if not settings.OPENAI_API_KEY:
        return None

    try:
        client = get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个专业的标题生成助手。"},
                {"role": "user", "content": _build_conversation_title_prompt(question)},
            ],
            temperature=0.7,
            max_tokens=20,
        )
        title = response.choices[0].message.content or ""
        return title.strip().replace("“", "").replace("”", "").replace('"', "")
    except Exception:
        return None
