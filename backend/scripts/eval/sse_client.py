"""共用 SSE 客户端，给评估脚本和 Locust 复用。"""

import json
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx


@dataclass
class AskResult:
    answer: str = ""
    citations: list[dict] = field(default_factory=list)
    outcome: str = "unknown"
    error_code: str | None = None
    ttft_ms: int | None = None
    total_ms: int | None = None
    raw_events: list[dict] = field(default_factory=list)


async def ask_question(
    base_url: str,
    token: str,
    conversation_id: str,
    question: str,
    timeout: float = 60.0,
) -> AskResult:
    """通过 SSE 接口提问，返回完整结果。"""

    url = f"{base_url}/api/v1/qa/conversations/{conversation_id}/ask"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"question": question}

    result = AskResult()
    start = time.perf_counter()
    first_token_at: float | None = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    # 查找 data: 开头的行
                    data_line = None
                    for line in block.split("\n"):
                        if line.startswith("data: "):
                            data_line = line
                            break

                    if not data_line:
                        continue

                    raw = data_line[len("data: ") :]
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    result.raw_events.append(event)

                    etype = event.get("type")
                    if etype == "token":
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        result.answer += event.get("content", "")
                    elif etype == "citations":
                        result.citations = event.get("data", [])
                    elif etype == "error":
                        result.outcome = "error"
                        result.error_code = event.get("code")
                    elif etype == "done":
                        if result.outcome == "unknown":
                            result.outcome = "success"

    total = time.perf_counter() - start
    result.total_ms = int(total * 1000)
    if first_token_at is not None:
        result.ttft_ms = int((first_token_at - start) * 1000)
    return result
