# Weather Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在聊天输入框支持天气查询，通过高德 API 返回实况与预报，以纯文字流式输出。

**Architecture:** 在 `qa_service.stream_answer` 内新增第三条快速通道（天气），与现有 greeting/kb_listing 结构完全一致。`weather_service.py` 封装高德逆地理编码 + 天气两个接口；前端在页面挂载时请求 Geolocation 并在 ask 时随 question 一起传入坐标。

**Tech Stack:** Python/FastAPI（后端）、httpx（高德 HTTP 调用）、gpt-4o-mini（意图分类 + 城市提取）、Next.js/TypeScript（前端）、高德开放平台 Web 服务 API

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/core/config.py` | 修改 | 新增 `AMAP_API_KEY` 配置项 |
| `backend/app/schemas/qa.py` | 修改 | 新增 `LocationInput`，`AskRequest` 加 `location` 字段 |
| `.env.example` | 修改 | 补充 `AMAP_API_KEY=` |
| `backend/app/services/weather_service.py` | **新建** | 高德 API 封装（逆地理编码、正地理编码、天气查询） |
| `backend/tests/services/test_weather_service.py` | **新建** | weather_service 单元测试 |
| `backend/app/services/qa_service.py` | 修改 | 新增意图分类、城市解析、天气 prompt 构建、weather 快速通道 |
| `backend/app/modules/qa/router.py` | 修改 | `AskRequest` 已带 location，透传至 `stream_answer` |
| `frontend/src/services/qa.ts` | 修改 | `askConversation` / `createConversation` 增加 `location` 参数 |
| `frontend/src/features/chat/components/chat-page.tsx` | 修改 | 页面挂载时请求 Geolocation，ask 时携带坐标 |

---

## Task 1: 配置与 Schema

**Files:**
- Modify: `backend/app/core/config.py:79-83`
- Modify: `backend/app/schemas/qa.py:52-53`
- Modify: `.env.example`

- [ ] **Step 1: 在 config.py 中加入 AMAP_API_KEY**

在 `COHERE_BASE_URL` 后加一行：

```python
    COHERE_API_KEY: str | None = None
    COHERE_BASE_URL: str | None = None
    AMAP_API_KEY: str | None = None   # 高德开放平台 Web 服务 Key
```

- [ ] **Step 2: 在 schemas/qa.py 中新增 LocationInput 并更新 AskRequest**

文件顶部 import 已有 `Field`，在 `AskRequest` 之前插入新类，并更新 `AskRequest`：

```python
class LocationInput(BaseModel):
    lat: float
    lng: float


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    location: LocationInput | None = None
```

- [ ] **Step 3: 在 .env.example 补充变量名**

在 COHERE 相关行后追加：

```
AMAP_API_KEY=
```

---

## Task 2: weather_service.py

**Files:**
- Create: `backend/app/services/weather_service.py`
- Create: `backend/tests/services/test_weather_service.py`

- [ ] **Step 1: 创建 weather_service.py**

```python
import logging
from dataclasses import dataclass, field

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

AMAP_BASE = "https://restapi.amap.com/v3"


@dataclass
class LiveWeather:
    city: str
    weather: str
    temperature: str
    wind_direction: str
    wind_power: str
    humidity: str


@dataclass
class DayForecast:
    date: str
    day_weather: str
    night_weather: str
    day_temp: str
    night_temp: str
    day_wind: str
    day_power: str


@dataclass
class WeatherData:
    city: str
    live: LiveWeather
    forecast: list[DayForecast] = field(default_factory=list)


async def reverse_geocode(lat: float, lng: float) -> str | None:
    """坐标 → 高德 adcode（6 位区划码）。失败返回 None。"""
    if not settings.AMAP_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{AMAP_BASE}/geocode/regeo",
                params={"key": settings.AMAP_API_KEY, "location": f"{lng},{lat}", "extensions": "base"},
            )
            data = resp.json()
            if data.get("status") != "1":
                return None
            return data["regeocode"]["addressComponent"]["adcode"] or None
    except Exception as exc:
        logger.warning("reverse_geocode failed: %s", exc)
        return None


async def geocode_city(city_name: str) -> str | None:
    """城市名 → 高德 adcode。失败返回 None。"""
    if not settings.AMAP_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{AMAP_BASE}/geocode/geo",
                params={"key": settings.AMAP_API_KEY, "address": city_name},
            )
            data = resp.json()
            if data.get("status") != "1" or not data.get("geocodes"):
                return None
            return data["geocodes"][0]["adcode"] or None
    except Exception as exc:
        logger.warning("geocode_city failed: %s", exc)
        return None


async def fetch_weather(adcode: str) -> WeatherData | None:
    """查询实况 + 预报。失败返回 None。"""
    if not settings.AMAP_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            live_resp, forecast_resp = await _fetch_both(client, adcode)

        live_data = live_resp.json()
        forecast_data = forecast_resp.json()

        if live_data.get("status") != "1" or not live_data.get("lives"):
            return None

        live_raw = live_data["lives"][0]
        live = LiveWeather(
            city=live_raw.get("city", ""),
            weather=live_raw.get("weather", ""),
            temperature=live_raw.get("temperature", ""),
            wind_direction=live_raw.get("winddirection", ""),
            wind_power=live_raw.get("windpower", ""),
            humidity=live_raw.get("humidity", ""),
        )

        forecast: list[DayForecast] = []
        if forecast_data.get("status") == "1" and forecast_data.get("forecasts"):
            for cast in forecast_data["forecasts"][0].get("casts", []):
                forecast.append(
                    DayForecast(
                        date=cast.get("date", ""),
                        day_weather=cast.get("dayweather", ""),
                        night_weather=cast.get("nightweather", ""),
                        day_temp=cast.get("daytemp", ""),
                        night_temp=cast.get("nighttemp", ""),
                        day_wind=cast.get("daywind", ""),
                        day_power=cast.get("daypower", ""),
                    )
                )

        return WeatherData(city=live.city, live=live, forecast=forecast)
    except Exception as exc:
        logger.warning("fetch_weather failed: %s", exc)
        return None


async def _fetch_both(
    client: httpx.AsyncClient, adcode: str
) -> tuple[httpx.Response, httpx.Response]:
    import asyncio

    live_task = client.get(
        f"{AMAP_BASE}/weather/weatherInfo",
        params={"key": settings.AMAP_API_KEY, "city": adcode, "extensions": "base"},
    )
    forecast_task = client.get(
        f"{AMAP_BASE}/weather/weatherInfo",
        params={"key": settings.AMAP_API_KEY, "city": adcode, "extensions": "all"},
    )
    return await asyncio.gather(live_task, forecast_task)
```

- [ ] **Step 2: 编写 test_weather_service.py**

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services import weather_service


def _mock_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


@pytest.mark.asyncio
async def test_reverse_geocode_returns_adcode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")
    response_data = {
        "status": "1",
        "regeocode": {"addressComponent": {"adcode": "110105"}},
    }
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_mock_response(response_data))

    with patch("backend.app.services.weather_service.httpx.AsyncClient", return_value=mock_client):
        result = await weather_service.reverse_geocode(39.9, 116.4)

    assert result == "110105"


@pytest.mark.asyncio
async def test_reverse_geocode_returns_none_on_api_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_mock_response({"status": "0"}))

    with patch("backend.app.services.weather_service.httpx.AsyncClient", return_value=mock_client):
        result = await weather_service.reverse_geocode(39.9, 116.4)

    assert result is None


@pytest.mark.asyncio
async def test_reverse_geocode_returns_none_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", None)
    result = await weather_service.reverse_geocode(39.9, 116.4)
    assert result is None


@pytest.mark.asyncio
async def test_geocode_city_returns_adcode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")
    response_data = {"status": "1", "geocodes": [{"adcode": "310000"}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_mock_response(response_data))

    with patch("backend.app.services.weather_service.httpx.AsyncClient", return_value=mock_client):
        result = await weather_service.geocode_city("上海")

    assert result == "310000"


@pytest.mark.asyncio
async def test_fetch_weather_returns_weather_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")
    live_data = {
        "status": "1",
        "lives": [{
            "city": "北京市",
            "weather": "晴",
            "temperature": "26",
            "winddirection": "南",
            "windpower": "≤3",
            "humidity": "30",
        }],
    }
    forecast_data = {
        "status": "1",
        "forecasts": [{
            "casts": [{
                "date": "2026-05-18",
                "dayweather": "晴",
                "nightweather": "晴",
                "daytemp": "29",
                "nighttemp": "16",
                "daywind": "南",
                "daypower": "≤3",
            }]
        }],
    }

    async def mock_fetch_both(client, adcode):
        return _mock_response(live_data), _mock_response(forecast_data)

    monkeypatch.setattr(weather_service, "_fetch_both", mock_fetch_both)

    with patch("backend.app.services.weather_service.httpx.AsyncClient"):
        result = await weather_service.fetch_weather("110000")

    assert result is not None
    assert result.city == "北京市"
    assert result.live.weather == "晴"
    assert result.live.temperature == "26"
    assert len(result.forecast) == 1
    assert result.forecast[0].day_temp == "29"


@pytest.mark.asyncio
async def test_fetch_weather_returns_none_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(weather_service.settings, "AMAP_API_KEY", "test-key")

    async def mock_fetch_both(client, adcode):
        return _mock_response({"status": "0"}), _mock_response({"status": "0"})

    monkeypatch.setattr(weather_service, "_fetch_both", mock_fetch_both)

    with patch("backend.app.services.weather_service.httpx.AsyncClient"):
        result = await weather_service.fetch_weather("110000")

    assert result is None
```

- [ ] **Step 3: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/services/test_weather_service.py -v
```

期望：5 个 PASS

---

## Task 3: qa_service 意图检测 + 城市解析 + Prompt 构建

**Files:**
- Modify: `backend/app/services/qa_service.py`

在文件顶部 imports 区域加入 weather_service 引用，然后在 `_is_kb_listing` 函数之后、`_classify_retrieval_intent` 之前添加以下三个函数。

- [ ] **Step 1: 在 qa_service.py 顶部补充 import**

在现有 import 块中加入：

```python
from backend.app.services import weather_service
from backend.app.services.weather_service import WeatherData
```

- [ ] **Step 2: 添加 _is_weather_query**

在 `_is_kb_listing` 函数（约第 786 行）之后插入：

```python
async def _is_weather_query(
    question: str, recent_messages: list[Message] | None = None
) -> bool:
    """判断用户是否在询问天气（当天或预报），含追问城市名的场景。失败时返回 False。"""
    try:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是一个意图分类助手。请判断用户是否在询问天气信息（当天天气、明天天气、未来几天预报等），"
                    "或者是在回答上一轮助手关于城市的追问（如助手问「您想查询哪里的天气」，用户回复「北京」）。\n"
                    "如果是，回答 YES；否则回答 NO。\n"
                    "只输出 YES 或 NO，不要输出其他内容。"
                ),
            }
        ]
        if recent_messages:
            for msg in recent_messages:
                messages.append({"role": msg.role, "content": msg.content[:200]})
        messages.append({"role": "user", "content": question})
        client = _openai_client()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            max_tokens=5,
        )
        return (resp.choices[0].message.content or "NO").strip().upper() == "YES"
    except Exception as e:
        logger.warning("Weather query check failed: %s", e)
        return False
```

- [ ] **Step 3: 添加 _extract_city_from_question（LLM 从文本提取城市名）**

```python
async def _extract_city_from_question(question: str) -> str | None:
    """从问题文本中提取城市名，提取不到返回 None。"""
    try:
        client = _openai_client()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "从用户的问题中提取城市名。如果有城市名，只输出城市名（如「北京」「上海」「成都市」），"
                        "不要输出任何其他内容。如果没有城市名，输出 NONE。"
                    ),
                },
                {"role": "user", "content": question},
            ],  # type: ignore[arg-type]
            temperature=0,
            max_tokens=20,
        )
        result = (resp.choices[0].message.content or "NONE").strip()
        return None if result.upper() == "NONE" else result
    except Exception as e:
        logger.warning("City extraction failed: %s", e)
        return None
```

- [ ] **Step 4: 添加 _resolve_city_adcode（城市解析，优先级：坐标 > 文本 > 历史）**

```python
async def _resolve_city_adcode(
    question: str,
    location: "LocationInput | None",
    recent_messages: list[Message],
) -> str | None:
    """按优先级解析城市 adcode：坐标逆解 → 问题文本提取 → 对话历史城市名。"""
    # 1. 坐标逆解
    if location is not None:
        adcode = await weather_service.reverse_geocode(location.lat, location.lng)
        if adcode:
            return adcode

    # 2. 从问题文本提取城市名
    city = await _extract_city_from_question(question)
    if city:
        adcode = await weather_service.geocode_city(city)
        if adcode:
            return adcode

    # 3. 从对话历史提取（用户回答了追问）
    for msg in reversed(recent_messages):
        if msg.role == "user" and len(msg.content.strip()) <= 20:
            adcode = await weather_service.geocode_city(msg.content.strip())
            if adcode:
                return adcode

    return None
```

- [ ] **Step 5: 添加 _build_weather_prompt**

```python
def _build_weather_prompt(
    question: str,
    weather: WeatherData,
    recent_messages: list[Message],
) -> list[dict[str, str]]:
    """把天气数据拼入 system prompt，让 LLM 用自然语言回答。"""
    live = weather.live
    live_text = (
        f"{weather.city}当前天气：{live.weather}，气温 {live.temperature}°C，"
        f"{live.wind_direction}风 {live.wind_power} 级，湿度 {live.humidity}%。"
    )
    forecast_lines = []
    for day in weather.forecast:
        forecast_lines.append(
            f"{day.date}：白天 {day.day_weather} {day.day_temp}°C / "
            f"夜间 {day.night_weather} {day.night_temp}°C，{day.day_wind}风 {day.day_power} 级"
        )
    forecast_text = "\n".join(forecast_lines)

    system = (
        "你是一个友好的助手 OfferPilot。请根据以下天气数据，用自然、简洁的中文回答用户的天气问题。\n\n"
        f"【实况】{live_text}\n"
        f"【预报】\n{forecast_text}"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages
```

- [ ] **Step 6: 为 stream_answer 的 location 参数添加类型引用**

在文件顶部已有的 imports 区域末尾添加（放在其他 schema imports 附近）：

```python
from backend.app.schemas.qa import LocationInput
```

---

## Task 4: stream_answer 接入天气快速通道

**Files:**
- Modify: `backend/app/services/qa_service.py:1051`

- [ ] **Step 1: stream_answer 签名加 location 参数**

将函数签名从：
```python
async def stream_answer(
    db: AsyncSession,
    conv_id: uuid.UUID,
    user_id: int,
    question: str,
    *,
    debug: bool = False,
) -> AsyncGenerator[dict[str, Any], None]:
```

改为：
```python
async def stream_answer(
    db: AsyncSession,
    conv_id: uuid.UUID,
    user_id: int,
    question: str,
    *,
    debug: bool = False,
    location: LocationInput | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
```

- [ ] **Step 2: 在 _is_kb_listing 通道之后插入天气通道**

找到 `if await _is_kb_listing(question, recent):` 块（约第 1151 行），在该块的 `return` 语句之后、`# 2. 检索意图处理` 注释之前，插入：

```python
        if await _is_weather_query(question, recent):
            adcode = await _resolve_city_adcode(question, location, recent)
            if adcode is None:
                async for event in _send_general_response(
                    db,
                    conv_id,
                    question,
                    _build_general_prompt(
                        "您想查询哪里的天气呢？请告诉我城市名称。",
                        recent,
                        conv.summary,
                    ),
                    conv.message_count or 0,
                    "weather_ask_city",
                ):
                    yield event
                return
            weather_data = await weather_service.fetch_weather(adcode)
            if weather_data is None:
                async for event in _send_general_response(
                    db,
                    conv_id,
                    question,
                    _build_general_prompt(
                        "暂时无法获取天气信息，请稍后重试。",
                        recent,
                        conv.summary,
                    ),
                    conv.message_count or 0,
                    "weather_fetch_error",
                ):
                    yield event
                return
            async for event in _send_general_response(
                db,
                conv_id,
                question,
                _build_weather_prompt(question, weather_data, recent),
                conv.message_count or 0,
                "weather",
            ):
                yield event
            return
```

---

## Task 5: router.py 透传 location

**Files:**
- Modify: `backend/app/modules/qa/router.py:129-153`

- [ ] **Step 1: ask 端点透传 location 到 stream_answer**

将 `event_stream` 函数内对 `qa_service.stream_answer` 的调用从：
```python
        async for event in qa_service.stream_answer(
            db, conv_id, user_id, body.question, debug=debug_enabled
        ):
```

改为：
```python
        async for event in qa_service.stream_answer(
            db, conv_id, user_id, body.question,
            debug=debug_enabled,
            location=body.location,
        ):
```

- [ ] **Step 2: 运行后端测试确认无回归**

```bash
cd backend && uv run pytest tests/ -v --ignore=tests/services/test_rag_real_chain_eval_service.py -q
```

期望：所有已有测试 PASS（新增测试在 Task 2 已验证）

---

## Task 6: 前端 Geolocation + location 透传

**Files:**
- Modify: `frontend/src/services/qa.ts:57-97`
- Modify: `frontend/src/features/chat/components/chat-page.tsx`

- [ ] **Step 1: 更新 qa.ts 的 askConversation 签名与实现**

将 `askConversation` 及 `fetchAskConversation` 改为：

```typescript
type LocationInput = { lat: number; lng: number } | null;

export function askConversation(
  conversationId: string,
  question: string,
  location?: LocationInput,
  signal?: AbortSignal,
): Promise<Response>;
export async function askConversation(
  conversationId: string,
  question: string,
  location?: LocationInput,
  signal?: AbortSignal,
): Promise<Response> {
  return fetchAskConversation({ conversationId, question, location, signal });
}

async function fetchAskConversation({
  conversationId,
  question,
  location,
  signal,
}: {
  conversationId: string;
  question: string;
  location?: LocationInput;
  signal?: AbortSignal;
}) {
  const accessToken = await getValidAccessToken();
  const headers = new Headers({ "Content-Type": "application/json" });
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return fetch(`${env.apiBaseUrl}/qa/conversations/${conversationId}/ask`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify({ question, location: location ?? null }),
    signal,
  });
}
```

- [ ] **Step 2: 在 chat-page.tsx 中请求 Geolocation 并透传**

在 `ChatPage` 组件中，在现有 state 声明区加入 location state：

```typescript
const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
```

在已有的第一个 `useEffect`（用户信息获取）之后，加入 geolocation effect：

```typescript
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setLocation(null),
    );
  }, []);
```

然后找到调用 `askConversation` 的地方，将 `location` 作为第三个参数传入：

```typescript
// 原来
const response = await askConversation(convId, question, abortController.signal);
// 改为
const response = await askConversation(convId, question, location, abortController.signal);
```

- [ ] **Step 3: 运行 prettier 格式化前端改动文件**

```bash
cd frontend && pnpm prettier --write src/services/qa.ts src/features/chat/components/chat-page.tsx
```

- [ ] **Step 4: 运行后端 black + isort**

```bash
cd backend && uv run black app/services/weather_service.py app/services/qa_service.py app/modules/qa/router.py app/core/config.py app/schemas/qa.py && uv run isort app/services/weather_service.py app/services/qa_service.py app/modules/qa/router.py app/core/config.py app/schemas/qa.py
```

- [ ] **Step 5: 启动本地环境，手动验证天气功能**

```bash
# 终端 1
./dev.sh

# 在聊天框输入「今天天气怎么样」
# 预期：浏览器弹出定位请求 → 允许后 → 流式回复当地天气
# 再输入「北京明天会下雨吗」
# 预期：不依赖坐标，直接从问题提取「北京」→ 查询并回复
```

- [ ] **Step 6: Commit**

```bash
git add \
  backend/app/core/config.py \
  backend/app/schemas/qa.py \
  backend/app/services/weather_service.py \
  backend/app/services/qa_service.py \
  backend/app/modules/qa/router.py \
  backend/tests/services/test_weather_service.py \
  frontend/src/services/qa.ts \
  frontend/src/features/chat/components/chat-page.tsx \
  .env.example \
  docs/superpowers/specs/2026-05-18-weather-query-design.md
git commit -m "feat: 支持天气查询，集成高德 API 实况与预报"
```
