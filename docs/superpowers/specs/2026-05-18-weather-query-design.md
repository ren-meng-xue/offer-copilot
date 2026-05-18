# 天气查询功能设计文档

**日期**：2026-05-18  
**功能**：在聊天输入框中支持天气查询，通过高德 API 返回实况与预报

---

## 1. 背景与目标

用户在 OfferPilot 聊天界面提问时，可能询问天气相关问题（如「今天天气怎么样」「北京明天会下雨吗」）。当前系统无法处理此类问题，会走 RAG 检索流程并返回「无法回答」。

**目标**：在不改变现有 RAG 架构的前提下，新增天气快速通道，利用高德 API 返回实况 + 预报天气，以纯文字流式方式输出。

---

## 2. 方案选择

采用**方案 A：在 `qa_service` 加第三条快速通道**，与现有 `_is_greeting` / `_is_kb_listing` 模式完全一致。

放弃 OpenAI Function Calling（改造流式管道成本过高）和独立端点（天气对话无法进入消息历史）。

---

## 3. 数据流

```
用户提问「今天天气怎么样」
  │
  ├─ 前端：navigator.geolocation → {lat, lng}（失败则 null）
  │
  └─ POST /qa/conversations/{id}/ask
       body: { question: string, location: { lat, lng } | null }
         │
         ▼
     stream_answer(question, location=...)
         │
         ├─ [已有] _is_greeting → 招呼通道
         ├─ [已有] _is_kb_listing → 知识库列表通道
         ├─ [新增] _is_weather_query → 天气通道
         │     │
         │     ├─ 城市解析（优先级顺序）：
         │     │   1. location 坐标 → 高德逆地理编码 → adcode
         │     │   2. 问题文本 LLM 提取城市名 → 高德正地理编码 → adcode
         │     │   3. 对话历史追问（上一轮 assistant 已追问城市）→ 从用户回复提取
         │     │   4. 以上均失败 → 流式回复「您想查询哪里的天气呢？」
         │     │
         │     └─ 获得 adcode 后：
         │         ├─ fetch_weather(adcode, extensions=base)  → 今日实况
         │         └─ fetch_weather(adcode, extensions=all)   → 未来 4 天预报
         │               │
         │               └─ _build_weather_prompt → _send_general_response 流式输出
         │
         └─ [已有] RAG 检索通道（其余问题）
```

---

## 4. 新增组件

### 4.1 `backend/app/services/weather_service.py`（新文件）

```python
# 对外暴露的函数：
async def reverse_geocode(lat: float, lng: float) -> str | None
    """坐标 → 高德 adcode（6 位区划码）"""

async def geocode_city(city_name: str) -> str | None
    """城市名文字 → adcode"""

async def fetch_weather(adcode: str) -> WeatherData
    """查询实况 + 预报，返回结构化数据"""

@dataclass
class WeatherData:
    city: str
    live: LiveWeather          # 今日实况
    forecast: list[DayForecast]  # 未来 4 天

@dataclass
class LiveWeather:
    weather: str    # 晴、多云等
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
```

调用的高德接口：
- 逆地理编码：`GET https://restapi.amap.com/v3/geocode/regeo?key=KEY&location=lng,lat`
- 正地理编码：`GET https://restapi.amap.com/v3/geocode/geo?key=KEY&address=城市名`
- 天气查询：`GET https://restapi.amap.com/v3/weather/weatherInfo?key=KEY&city=adcode&extensions=base|all`

### 4.2 `backend/app/services/qa_service.py` 改动

```python
# 新增意图分类器（同 _is_kb_listing 结构）
async def _is_weather_query(question: str, recent_messages: list[Message]) -> bool

# 新增城市解析器
async def _resolve_city_adcode(
    question: str,
    location: LocationInput | None,
    recent_messages: list[Message],
) -> str | None

# 新增 Prompt 构建器
def _build_weather_prompt(
    question: str,
    weather: WeatherData,
    recent_messages: list[Message],
) -> list[dict]

# stream_answer 新增参数
async def stream_answer(
    db, conv_id, user_id, question,
    *,
    debug: bool = False,
    location: LocationInput | None = None,   # 新增
) -> AsyncGenerator[dict, None]
```

在 `stream_answer` 快速通道判断中，在 `_is_kb_listing` 之后插入天气通道：

```python
if await _is_weather_query(question, recent):
    adcode = await _resolve_city_adcode(question, location, recent)
    if adcode is None:
        # 追问城市
        async for event in _send_general_response(..., "您想查询哪里的天气呢？"):
            yield event
        return
    weather = await weather_service.fetch_weather(adcode)
    async for event in _send_general_response(
        ..., _build_weather_prompt(question, weather, recent)
    ):
        yield event
    return
```

### 4.3 `backend/app/schemas/qa.py` 改动

```python
class LocationInput(BaseModel):
    lat: float
    lng: float

class AskRequest(BaseModel):
    question: str
    location: LocationInput | None = None   # 新增
```

### 4.4 `backend/app/core/config.py` 改动

```python
AMAP_API_KEY: str = ""   # 从环境变量读取
```

`.env.example` 同步新增 `AMAP_API_KEY=`

### 4.5 前端改动

**位置：** 聊天页面主组件（挂载时一次性请求定位）

```typescript
// 页面加载时请求一次，结果存入 state
const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);

useEffect(() => {
  navigator.geolocation.getCurrentPosition(
    (pos) => setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
    () => setLocation(null),
  );
}, []);

// 发送消息时带上 location
const payload = { question, location };
```

---

## 5. 错误处理

| 场景 | 处理 |
|------|------|
| 用户拒绝定位 + 问题无城市名 | 回复「您想查询哪里的天气呢？」，等待用户补充 |
| 高德逆/正地理编码失败 | 同上，降级追问 |
| 高德天气接口超时/报错 | 捕获异常，回复「暂时无法获取天气信息，请稍后重试」 |
| 用户问题含明确城市 | LLM 提取城市名 → 正地理编码，无需坐标 |
| 用户回复追问后的城市 | 从对话历史中识别补充城市名并查询 |
| 天气意图误判 | `_is_weather_query` 失败时保守返回 False，进入 RAG 流程 |

---

## 6. 配置项

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AMAP_API_KEY` | 高德开放平台 Web 服务 API Key | 必填 |

---

## 7. 不在本次范围内

- 天气卡片 UI 组件（纯文字输出已满足需求）
- 小时级精细预报（高德免费额度仅支持日级）
- 历史天气查询
